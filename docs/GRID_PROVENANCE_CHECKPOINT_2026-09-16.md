# Grid provenance checkpoint — 2026-09-16

Status: **guarded sandbox branch; no production promotion or forecast authorization**.
This note records why the race/sprint grid was held for review, the bounded
source mapping, and the next evidence needed. It supplements the existing
session-readiness policy rather than removing its race/sprint grid requirement.

## Evidence and interpretation

- The processor used the current session key for every OpenF1 endpoint. Madrid
  Race `11369` therefore fetched `starting_grid` as a 404, while Qualifying
  `11365` in meeting `1294` already held 22 grid rows. The qualifying grid was
  captured at `2026-09-13T11:59:17Z`, ahead of the race start at 13:00 UTC.
- Equivalent stored observations: Monza Qualifying `11357` supplies Race
  `11361`; Zandvoort Qualifying `11349` supplies Race `11353`, and Sprint
  Qualifying `11344` supplies Sprint `11348`. The corresponding direct
  race/sprint grid fetches were empty or 404. These are observed mappings,
  not a guarantee about every future weekend.
- Madrid's starting-grid order differs from qualifying classification for
  several drivers (including car 55). Never reconstruct the grid by sorting
  qualifying result rows. OpenF1 calls this its *starting grid for the upcoming
  race*, available after official results, but does not certify in each row
  when a later grid revision took effect. The OpenF1 source is unofficial:
  <https://openf1.org/docs/#starting-grid>.
- **Correction on 20 September:** FIA [provisional grid, Doc 57](https://www.fia.com/system/files/decision-document/2026_spanish_grand_prix_-_provisional_starting_grid.pdf)
  assigned car 87 a numbered slot. [Stewards' Doc 63](https://www.fia.com/system/files/decision-document/2026_spanish_grand_prix_-_infringement_-_car_87_-_pu_elements_changed_during_parc_ferme.pdf)
  subsequently required it to start from the pit lane. FIA [final grid, Doc 65](https://www.fia.com/system/files/decision-document/2026_spanish_grand_prix_-_final_starting_grid.pdf)
  lists car 87 under pit-lane starters and car 18 at grid position 21. The
  stored OpenF1 capture still has car 87 at 21 and car 18 at 22. Doc 65 was
  published at 14:00 on race day, one hour before the scheduled race start;
  the stored OpenF1 capture time was 11:59:17 UTC. The source key lookup was
  correct, but its grid was **not** the final official grid. FIA [2026 sporting
  regulations, B2.3.4 and B2.4.4](https://api.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_07_-_2026-06-25.pdf)
  specify final-grid publication one hour before the formation lap and allow
  positions to remain vacant after late withdrawals.

## Sandbox contract

1. Query the target race/sprint session first. Preserve a successful direct
   result. Only an empty response or HTTP 404 permits the associated-session
   lookup; other failures retain manual review.
2. Race requires exactly one same-meeting ordinary Qualifying; Sprint requires
   exactly one same-meeting Sprint Qualifying. Its end must precede the target
   start, and both keys must exist. Ambiguity or invalid timing never triggers
   a guess. Other endpoints retain their original session handling.
3. Persist fetched rows unchanged, including the **source** session key.
   Validate against that source key and the same meeting. Attach target key,
   resolution method, capture time, direct-fetch failure, hash, and comparisons
   against prior target and qualifying snapshots to the grid validation report.
   Existing latest/history paths and aggregation rules stay intact.
4. Duplicate or invalid positions, driver/roster discrepancies, conflicting
   source identifiers, or a grid revision first observed after the target start
   require review. A hash difference proves a change between captures; it does
   **not** date that change. No snapshot is certified as the official final
   grid or as a forecast-time input merely because the OpenF1 fetch succeeded.
5. `official_final_grid_verified=false`, `forecast_as_of_eligible=false`, and
   `promotion_allowed=false` remain explicit. A race/sprint grid's valid OpenF1
   rows are recorded separately as `provenance.openf1_row_status=clean`, but its
   required **source status remains `needs_manual_review`** with anomaly
   `fia_final_grid_unverified`. This prevents downstream readiness from
   treating an unverified OpenF1 grid as the final FIA grid. No prediction is
   generated or published.

## Remaining closure work

- Obtain an independently time-stamped official final-grid source and define
  the authority/precedence policy for penalties, pit-lane starts, withdrawals,
  and late revisions. Review observed source mismatches rather than filling
  missing grid positions from qualifying order.
- Before any **forecast** use, prove each input was observed at or before the
  forecast lock time; retain immutable snapshots, source URLs/hashes, and
  review late changes. Historical API responses cannot prove their earlier
  availability merely because they are fetchable now.
- Validate representative sprint and race weekends in a read-only replay,
  then review downstream consumers and notification behavior. The branch does
  not change the stable engine, canonical workbook, scheduled production
  workflows, or the main branch.

Offline acceptance: `python scripts/ops/grid_provenance_acceptance_v1.py`.
