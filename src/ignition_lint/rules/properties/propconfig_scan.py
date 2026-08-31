"""
Shared helpers for scanning propConfig metadata out of flattened view JSON.

Ignition Perspective stores per-property configuration (persistence, access mode,
bindings, onChange scripts, param direction) in `propConfig` dictionaries keyed by
dotted property paths, e.g. `"custom.myProp": {"persistent": false, "access": "PRIVATE"}`.
propConfig dictionaries exist at the view level and on every component.

The object model only surfaces this metadata for view-level properties (see builder
gaps around component-level propConfig), so rules that need complete coverage scan
the flattened JSON directly. This module centralizes that scanning so the
persistence and access rules share one parser.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# Sentinel distinguishing "key absent" from a stored None/null value.
MISSING = object()

# Known direct sub-keys of a propConfig property entry. Anything nested deeper than
# one of these segments belongs to that attribute's configuration, not the property key.
PROPCONFIG_ATTRS = ('binding', 'persistent', 'access', 'paramDirection', 'onChange')

_ATTR_KEY_RE = re.compile(
	r'^(?:(?P<owner>.+)\.)?propConfig\.'
	r'(?P<prop>(?:custom|params|props)\..+?)\.'
	r'(?P<attr>binding|persistent|access|paramDirection|onChange)(?:[.\[]|$)'
)
# Fallback for entries whose config carries no known attribute, e.g. an empty
# entry preserved by the flattener as `propConfig.custom.ghost = {}`.
_ENTRY_KEY_RE = re.compile(r'^(?:(?P<owner>.+)\.)?propConfig\.(?P<prop>(?:custom|params|props)\..+)$')

_META_NAME_SUFFIX = '.meta.name'


@dataclass
class PropConfigEntry:
	"""One propConfig entry: the property it configures plus its declared metadata."""
	owner: Optional[str]  # Component flattened path (indices intact), or None for the view itself
	prop_key: str  # Exact propConfig key, e.g. 'custom.myProp' or 'props.params.configuring'
	attrs: Set[str] = field(default_factory=set)
	persistent: Optional[bool] = None
	access: Optional[str] = None
	binding_type: Optional[str] = None  # 'expr', 'expr-struct', 'property', 'query', 'tag'
	tag_mode: Optional[str] = None  # 'direct', 'indirect', 'expression' (tag bindings only)

	@property
	def scope(self) -> str:
		"""Property scope: 'custom', 'params', or 'props'."""
		return self.prop_key.split('.', 1)[0]

	@property
	def has_binding(self) -> bool:
		"""Whether this entry configures a binding."""
		return 'binding' in self.attrs

	@property
	def full_path(self) -> str:
		"""Owner-qualified property path used in violation messages."""
		return f"{self.owner}.{self.prop_key}" if self.owner else self.prop_key


def collect_component_paths(flattened_json: Dict[str, Any]) -> Set[str]:
	"""Return the flattened paths of all components (identified by their meta.name key)."""
	return {key[:-len(_META_NAME_SUFFIX)] for key in flattened_json if key.endswith(_META_NAME_SUFFIX)}


def collect_propconfig_entries(
	flattened_json: Dict[str, Any], component_paths: Optional[Set[str]] = None
) -> Dict[Tuple[Optional[str], str], PropConfigEntry]:
	"""
	Parse every propConfig entry (view-level and component-level) out of flattened JSON.

	Returns a dict keyed by (owner, prop_key). Owners are validated against real
	component paths so structures that merely contain a 'propConfig' segment in an
	unexpected position are ignored.
	"""
	if component_paths is None:
		component_paths = collect_component_paths(flattened_json)

	entries: Dict[Tuple[Optional[str], str], PropConfigEntry] = {}
	for key in flattened_json:
		if 'propConfig' not in key:
			continue
		match = _ATTR_KEY_RE.match(key)
		if match:
			attr = match.group('attr')
		else:
			match = _ENTRY_KEY_RE.match(key)
			if not match:
				continue
			attr = None
		owner = match.group('owner')
		if owner is not None and owner not in component_paths:
			continue
		entry_key = (owner, match.group('prop'))
		entry = entries.get(entry_key)
		if entry is None:
			entry = PropConfigEntry(owner=owner, prop_key=match.group('prop'))
			entries[entry_key] = entry
		if attr:
			entry.attrs.add(attr)

	for (owner, prop_key), entry in entries.items():
		base = f"{owner}.propConfig.{prop_key}" if owner else f"propConfig.{prop_key}"
		entry.persistent = flattened_json.get(f"{base}.persistent")
		entry.access = flattened_json.get(f"{base}.access")
		entry.binding_type = flattened_json.get(f"{base}.binding.type")
		entry.tag_mode = flattened_json.get(f"{base}.binding.config.mode")

	return entries


def has_value_entry(flattened_json: Dict[str, Any], owner: Optional[str], prop_key: str) -> bool:
	"""Check whether a property has a stored value entry (e.g. custom.<name> exists)."""
	base = f"{owner}.{prop_key}" if owner else prop_key
	if base in flattened_json:
		return True
	dot_prefix = base + '.'
	bracket_prefix = base + '['
	return any(key.startswith(dot_prefix) or key.startswith(bracket_prefix) for key in flattened_json)


def collect_custom_value_props(flattened_json: Dict[str, Any],
				component_paths: Optional[Set[str]] = None) -> Set[Tuple[Optional[str], str]]:
	"""
	Return (owner, top_level_name) pairs for every custom property with a value entry.

	Only 'custom' objects belonging to the view root or a real component are
	considered, so a component that happens to be named 'custom' (or structures like
	propConfig subtrees) can never be misread as a custom-property scope.
	"""
	if component_paths is None:
		component_paths = collect_component_paths(flattened_json)

	props: Set[Tuple[Optional[str], str]] = set()
	for key in flattened_json:
		owner: Optional[str] = None
		rest: Optional[str] = None
		if key.startswith('custom.'):
			rest = key[len('custom.'):]
		else:
			index = key.find('.custom.')
			while index != -1:
				candidate = key[:index]
				if candidate in component_paths:
					owner = candidate
					rest = key[index + len('.custom.'):]
					break
				index = key.find('.custom.', index + 1)
		if rest is None:
			continue
		top_name = re.split(r'[.\[]', rest, maxsplit=1)[0]
		if top_name:
			props.add((owner, top_name))
	return props


def resolve_owner_json_path(path_translator, owner: Optional[str]) -> Optional[List[Any]]:
	"""
	Resolve an entry owner to a JSON dict path ([] for the view root).

	Owners produced by this module come straight from flattened keys, so they retain
	array indices and resolve with a direct PathTranslator lookup.
	"""
	if owner is None:
		return []
	return path_translator.model_path_to_json_path(owner)


def get_json_value(path_translator, json_path: List[Any]) -> Any:
	"""Read a value from the fix-context JSON, returning MISSING when the path is absent."""
	try:
		return path_translator.get_value(json_path)
	except (KeyError, IndexError, TypeError):
		return MISSING
