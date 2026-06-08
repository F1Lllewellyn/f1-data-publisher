# F1 Hands-Free OpenF1 + FastF1 Public Data Publisher

This is the fully hands-free version.

It does not just create a GitHub Actions artifact. It publishes a small static data site with stable public URLs that ChatGPT can fetch directly.

## Stable URLs after setup

Replace `<owner>` and `<repo>`:

```text
https://<owner>.github.io/<repo>/latest/latest_manifest.json
https://<owner>.github.io/<repo>/latest/data_readiness.json
https://<owner>.github.io/<repo>/latest/combined_source_manifest.csv
https://<owner>.github.io/<repo>/latest/latest.zip
```

Once these exist, you can ask ChatGPT:

> Fetch the latest F1 data publisher manifest and update the model.

No manual ZIP download/upload is needed.

## One-time setup

1. Create a GitHub repo.
2. Upload this package contents.
3. Enable GitHub Pages with GitHub Actions as the source.
4. Edit `config/race_config.json` for the next event.
5. Run the workflow once manually.
6. Give ChatGPT the stable `latest_manifest.json` URL.

After that, the scheduled workflow republishes the latest data automatically.

## Default target

- 2026 Spanish Grand Prix
- FP3, Qualifying, Race
- OpenF1 + FastF1
- Team radio included
- High-volume car_data disabled
