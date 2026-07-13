# ADR 0001 — rm-tooling profile: static

- **Status:** Accepted
- **Date:** 2026-07-13
- **Owner:** Director

## Context

`rm-tooling` ships the `rm-validate` CLI. It reads files and prints a report. It
has no persistent state, no authentication, no network surfaces, no
multi-tenancy, and does not process payments or emit events. Its only external
dependency is `PyYAML`.

## Decision

`rm-tooling` adopts the **`static`** profile with an empty `capabilities` map.

The `static` profile covers exactly what this repo is: the non-negotiable
universal base (secrets scan, dependency-audit hook, CHANGELOG), file-size
limits, the prompt gate, and the layer-agnostic `no_circular_dependencies`
fitness function. No database, auth, multi-tenant, API, webhook, MCP or agent
capability applies, so none is declared.

No layer-based fitness function is enabled, so no `layering_patterns` are
declared — enabling one without its globs would (correctly) fail the layering
config lock.

## Consequences

- `rm-validate check .` runs in CI against this very policy. If any lock (ADR,
  layering config, capability mismatch) regressed, this repo's own CI would go
  red — the self-check is real, not decorative.
- If `rm-tooling` ever grows a real capability (say, an MCP surface), this ADR is
  superseded by a new one that raises the profile and declares the capability;
  the code is never allowed to redefine the profile silently.
