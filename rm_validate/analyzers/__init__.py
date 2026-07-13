"""Language analyzers (Ports & Adapters).

Supporting a new language means adding an adapter here, never editing the
checks. Each adapter declares the extensions it handles and whether it can back
a full import graph (needed by ``no_circular_dependencies``). The invariant the
whole package enforces: a check that cannot analyze the files its globs matched
never reports success — unsupported language fails as "config incompleta".
"""
