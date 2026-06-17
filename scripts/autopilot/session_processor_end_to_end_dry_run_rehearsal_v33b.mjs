
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const VERSION = 'v33B-R3';
const DEFAULT_POLICY = 'scripts/autopilot/session_processor_end_to_end_dry_run_policy_v33b.json';

function parseArgs(argv) {
  const args = {
    repoRoot: process.cwd(),
    policy: DEFAULT_POLICY,
    mode: 'repo',
    fixture: null,
    output: null,
    allow_live: false,
    production_automation: false,
    workbook_write: false,
    ledger_write: false,
    race_predictions_refresh: false,
    fantasy_predictions_refresh: false,
    notification_send: false,
    model_promotion: false
  };
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const next = argv[i + 1];
    if (!key.startsWith('--')) continue;
    const name = key.slice(2).replaceAll('-', '_');
    if (name in args) {
      if (typeof args[name] === 'boolean') {
        if (next === 'true' || next === 'false') {
          args[name] = next === 'true';
          i += 1;
        } else {
          args[name] = true;
        }
      } else {
        args[name] = next;
        i += 1;
      }
    } else if (name === 'help') {
      printHelpAndExit();
    } else {
      throw new Error(`Unknown argument: ${key}`);
    }
  }
  return args;
}

function printHelpAndExit() {
  console.log(`Usage:
  node scripts/autopilot/session_processor_end_to_end_dry_run_rehearsal_v33b.mjs \\
    --repo-root . \\
    --policy scripts/autopilot/session_processor_end_to_end_dry_run_policy_v33b.json \\
    --mode repo \\
    --output artifacts/autopilot/v33b/rehearsal_output_v33b.json

Fixture self-test:
  node scripts/autopilot/session_processor_end_to_end_dry_run_rehearsal_v33b.mjs \\
    --mode fixture \\
    --fixture fixtures/autopilot/v33b/happy_path_operator_packet.json

Safety flags default false and must remain false for v33B:
  --allow-live false
  --production-automation false
  --workbook-write false
  --ledger-write false
  --race-predictions-refresh false
  --fantasy-predictions-refresh false
  --notification-send false
  --model-promotion false`);
  process.exit(0);
}

function readJson(absPath) {
  const raw = fs.readFileSync(absPath, 'utf8');
  return JSON.parse(raw);
}

function maybeReadJson(absPath) {
  try {
    if (fs.existsSync(absPath)) return readJson(absPath);
  } catch (error) {
    return { __parse_error: String(error?.message || error) };
  }
  return null;
}

function ensureDirForFile(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function canonicalStatus(value) {
  return String(value || '').trim().toUpperCase();
}

function sha256Object(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

function pathExistsAny(repoRoot, candidates) {
  const checked = [];
  for (const rel of candidates || []) {
    const abs = path.resolve(repoRoot, rel);
    checked.push(rel);
    const obj = maybeReadJson(abs);
    if (obj) return { found: true, relPath: rel, absPath: abs, object: obj, checked };
  }
  return { found: false, relPath: null, absPath: null, object: null, checked };
}

function validateRequiredFields(name, packet, spec) {
  const blockers = [];
  const warnings = [];
  if (!packet) {
    blockers.push(`${name}: missing packet`);
    return { blockers, warnings };
  }
  if (packet.__parse_error) {
    blockers.push(`${name}: JSON parse/read failure: ${packet.__parse_error}`);
    return { blockers, warnings };
  }
  for (const [field, expected] of Object.entries(spec.required_fields || {})) {
    if (!(field in packet)) {
      blockers.push(`${name}: missing required field '${field}'`);
    } else if (packet[field] !== expected) {
      blockers.push(`${name}: field '${field}' expected ${JSON.stringify(expected)} but found ${JSON.stringify(packet[field])}`);
    }
  }
  const status = canonicalStatus(packet.status);
  const allowed = (spec.allowed_statuses || []).map(canonicalStatus);
  if (!allowed.includes(status)) {
    blockers.push(`${name}: status '${packet.status ?? 'missing'}' is not in allowed statuses ${JSON.stringify(spec.allowed_statuses || [])}`);
  }
  if (packet.notes && String(packet.notes).toLowerCase().includes('fixture')) {
    warnings.push(`${name}: fixture note detected; not production evidence`);
  }
  return { blockers, warnings };
}

function validateFalseFlags(args, policy) {
  const blockers = [];
  for (const flag of policy.required_explicit_false_flags || []) {
    const argName = flag;
    if (args[argName] !== false) {
      blockers.push(`safety flag '${argName}' must be explicitly false for ${VERSION}`);
    }
  }
  return blockers;
}

function isPathInside(parentAbs, childAbs) {
  const rel = path.relative(parentAbs, childAbs);
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
}

function normalizeRelPath(relPath) {
  return relPath.replaceAll('\\\\', '/');
}

function pathMatchesProtected(writePath, protectedPath) {
  const normalizedWrite = normalizeRelPath(writePath);
  const normalizedProtected = normalizeRelPath(protectedPath);
  if (normalizedWrite === normalizedProtected) return true;
  if (normalizedProtected.endsWith('/')) return normalizedWrite.startsWith(normalizedProtected);
  return normalizedWrite.startsWith(`${normalizedProtected}/`);
}

function protectedPathAudit(policy, plannedWrites) {
  const touches = [];
  const protectedPaths = policy.protected_paths || [];
  for (const writePath of plannedWrites) {
    for (const protectedPath of protectedPaths) {
      if (pathMatchesProtected(writePath, protectedPath)) {
        touches.push({ writePath, protectedPath });
      }
    }
  }
  return touches;
}

function validateOutputTarget(args, policy) {
  if (!args.output) {
    return {
      requested: false,
      writePermitted: false,
      relPath: null,
      absPath: null,
      blockers: [],
      protectedTouches: []
    };
  }

  const repoRootAbs = path.resolve(args.repoRoot);
  const absPath = path.resolve(repoRootAbs, args.output);
  const insideRepo = isPathInside(repoRootAbs, absPath);
  const relPath = insideRepo ? normalizeRelPath(path.relative(repoRootAbs, absPath)) : normalizeRelPath(path.relative(repoRootAbs, absPath));
  const blockers = [];

  if (!insideRepo) {
    blockers.push(`output path must remain inside repo root for ${VERSION}: ${relPath}`);
  }

  const allowedRoots = policy.allowed_output_roots || ['artifacts/autopilot/v33b/', 'verification/'];
  const insideAllowedRoot = allowedRoots.some((root) => {
    const normalizedRoot = normalizeRelPath(root);
    return relPath === normalizedRoot.replace(/\/$/, '') || relPath.startsWith(normalizedRoot);
  });
  if (!insideAllowedRoot) {
    blockers.push(`output path must be under an allowed dry-run artifact root: ${JSON.stringify(allowedRoots)}`);
  }

  const protectedTouches = protectedPathAudit(policy, [relPath]);
  if (protectedTouches.length > 0) {
    blockers.push(`planned write touches protected path: ${JSON.stringify(protectedTouches)}`);
  }

  return {
    requested: true,
    writePermitted: blockers.length === 0,
    relPath,
    absPath,
    allowedRoots,
    blockers,
    protectedTouches
  };
}

function buildEvidenceFromFixture(fixtureObject) {
  return {
    v32N_dry_run_operator_packet: {
      found: Boolean(fixtureObject?.v32N_dry_run_operator_packet),
      relPath: 'fixture:v32N_dry_run_operator_packet',
      object: fixtureObject?.v32N_dry_run_operator_packet || null,
      checked: ['fixture:v32N_dry_run_operator_packet']
    },
    v33A_operator_review_verifier: {
      found: Boolean(љ^\™SШљ™XЭЛќЊМРWЫЬ\]Ь—Ь™]љY]ЧЭ™\љYљY\ЉK€™[]€	Щљ^\™NќЊМРWЫЬ\]Ь—Ь™]љY]ЧЭ™\љYљY\‰Л€Шљ™XЭ€љ^\™SШљ™XЭЛќЊМРWЫЬ\]Ь—Ь™]љY]ЧЭ™\љYљY\€ќ[€ЪXЪЩY€ЙЩљ^\™NќЊМРWЫЬ\]Ь—Ь™]љY]ЧЭ™\љYљY\‰ЧB€B€NВџB‚™ќ[Э[Ы€ќZ[]љY[ЩQњ›ЫT™\К™\Ф›ЫЭЫXЮJHВ€ЫЫњЭЭ]HЯNВ€›Ь€
ЫЫњЭЫ[YKЬXЧHЩ€Шљ™XЭ™[ќљY\КЫXЮKњ™\]Z\™YЩ]љY[ЩWШЪZ[€ЯJJHВ€Э]Ы[YWHH]^\ЭР[ћJ™\Ф›ЫЭЬXЛШ[™Y]WЬ]ИЧJNВ€B€™]\›€Э]ВџB‚™ќ[Э[Ы€ЭYЩJ[YKЭ]\Л]Z[ИHЯK›ШЪЩ\њИHЧKШ\›љ[™ЬИHЧJHВ€™]\›€И[YKЭ]\Л]Z[Л›ШЪЩ\њЛШ\›љ[™ЬИNВџB‚™ќ[Э[Ы€ќ[”™ZX\њШ[
\™ЬЛЫXЮJHВ€ЫЫњЭЭ\ќY]ИH™]И]J
KќТTУФЭљ[™К
NВ€ЫЫњЭЭ]][€H[Y]SЭ]]\™Щ]
\™ЬЛЫXЮJNВ€ЫЫњЭ[›™YЬљ]\ИHЭ]][‹њ™[]ИЫЭ]][‹њ™[]H€ЧNВ‚€ЫЫњЭШY™]P›ШЪЩ\њИH[Y]Q[ЩQ›YЬК\™ЬЛЫXЮJNВ€ЫЫњЭ›ЭXЭYЭXЪ\ИHЭ]][‹њ›ЭXЭYЭXЪ\И›ЭXЭY]]Y]
ЫXЮK[›™YЬљ]\КNВ€ЫЫњЭЭYЩ\ИHЧNВ€ЫЫњЭ[›ШЪЩ\њИHЧNВ€ЫЫњЭ[Ш\›љ[™ЬИHЧNВ‚€[›ШЪЩ\њЛњ\Ъ
‹‹›Э]][‹›ШЪЩ\њКNВ€[›ШЪЩ\њЛњ\Ъ
‹‹њШY™]P›ШЪЩ\њКNВ‚€ЭYЩ\Лњ\Ъ
ЭYЩJ	ЬЫXЮWЩЭX\™	Л[›ШЪЩ\њЛ›[™ЭOOHИ	Ь\ЬЙИ€	Ш›ШЪЩY	ЛВ€[ЩN€\™ЬЛ›[ЩK€™\]Z\™YЩ[ЩWЩ›YЬО€ЫXЮKњ™\]Z\™YЩ^XЪ]Щ[ЩWЩ›YЬЛ€›ЭXЭYЬ]ЭЭXЪ\О€›ЭXЭYЭXЪ\Л€[›™YЭЬљ]\О€[›™YЬљ]\Л€Э]]ЭЬљ]WЬ\›Z]Y€Э]][‹ќЬљ]T\›Z]Y€[ЭЩYЫЭ]]Ь›ЫЭО€Э]][‹[ЭЩY›ЫЭИЧB€KЛ‹‹[›ШЪЩ\њЧJJNВ‚€]]љY[ЩNВ€Y€
\™ЬЛ›[ЩHOOH	Щљ^\™IКHВ€Y€
X\™ЬЛ™љ^\™JH›ЭИ™]И\њ›ЬЉ	ЛKYљ^\™H\И™\]Z\™YЪ[€K[[ЩHљ^\™IКNВ€ЫЫњЭљ^\™SШљ™XЭH™XYњЫЫЉ]њ™\ЫЫ™J\™ЬЛњ™\Ф›ЫЭ\™ЬЛ™љ^\™JJNВ€]љY[ЩHHќZ[]љY[ЩQњ›ЫQљ^\™Jљ^\™SШљ™XЭ
NВ€H[ЩHY€
\™ЬЛ›[ЩHOOH	Ь™\ЙКHВ€]љY[ЩHHќZ[]љY[ЩQњ›ЫT™\К]њ™\ЫЫ™J\™ЬЛњ™\Ф›ЫЭ
KЫXЮJNВ€H[ЩHВ€›ЭИ™]И\њ›ЬЉ[њЭ\ЬќY[ЩH	ЙШ\™ЬЛ›[Щ_IЛ€\ЩH™\ИЬ€љ^\™K
NВ€B‚€ЫЫњЭ]љY[ЩQ]Z[ИHЯNВ€ЫЫњЭ]љY[ЩP›ШЪЩ\њИHЧNВ€ЫЫњЭ]љY[ЩUШ\›љ[™ЬИHЧNВ€›Ь€
ЫЫњЭЫ[YKЬXЧHЩ€Шљ™XЭ™[ќљY\КЫXЮKњ™\]Z\™YЩ]љY[ЩWШЪZ[€ЯJJHВ€ЫЫњЭ][HH]љY[ЩVЫ[YWNВ€]љY[ЩQ]Z[ЦЫ[YWHHВ€›Э[™€][OЛ™›Э[™[ЩK€™[]€][OЛњ™[]ќ[€ЪXЪЩY€][OЛЪXЪЩYЧK€ЫЫќ[ќЬЪLЌMЋ€][OЛ›Шљ™XЭИЪLЌM“Шљ™XЭ
][K›Шљ™XЭ
H€ќ[€NВ€ЫЫњЭ[Y][Ы€H[Y]T™\]Z\™YљY[К[YK][OЛ›Шљ™XЭЬXКNВ€]љY[ЩP›ШЪЩ\њЛњ\Ъ
‹‹ќ[Y][Ы‹›ШЪЩ\њКNВ€]љY[ЩUШ\›љ[™ЬЛњ\Ъ
‹‹ќ[Y][Ы‹ќШ\›љ[™ЬКNВ€B€[›ШЪЩ\њЛњ\Ъ
‹‹™]љY[ЩP›ШЪЩ\њКNВ€[Ш\›љ[™ЬЛњ\Ъ
‹‹™]љY[ЩUШ\›љ[™ЬКNВ€ЭYЩ\Лњ\Ъ
ЭYЩJ	Щ]љY[ЩWШЪZ[‰Л]љY[ЩP›ШЪЩ\њЛ›[™ЭOOHИ	Ь\ЬЙИ€	Ш›ШЪЩY	Л]љY[ЩQ]Z[Л]љY[ЩP›ШЪЩ\њЛ]љY[ЩUШ\›љ[™ЬКJNВ‚€ЫЫњЭћTќ[”[€HВ€В€[YN€	ШњљYЩWЪ[ќZЩIЛ€]Z[О€В€Ь\][ЫЋ€	Ь™XYЭ[Y]HњљYЩH™\]Y\Э[ќ™[ЬHЫ›IЛ€]]][ЫЋ€[ЩK€›ЩXЭ[Ы—Ш]]ЫX][ЫЋ€[ЩB€B€K€В€[YN€	ЬЫЭ\ЩWЩШ]WЩ]XЭЬ‰Л€]Z[О€В€Ь\][ЫЋ€	ЬЪ[][]HЩ\ЬЪ[Ы‹Y[™Y™XY[™\ЬИШ]H]XЭ[Ы€њ›ЫHЭ\YYXЪЩ]Щљ^\™IЛ€]]][ЫЋ€[ЩK€™]ЫЬљЧЩ™]Ъ€[ЩB€B€K€В€[YN€	ЬЫЭ\ЩWЩ™]ЪЬ[‰Л€]Z[О€В€Ь\][ЫЋ€	ШЫЫњЭќXЭЬ[‘ЊKС\ЭЊKС’PKЬX›XИ[[€Ъ]Э]^XЭ][™И™]ЫЬљИШ[ЙЛ€]]][ЫЋ€[ЩK€™]ЫЬљЧЩ™]Ъ€[ЩB€B€K€В€[YN€	Щ]WЭ[Y]Ь‰Л€]Z[О€В€Ь\][ЫЋ€	Э[Y]H^XЭYШЪ[XH[™[›ЫX[HЪXЪЬИYШZ[њЭћK\ќ[€XЪЩ]Y]Y]HЫ›IЛ€ЪXЪЬО€ЙЪYЙЛ	Э[Y\Э[\ЙЛ	Ы\ШЫЭ[ќЙЛ	Щ\XШ]\ЙЛ	Ы]WЩ]IЛ	ШЫЫ™›XЭ[™ЧЩ]IЛ	ЫX[ќX[Ь™]љY]ЧЬ™\]Z\™Y	ЧK€]]][ЫЋ€[ЩB€B€K€В€[YN€	ЫX[љY™\ЭЭЬљ]\—Ь[‰Л€]Z[О€В€Ь\][ЫЋ€	Ь[€]\ЭЫX[љY™\ЭљњЫЫ‹]WЬ™XY[™\ЬЛљњЫЫ‹ЫЫXљ[™YЬЫЭ\ЩWЫX[љY™\ЭљњЫЫ€Ьљ]\ИЫ›IЛ€]]][ЫЋ€[ЩK€[›™YШ\ќYXЭО€ЙЫ]\ЭЫX[љY™\ЭљњЫЫ‰Л	Щ]WЬ™XY[™\ЬЛљњЫЫ‰Л	ШЫЫXљ[™YЬЫЭ\ЩWЫX[љY™\ЭљњЫЫ‰ЧB€B€K€В€[YN€	Щ›Ь™XШ\ЭШќ[™WЫYЩ\—Ь[‰Л€]Z[О€В€Ь\][ЫЋ€	Ь[€›Ь™XШ\Эќ[™HYЩ\€Ы\ЪЭЫ›IЛ€]]][ЫЋ€[ЩK€ЭX›WЫЩЪXЧШЪ[™ЩN€[ЩK€[Щ[Ь›Ы[Э[ЫЋ€[ЩB€B€K€В€[YN€	ЬШ[™›ЮЭЫЬљШ›ЫЪЧЪЬWЬ[‰Л€]Z[О€В€Ь\][ЫЋ€	Ь[€Ш[™›ЮЫЬљШ›ЫЪЛТФK\™XYH™Yњ™\ЪЫ›IЛ€]]][ЫЋ€[ЩK€Ш[›ЫљXШ[ЭЫЬљШ›ЫЪЧЭЬљ]N€[ЩK€ЭX›WЩ[™Ъ[™WЭЭXЪ€[ЩB€B€K€В€[YN€	ЬXЩWЩ[ќ\ЮWЬ™XY[™\ЬЧЬ[‰Л€]Z[О€В€Ь\][ЫЋ€	Ь[€™XY[™\ЬИ^[ШY[™Щ™€QИЫ›IЛ€]]][ЫЋ€[ЩK€›Ь™XШ\ЭЬ™Yњ™\Ъ€[ЩK€[ќ\ЮWЬ™Yњ™\Ъ€[ЩB€B€K€В€[YN€	Ы›ЭYљXШ][Ы—Ь[‰Л€]Z[О€В€Ь\][ЫЋ€	Ь[€X]\љX[XЪ[™ЩH›ЭYљXШ][Ы€[YЪXљ[]HЫ›IЛ€]]][ЫЋ€[ЩK€›ЭYљXШ][Ы—ЬЩ[™€[ЩB€B€B€NВ‚€›Ь€
ЫЫњЭИЩ€ћTќ[”[ЉHВ€ЫЫњЭ›ШЪЩYћTЫXЮHH[›ШЪЩ\њЛ›[™Э€В€ЭYЩ\Лњ\Ъ
ЭYЩJЛ›[YK›ШЪЩYћTЫXЮHИ	Ш›ШЪЩY	И€	Ь\ЬЙЛЛ™]Z[Л›ШЪЩYћTЫXЮHИЙЭ\Э™X[HЫXЮKЩ]љY[ЩHЪZ[€›Э™XYIЧH€ЧJJNВ€B‚€ЫЫњЭЭ]\ИH[›ШЪЩ\њЛ›[™ЭOOHИ	Ф‘PQIИ€	Р“РТСQ	ОВ€™]\›€В€™\њЪ[ЫЋ€‘T”ТSУ‹€ќ[—ЪY€	Х‘T”ТSУџKIЬЭ\ќY]Лњ™\XЩJЦО‹—KЩЛ	ЛIК_X€Э\ќYЭ]О€Э\ќY]Л€љ[љ\ЪYЭ]О€™]И]J
KќТTУФЭљ[™К
K€[ЩN€\™ЬЛ›[ЩK€Э]\Л€\њЬЩN€ЫXЮKњ\њЬЩK€ЪYWЩY™™XЭО€В€™]ЫЬљЧЩ™]Ъ€[ЩK€›ЩXЭ[Ы—Ш]]ЫX][ЫЋ€[ЩK€ЫЬљШ›ЫЪЧЭЬљ]N€[ЩK€YЩ\—ЭЬљ]N€[ЩK€XЩWЬ™YXЭ[ЫњЧЬ™Yњ™\Ъ€[ЩK€[ќ\ЮWЬ™YXЭ[ЫњЧЬ™Yњ™\Ъ€[ЩK€›ЭYљXШ][Ы—ЬЩ[™€[ЩK€[Щ[Ь›Ы[Э[ЫЋ€[ЩK€›ЭXЭYЬ]ЭЭXЪ€›ЭXЭYЭXЪ\Л›[™Э€€™ZX\њШ[Ш\ќYXЭЭЬљ][Ћ€›ЫЫX[Љ\™ЬЛ›Э]]	‰€Э]][‹ќЬљ]T\›Z]Y
B€K€›ЭXЭYЬ]ЭЭXЪ\О€›ЭXЭYЭXЪ\Л€[›™YЭЬљ]\О€[›™YЬљ]\Л€Э]]ЭЬљ]WЬ\›Z]Y€Э]][‹ќЬљ]T\›Z]Y€Э]]ЬЫXЮWШ›ШЪЩ\њО€Э]][‹›ШЪЩ\њИЧK€›ШЪЩ\њО€Л‹‹›™]ИЩ]
[›ШЪЩ\њКWK€Ш\›љ[™ЬО€Л‹‹›™]ИЩ]
[Ш\›љ[™ЬКWK€ЭYЩ\Л€™^Ь™XЫЫ[Y[™YЬЭ\€Э]\ИOOH	Ф‘PQIВ€И	Ф›ШЩYYИЊМРИ‹[Ы›HШ[™›Ю[™Щ™€љ[™\ЋИЭ[›И]™H™]ЪЭЫЬљШ›ЫЪИЬљ]KЫYЩ\€Ьљ]KЫ›ЭYљXШ][Ы‹Ы[Щ[›Ы[Э[Ы‹‰В€€	Ф™\ЫЫ™HZ\ЬЪ[™ИЬ€›Ы‹\™XYHЊМ“‹ЭЊМРH]љY[ЩKXЪZ[€XЪЩ]Л™\ќ[€ЊМР€[€™\И[ЩK[™ЩY\[ШY™]H›YЬИ[ЩK‰Л€ЫЭ™\›[ЩN€В€ЭX›WЩ[™Ъ[™WЬ›ЭXЭY€ќYK€ЭX›WЭњЧЩ^\љ[Y[ќ[ЬЩ\\]Y€ќYK€›ЧШXШЭ\XЮWШЫZ[N€ќYK€›ЧМЊЌ—ЩњЧШ\ЬЭ[\[ЫЋ€ќYK€›ЧШ]]ЫX][Ы—ШЪ[™ЩN€ќYK€—ЫЫ›N€ќYB€B€NВџB‚™ќ[Э[Ы€XZ[Љ
HВ€ЫЫњЭ\™ЬИH\њЩP\™ЬК›ШЩ\ЬЛ\™ЭЉNВ€ЫЫњЭ™\Ф›ЫЭH]њ™\ЫЫ™J\™ЬЛњ™\Ф›ЫЭ
NВ€ЫЫњЭЫXЮT]H]њ™\ЫЫ™J™\Ф›ЫЭ\™ЬЛњЫXЮJNВ€ЫЫњЭЫXЮHH™XYњЫЫЉЫXЮT]
NВ€ЫЫњЭЭ]]Hќ[”™ZX\њШ[
\™ЬЛЫXЮJNВ€ЫЫњЭ™[™\™YH”УУ‹њЭљ[™ЪYћJЭ]]ќ[ЉNВ€Y€
\™ЬЛ›Э]]	‰€Э]]›Э]]ЭЬљ]WЬ\›Z]Y
HВ€ЫЫњЭXњУЭ]]H]њ™\ЫЫ™J™\Ф›ЫЭ\™ЬЛ›Э]]
NВ€[њЭ\™Q\‘›Ь‘љ[JXњУЭ]]
NВ€њЛќЬљ]Qљ[TЮ[КXњУЭ]]	Ь™[™\™YW€	Э]Ћ	КNВ€B€ЫЫњЫЫK›ЩК™[™\™Y
NВ€›ШЩ\ЬЛ™^]
Э]]њЭ]\ИOOH	Ф‘PQIИИ€ЉNВџB‚ќћHВ€XZ[Љ
NВџHШ]Ъ
\њ›ЬЉHВ€ЫЫњЭZ[\™HHВ€™\њЪ[ЫЋ€‘T”ТSУ‹€Э]\О€	СT”“Ф‰Л€\њ›ЬЋ€Эљ[™К\њ›ЬЏЛњЭXЪИ\њ›ЬЏЛ›Y\ЬШYЩH\њ›ЬЉK€ЪYWЩY™™XЭО€В€™]ЫЬљЧЩ™]Ъ€[ЩK€›ЩXЭ[Ы—Ш]]ЫX][ЫЋ€[ЩK€ЫЬљШ›ЫЪЧЭЬљ]N€[ЩK€YЩ\—ЭЬљ]N€[ЩK€XЩWЬ™YXЭ[ЫњЧЬ™Yњ™\Ъ€[ЩK€[ќ\ЮWЬ™YXЭ[ЫњЧЬ™Yњ™\Ъ€[ЩK€›ЭYљXШ][Ы—ЬЩ[™€[ЩK€[Щ[Ь›Ы[Э[ЫЋ€[ЩB€B€NВ€ЫЫњЫЫK™\њ›ЬЉ”УУ‹њЭљ[™ЪYћJZ[\™Kќ[ЉJNВ€›ШЩ\ЬЛ™^]
JNВџB