# Quillbook simulation — Team 08

Current inputs: **v7-mixed-network**,24representative profiles (8owners,8in-house bookkeepers,8partner accountants). Model: **calendar-grounded-v3**, Gemini `gemini-3.7-flash`, temperature1, actual seeds42/43. These are synthetic scenarios, not measured customer research. Methods and limitations are in `TEAM_DOC.md`; final figures are in `CLIENT_MEMO.md` and each run's `metrics.json`.

## Install and authenticate

Use Python3.11 or later. From the project root (or the extracted submission's `code/` directory):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create a local `.env` containing `TALP_KEY=your_supplied_vertex_key`. Credentials are intentionally excluded from the submission. Do not publish or print the key.

## Reproduce the five runs

In the working repository, the exact downloaded plan is `decisions/locked_plan.json`. In the extracted submission, it is `code/data/locked_plan.json`; run these commands from `code/`:

```bash
.venv/bin/python engine.py validate --locked-plan data/locked_plan.json
.venv/bin/python engine.py suite --locked-plan data/locked_plan.json --events data/official_events.json --parallel-runs 3 --concurrency 24 --output ../reproduced
.venv/bin/python audit_engine.py --run ../reproduced/runs/plan_1
```

For the working repository, substitute `decisions/locked_plan.json` for `data/locked_plan.json` and choose an output under `output/`. Run all24profiles; subsets are disabled. Repeating an identical command resumes using matching cached real responses. A changed prompt, profile, network, event, model or seed requires affected calls again. Changed manifests require a fresh output directory. Never splice a new network into saved weekly histories.

The conditions are `plan_1` and `plan_2` (same exact locked plan, seeds42/43), `nodecision_1` and `nodecision_2` (no decisions, seeds42/43), and `plan_nosurprises` (same plan, seed42, surprise events and updates removed). The known January switch remains in all five. Each released surprise is available from its original week, never at the start. The week9 reminder is the existing known crisis, not an added surprise. Seeds do not guarantee deterministic provider output; unchanged cached calls preserve matched prefixes.

## Inspect results and interview

Each `runs/NAME/` contains `run.json`, identical `personas.jsonl`, full `calls.jsonl`,240weekly rows in `weekly.jsonl`, `metrics.json`, and supporting manifests, states, interactions, support records and audits. `plan_1` and `nodecision_1` each contain384original questionnaire scores in `probe.jsonl`. Raw negative-item scores are not reversed. Every weekly row references the real model call that produced it. Repair attempts remain in the raw log.

From the extracted `code/` directory:

```bash
.venv/bin/python interview.py --run ../runs/plan_1 --persona A08 "Why did you make your final recommendation?"
.venv/bin/python project.py ui --port 8765
```

The interview uses the persona's saved final history and writes a separate interview log; it does not alter simulation results. The loopback dashboard is optional. All run, audit and interview functions remain terminal accessible. A reproduction output under `code/output/` is automatically discoverable by the dashboard.

## Metrics and limits

Renewal is the fraction of4000original due plans renewed. Churn is the maximum rolling four-week departure percentage, a monthly proxy. Partner satisfaction is weighted final minus baseline on a1–5scale. Support is maximum daily weighted response hours excluding January4–5, using an uncalibrated baseline-anchored workload proxy. Business and accountant populations are aggregated separately. Portfolio allocations sum exactly without adding managed businesses again.

Network relationships, operational exposures,50/50internal splits in O01/A08, and support/action-effect parameters are modeling assumptions. LLMs choose reactions, advice, statuses, cohort shares and renewal decisions; code handles timing, exposure, routing, validation and metric aggregation. No rule forces board targets to pass. Both locked packages total$1.38M; their exact messages and effective weeks are preserved. More satisfied accountants do not automatically move their clients.

## Validate and package

In the working repository:

```bash
.venv/bin/python submission.py --suite output/final_v7_week9_20261024_1720 --locked-plan decisions/locked_plan.json --output team-08_submission.zip
python3 yeni-case-5-sirket/check.py team-08_submission.zip
```

Packaging requires five complete consistent runs, exact locked-plan equality, local audits and the unchanged official checker. It copies code and inputs by allowlist, excludes environments/credentials/caches/stale experiments, scans for credential patterns and checks the ZIP. It does not upload. A checker pass establishes format/integrity checks, not calibrated behavioral accuracy. Historical outputs remain backups outside the archive.
