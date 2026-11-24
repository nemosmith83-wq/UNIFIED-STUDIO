# FadeL The New Era + Unified Studio Android merge

The Android integrated build combines the existing Unified Studio 1.2.0 app with the original FadeL The New Era v16 web/PWA and its supplemental tools.

## What is merged

- The existing Unified Studio Android shell and backend remain the base.
- The New Era v16 entry point and its static assets are packaged under `app/src/main/assets/frontend/new-era/`.
- The supplemental tools ZIP is unpacked into `frontend/new-era/tools/` and its reference files into `frontend/new-era/resources/`.
- A navigation entry opens `/new-era/unified-launcher.html`, which links to the original New Era app and the additional tools.
- The build verifies that the main app, launcher, at least 15 HTML tools, and reference assets are present in the APK.

## Build

GitHub Actions workflow: [Build Unified Studio Android 1.2.0 Integrated APK](.github/workflows/android-integrated-1.2.0.yml)

The workflow downloads the verified source archives from the project's hosted static assets, merges them into the Android asset tree, runs regression tests, builds the debug APK, verifies the APK signature and embedded paths, and uploads the APK as an Actions artifact named `Unified-Studio-Android-1.2.0-Integrated-APK`.

Open **Actions → Build Unified Studio Android 1.2.0 Integrated APK → latest successful run → Artifacts** to download the APK.

## Security note

The original uploaded archive contained a signing-key file. Signing keys, BitLocker recovery material, and other private secrets are intentionally excluded from this merge and must never be committed to the public repository.
