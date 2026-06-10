# F1 OpenF1 Lightweight Source Closure Patch Install Report

Generated: 2026-06-10T18:59:09.9696941-04:00
Mode: APPLY

Installed source-closure workflow and publisher for:
- weather
- race control
- intervals
- position
- stints
- pit
- starting grid
- drivers
- team radio when available

Heavy OpenF1 car_data and location are excluded by default.

Archived previous copies at:
C:\Users\Matt Llewellyn\OneDrive\Documents\GitHub\f1-data-publisher\_archive\openf1_lightweight_source_closure_patch_20260610_185909

After commit/push:
- Run the GitHub workflow: F1 OpenF1 Lightweight Source Closure
- Verify latest/openf1_lightweight_source_closure/latest_manifest.json exists after the run.
- Verify source_readiness_summary.csv and zero_lane_diagnostics.csv exist.
- Do not rerun heavy OpenF1 car/location extraction unless specifically needed.
