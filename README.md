# app_store

Android apps I've made, free to download and try.

> [!WARNING]
> **Install these apps at your own risk.** They are personal projects, provided "as is" with no
> warranty of any kind, and many are early or test builds that may have bugs. By downloading or
> installing any app here, you accept full responsibility for doing so. I accept no
> responsibility or liability for any loss, damage or other issues, including to your device or
> your data, that arise from downloading, installing or using them.

## Apps

<!-- apps:start -->
| App | What it does | Version | Download |
| --- | --- | --- | --- |
| **Hermano Mano** | An endless-runner game starring Hermano the dog — dodge, jump and snack your way up the footpath — plus a tracker for logging the dogs' meals and walks. | 0.1.0.19 | [hermano-mano-0.1.0.19.apk](https://github.com/DemianCode/app_store/releases/download/hermano-mano-v0.1.0.19/hermano-mano-0.1.0.19.apk) (19.1 MB) |
| **EduDrop** | Offline classroom tool: the teacher's phone runs a local server and pushes lessons to students' browsers over local Wi-Fi. No internet, no accounts, no student app. | 0.1.0.9 | [edudrop-0.1.0.9.apk](https://github.com/DemianCode/app_store/releases/download/edudrop-v0.1.0.9/edudrop-0.1.0.9.apk) (32.6 MB) |
| **Cardio** | A card table: five solitaire games (Klondike, Spider, FreeCell, TriPeaks, Pyramid) plus Thirteen, Canasta, Texas Hold'em and 500 against computer players. | 1.1.0 | [cardio-1.1.0.apk](https://github.com/DemianCode/app_store/releases/download/cardio-v1.1.0/cardio-1.1.0.apk) (1.5 MB) |
<!-- apps:end -->

## How to install

By installing an app you agree to the warning at the top of this page.

1. On your Android phone, tap the download link for the app you want.
2. Open the downloaded `.apk` file (from the notification, or your **Downloads** folder).
3. If Android asks, allow your browser or file manager to **install unknown apps**, then tap
   **Install**.

These are one-off downloads: the app won't update itself. To get a newer version, come back here
and download it again. Some apps are test builds; if Android says *"App not installed"* when you
already have an older copy, uninstall the old one first (this clears the app's data).

All downloads are also listed on the [Releases page](../../releases).

## Maintaining this repo

The table above is filled in automatically by the **Sync app releases** workflow
(`.github/workflows/sync-releases.yml`). Every six hours, when it's run by hand from the Actions
tab, or when `apps.json` changes, it:

1. reads the releases of each app listed in [`apps.json`](apps.json), whose repos stay private;
2. takes the newest full release with an APK, or the newest prerelease if there's no full
   release yet;
3. if that version isn't here yet, re-publishes the APK as a release in this repo (renamed to
   `<app>-<version>.apk`) and deletes this repo's copy of the previous version;
4. rewrites the table between the `apps:start`/`apps:end` markers above. The rest of this README
   is never touched, so edit it freely.

Only the APK and its version number are copied; the release notes here are written from
`apps.json`, so nothing from the private repos (commit IDs, URLs) leaks out.

### One-time setup: the `SOURCE_REPOS_TOKEN` secret

The workflow's built-in token can only see this repo, so it needs a token that can read the
private ones:

1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token**.
2. **Repository access:** *Only select repositories* → pick each app repo (`hermano-mano`,
   `edudrop`, `cardio`).
3. **Permissions:** *Repository permissions → Contents → Read-only*. Nothing else.
4. Copy the token. In this repo: **Settings → Secrets and variables → Actions → New repository
   secret**, name it `SOURCE_REPOS_TOKEN`, paste the token.
5. **Actions → Sync app releases → Run workflow** to publish straight away.

Fine-grained tokens expire (you choose when, up to a year). When it does, the workflow fails with
a 401/404 error; generate a new one and replace the secret.

### Adding (or removing) an app

1. Add an entry to `apps.json`:
   ```json
   {
     "id": "my-app",
     "repo": "DemianCode/my-app",
     "name": "My App",
     "description": "One or two sentences about what it does."
   }
   ```
   `id` is used in file and tag names, so keep it short, lowercase, with no spaces.
2. Give `SOURCE_REPOS_TOKEN` access to the new repo (edit the token → *Repository access*).
3. Commit. The workflow runs on its own and publishes the app.

Deleting an entry from `apps.json` removes that app's download from this repo on the next run.
