# F1 OpenF1 Lightweight Source Closure + Zero-Lane Diagnostics Patch

## Purpose

This patch adds a GitHub-side lightweight source-closure workflow so missing source lanes are captured automatically going forward, without repeatedly pulling heavy OpenF1 car/location data.

It is designed to prevent the manual Colab catch-up cycle we just went through.

## Single-click Windows install

1. Unzip this package.
2. Open the `installer` folder.
3. Double-click:

`RUN_OPENF1_LIGHTWEIGHT_SOURCE_CLOSURE_PATCH_WINDOWS.bat`

4. When asked for the repo path, paste only your local repo folder path, for example:

`C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher`

5. After the installer completes, commit and push the changes to GitHub.

## What it installs

- A new GitHub Actions workflow for lightweight OpenF1 source closure.
- A new Python publisher script.
- A source-closure policy file.
- Documentation, manifest, and install reporting.

## What it captures going forward

Default lightweight lanes:

- weather
- race control
- intervals
- position
- stints
- pit
- starting grid
- drivers
- team radio when available

It does not pull heavy `car_data` or `location` by default.

## After installing

Run the GitHub workflow:

`F1 OpenF1 Lightweight Source Closure`

Use `workflow_dispatch` first. If it succeeds, it can run on its schedule going forward.

## Safety

This patch does not change the canonical workbook, stable model, automations, or prediction logic. It only adds GitHub-side source capture and diagnostics.
