"""rm-validate — generic policy validator for the RM Method.

The validator makes no assumptions about the layout of a target repo. Every
rule, path and pattern comes from the target's own ``rm-policy.yaml``; the
package ships only the mechanism, never project-specific knowledge.
"""

__version__ = "0.1.0"
