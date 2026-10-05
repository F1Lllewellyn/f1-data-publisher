# Peak Elite heredoc-aware workflow validator repair

Work order: [#157](https://github.com/F1Lllewellyn/f1-data-publisher/issues/157), `F1-WO-MAINT-PEAK-ELITE-HEREDOC-001`. Tracking: #155 item 1 only.
Implementation and local validation: 2026-10-05 UTC. The filename follows the work order's prescribed 2026-10-04 path.
Status: completed implementation; independent Adviser review pending.

## Predecessor and scope

Accepted PR #156 was verified at reviewed head `f1c8c7db8eb47ce6df1ba10346979f4af4f49d2c`, with exactly the three reviewed additions, and merged unchanged as `4986bb7011bd03e50614ec6b1f73844120d7c6fc`.

Starting main: `42058f0ffde858d06721c4132b5828982d0b9483`.
Implementation baseline after Part A: `4986bb7011bd03e50614ec6b1f73844120d7c6fc`.

Exactly five paths comprise this repair:

- MODIFY `scripts/ops/f1_workflow_meta_health_check_v1.py`
- MODIFY `scripts/ops/f1_workflow_static_validator_v2.py`
- ADD `scripts/ops/f1_workflow_shell_scan_v1.py`
- ADD `tests/test_f1_workflow_heredoc_validation_v1.py`
- ADD this checkpoint.

No workflow, DR-002 implementation, safe-push script, protected engine, producer, workbook, latest/history or production configuration changes.

## Cause and repair

Both validators applied their line-start Bash if/fi regex directly to entire YAML literal run blocks. Python inside the two DR-002 heredocs contributed 25 and 8 apparent shell if statements, with no shell fi statements.

Both now call the same pure `shell_visible_text(script)` helper before that existing manual balance check. Heredoc bodies and terminators become blank lines, retaining shell lines and line positions. The helper recognizes unquoted, single/double-quoted and escaped delimiter words, including concatenated quoting and `<<-` tab stripping. It handles multiple pending heredocs in declaration order and continued command lines. Comments, quoted literals, here-strings and arithmetic shifts do not open heredocs. Unquoted body backslash-newline handling preserves delimiter matching semantics.

Missing/malformed or unterminated delimiters raise `ShellScanError`. Validators record a failure and retain the original script for the manual count; they never silently hide the remainder after a scanner failure. Unsupported continued delimiter words fail closed.

The helper is a bounded heredoc scanner, not a full Bash parser. Existing manual line-start if/fi rules and YAML run-block extraction are unchanged. Bash syntax validation remains the static validator's authority for general shell grammar. This change makes no new claim about previously unsupported shell/YAML constructs.

## Preserved validation and report semantics

The only changes in each existing validator are the shared import and the filter/failure handling around its two manual counts.

- Static validation still calls `bash -n` on the **original**, unfiltered block.
- Raw git-push warnings and static force-push failures still inspect original text, including heredoc bodies, exactly as before.
- BOM warnings, required workflow-key failures, required stability-file checks and protected engine/workbook checks are unchanged.
- Existing report keys, statuses, severities, output paths and existing issue messages are unchanged. Scanner failures use the existing issue structures: meta-health `Shell heredoc scan failed: ...`; static `shell_heredoc_scan_failed` plus detail. No public report field/schema was added or removed.
- No push/rebase retry behavior changes.

## Focused offline evidence

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_f1_workflow_heredoc_validation_v1.py' -v
```

Final result: **19 test methods PASS; zero failures/errors**, including matrix/subtests.

| Case | Result |
|---|---|
| Exact current DR-002 capture workflow | Former 25 body if lines excluded; no failure from either validator; original block passes bash -n |
| Exact current frozen-producer workflow | Former 8 body if lines excluded; no failure from either validator; original block passes bash -n |
| Arbitrary Python/text if, fi, for inside body | Does not affect manual Bash balance |
| Real multiline Bash if/fi around and beside heredoc | Pass |
| Unmatched real Bash if; body fi attempting to close it | Both validators fail |
| Plain/single/double-quoted, escaped/concatenated delimiters, empty quoted delimiter and tab-stripping forms | Pass |
| Multiple heredocs and continued headers | Pass |
| Missing/malformed/unterminated delimiter, spaces instead of permitted tabs, trailing delimiter space | Fail closed |
| Unquoted body backslash-newline | Correct termination or fail-closed when not terminated |
| Original block supplied to bash -n | Verified |
| Push/force-push, BOM/keys, protected assets | Existing behavior retained |
| Shared helper, determinism, line positions | Verified |
| Six nonmodified dependency blobs | Exact Git hashes match |

An initial test combined a raw carriage-return terminator case with a YAML fixture generator that itself normalized line endings, so its end-to-end expectation was invalid. That case was moved to a direct helper regression, where the raw bytes remain intact. No validator extraction semantics were changed to accommodate it. The final focused suite passes.

The tests run local Python validators and Bash syntax checks only. No shell payload, producer, live capture or workflow was executed. Meta-health subprocesses write reports solely inside temporary test directories. The protected-file probe uses a mocked git-status response; it does not alter protected files.

## Dependency evidence

All eight declared blobs matched fresh main after Part A. The two validator changes are the authorized exceptions; the other six remain byte-identical and are checked by the focused suite.

| Dependency | Accepted baseline Git blob |
|---|---|
| `scripts/ops/f1_workflow_meta_health_check_v1.py` | `19c2f2a9a13f2fb65e051ed61bc75e68fb562954` |
| `scripts/ops/f1_workflow_static_validator_v2.py` | `12b0097ea76dd324eb612761988672624a1b0a39` |
| `.github/workflows/dr002-capture-provenance-pilot.yml` | `883fcbc1a00ec9ae1dd6dd40423a03af05ae1fe3` |
| `.github/workflows/dr002-frozen-producer-shadow-pilot.yml` | `850e96cbea815c3dec3f14c3a731f2f65cce2944` |
| `.github/workflows/f1-peak-elite-control-room-one-click-v1.yml` | `42c107142e076ac4d056f2e33e93dab4163f3b72` |
| `scripts/ops/f1_peak_elite_health_v1.py` | `7e27e30a12649cf36eaaa19c0862d468579c314a` |
| `scripts/ops/safe_git_push_rebase_retry.sh` | `85f85bb540cf8442827a1586d5ccf0c5602d7a75` |
| `docs/control/F1_AGENT_HANDOFF_CONTRACT_v1.md` | `85ce44807ef159b5ba5d3bfd543ea1f945097f77` |

The complete five-path publication delta is the authoritative evidence that no workflow or safe-push file changed.

## Required conclusions

- The two reported DR-002 heredoc false positives are removed by local regression evidence.
- Actual unmatched Bash if detection remains fail-closed; static Bash syntax checking is preserved.
- No DR-002 workflow bytes changed.
- No safe-push behavior changed.
- Issue #155 item 1 alone is addressed.
- Issue #155 item 2, the scheduled-writer dirty-path safe-push collision, **remains deferred**.

No manual Peak Elite rerun occurred. A passing local repair does not claim a new successful scheduled run or resolution of the separate collision. DR-002 remains PROPOSED — NOT ACTIVATED; forecast gate OFF; promotion NOT ALLOWED. Next decision: independent Adviser review of this Work Result, not automatic merge or further implementation.

