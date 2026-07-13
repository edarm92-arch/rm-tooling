# rm-validate

**A generic policy validator for the RM Method.** It reads a repo's own
`rm-policy.yaml`, runs the checks that its declared capabilities gate plus a
non-negotiable universal base, and reports `file · rule · value vs. limit ·
severity` with an exit code driven by the policy's enforcement mode.

The validator is **generic by design**: it assumes nothing about the layout of a
target repo. Every rule, path, threshold and layer pattern comes from that
repo's `rm-policy.yaml`. Where a check needs to know "what is what" in the code
(e.g. which folder is the domain layer), that mapping is **declared explicitly**
in the policy — the validator never guesses, and never silently skips.

> **Disclaimer:** rm-validate is tooling for the RM Method, provided **as-is,
> without warranties**. It runs cheap, high-value checks; it is not a full
> policy engine, type checker, or security scanner. Licensed under Apache-2.0.

---

## Install

```bash
# from PyPI (once published)
pip install rm-validate

# or straight from Git
pip install "git+https://github.com/rm-tooling/rm-validate"

# or run without installing
uvx --from "git+https://github.com/rm-tooling/rm-validate" rm-validate check .
```

Only runtime dependency: **PyYAML**. Python 3.11+.

## Quickstart

```bash
# 1. Infer capabilities from the code and write a commented policy (run once).
rm-validate init .

# 2. Confirm the suggested profile with an ADR (e.g. ADR/0001-perfil-app.md).

# 3. Validate — locally and in CI.
rm-validate check .

# Trace any check: what activates it, what parametrizes it, which languages.
rm-validate explain engines_must_be_pure .
```

- **`init`** — infers capabilities from the real code (with evidence), suggests
  a profile (`static` / `app` / `platform`), and writes an evidence-commented
  `rm-policy.yaml`. It configures; it does not validate.
- **`check`** — runs the universal base + capability-gated + enabled fitness
  checks. Exit code follows `enforcement.mode`.
- **`explain <check> [path]`** — traceability: activation, parametrizing policy
  key, required `layering_patterns` keys, supported languages, and (given a
  path) *files analyzed vs. matched*.

If a repo has **no** `rm-policy.yaml`, `check` does not fail or grade it — it
degrades gracefully (exit 0) and points you to `init`. The validator is an
advisor until rules are declared, then a judge.

## Capabilities are the truth; profiles are shortcuts

A rule applies **if and only if** the system has the thing that rule protects.
Capabilities are declared in the policy and re-inferred on every `check`;
profiles are just presets of capability defaults (`platform` extends `app`
extends `static`), overridable per capability.

| Capability | Gated checks |
|---|---|
| _(universal base — always on)_ | `secrets_scan`, `changelog`, `dependency_audit_hook`, `file_limits`, `prompt_gate` |
| `has_database` | `db_migrations_present` |
| _fitness (opt-in via `fitness_functions`)_ | `no_circular_dependencies`, `domain_must_not_import_infrastructure`, `ui_must_not_access_db_directly`, `engines_must_be_pure`, `mutations_server_side_only` |
| _config-driven_ | `forbidden_deps` (when `forbidden_imports` is declared) |

The universal base is **not toggleable**. Adding a new check means mapping it to
a capability or the universal base — a check that maps to no existing capability
proposes a new capability in review, never invents one silently.

## Layering patterns (declared, never inferred)

Layer-based fitness functions need to know which globs are which layer. That
mapping is **always declared by hand** in `layering_patterns` — inferring folder
conventions is a high-risk silent false negative, so the method forbids it. If a
layering fitness function is enabled without the keys it needs, `check` fails
with **`config incompleta: falta layering_patterns.<key>`** — even in `warning`
mode (it is config integrity, not code severity).

| `fitness_function` | Requires in `layering_patterns` |
|---|---|
| `domain_must_not_import_infrastructure` | `domain`, `infrastructure` |
| `ui_must_not_access_db_directly` | `ui`, `db_access` |
| `engines_must_be_pure` | `engines` |
| `mutations_server_side_only` | `ui` (or `server_mutations`) |
| `no_circular_dependencies` | _none — import-graph, layer-agnostic_ |

## Multi-language support

Import-based checks route through **language analyzers** (Ports & Adapters).
Supporting a new language means adding an adapter under `rm_validate/analyzers/`
— the checks never change.

**The invariant:** a check that cannot analyze the files its globs matched
**never reports success**. "Could not analyze" is indistinguishable from "no
violations" in an `exit 0`, and that indistinguishability *is* the false
confidence. So an unsupported language **fails** as `config incompleta` (even in
`warning` mode). A check that "does not apply" must be set `false` in the policy
— an honest human act — never resolved to green by emptiness.

| Check | Languages (v0.1.0) | Mechanism |
|---|---|---|
| `engines_must_be_pure` | Python | `ast` (stdlib, precise) |
| `domain_must_not_import_infrastructure` | Python · TS/JS | `ast` / regex |
| `ui_must_not_access_db_directly` | Python · TS/JS | `ast` / regex |
| `mutations_server_side_only` | Python · TS/JS | `ast` / regex |
| `no_circular_dependencies` | **Python only** | `ast` + graph |

Cycle detection needs a precise, complete graph; TypeScript module resolution
(path aliases, barrels, `tsconfig.paths`) is genuinely hard, so TS graph support
is **deferred (v0.2.0), not faked**. Pointing `no_circular_dependencies` at TS
globs fails honestly. The `ImportAnalyzer` port allows future adapters to
delegate to mature tools (`madge`, `dependency-cruiser`, `import-linter`)
without breaking the "only external dep: PyYAML" rule; if an external analyzer
is unavailable the check fails honestly rather than pretending.

## The four anti-theatre locks

All four are **config-integrity** failures — they block even in `warning` mode
(only *severity* violations are downgraded to warnings), and they are not
optional:

1. **Profile ADR** — `check` fails if `require_profile_adr` is on and no ADR
   matches `adr_glob`. The lazy shortcut of declaring a profile without an owned
   decision does not pass.
2. **Layering config** — an enabled layering fitness function without its
   declared globs fails (see above).
3. **Capability mismatch** — capabilities are re-inferred every run. Asymmetric:
   *under-declaring* (`has_database: false` with `migrations/` present) **fails**
   (it silences a rule that should apply); *over-declaring* (`exposes_mcp: true`
   with no MCP code) is only a **warning** (it just adds the repo's own
   overhead).
4. **CI self-check** — `check` is a required CI step, not discipline. rm-validate
   runs `check .` on itself in its own CI.

## Baseline + ratchet (legacy adoption)

Enable `enforcement.baseline_ratchet` to adopt the validator on an existing
codebase. The first run inventories current violations into
`.rm/baseline.json` as accepted debt; later runs surface (and, in `blocking`
mode, fail on) only *new* violations. A resolved violation leaves the baseline —
the file only ever decreases. Config-integrity findings are never baselined.

## Enforcement modes

- `warning` (default) — reports everything, exit 0 for severity findings. Start
  here.
- `blocking` — a severity (error) finding fails the merge (exit 1). The Director
  flips this from the policy once things stabilize.

Config-integrity findings (the four locks, unsupported languages) fail in
**both** modes.

## `rm-policy.yaml` reference (essentials)

```yaml
extends: app                    # static | app | platform (preset of capabilities)
capabilities:                   # per-capability overrides (the truth)
  has_database: true
enforcement:
  mode: warning                 # warning | blocking
  require_profile_adr: true
  adr_glob: "ADR/*perfil*.md"
  capability_mismatch_fails: true
  baseline_ratchet: { enabled: false, baseline_file: ".rm/baseline.json", block_only_new_violations: true }
modularity:
  code_file_lines: { soft: 300, hard: 500 }
  context_file_lines: { hard: 500 }
fitness_functions:
  no_circular_dependencies: true
layering_patterns:              # declared globs, never inferred
  domain: ["app/domain/**"]
  infrastructure: ["app/adapters/**"]
graph_scope: ["**/*.py"]        # scope for no_circular_dependencies (Python only)
prompt_gate:
  required_sections: [objetivo, criterios_de_aceptacion, rollback]
  paths: ["prompts/**/*.md"]
security:
  no_secrets_in_repo: true
  dependency_scan_in_ci: true
forbidden_imports:              # optional generic import-edge bans
  - name: "adapters must not import domain internals"
    src: ["app/adapters/**"]
    dst: ["app/domain/_internal/**"]
inference:
  exclude: []                   # files to skip during capability inference
```

Full, annotated examples for each profile live in
[`examples/`](examples/) (`static`, `app`, `platform`).

## Extending: add a language

1. Add an adapter class in `rm_validate/analyzers/` implementing `ImportAnalyzer`
   (`LANGUAGES`, `supports_graph`, `extract_imports`, `prepare`, `resolve`).
2. Register it in `rm_validate/analyzers/registry.py`.

No check changes. If your adapter cannot back a precise graph, set
`supports_graph = False` — the coverage gate will keep it out of cycle detection
honestly.

## Self-adoption

rm-validate applies the RM Method to itself: it ships its own
[`rm-policy.yaml`](rm-policy.yaml) (profile `static`, no capabilities) and
[`ADR/0001-perfil-static.md`](ADR/0001-perfil-static.md). Its CI runs
`rm-validate check .` for real — if any lock regressed on this repo, its own CI
would go red, exactly like any consumer.

## Development

```bash
pip install -e ".[dev]"
ruff check rm_validate tests
mypy rm_validate
pytest -q
python -m rm_validate check .   # self-check
```
