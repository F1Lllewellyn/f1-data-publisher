# Auto-Repair Scheduled Integration Design

## Goal

Eliminate the manual gap between session ingestion and workbook/KPI refresh validation.

## Design

The integrated workflow runs after watcher windows. It does not rely on the user manually choosing the right sequence of Session Processor, Workbook/KPI Refresh, and Auto-Repair.

It performs:

1. dependency preflight;
2. integration health check;
3. Session Data Processor run;
4. Auto-Repair recovery run;
5. report echo;
6. artifact upload;
7. source-backed commit gate.

## Safety rules

- No stable overwrite.
- No canonical workbook overwrite.
- No promotion.
- No commit unless Auto-Repair says the final Workbook/KPI refresh is source-backed.
- No deletion of old artifacts.
- Dated outputs only.
