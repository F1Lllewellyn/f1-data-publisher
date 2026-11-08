# Race-day weather evidence update — observational supplement, not forecast regeneration

Logged at **2026-11-08T16:09:40.232Z** (UTC) before scheduled formation lap at 17:00Z.

## Source hierarchy and times

- Formula1.com preview, **2026-11-04 14:00Z**: Sunday 40% rain risk, race temp approx 13–19°C, potential heavy rain/thunderstorms. https://www.formula1.com/en/latest/article/what-is-the-weather-forecast-for-the-2026-sao-paulo-grand-prix.6DTTG84ES6tbC6eISpqnR8
- Pirelli post-qualifying analysis, **2026-11-07**: approximately 60% rain risk; if dry, preferred two-stop soft-soft-medium reference. https://press.pirelli.com/from-full-wets-to-inters-in-qualifying-norris-takes-pole-in-so-paulo/
- Updated 2026-11-08 race-hour forecast **published 08:34–08:39Z** by F1LivePulse citing the Met Office: hourly probability 95% or higher from 14:00–16:00 Sao Paulo local, *light rain* forecast, 16–17°C; Climatempo estimate ~80% near formation lap. This is a secondary report of forecaster estimates, **not FIA/F1 official observed weather**, and probability windows differ. https://blog.f1livepulse.com/2026-sao-paulo-gp-race-day-weather
- F1Weather independently lists Open-Meteo/OpenWeatherMap 98% rain probability for event, **updated 11:55Z**. Not official F1; dynamic third-party API aggregator. https://f1weather.com/

**Scientific interpretation:** Wet track conditions have a substantially stronger weather-forecast case at this observation than when earlier weekend forecasts were published. Forecast probabilities cannot be reweighted as calibrated model weights. The 22-driver original prospective benchmark `prospective_frozen_v1.json` (committed at 15:53:58Z) remains **immutable** and contains both dry and wet ranks. The result to score is the original frozen output, never a revised weather-picking artifact that takes advantage of outcome knowledge. No actual precipitation, race tyre choice or safety-car starting procedure claimed.

**Model controls:** Protected stable engine not executed. No underlying revised grid/final FIA grid verified. This memo is a dated evidence update, not a second forecast.
