#!/usr/bin/env python3
"""
F1 Prediction Engine GitHub Automation One-Run Installer v2 CLEAN.

Default behavior:
- Dry-run unless --apply is supplied.
- When --apply is supplied, it cleans old/conflicting paths first by moving them
  into _archive/f1_github_automation_preinstall_cleanup_<timestamp>/, then installs
  the new files.
"""

from pathlib import Path
import argparse, shutil, subprocess, sys, json, csv
from datetime import datetime, timezone

INSTALLER_ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_ROOT = INSTALLER_ROOT / 'payload'
CLEANUP_TARGETS = json.loads((PAYLOAD_ROOT / 'CLEANUP_TARGETS.json').read_text(encoding='utf-8'))['targets']
GITIGNORE_BLOCK = (PAYLOAD_ROOT / 'F1_GITIGNORE_BLOCK.txt').read_text(encoding='utf-8')
SKIP_PAYLOAD_FILES = {'PAYLOAD_MANIFEST.csv', 'F1_GITIGNORE_BLOCK.txt', 'CLEANUP_TARGETS.json'}

def run(cmd, cwd=None, check=True):
    print('+', ' '.join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=False)

def unique_archive_path(path):
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_name(path.name + f'__{i}')
        if not candidate.exists():
            return candidate
        i += 1

def clean_old_paths(repo, apply=False):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    archive_root = repo / '_archive' / f'f1_github_automation_preinstall_cleanup_{stamp}'
    rows = []
    for rel in CLEANUP_TARGETS:
        target = repo / rel
        if target.exists():
            archive_target = unique_archive_path(archive_root / rel)
            rows.append({'path': rel, 'exists': True, 'action': 'would_archive_and_remove' if not apply else 'archived_and_removed', 'archive': str(archive_target)})
            if apply:
                archive_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(archive_target))
        else:
            rows.append({'path': rel, 'exists': False, 'action': 'not_present', 'archive': ''})
    if apply:
        archive_root.mkdir(parents=True, exist_ok=True)
        with (archive_root / 'CLEANUP_MANIFEST.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['path','exists','action','archive'])
            writer.writeheader()
            writer.writerows(rows)
    return rows, archive_root

def copy_payload(repo, apply=False):
    rows = []
    for src in PAYLOAD_ROOT.rglob('*'):
        if src.is_dir():
            continue
        rel = src.relative_to(PAYLOAD_ROOT)
        if rel.name in SKIP_PAYLOAD_FILES:
            continue
        dest = repo / rel
        rows.append({'source': str(rel), 'target': str(dest), 'action': 'would_copy' if not apply else 'copied'})
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    return rows

def update_gitignore(repo, apply=False):
    gitignore = repo / '.gitignore'
    existing = gitignore.read_text(encoding='utf-8') if gitignore.exists() else ''
    if '# --- F1 Prediction Engine generated outputs ---' in existing:
        return {'file': str(gitignore), 'action': 'already_present'}
    if apply:
        with gitignore.open('a', encoding='utf-8') as f:
            if existing and not existing.endswith('\n'):
                f.write('\n')
            f.write('\n' + GITIGNORE_BLOCK)
        return {'file': str(gitignore), 'action': 'appended'}
    return {'file': str(gitignore), 'action': 'would_append'}

def validate(repo):
    required = [
        '.github/workflows/openf1-high-frequency-auto-ingest.yml',
        '.github/workflows/openf1-post-event-reliability-metric.yml',
        '.github/workflows/elite-weekend-engine-run.yml',
        'scripts/openf1/openf1_high_frequency_auto_ingest.py',
        'scripts/weekend_run_orchestrator.py',
        'tests/validate_openf1_high_frequency_output.py',
        'configs/openf1/openf1_high_frequency_ingest_policy.json',
        'configs/elite/elite_operational_proof_pattern_control_full7_policy.json',
        'schemas/locked_forecast_ledger_v2_schema.json',
        'templates/dnf_all_precursor_board_template.csv',
        'workbook_bridge/elite_control_room_export_manifest.csv',
    ]
    return [{'path': r, 'exists': (repo / r).exists()} for r in required]

def write_install_report(repo, clean_rows, copy_rows, gitignore_result, validation_rows, archive_root, apply):
    report_dir = repo / 'docs'
    if apply:
        report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / 'F1_GITHUB_AUTOMATION_INSTALL_REPORT.md'
    missing = [r['path'] for r in validation_rows if not r['exists']]
    cleaned = [r for r in clean_rows if r['exists']]
    text = f"""# F1 GitHub Automation Install Report

Generated: {datetime.now(timezone.utc).isoformat()}

Mode: {'APPLY' if apply else 'DRY RUN'}

## Result

{'PASS' if apply and not missing else 'DRY RUN COMPLETE' if not apply else 'CHECK REQUIRED'}

## Pre-install cleanup

Existing old/conflicting paths found: {len(cleaned)}

Cleanup behavior:
- Existing old paths are moved to `_archive/...` first.
- Then new files are installed into clean active paths.
- This removes active conflicts without permanently destroying the old files.

Archive location:
`{archive_root}`

## Gitignore

- {gitignore_result['action']}

## Validation

| Path | Exists |
|---|---:|
"""
    for r in validation_rows:
        text += f"| `{r['path']}` | {r['exists']} |\n"
    text += """

## Guardrails

- Generated high-frequency outputs are ignored by Git.
- No raw telemetry should be committed by default.
- No automatic stable race P1-P20 rank changes are enabled.
- No automatic qualifying P1-P5 rank changes are enabled.
"""
    if apply:
        report.write_text(text, encoding='utf-8')
    else:
        print(text)
    return report

def git_commit(repo, push=False):
    if not (repo / '.git').exists():
        print('Not a git repository; skipping commit.')
        return
    run(['git', 'status', '--short'], cwd=repo, check=False)
    run(['git', 'add', '.github', 'scripts', 'tests', 'configs', 'schemas', 'templates', 'workbook_bridge', 'docs', 'requirements-f1-engine-automation.txt', 'requirements-openf1-ingest.txt', '.gitignore', 'ledgers', '_archive'], cwd=repo, check=False)
    run(['git', 'commit', '-m', 'Clean install F1 OpenF1 automation and elite engine workflows'], cwd=repo, check=False)
    if push:
        run(['git', 'push'], cwd=repo, check=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True, help='Path to your local GitHub repository folder')
    ap.add_argument('--apply', action='store_true', help='Actually clean/copy files. Without this, dry-run only.')
    ap.add_argument('--no-clean-old', action='store_true', help='Do not clean old paths first.')
    ap.add_argument('--commit', action='store_true', help='Create a git commit after applying.')
    ap.add_argument('--push', action='store_true', help='Push after commit.')
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.exists():
        raise SystemExit(f'Repo path does not exist: {repo}')

    print(f'Repo: {repo}')
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f'Clean old paths: {not args.no_clean_old}')

    if args.no_clean_old:
        clean_rows, archive_root = [], repo / '_archive' / 'cleanup_skipped'
    else:
        clean_rows, archive_root = clean_old_paths(repo, apply=args.apply)

    copy_rows = copy_payload(repo, apply=args.apply)
    gitignore_result = update_gitignore(repo, apply=args.apply)
    validation_rows = validate(repo) if args.apply else [{'path': r['target'], 'exists': False} for r in copy_rows[:10]]
    report = write_install_report(repo, clean_rows, copy_rows, gitignore_result, validation_rows, archive_root, args.apply)

    print(f'Cleanup targets checked: {len(clean_rows)}')
    print(f'Files copied/queued: {len(copy_rows)}')

    if args.apply:
        print(f'Archive folder: {archive_root}')
        print(f'Install report: {report}')
        missing = [r['path'] for r in validation_rows if not r['exists']]
        if missing:
            print('Missing after install:')
            print('\n'.join(missing))
            sys.exit(2)
        if args.commit:
            git_commit(repo, push=args.push)
    else:
        print('Dry run complete. Re-run with --apply to clean and install.')

if __name__ == '__main__':
    main()
