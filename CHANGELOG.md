# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — rm-policy-validator inicial (público, Apache-2.0)

### Added
- CLI `init` / `check` / `explain`; capability inference with evidence; profiles
  static/app/platform (extends + overrides).
- Sub-schema `layering_patterns`: each target repo declares its layer globs
  explicitly; config-incomplete lock when a layering fitness function is enabled
  without its declared keys.
- Non-toggleable universal base; locks: config-incomplete (ADR + layering),
  capability-mismatch, and a CI self-check step.
- Baseline + ratchet for adopting the validator on legacy repos; graceful
  degradation with no config.
- Checks: secrets, dependency-audit hook, changelog, file limits, prompt gate,
  fitness (pure engines, forbidden deps, layering, circular deps), db.
- Multi-language analyzers (Ports & Adapters): Python via `ast`, TS/JS via
  regex. Containment checks (layering) run on Python and TS/JS; the import-graph
  check (`no_circular_dependencies`) is Python-only. Invariant: a check that
  cannot analyze the files its globs matched fails as `config incompleta` (even
  in `warning` mode) — never a false-green empty pass. TS cycle detection is
  deferred to v0.2.0, not faked. Adding a language is a new adapter, not a check
  change. `graph_scope` scopes the cycle check; `explain` reports supported
  languages and files analyzed vs. matched.
- rm-tooling adopts the RM Method on itself: its own `rm-policy.yaml` (static
  profile) + `ADR/0001-perfil-static.md`; the self-check runs for real in CI.
