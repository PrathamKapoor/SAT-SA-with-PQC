"""Security policies module.

Phase 1 keeps the declarative policy-engine extension point here. The
supervisor's governance rules (observation -> evidence -> evaluation ->
policy validation -> approved action -> execution -> verification) live in
``qsmlops.supervisor.policy``; organization-level policy sets bind to this
package without moving that engine.

``loader`` provides hot-reloadable, file-backed policy sets
(JSON/YAML) that reuse the supervisor's PolicyEngine evaluation semantics.
"""

__all__ = [
    "DynamicPolicySet",
    "PolicyRegistry",
    "write_default_document",
]


def __getattr__(name: str):
    if name in __all__:
        from qsmlops.security.policies import loader

        return getattr(loader, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
