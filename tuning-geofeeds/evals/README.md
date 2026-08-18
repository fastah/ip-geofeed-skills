# Evaluation workflow

`evals.json` is the canonical prompt and assertion inventory. It intentionally
has no v1, without-skill, or comparative bakeoff configuration. Mechanical
assertions are graded by `scripts/evaluate.py`; agent behavior, activation,
execution traces, and visual usefulness remain explicit agent/human review
items rather than fabricated passes.

Use a sibling workspace that is never part of the distribution:

```text
tuning-geofeeds-workspace/
└── iteration-1/
    ├── valid-mixed-report/
    │   └── with_skill/
    │       ├── outputs/
    │       ├── grading.json
    │       └── timing.json
    ├── ...
    ├── feedback.json
    └── benchmark.json
```

Run deterministic grading from any working directory:

```bash
python3.14 /absolute/skill/root/scripts/evaluate.py \
  --workspace /absolute/path/to/tuning-geofeeds-workspace \
  --iteration 1
```

The evaluator refuses an existing iteration directory. Copy
`human-feedback.template.json` to `iteration-N/feedback.json` for dashboard
review. Copy `timing.template.json` only when a host-runner does not generate
timing itself; leave unavailable values as `null`, never zero.
Successful evaluator and fixture-verifier results use stdout; expected input,
filesystem, or child-command diagnostics use stderr and exit status 2. An
unexpected programming defect is intentionally not converted into a normal
operational error.

For clean-context agent runs, give the agent only the installed skill path, one
prompt and its listed fixture files, and a fresh `with_skill/outputs/`
directory. Save the execution trace beside `grading.json`, run the evaluator's
mechanical checks, then grade remaining assertions with concrete quoted or file
evidence. Aggregate pass/fail counts without a comparative delta.

`trigger-queries.json` contains fixed train/validation positive and near-miss
prompts. Run each in a clean client context and record whether `SKILL.md` was
loaded. Optimize descriptions from train failures only; use validation results
to select an iteration rather than overfitting wording.

## Public sample fixture

`files/public-cloudflare-starlink-sample.csv` is a deterministic 200-row
evaluation sample from the public Cloudflare and Starlink geofeed endpoints.
Its adjacent manifest records source-response provenance, raw source digests,
rejected rows, the fixed hash-selection method, selected source line numbers,
and per-row hashes without duplicating prefixes. The balanced source/country
allocation is deliberately compact and is not statistically representative.

Endpoint availability is not independent validation or evidence of license,
ownership, endorsement, or redistribution rights. Review the source terms
before redistributing the fixture outside this repository. Full source
snapshots are not committed. If the exact snapshots are available locally,
verify complete reconstruction with:

```bash
python3.14 scripts/verify_public_sample.py verify \
  --fixture evals/files/public-cloudflare-starlink-sample.csv \
  --manifest evals/files/public-cloudflare-starlink-sample.manifest.json \
  --snapshot-dir /path/to/source-snapshots
```
