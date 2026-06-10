# F1 Elite v2 Artifact Wiring + Node24 Installer

## Use

1. Unzip this package.
2. Open the `installer` folder.
3. Double-click:

`RUN_ELITE_V2_ARTIFACT_WIRING_NODE24_INSTALLER_WINDOWS.bat`

4. When asked for the repo path, paste only:

`C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher`

5. Commit and push in GitHub Desktop.

## After installing

Run:

`Elite Weekend Engine Run`

Expected output should no longer say `stub_ready`.

It should download the latest OpenF1 autopilot artifacts and produce real control outputs, likely with status:

`READY_WITH_POSTRACE_SIGNAL_WARNING`

until the post-race feature-row issue is resolved.
