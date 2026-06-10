# F1 GitHub Automation One-Run CLEAN Installer

Generated: 2026-06-10

This version cleans old/conflicting F1 automation files before installing the new files.

## Important

It does not permanently destroy old files. It moves them out of active repo paths into:

`_archive/f1_github_automation_preinstall_cleanup_<timestamp>/`

Then it installs the new clean files.

## Easiest command

Mac/Linux:

```bash
python3 installer/install_f1_github_automation_clean.py --repo "/path/to/your/repo" --apply
```

Windows:

```bat
python installer\install_f1_github_automation_clean.py --repo "C:\path\to\your\repo" --apply
```

## Dry run first

```bash
python3 installer/install_f1_github_automation_clean.py --repo "/path/to/your/repo"
```

## Optional commit

```bash
python3 installer/install_f1_github_automation_clean.py --repo "/path/to/your/repo" --apply --commit
```

## After install

Go to GitHub → Actions and run:

1. `OpenF1 High-Frequency Auto Ingest`
   - mode: `prerace`
   - fetch_mode: `driver_full_session`

2. After a race weekend:
   - mode: `all`

3. Optional:
   - `Elite Weekend Engine Run`
   - mode: `pre_event` or `post_event`
