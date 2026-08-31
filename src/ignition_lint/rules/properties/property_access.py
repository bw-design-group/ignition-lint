"""
Rule to validate the `access` mode declared on custom properties.

Ignition Perspective properties have three access modes (declared per property in
`propConfig`, absent means PUBLIC):
- PUBLIC: unrestricted - the value is synchronized to the client DOM and browser
  JavaScript can read and write it.
- PROTECTED: the client can read the value, but the back-end ignores writes.
- PRIVATE: hidden - the value is never sent to the client.

Custom properties are frequently used as gateway-side staging: a view aggregates a
large dataset once on `custom.data` and ten other bindings fan out from it. The
client never uses the staging value directly, so leaving it PUBLIC ships the whole
dataset to the browser for nothing - marking it PRIVATE cuts client traffic and
improves responsiveness.

This rule checks USER-CONFIGURED custom properties only (view-level `custom.*` and
component-level `<component>.custom.*`). It never touches component `props.*` -
setting PRIVATE on something like a table's `props.data` would stop the component
from rendering - and never touches `params.*`, which form the view's public
interface. The rule is inert unless `expected_access` is configured, making it
strictly opt-in.
"""

import re
from typing import Any, Dict, List, Optional

from .propconfig_scan import (
	collect_component_paths, collect_custom_value_props, collect_propconfig_entries, get_json_value,
	resolve_owner_json_path
)
from ..common import FixableMixin, LintingRule
from ..registry import register_rule
from ...common.fix_operations import Fix, FixOperation, FixOperationType

VALID_ACCESS_MODES = frozenset({'PUBLIC', 'PROTECTED', 'PRIVATE'})


@register_rule
class PropertyAccessRule(FixableMixin, LintingRule):
	"""Validates that custom properties declare the project's expected access mode."""

	def __init__(self, *, expected_access=None, exempt_props=None, severity="error"):
		"""
		Initialize the rule.

		Args:
			expected_access: Expected access mode for custom properties - "PUBLIC",
				"PROTECTED", or "PRIVATE" (case-insensitive). None (default) disables
				the rule entirely, making it opt-in.
			exempt_props: Properties to skip. Each entry matches the bare property
				name at any level ("data" exempts custom.data on the view and every
				component), the prop key at any level ("custom.data"), or the
				fully-qualified path ("root.root.children[0].Chart.custom.data").
				'*' (any characters) and '?' (one character) wildcards are supported
				in every form; brackets are literal so indexed paths match as written.
			severity: Severity level - "error" (default) or "warning".
		"""
		super().__init__(set(), severity)  # Empty set - we process flattened JSON directly
		if expected_access is not None:
			expected_access = str(expected_access).upper()
			if expected_access not in VALID_ACCESS_MODES:
				raise ValueError(
					f"expected_access must be one of {sorted(VALID_ACCESS_MODES)}; got {expected_access!r}"
				)
		self.expected_access = expected_access
		self.exempt_props = list(exempt_props or [])
		self._exempt_patterns = [self._compile_exempt_pattern(entry) for entry in self.exempt_props]
		self.flattened_json: Dict[str, Any] = {}
		self._owners_pending_propconfig = set()

	@staticmethod
	def _compile_exempt_pattern(entry: str):
		"""
		Compile an exempt_props entry to a regex. Only '*' (any characters) and '?'
		(one character) are wildcards; everything else - including brackets, which
		appear literally in indexed component paths - is matched verbatim.
		"""
		regex = re.escape(entry).replace(r'\*', '.*').replace(r'\?', '.')
		return re.compile(f'^{regex}$')

	def _is_exempt(self, top_name: str, prop_key: str, full_path: str) -> bool:
		"""Check a property against exempt_props by bare name, prop key, or full path."""
		return any(
			pattern.match(top_name) or pattern.match(prop_key) or pattern.match(full_path)
			for pattern in self._exempt_patterns
		)

	@property
	def error_message(self) -> str:
		return "Custom property access mode does not match the project's expected configuration"

	def set_flattened_json(self, flattened_json: Dict[str, Any]):
		"""Set the flattened JSON for analysis."""
		self.flattened_json = flattened_json

	def process_nodes(self, nodes):
		"""Scan custom properties in the flattened JSON for access-mode violations."""
		self.errors = []
		self.warnings = []
		self.reset_fixes()
		self._owners_pending_propconfig = set()

		if self.expected_access is None:
			return

		component_paths = collect_component_paths(self.flattened_json)
		entries = collect_propconfig_entries(self.flattened_json, component_paths)

		# Union of custom props with value entries and custom props configured in
		# propConfig, evaluated at top-level property granularity.
		candidates = collect_custom_value_props(self.flattened_json, component_paths)
		for (owner, prop_key) in entries:
			if prop_key.startswith('custom.'):
				top_name = prop_key[len('custom.'):].split('.', 1)[0].split('[', 1)[0]
				if top_name:
					candidates.add((owner, top_name))

		for owner, top_name in sorted(candidates, key=lambda item: (item[0] or '', item[1])):
			prop_key = f"custom.{top_name}"
			full_path = f"{owner}.{prop_key}" if owner else prop_key
			if self._is_exempt(top_name, prop_key, full_path):
				continue
			entry = entries.get((owner, prop_key))
			declared_access = entry.access if entry else None
			actual = declared_access.upper() if isinstance(declared_access, str) else 'PUBLIC'
			if actual == self.expected_access:
				continue
			message = f"{full_path}: custom property access mode is {actual}, expected {self.expected_access}"
			self.add_violation(message)
			if self.has_fix_context:
				self._add_access_fix(owner, prop_key, full_path, declared_access, message)

	def _add_access_fix(
		self, owner: Optional[str], prop_key: str, full_path: str, declared_access, violation_message: str
	):
		"""
		Generate the safe fix that aligns a custom property's access mode.

		The fix is tightly scoped: operations may only target `custom.*` propConfig
		entries. A final guard drops the whole fix if any operation would land
		anywhere else (defense in depth against future scanner regressions).
		"""
		owner_json_path = resolve_owner_json_path(self._path_translator, owner)
		if owner_json_path is None:
			return

		if self.expected_access == 'PUBLIC':
			operations = self._build_public_operations(owner_json_path, prop_key)
		else:
			operations = self._build_set_access_operations(
				owner, owner_json_path, prop_key, declared_access
			)

		if not operations or not all(self._targets_custom_propconfig(op) for op in operations):
			return

		self.add_fix(
			Fix(
				rule_name=self.error_key, violation_message=violation_message,
				description=f"Set access mode of '{full_path}' to {self.expected_access}",
				operations=operations, is_safe=True
			)
		)

	def _build_set_access_operations(
		self, owner: Optional[str], owner_json_path: List[Any], prop_key: str, declared_access
	) -> List[FixOperation]:
		"""Build operations that declare the expected access mode on the propConfig entry."""
		entry_path = owner_json_path + ['propConfig', prop_key]
		if isinstance(get_json_value(self._path_translator, entry_path), dict):
			return [
				FixOperation(
					operation=FixOperationType.SET_VALUE, json_path=entry_path + ['access'],
					old_value=declared_access, new_value=self.expected_access,
					description=f"Set access={self.expected_access} on propConfig entry '{prop_key}'"
				)
			]

		propconfig_path = owner_json_path + ['propConfig']
		propconfig_exists = (
			isinstance(get_json_value(self._path_translator, propconfig_path), dict) or
			owner in self._owners_pending_propconfig
		)
		if propconfig_exists:
			# The propConfig dict exists (or an earlier fix in this run creates it,
			# and fixes are applied in generation order): add the entry.
			return [
				FixOperation(
					operation=FixOperationType.SET_VALUE, json_path=entry_path,
					new_value={'access': self.expected_access}, description=
					f"Add propConfig entry '{prop_key}' with access={self.expected_access}"
				)
			]

		self._owners_pending_propconfig.add(owner)
		return [
			FixOperation(
				operation=FixOperationType.SET_VALUE, json_path=propconfig_path,
				new_value={prop_key: {
					'access': self.expected_access
				}},
				description=f"Create propConfig with entry '{prop_key}' (access={self.expected_access})"
			)
		]

	def _build_public_operations(self, owner_json_path: List[Any], prop_key: str) -> List[FixOperation]:
		"""Build operations that restore the PUBLIC default by removing the access declaration."""
		entry_path = owner_json_path + ['propConfig', prop_key]
		entry_value = get_json_value(self._path_translator, entry_path)
		if not isinstance(entry_value, dict) or 'access' not in entry_value:
			return []
		if set(entry_value.keys()) == {'access'}:
			# The entry only declared access; remove the now-empty entry entirely.
			return [
				FixOperation(
					operation=FixOperationType.DELETE_KEY, json_path=entry_path,
					old_value=entry_value, description=
					f"Remove propConfig entry '{prop_key}' (access-only, PUBLIC is the default)"
				)
			]
		return [
			FixOperation(
				operation=FixOperationType.DELETE_KEY, json_path=entry_path + ['access'],
				old_value=entry_value['access'], description=
				f"Remove access declaration from propConfig entry '{prop_key}' (PUBLIC is the default)"
			)
		]

	@staticmethod
	def _targets_custom_propconfig(operation: FixOperation) -> bool:
		"""Guard: every operation must target a `custom.*` key inside a propConfig dict."""
		path = operation.json_path
		if 'propConfig' not in path:
			return False
		remainder = path[path.index('propConfig') + 1:]
		if not remainder:
			# Creating the propConfig dict itself: every key it introduces must be custom.*.
			return (
				isinstance(operation.new_value, dict) and bool(operation.new_value) and
				all(isinstance(key, str) and key.startswith('custom.') for key in operation.new_value)
			)
		return isinstance(remainder[0], str) and remainder[0].startswith('custom.')
