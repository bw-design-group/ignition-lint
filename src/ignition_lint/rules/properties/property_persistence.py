"""
Rule to validate the `persistent` flag on bound properties.

In Ignition Perspective, every property configured in `propConfig` carries a
`persistent` flag (absent means true, the Ignition default). For a BOUND property,
`persistent: true` means the designer saves the last binding result into view.json
on every save - producing constant git diff churn with no runtime benefit, because
at runtime the binding recomputes the value anyway.

Best practice is `persistent: false` on bound properties, with two caveats teams
must consciously accept:
- The property key does not exist in the view model until the binding first
  evaluates. Downstream bindings must chain off the property (and handle nulls)
  rather than assume a value is present at startup.
- Tag bindings - especially indirect tag bindings - never create the key at all
  when the tag is not found. For that reason tag bindings are exempt by default
  (configurable via `exempt_binding_types`).

This rule is inert unless `expected_persistent` is configured, making it strictly
opt-in. Projects that prefer stored defaults can instead set
`expected_persistent: true`, which also requires bound persistent properties to
have a stored default value (the point of persistence is that the key exists
before the first binding evaluation).
"""

from typing import Any, Dict

from .propconfig_scan import (
	MISSING, PropConfigEntry, collect_propconfig_entries, get_json_value, has_value_entry, resolve_owner_json_path
)
from ..common import FixableMixin, LintingRule
from ..registry import register_rule
from ...common.fix_operations import Fix, FixOperation, FixOperationType

VALID_EXEMPT_TOKENS = frozenset({
	'expr', 'expr-struct', 'property', 'query', 'tag', 'tag.direct', 'tag.indirect', 'tag.expression'
})
DEFAULT_EXEMPT_BINDING_TYPES = ('tag',)


@register_rule
class PropertyPersistenceRule(FixableMixin, LintingRule):
	"""Validates that bound properties declare the project's expected persistence."""

	def __init__(self, *, expected_persistent=None, exempt_binding_types=None, severity="error"):
		"""
		Initialize the rule.

		Args:
			expected_persistent: Expected `persistent` value for bound properties.
				None (default) disables the rule entirely, making it opt-in.
			exempt_binding_types: Binding types to skip. Tokens are binding types
				('tag', 'expr', 'expr-struct', 'property', 'query') or tag modes
				('tag.direct', 'tag.indirect', 'tag.expression'). Defaults to ['tag']
				because tag bindings may never create the property key when the tag
				is missing. Pass [] to check every binding type.
			severity: Severity level - "error" (default) or "warning".
		"""
		super().__init__(set(), severity)  # Empty set - we process flattened JSON directly
		if expected_persistent is not None and not isinstance(expected_persistent, bool):
			raise ValueError(
				f"expected_persistent must be true, false, or null; got {expected_persistent!r}"
			)
		self.expected_persistent = expected_persistent
		self.exempt_binding_types = self._validated_tokens(
			exempt_binding_types, DEFAULT_EXEMPT_BINDING_TYPES, VALID_EXEMPT_TOKENS, 'exempt_binding_types'
		)
		self.flattened_json: Dict[str, Any] = {}

	@staticmethod
	def _validated_tokens(values, defaults, valid, option_name):
		"""Normalize a token-list option, raising on unknown tokens."""
		if values is None:
			return set(defaults)
		tokens = set(values)
		unknown = tokens - valid
		if unknown:
			raise ValueError(
				f"Unknown {option_name} token(s) {sorted(unknown)}; valid tokens: {sorted(valid)}"
			)
		return tokens

	@property
	def error_message(self) -> str:
		return "Bound property persistence does not match the project's expected configuration"

	def set_flattened_json(self, flattened_json: Dict[str, Any]):
		"""Set the flattened JSON for analysis."""
		self.flattened_json = flattened_json

	def process_nodes(self, nodes):
		"""Scan propConfig entries in the flattened JSON for persistence violations."""
		self.errors = []
		self.warnings = []
		self.reset_fixes()

		if self.expected_persistent is None:
			return

		for entry in collect_propconfig_entries(self.flattened_json).values():
			# Hard-scoped to custom.* like PropertyAccessRule: persistence on
			# component props.* and view params.* is Designer-managed territory.
			if entry.scope != 'custom' or not entry.has_binding or self._is_exempt(entry):
				continue
			# Absent persistent flag means persistent, the Ignition default.
			effective_persistent = entry.persistent if entry.persistent is not None else True
			if self.expected_persistent is False:
				if effective_persistent:
					self._flag_persistent_binding(entry)
			else:
				self._check_expected_persistent(entry, effective_persistent)

	def _is_exempt(self, entry: PropConfigEntry) -> bool:
		"""Check whether the entry's binding type (or tag mode) is exempt."""
		if entry.binding_type in self.exempt_binding_types:
			return True
		if entry.binding_type == 'tag' and entry.tag_mode:
			return f"tag.{entry.tag_mode}" in self.exempt_binding_types
		return False

	def _flag_persistent_binding(self, entry: PropConfigEntry):
		"""Flag a bound property that stores its designer result (expected_persistent=false)."""
		message = (
			f"{entry.full_path}: bound property is persistent; set persistent=false to stop "
			f"storing designer results in view.json"
		)
		self.add_violation(message)
		if self.has_fix_context:
			self._add_persistence_fix(entry, message)

	def _check_expected_persistent(self, entry: PropConfigEntry, effective_persistent: bool):
		"""Validate a bound property against expected_persistent=true (no auto-fix)."""
		if not effective_persistent:
			self.add_violation(
				f"{entry.full_path}: bound property is not persistent; this project expects persistent=true"
			)
		elif not has_value_entry(self.flattened_json, entry.owner, entry.prop_key):
			self.add_violation(f"{entry.full_path}: persistent bound property has no stored default value")

	def _add_persistence_fix(self, entry: PropConfigEntry, violation_message: str):
		"""
		Generate the safe fix for a persistent bound property: set persistent=false on
		the propConfig entry and delete the stale designer value entry when present.
		Mirrors the established manual cleanup workflow for bound custom properties.
		"""
		owner_json_path = resolve_owner_json_path(self._path_translator, entry.owner)
		if owner_json_path is None:
			return

		operations = [
			FixOperation(
				operation=FixOperationType.SET_VALUE,
				json_path=owner_json_path + ['propConfig', entry.prop_key, 'persistent'],
				old_value=entry.persistent, new_value=False,
				description=f"Set persistent=false on propConfig entry '{entry.prop_key}'"
			)
		]

		# Delete the stale stored value. Skip indexed keys (e.g. custom.list[0]):
		# deleting list elements would shift sibling indices and is unsupported.
		if '[' not in entry.prop_key:
			value_json_path = owner_json_path + entry.prop_key.split('.')
			value = get_json_value(self._path_translator, value_json_path)
			if value is not MISSING:
				operations.append(
					FixOperation(
						operation=FixOperationType.DELETE_KEY, json_path=value_json_path,
						old_value=value,
						description=f"Remove stale stored value '{entry.prop_key}'"
					)
				)

		self.add_fix(
			Fix(
				rule_name=self.error_key, violation_message=violation_message,
				description=f"Make bound property '{entry.full_path}' non-persistent",
				operations=operations, is_safe=True
			)
		)
