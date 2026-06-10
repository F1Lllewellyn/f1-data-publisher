# F1 GitHub Tabulate Hotfix

The OpenF1 GitHub Action completed the heavy extraction but failed while writing the Markdown report:

`ImportError: Import tabulate failed`

This hotfix adds `tabulate` to the workflow dependency installs and requirements files.

## Use

1. Unzip this package.
2. Open `installer`.
3. Double-click `RUN_TABULATE_HOTFIX_WINDOWS.bat`.
4. When asked for the repo path, paste only:

`C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher`

5. Commit and push the changed files.
6. Re-run `OpenF1 High-Frequency Auto Ingest` with:
   - year = 2026
   - mode = prerace
   - fetch_mode = driver_full_session
