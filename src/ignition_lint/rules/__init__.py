"""
Linting rules package for ign-lint.

This module provides the rule system infrastructure and built-in rules
for linting Ignition Perspective view files. It includes the dynamic rule
registration system and auto-discovery of custom rules.
"""

from .common import LintingRule, NodeVisitor, BindingRule
from .registry import register_rule, get_registry, get_all_rules, discover_rules

# Import and register built-in rules
from .scripts.lint_script import PylintScriptRule
from .performance.polling_interval import PollingIntervalRule
from .naming.name_pattern import NamePatternRule
from .structure.bad_component_reference import BadComponentReferenceRule

# Auto-discover and register all rules in this package
_discovered_rules = discover_rules()


# Create RULES_MAP for backward compatibility
def get_rules_map():
	"""Get the current rules map for backward compatibility."""
	return get_all_rules()


# Dynamic RULES_MAP that stays up-to-date
RULES_MAP = get_rules_map()

__all__ = [
	"LintingRule",
	"NodeVisitor",
	"BindingRule",
	"PylintScriptRule",
	"PollingIntervalRule",
	"NamePatternRule",
	"BadComponentReferenceRule",
	"RULES_MAP",
	"register_rule",
	"get_registry",
	"get_all_rules",
	"discover_rules",
]
