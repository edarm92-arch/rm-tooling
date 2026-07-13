# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.1] — Cierre del bypass de inferencia (fix de seguridad del harness)

### Security
- `inference.exclude` deja de existir como clave pública: permitía silenciar el
  candado de capability-mismatch desde el mismo `rm-policy.yaml` que el candado
  debe vigilar (`exclude: ["**"]` convertía un fail de integridad en exit 0).
  Un `rm-policy.yaml` con la clave `inference:` ahora falla al cargar.
- La inferencia dejó de honrar `modularity.exclude_globs`: excluir `migrations/`
  ya no oculta evidencia del candado (la superficie de inferencia es fija).
- Un glob de exclusión total (`**`, `*`, `.`) en cualquier lista de exclusión es
  ahora error de config.
- Toda exclusión declarada a mano se reporta (`WARNING inference_exclusion`); las
  estructurales (node_modules, .venv, dist) siguen silenciosas.
- `dependency_audit_hook` detecta steps de audit neutralizados (`|| true`,
  `continue-on-error: true`, `|| exit 0`): un scanner que no puede fallar no
  cuenta como scanner.
- También se removió el override `inference_rules` del YAML (mismo vector: podía
  neutralizar los patterns de detección desde el policy). Los patterns se mejoran
  upstream, no se sobreescriben localmente.

### Fixed
- El auto-scan de rm-tooling (un scanner que se detectaba a sí mismo por sus
  propios patterns) se resuelve con una deny-list interna del paquete, versionada
  y aplicada solo a rm-tooling (paquete `rm_validate/` presente + `project:
  rm-tooling`), no con configuración expuesta al consumidor.
- CI propio: `pip-audit` corre sin `|| true`.

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
