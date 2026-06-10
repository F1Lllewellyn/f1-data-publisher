# F1 Live Source Feed Capture Cron Hotfix Install Report

Installed at: 2026-06-10T19:55:51.2041587-04:00
Repo path: C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher
Backup folder: C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher\_archive\live_source_feed_capture_cron_hotfix_20260610_195551

## Fixed issue
Replaced invalid four-field cron:

``text
*/15 * * 5,6,0
``

with valid five-field GitHub Actions cron:

``text
*/15 * * * 5,6,0
``

## Next manual steps
1. Review git status.
2. Commit and push this hotfix.
3. Re-open GitHub Actions and confirm the workflow no longer has the invalid cron annotation.
4. Run a short manual test capture before relying on scheduled capture.
