# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (latest) | ✅ |
| 0.1.0 | ❌ — has a known harness-lock bypass; upgrade to **0.1.1+** |

## Reporting a vulnerability

Please report privately via GitHub's **"Report a vulnerability"** button on the
repository's [Security tab](https://github.com/edarm92-arch/rm-tooling/security/advisories/new)
— **do not open a public issue** for a suspected vulnerability.

We aim to acknowledge a report within a few days and to release a fix (and a
GitHub Security Advisory) once it is confirmed.

## What counts as a security issue here

rm-validate is a policy **harness**: its whole point is that its rules cannot be
disabled by the code they govern. So, beyond ordinary code vulnerabilities, we
treat as a **security issue** any way for a *target repo* to disable or bypass an
integrity lock from its own configuration — for example:

- silencing the capability-mismatch lock (declaring a capability `false` while
  the code clearly has it),
- hiding evidence from capability inference via configuration,
- making a check report success (`exit 0`) without actually running,
- neutralizing a check that is meant to be able to fail.

`v0.1.1` fixed exactly this class of bug (the `inference.exclude` bypass). If you
find another way to switch off or blind an integrity lock from a policy file,
that is in scope — please report it privately.
