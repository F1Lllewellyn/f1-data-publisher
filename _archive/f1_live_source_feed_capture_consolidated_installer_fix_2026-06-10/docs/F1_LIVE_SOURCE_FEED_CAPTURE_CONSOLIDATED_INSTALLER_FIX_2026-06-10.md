# F1 Live Source Feed Capture — Consolidated Installer Fix

Date: 2026-06-10
Status: Experimental patch installer fix

## Purpose

This package fixes the consolidated validation patch installer so that the files referenced by the installer match the files included in the package.

## Cause of prior failure

The prior consolidated validation patch installer referenced legacy latest-preserve documentation filenames that were not included in that package. PowerShell therefore failed on `Copy-Item` before the installation completed.

## Safety

This package is cumulative for the experimental live source-feed capture layer. It installs/replaces the workflow and capture script, adds documentation/register files, and writes an install report. It does not touch the canonical workbook, stable engine, Method E workbook, predictions, or existing OpenF1 source-closure workflow.

## Recommended validation after install

Run the GitHub workflow manually with:

- capture_mode: manual
- manual_validation_mode: infrastructure_only
- duration_minutes: 2
- session_label: manual_test
- commit_outputs: true

Expected result: Pass with warnings, with infrastructure artifacts committed and no deletion of latest evidence-bearing capture files.
