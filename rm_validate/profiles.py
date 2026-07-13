"""Profile presets: ``static`` / ``app`` / ``platform``.

Capabilities are the truth; profiles are shortcuts. A profile is just a preset
set of capability defaults that a repo's ``rm-policy.yaml`` overrides via the
``capabilities:`` map. ``platform`` extends ``app`` extends ``static``.

Adding a capability here is a deliberate, reviewable act — a capability is born
only when a check requires it.
"""

from __future__ import annotations

# The full capability vocabulary. Every capability defaults to ``False``; a
# profile flips on the ones it implies. Keeping the vocabulary in one place
# means an unknown capability in a policy file is a config error, not a typo
# that silently does nothing.
ALL_CAPABILITIES: tuple[str, ...] = (
    "has_database",
    "has_auth",
    "multi_tenant",
    "handles_payments",
    "exposes_public_api",
    "emits_webhooks",
    "exposes_mcp",
    "has_agents",
)

# Preset capability sets, before ``extends`` resolution. ``platform`` and
# ``app`` are expressed relative to what they extend so the intent stays legible.
_PRESETS: dict[str, dict[str, object]] = {
    "static": {
        "extends": None,
        "capabilities": {cap: False for cap in ALL_CAPABILITIES},
    },
    "app": {
        "extends": "static",
        "capabilities": {
            "has_database": True,
            "has_auth": True,
        },
    },
    "platform": {
        "extends": "app",
        "capabilities": {
            "multi_tenant": True,
            "exposes_public_api": True,
            "emits_webhooks": True,
            "exposes_mcp": True,
            "has_agents": True,
        },
    },
}

VALID_PROFILES: tuple[str, ...] = tuple(_PRESETS.keys())


def resolve_profile(name: str) -> dict[str, bool]:
    """Return the fully-resolved capability map for a profile name.

    Walks the ``extends`` chain from the base up, layering each preset's
    capability flags on top. Raises :class:`ValueError` for an unknown profile.
    """
    if name not in _PRESETS:
        raise ValueError(
            f"unknown profile '{name}'; valid profiles: {', '.join(VALID_PROFILES)}"
        )

    # Build the chain base-first so nearer presets win.
    chain: list[str] = []
    current: str | None = name
    while current is not None:
        if current in chain:
            raise ValueError(f"circular profile extends chain at '{current}'")
        chain.append(current)
        current = _PRESETS[current]["extends"]  # type: ignore[assignment]
    chain.reverse()

    caps: dict[str, bool] = {cap: False for cap in ALL_CAPABILITIES}
    for profile_name in chain:
        preset_caps = _PRESETS[profile_name]["capabilities"]
        assert isinstance(preset_caps, dict)
        for cap, value in preset_caps.items():
            caps[cap] = bool(value)
    return caps
