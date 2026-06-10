# F1 Elite v2 Artifact Download 401 Hotfix

## Problem

The Elite v2 workflow failed at:

`Download latest OpenF1 autopilot artifacts`

with:

`HTTP Error 401: Server failed to authenticate the request`

## Cause

GitHub artifact download endpoints redirect to a temporary signed storage URL. The previous script let urllib follow the redirect while still inside the authenticated request flow. The storage backend can reject that with 401.

## Fix

The new downloader:

1. Calls the GitHub artifact API with `GITHUB_TOKEN`.
2. Captures the redirect `Location` URL.
3. Downloads the signed URL without the GitHub Authorization header.
4. Writes a diagnostic manifest if any artifact download still fails.

## Also adjusted

The Elite workflow now includes the input manifest folder in the artifact upload and changes `if-no-files-found` to `warn`, so a download-stage failure still leaves diagnostics instead of a second hard artifact-upload error.
