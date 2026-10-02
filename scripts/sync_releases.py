#!/usr/bin/env python3
"""Mirror the latest APK of each app in apps.json into this repository's releases.

For every app, the newest release in its (private) source repo that carries an .apk is found.
A full release is preferred; a prerelease is used only when the app has no full release yet. If
this repo doesn't already have that version, the APK is downloaded and re-published here as a
release tagged <id>-<source tag>, and the older copies of that app are deleted, so the releases
page always holds exactly one download per app. Finally the app table in README.md is rewritten.

Nothing from the source release is copied except the APK and its version: release notes there
can mention commit SHAs or private URLs, so the notes here are written from apps.json.

Environment:
  SOURCE_TOKEN       token that can read the source repos' releases (Contents: read)
  GITHUB_TOKEN       token that can write this repo's releases (Contents: write)
  GITHUB_REPOSITORY  owner/name of this repo (set by Actions)

  --dry-run          read everything and print the plan, but change nothing
"""

import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = re.compile(r"<!-- app-store:id=([\w.-]+) -->")
README_START = "<!-- apps:start -->"
README_END = "<!-- apps:end -->"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # Asset downloads redirect to a pre-signed storage URL, which rejects a request that also
    # carries our Authorization header. Stop at the redirect and follow it without the token.
    def redirect_request(self, *args, **kwargs):
        return None


_no_redirect = urllib.request.build_opener(_NoRedirect)


def request(method, url, token, body=None, content_type="application/json", accept=None):
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": accept or "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "app-store-sync",
    }
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url} failed: {e.code} {e.read().decode(errors='replace')}")
    return json.loads(raw) if raw else None


def list_releases(repo, token):
    releases, page = [], 1
    while True:
        batch = request("GET", f"{API}/repos/{repo}/releases?per_page=100&page={page}", token)
        releases += batch
        if len(batch) < 100:
            return releases
        page += 1


def pick_release(releases):
    """Newest full release with an APK, else the newest prerelease with one."""
    candidates = []
    for rel in releases:
        if rel["draft"]:
            continue
        apks = [a for a in rel["assets"] if a["name"].lower().endswith(".apk")]
        if apks:
            candidates.append((rel, apks[0]))
    candidates.sort(key=lambda c: c[0]["published_at"] or "", reverse=True)
    for rel, apk in candidates:
        if not rel["prerelease"]:
            return rel, apk
    return candidates[0] if candidates else (None, None)


def download_asset(asset, token, dest):
    req = urllib.request.Request(
        asset["url"],
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/octet-stream",
            "User-Agent": "app-store-sync",
        },
    )
    try:
        resp = _no_redirect.open(req)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            sys.exit(f"Downloading {asset['name']} failed: {e.code}")
        resp = urllib.request.urlopen(
            urllib.request.Request(e.headers["Location"], headers={"User-Agent": "app-store-sync"})
        )
    sha = hashlib.sha256()
    with resp, open(dest, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            sha.update(chunk)
    return sha.hexdigest()


def version_of(tag):
    return tag[1:] if tag[:1] in ("v", "V") else tag


def release_notes(app, version, source_rel, sha256):
    lines = [
        f"<!-- app-store:id={app['id']} -->",
        app["description"],
        "",
        "| | |",
        "| --- | --- |",
        f"| Version | {version} |",
        f"| APK SHA-256 | `{sha256}` |",
    ]
    if source_rel["prerelease"]:
        lines += [
            "",
            "> [!NOTE]",
            "> This is a test build. If you already have an earlier copy of this app installed,",
            "> Android may refuse to install this one over it: uninstall the old one first (that",
            "> clears the app's data).",
        ]
    return "\n".join(lines) + "\n"


def human_size(n):
    return f"{n / 1_000_000:.1f} MB"


def render_table(rows):
    out = ["| App | What it does | Version | Download |", "| --- | --- | --- | --- |"]
    for row in rows:
        if row is None:
            continue
        out.append(
            f"| **{row['name']}** | {row['description']} | {row['version']} "
            f"| [{row['file']}]({row['url']}) ({human_size(row['size'])}) |"
        )
    if len(out) == 2:
        out.append("| _No apps published yet._ | | | |")
    return "\n".join(out)


def update_readme(table):
    path = os.path.join(ROOT, "README.md")
    with open(path) as f:
        text = f.read()
    block = f"{README_START}\n{table}\n{README_END}"
    if README_START in text and README_END in text:
        new = re.sub(re.escape(README_START) + ".*?" + re.escape(README_END),
                     lambda _: block, text, flags=re.S)
    else:
        new = text.rstrip() + "\n\n" + block + "\n"
    if new != text:
        with open(path, "w") as f:
            f.write(new)
        print("README.md updated")


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    target = os.environ.get("GITHUB_REPOSITORY") or "DemianCode/app_store"
    target_token = os.environ.get("GITHUB_TOKEN")
    source_token = os.environ.get("SOURCE_TOKEN") or target_token
    if not target_token:
        sys.exit("GITHUB_TOKEN is not set")

    with open(os.path.join(ROOT, "apps.json")) as f:
        apps = json.load(f)["apps"]

    mirrored = {}  # app id -> releases of it already in this repo
    for rel in list_releases(target, target_token):
        m = MARKER.search(rel.get("body") or "")
        if m:
            mirrored.setdefault(m.group(1), []).append(rel)

    rows = []
    for app in apps:
        source_rel, apk = pick_release(list_releases(app["repo"], source_token))
        if source_rel is None:
            print(f"{app['id']}: no release with an APK in {app['repo']}, skipping")
            rows.append(None)
            continue

        version = version_of(source_rel["tag_name"])
        tag = f"{app['id']}-v{version}"
        filename = f"{app['id']}-{version}.apk"
        existing = mirrored.get(app["id"], [])
        current = next((r for r in existing if r["tag_name"] == tag), None)

        if current and any(a["name"] == filename for a in current["assets"]):
            print(f"{app['id']}: {version} already published")
            asset = next(a for a in current["assets"] if a["name"] == filename)
            url, size = asset["browser_download_url"], asset["size"]
        elif dry_run:
            print(f"{app['id']}: would publish {version} from {source_rel['tag_name']} "
                  f"({apk['name']}, {human_size(apk['size'])})")
            url = f"https://github.com/{target}/releases/download/{tag}/{filename}"
            size = apk["size"]
        else:
            print(f"{app['id']}: publishing {version} from {source_rel['tag_name']}")
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, filename)
                sha256 = download_asset(apk, source_token, path)
                if current is None:
                    current = request("POST", f"{API}/repos/{target}/releases", target_token, {
                        "tag_name": tag,
                        "name": f"{app['name']} {version}",
                        "body": release_notes(app, version, source_rel, sha256),
                        "make_latest": "false",
                    })
                with open(path, "rb") as f:
                    asset = request(
                        "POST",
                        f"{UPLOADS}/repos/{target}/releases/{current['id']}/assets"
                        f"?name={urllib.parse.quote(filename)}",
                        target_token, f.read(),
                        content_type="application/vnd.android.package-archive",
                    )
            url, size = asset["browser_download_url"], asset["size"]

        # Keep one download per app: drop the copies of older versions.
        for old in existing:
            if old["tag_name"] == tag:
                continue
            if dry_run:
                print(f"{app['id']}: would remove old release {old['tag_name']}")
                continue
            print(f"{app['id']}: removing old release {old['tag_name']}")
            request("DELETE", f"{API}/repos/{target}/releases/{old['id']}", target_token)
            request("DELETE", f"{API}/repos/{target}/git/refs/tags/"
                    f"{urllib.parse.quote(old['tag_name'])}", target_token)

        rows.append({**app, "version": version, "file": filename, "url": url, "size": size})

    # An app taken out of apps.json is unpublished.
    listed = {app["id"] for app in apps}
    for app_id, releases in mirrored.items():
        if app_id in listed:
            continue
        for old in releases:
            if dry_run:
                print(f"{app_id}: would remove {old['tag_name']} (no longer in apps.json)")
                continue
            print(f"{app_id}: removing {old['tag_name']} (no longer in apps.json)")
            request("DELETE", f"{API}/repos/{target}/releases/{old['id']}", target_token)
            request("DELETE", f"{API}/repos/{target}/git/refs/tags/"
                    f"{urllib.parse.quote(old['tag_name'])}", target_token)

    table = render_table(rows)
    if dry_run:
        print("\nREADME table would be:\n" + table)
    else:
        update_readme(table)


if __name__ == "__main__":
    main()
