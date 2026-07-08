"""
Rule to detect unused custom properties and view parameters.

This rule identifies custom properties and view parameters that are defined but never referenced
or populated in bindings, scripts, or other expressions throughout the view.

Custom properties can be located at:
- custom.* - View-level custom properties
- params.* - View parameters (inputs and outputs)
- {component_path}.custom.* - Component-level custom properties

SUPPORTED DETECTION:
- ✅ View-level custom properties (custom.*)
- ✅ View parameters (params.*)
- ✅ Component-level custom properties (*.custom.*)
- ✅ References in expression bindings ({view.custom.prop}, {this.custom.prop})
- ✅ Properties with bindings (a property with a binding is considered "used")
- ✅ Persistent vs non-persistent property handling

These properties are considered "used" if:
1. They have a binding (expression, property, tag, query, etc.) that populates their value
2. They are referenced in:
   - ✅ Expression bindings (e.g., {view.custom.myProp}, {this.custom.myProp})
   - ✅ Property bindings (e.g., property paths like "view.custom.breakerStatus")
   - ✅ Tag bindings (e.g., tag paths containing property references)
   - ✅ Script expressions in event handlers, message handlers, transforms, etc.
   - ✅ Custom method scripts
   - ✅ Any other context where property paths appear as strings in the view definition

IMPORTANT: Output parameters (paramDirection: "output") are only considered used if they have
a binding or are referenced elsewhere in the view. An output param without a binding or references
is unused because it provides no data to parent views.
"""

import re
from typing import Set, Dict, Any, Optional
from ..common import LintingRule, FixableMixin
from ..registry import register_rule
from ...common.fix_operations import Fix, FixOperation, FixOperationType
from ...model.node_types import NodeType

# Sentinel distinguishing "path not present in the JSON" from a legitimate None value.
_MISSING = object()

# Matches flattened-JSON keys under a binding declaration and captures the property that
# owns the binding. Works for view-level keys (propConfig.custom.X.binding.type) and
# component-level keys (root.root.children[0].Btn.propConfig.custom.X.binding.type).
_BINDING_OWNER_RE = re.compile(r'^(?:(?P<owner>.+)\.)?propConfig\.(?P<prop>(?:custom|params)\..+?)\.binding(?:[.\[]|$)')


@register_rule
class UnusedCustomPropertiesRule(FixableMixin, LintingRule):
	"""Detects custom properties and view parameters that are defined but never referenced.

	Supports auto-fix: when fix context is available, generates Fix objects that remove the
	unused property definition (its value entry and any propConfig entries). Removing a custom
	property is safe; removing a view parameter is unsafe because it changes the view's public
	interface (parent views passing the parameter are not updated).
	"""

	def __init__(self, severity="error"):
		# We need to examine all node types to find property definitions and references
		super().__init__({
			NodeType.PROPERTY, NodeType.COMPONENT, NodeType.EXPRESSION_BINDING, NodeType.PROPERTY_BINDING,
			NodeType.TAG_BINDING, NodeType.EVENT_HANDLER, NodeType.MESSAGE_HANDLER, NodeType.CUSTOM_METHOD,
			NodeType.TRANSFORM
		}, severity)

		# Track defined properties and where they're used
		self.defined_properties: Dict[str, str] = {}  # prop_path -> definition_location
		self.used_properties: Set[str] = set()
		self.flattened_json: Dict[str, Any] = {}  # Store flattened JSON for direct inspection
		self._finalize_complete = False  # Track if finalize has been called to prevent duplicates

	@property
	def error_message(self) -> str:
		return "Unused custom properties and view parameters detection"

	def reset(self):
		"""Reset tracking between view files."""
		self.defined_properties = {}
		self.used_properties = set()
		self.flattened_json = {}
		self._finalize_complete = False
		self.reset_fixes()

	def set_flattened_json(self, flattened_json: Dict[str, Any]):
		"""Set the flattened JSON for comprehensive property reference searching."""
		self.flattened_json = flattened_json

	def process_nodes(self, nodes):
		"""Process nodes to detect unused custom properties and view parameters."""
		# Reset tracking state before processing this file
		# Note: flattened_json is set via set_flattened_json() before this is called
		self.defined_properties = {}
		self.used_properties = set()
		self._finalize_complete = False
		self.reset_fixes()

		# Call parent process_nodes first to get standard property processing
		super().process_nodes(nodes)

		# After processing all nodes, check for unused properties
		self.finalize()
		# Mark finalize as complete to prevent duplication in finalize_batch_rules
		self._finalize_complete = True

	def post_process(self):
		"""Called after all nodes are visited - but we handle this in process_nodes."""

	def visit_property(self, node):
		"""Visit property nodes to find custom property definitions."""
		path = node.path

		# Check for view-level custom properties: custom.propName
		if path.startswith('custom.') and '.' not in path[7:]:  # Exactly custom.propName
			prop_name = path[7:]  # Remove 'custom.' prefix
			full_prop_path = f"view.custom.{prop_name}"
			self.defined_properties[full_prop_path] = path

		# Check for view-level parameters: params.paramName
		elif path.startswith('params.') and '.' not in path[7:]:  # Exactly params.paramName
			prop_name = path[7:]  # Remove 'params.' prefix
			full_prop_path = f"view.params.{prop_name}"
			self.defined_properties[full_prop_path] = path

		# Check for component custom properties: *.custom.propName
		elif '.custom.' in path and not path.startswith('propConfig.'):
			# Extract the property name (last part after .custom.)
			custom_match = re.search(r'\.custom\.([^.]+)$', path)
			if custom_match:
				prop_name = custom_match.group(1)

				# Extract component identifier from path
				component_path = path.split('.custom.')[0]
				# Get component name from path (last segment)
				component_name = component_path.split('.')[-1]
				full_prop_path = f"{component_name}.custom.{prop_name}"

				self.defined_properties[full_prop_path] = path

	def visit_expression_binding(self, node):
		"""Check expression bindings for custom property references."""
		self._check_expression_for_references(node.expression)

		# Also mark the property that owns this binding as used
		# A property with a binding is actively being populated/managed
		self._mark_binding_owner_as_used(node.path)

	def visit_property_binding(self, node):
		"""Check property bindings for custom property references."""
		# Property bindings might reference custom properties in their target paths
		if hasattr(node, 'target_path') and node.target_path:
			self._check_expression_for_references(node.target_path)

		# Also mark the property that owns this binding as used
		# A property with a binding is actively being populated/managed
		self._mark_binding_owner_as_used(node.path)

	def visit_tag_binding(self, node):
		"""Check tag bindings for custom property references in tag paths."""
		if hasattr(node, 'tag_path') and node.tag_path:
			self._check_expression_for_references(node.tag_path)

		# Also mark the property that owns this binding as used
		# A property with a binding is actively being populated/managed
		self._mark_binding_owner_as_used(node.path)

	def visit_event_handler(self, node):
		"""Check event handler scripts for custom property references."""
		if hasattr(node, 'script') and node.script:
			self._check_script_for_references(node.script)

	def visit_message_handler(self, node):
		"""Check message handler scripts for custom property references."""
		if hasattr(node, 'script') and node.script:
			self._check_script_for_references(node.script)

	def visit_custom_method(self, node):
		"""Check custom method scripts for custom property references."""
		if hasattr(node, 'script') and node.script:
			self._check_script_for_references(node.script)

	def visit_transform(self, node):
		"""Check transform scripts for custom property references."""
		if hasattr(node, 'script') and node.script:
			self._check_script_for_references(node.script)

	def _mark_binding_owner_as_used(self, binding_path: str):
		"""
		Mark the property that owns a binding as used.

		A property with a binding is actively being populated/managed, so it should
		be considered "used" even if not referenced elsewhere in the view.

		Examples:
		- propConfig.params.breakerStatus -> marks view.params.breakerStatus as used
		- propConfig.params.currentDetected.binding.transforms[0] -> marks view.params.currentDetected as used
		- propConfig.custom.myProp -> marks view.custom.myProp as used
		"""
		property_path = binding_path

		# Remove propConfig prefix if present
		if property_path.startswith('propConfig.'):
			property_path = property_path[len('propConfig.'):]

		# Remove binding-related suffixes to get just the property name
		# Strip everything after the property name (binding, transforms, etc.)
		for suffix in ['.binding', '.persistent', '.paramDirection']:
			if suffix in property_path:
				property_path = property_path.split(suffix)[0]
				break

		# Mark the property as used based on its type. We keep the full (possibly nested)
		# property path so that a parent/container property can be credited when only its
		# nested children are bound (e.g. custom.network.nat1 credits custom.network). See
		# the descendant check in finalize().
		if property_path.startswith('custom.'):
			# View-level custom property: custom.propName (or custom.parent.child)
			prop_name = property_path[len('custom.'):]
			self.used_properties.add(f"view.custom.{prop_name}")
		elif property_path.startswith('params.'):
			# View-level param: params.paramName (or params.parent.child)
			param_name = property_path[len('params.'):]
			self.used_properties.add(f"view.params.{param_name}")
		elif '.custom.' in property_path:
			# Component custom property: something.custom.propName (or .custom.parent.child)
			custom_match = re.search(r'([^.]+)\.custom\.(.+)$', property_path)
			if custom_match:
				component_name = custom_match.group(1)
				prop_name = custom_match.group(2)
				self.used_properties.add(f"{component_name}.custom.{prop_name}")

	def _check_expression_for_references(self, expression: str):
		"""Check an expression string for custom property references."""
		if not expression:
			return

		# Look for patterns like {view.custom.propName}, {this.custom.propName}, etc.
		pattern_handlers = [
			(r'\{view\.custom\.([^}]+)\}', lambda m: f"view.custom.{m}"),  # {view.custom.propName}
			(r'\{view\.params\.([^}]+)\}', lambda m: f"view.params.{m}"),  # {view.params.paramName}
			(r'\{this\.custom\.([^}]+)\}', lambda m: f"*.custom.{m}"),  # {this.custom.propName}
			(r'\{self\.view\.custom\.([^}]+)\}',
				lambda m: f"view.custom.{m}"),  # {self.view.custom.propName}
			(r'\{self\.view\.params\.([^}]+)\}',
				lambda m: f"view.params.{m}"),  # {self.view.params.paramName}
		]

		for pattern, handler in pattern_handlers:
			matches = re.findall(pattern, expression)
			for match in matches:
				used_prop = handler(match)
				self.used_properties.add(used_prop)

		# Whole-object references pass the entire params/custom object to a consumer —
		# typically an embedded view's props.params, which forwards the params to the
		# next view. Brace form ({view.params}) appears in expressions; the bare
		# whole-value form ('view.params') is a property-binding path. Any member may
		# be read downstream, so credit the full scope.
		if re.search(r'\{(?:self\.)?view\.params\}', expression) or expression.strip() == 'view.params':
			self.used_properties.add('view.params.*')
		if re.search(r'\{(?:self\.)?view\.custom\}', expression) or expression.strip() == 'view.custom':
			self.used_properties.add('view.custom.*')

	@staticmethod
	def _is_view_scope_script_path(json_path: str) -> bool:
		"""
		Determine whether a script/value at the given flattened-JSON path runs at view scope.

		In Perspective, `self` resolves to whatever owns the script. Scripts attached to the
		view's own custom properties / parameters (top-level ``propConfig.*``) or the view's
		event handlers (top-level ``events.*``) run with ``self`` == the view, so a bare
		``self.custom.X`` there is identical to ``self.view.custom.X``. Everything under
		``root.`` belongs to a component (the root container or a descendant), where ``self``
		is that component - so a bare ``self.custom.X`` there must NOT credit a view-level
		property (it would shadow/confuse a component's own custom of the same name).
		"""
		return json_path.startswith('propConfig.') or json_path.startswith('events.')

	def _check_script_for_references(self, script: str, view_scope: bool = False):
		"""
		Check a script string for custom property references.

		Args:
			script: The script body to scan.
			view_scope: True when the script provably runs with ``self`` == the view (see
				_is_view_scope_script_path). In that case a bare ``self.custom.X`` /
				``self.params.X`` also credits the view-level property, not just the
				component wildcard.
		"""
		if not script:
			return

		# Look for patterns like self.view.custom.propName, self.view.params.paramName, etc.
		# The capture group greedily includes nested children (e.g. network.nat1) so that
		# accessing a child of an object property credits the parent. See _is_property_used.
		nested = r'([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)'
		patterns = [
			rf'self\.view\.custom\.{nested}',  # self.view.custom.propName
			rf'self\.view\.params\.{nested}',  # self.view.params.paramName
			rf'self\.custom\.{nested}',  # self.custom.propName (component, or view when view-scoped)
			rf'self\.params\.{nested}',  # self.params.propName (component, or view when view-scoped)
		]

		for pattern in patterns:
			matches = re.findall(pattern, script)
			for match in matches:
				# Check for escaped versions of the substrings since patterns have escaped dots
				if r'\.view\.custom\.' in pattern:
					self.used_properties.add(f"view.custom.{match}")
				elif r'\.view\.params\.' in pattern:
					self.used_properties.add(f"view.params.{match}")
				elif r'\.custom\.' in pattern:
					self.used_properties.add(f"*.custom.{match}")
					# A view-scoped self.custom.X is equivalent to self.view.custom.X.
					if view_scope:
						self.used_properties.add(f"view.custom.{match}")
				elif r'\.params\.' in pattern:
					self.used_properties.add(f"*.params.{match}")
					# A view-scoped self.params.X is equivalent to self.view.params.X.
					if view_scope:
						self.used_properties.add(f"view.params.{match}")

		# Quoted subscript access reads one known member, not the whole params/custom object.
		subscript_patterns = [
			(r'self\.view\.params\s*\[\s*[\'\"]([a-zA-Z_][a-zA-Z0-9_]*)[\'\"]\s*\]', "view.params.{}"),
			(r'self\.view\.custom\s*\[\s*[\'\"]([a-zA-Z_][a-zA-Z0-9_]*)[\'\"]\s*\]', "view.custom.{}"),
		]
		for pattern, used_property_template in subscript_patterns:
			matches = re.findall(pattern, script)
			for match in matches:
				self.used_properties.add(used_property_template.format(match))

		# A bare self.view.params/custom reference may pass the full object to another consumer.
		# Since we can't know which members are read later, mark the full scope as used.
		# Dot access and quoted subscripts are handled above as specific member reads.
		if re.search(r'self\.view\.params\b(?!\s*(?:\.|\[\s*[\'\"]))', script):
			self.used_properties.add('view.params.*')
		if re.search(r'self\.view\.custom\b(?!\s*(?:\.|\[\s*[\'\"]))', script):
			self.used_properties.add('view.custom.*')

	def finalize(self):
		"""Called after all nodes are visited - check for unused properties."""
		# Skip if already called during process_nodes (prevents duplicates)
		if hasattr(self, '_finalize_complete') and self._finalize_complete:
			self.errors = []
			self.warnings = []
			return

		# Search entire flattened JSON for property references
		self._search_flattened_json_for_references()
		self._credit_bound_properties()

		unused_properties = []

		for prop_path, definition_location in self.defined_properties.items():
			if self._is_property_used(prop_path):
				continue

			# If we reach here, the property is unused
			unused_properties.append((prop_path, definition_location))

		# Report unused properties
		for prop_path, definition_location in unused_properties:
			prop_type = "view parameter" if ".params." in prop_path else "custom property"
			violation_msg = (
				f"{definition_location}: {prop_type} '{prop_path.split('.')[-1]}' is defined but never referenced"
			)
			self.add_violation(violation_msg)

			if self.has_fix_context:
				self._generate_removal_fix(prop_path, definition_location, prop_type, violation_msg)

	def _credit_bound_properties(self):
		"""
		Credit every property that owns a binding, regardless of binding type.

		The visitor-based crediting in visit_*_binding only covers binding types the model
		builder turns into nodes (expression, property, tag). Binding types without dedicated
		nodes (query, expr-struct, http, tag-history, ...) would leave their owner uncredited,
		flagging a live bound property as unused — and auto-fix would then delete a working
		binding. Scanning the flattened keys makes "a property with a binding is used" hold
		for every binding shape, present or future.
		"""
		for json_path in self.flattened_json:
			match = _BINDING_OWNER_RE.match(json_path)
			if not match:
				continue
			prop_path = match.group('prop')
			owner = match.group('owner')
			if owner is None:
				# View-level propConfig: propConfig.custom.X / propConfig.params.X
				self.used_properties.add(f"view.{prop_path}")
			else:
				# Component propConfig: credit under the component's name, matching
				# the {component_name}.custom.{prop} key format of defined_properties.
				component_name = owner.split('.')[-1]
				self.used_properties.add(f"{component_name}.{prop_path}")

	def _is_property_used(self, prop_path: str) -> bool:
		"""
		Determine whether a defined property is used.

		A property is considered used if it is referenced/bound directly, OR if any of its
		descendant paths are referenced/bound. The latter handles object/container properties
		(e.g. custom.network) whose nested children (custom.network.nat1) are the things that
		actually have bindings and references - the parent cannot be unused if its children are.
		"""
		# Direct usage
		if prop_path in self.used_properties:
			return True

		# A whole-object reference credits every property under that view scope.
		if prop_path.startswith('view.params.') and 'view.params.*' in self.used_properties:
			return True
		if prop_path.startswith('view.custom.') and 'view.custom.*' in self.used_properties:
			return True

		# Descendant usage credits the parent (e.g. view.custom.network.nat1 -> view.custom.network)
		descendant_prefix = f"{prop_path}."
		if any(used.startswith(descendant_prefix) for used in self.used_properties):
			return True

		# Component custom properties are also tracked via wildcard keys (*.custom.propName)
		if '.custom.' in prop_path and not prop_path.startswith('view.'):
			prop_name = prop_path.split('.custom.')[-1]
			if f"*.custom.{prop_name}" in self.used_properties:
				return True
			wildcard_prefix = f"*.custom.{prop_name}."
			if any(used.startswith(wildcard_prefix) for used in self.used_properties):
				return True

		# A view-level object custom property may have its children accessed via the
		# component-relative self.custom.X.child form in scripts (recorded as *.custom.X.child).
		# We only credit on a nested child access (not a bare *.custom.X) to preserve the
		# strict view-level behavior for plain self.custom.X references.
		if prop_path.startswith('view.custom.'):
			prop_name = prop_path.split('view.custom.')[-1]
			wildcard_prefix = f"*.custom.{prop_name}."
			if any(used.startswith(wildcard_prefix) for used in self.used_properties):
				return True

		# View params may be referenced via component-relative self.params (*.params.paramName)
		if prop_path.startswith('view.params.'):
			prop_name = prop_path.split('view.params.')[-1]
			if f"*.params.{prop_name}" in self.used_properties:
				return True
			wildcard_prefix = f"*.params.{prop_name}."
			if any(used.startswith(wildcard_prefix) for used in self.used_properties):
				return True

		return False

	def _search_flattened_json_for_references(self):
		"""Search the entire flattened JSON for any references to defined properties."""
		if not self.flattened_json or not self.defined_properties:
			return

		# Get all property paths we're looking for
		search_patterns = []

		for prop_path in self.defined_properties.keys():  # pylint: disable=consider-iterating-dictionary
			if prop_path.startswith('view.custom.'):
				# For view custom properties: view.custom.propName
				prop_name = prop_path[12:]  # Remove 'view.custom.'
				search_patterns.extend([
					f"view.custom.{prop_name}",
					f"self.view.custom.{prop_name}",
					f"{{{prop_name}}}",  # Short form in expressions
				])
			elif prop_path.startswith('view.params.'):
				# For view parameters: view.params.paramName
				param_name = prop_path[12:]  # Remove 'view.params.'
				search_patterns.extend([
					f"view.params.{param_name}",
					f"self.view.params.{param_name}",
					f"{{{param_name}}}",  # Short form in expressions
				])
			elif '.custom.' in prop_path:
				# For component custom properties: ComponentName.custom.propName
				parts = prop_path.split('.custom.')
				component_name = parts[0]
				prop_name = parts[1]
				search_patterns.extend([
					f"{component_name}.custom.{prop_name}",
					f"this.custom.{prop_name}",
					f"self.custom.{prop_name}",
				])

		# Search through all values in the flattened JSON
		for json_path, json_value in self.flattened_json.items():
			if not isinstance(json_value, str):
				continue

			# The flattened key tells us whether a bare self.custom.X / self.params.X here runs
			# at view scope (self == view) or component scope (self == component). See
			# _is_view_scope_script_path. This is the one place that retains location, so scope
			# decisions are made here rather than in the location-agnostic modeled-node visitors.
			view_scope = self._is_view_scope_script_path(json_path)

			# Check if any of our search patterns appear in this value
			for pattern in search_patterns:
				if pattern in json_value:
					# Mark the corresponding property as used
					self._mark_property_used_from_pattern(pattern)

			# Apply the full reference detectors to every string value so that detection is
			# location-independent. This catches references (notably the component-relative
			# self.custom.X / self.params.X form) inside scripts that are not modeled as their
			# own nodes - e.g. property-change (onChange) scripts - which would otherwise only
			# be matched by the narrower substring patterns above.
			self._check_script_for_references(json_value, view_scope)
			self._check_expression_for_references(json_value)

	def _generate_removal_fix(self, prop_path: str, definition_location: str, prop_type: str, violation_msg: str):
		"""
		Generate a Fix that removes an unused property definition.

		Removal covers both places a property definition can live:
		- the value entry in the owning custom/params object
		- the propConfig entry (or entries, for nested children of an object property)

		Only definitions we can locate unambiguously in the JSON get a fix; otherwise the
		violation still reports and the user removes the property manually.
		"""
		prop_name = prop_path.split('.')[-1]

		if prop_path.startswith('view.custom.'):
			owner_json_path: Optional[list] = []
			scope = 'custom'
		elif prop_path.startswith('view.params.'):
			owner_json_path = []
			scope = 'params'
		else:
			# Component custom property: definition_location is the (index-stripped)
			# flattened path ending in .custom.<name>; the prefix is the component.
			owner_json_path = self._resolve_component_json_path(
				definition_location[:-len(f'.custom.{prop_name}')]
			)
			scope = 'custom'

		if owner_json_path is None:
			return

		operations, removes_onchange = self._build_delete_operations(owner_json_path, scope, prop_name)
		if not operations:
			return

		description = f"Remove unused {prop_type} '{prop_name}'"
		safety_parts = []
		if scope == 'params':
			safety_parts.append(
				f"removing view parameter '{prop_name}' changes the view's public interface; "
				"parent views passing it are not updated"
			)
		if removes_onchange:
			safety_parts.append("also removes the property's onChange property-change script")

		self.add_fix(
			Fix(
				rule_name=self.error_key, violation_message=violation_msg, description=description,
				operations=operations, is_safe=not safety_parts,
				safety_notes="; ".join(safety_parts) if safety_parts else None
			)
		)

	def _build_delete_operations(self, owner_json_path: list, scope: str, prop_name: str):
		"""
		Build DELETE_KEY operations for a property's value entry and propConfig entries.

		Args:
			owner_json_path: JSON path of the dict owning the property ([] for the view,
				the component's JSON path for component custom properties).
			scope: 'custom' or 'params'.
			prop_name: Bare property name.

		Returns:
			Tuple of (operations, removes_onchange). removes_onchange is True when any
			removed propConfig entry contains an onChange property-change script.
			Returns no operations when a propConfig entry still contains a binding:
			a flagged property that owns a binding means the rule failed to credit it
			(a detection blind spot), and deleting it would destroy a live binding.
		"""
		operations = []
		removes_onchange = False

		# Value entry (absent for propConfig-only definitions, e.g. non-persistent props)
		value_json_path = owner_json_path + [scope, prop_name]
		value = self._get_json_value(value_json_path)
		if value is not _MISSING:
			operations.append(
				FixOperation(
					operation=FixOperationType.DELETE_KEY, json_path=value_json_path,
					old_value=value, description=f"Remove {scope}.{prop_name} value entry"
				)
			)

		# propConfig entries: exact key plus nested children of an object/array property
		# (e.g. "custom.network.nat1" or "custom.myList[0]" alongside "custom.network").
		prop_config = self._get_json_value(owner_json_path + ['propConfig'])
		if isinstance(prop_config, dict):
			exact_key = f"{scope}.{prop_name}"
			child_prefixes = (f"{exact_key}.", f"{exact_key}[")
			for key in prop_config:
				if key != exact_key and not key.startswith(child_prefixes):
					continue
				entry = prop_config[key]
				if isinstance(entry, dict) and 'binding' in entry:
					return [], False
				if isinstance(entry, dict) and 'onChange' in entry:
					removes_onchange = True
				operations.append(
					FixOperation(
						operation=FixOperationType.DELETE_KEY,
						json_path=owner_json_path + ['propConfig', key], old_value=entry,
						description=f"Remove propConfig entry '{key}'"
					)
				)

		return operations, removes_onchange

	def _resolve_component_json_path(self, component_model_path: str) -> Optional[list]:
		"""
		Resolve a component's JSON path from an index-stripped model path.

		Property definition locations come from the model builder, which strips array
		indices (root.root.children[0].Button -> root.root.children.Button), so an exact
		PathTranslator lookup can fail. Fall back to matching translator component paths
		with their indices stripped; sibling names are unique in Perspective, so at most
		one component should match. Returns None when unresolvable or ambiguous.
		"""
		json_path = self._path_translator.model_path_to_json_path(component_model_path)
		if json_path is not None:
			return json_path

		matches = [
			candidate for candidate in self._path_translator.get_all_component_paths()
			if re.sub(r'\[\d+\]', '', candidate) == component_model_path
		]
		if len(matches) != 1:
			return None
		return self._path_translator.model_path_to_json_path(matches[0])

	def _get_json_value(self, json_path: list):
		"""Read a value from the fix-context JSON, returning _MISSING when the path is absent."""
		try:
			return self._path_translator.get_value(json_path)
		except (KeyError, IndexError, TypeError):
			return _MISSING

	def _mark_property_used_from_pattern(self, pattern: str):
		"""Mark a property as used based on a found pattern."""
		# Extract the property path from the pattern
		if 'view.custom.' in pattern:
			# Extract property name from patterns like "view.custom.propName" or "self.view.custom.propName"
			match = re.search(r'view\.custom\.([a-zA-Z_][a-zA-Z0-9_]*)', pattern)
			if match:
				prop_name = match.group(1)
				self.used_properties.add(f"view.custom.{prop_name}")
		elif 'view.params.' in pattern:
			# Extract parameter name from patterns like "view.params.paramName" or "self.view.params.paramName"
			match = re.search(r'view\.params\.([a-zA-Z_][a-zA-Z0-9_]*)', pattern)
			if match:
				param_name = match.group(1)
				self.used_properties.add(f"view.params.{param_name}")
		elif '.custom.' in pattern:
			# Extract component and property name from patterns like "ComponentName.custom.propName" or "this.custom.propName"
			if pattern.startswith('this.custom.') or pattern.startswith('self.custom.'):
				# Generic component reference - mark as wildcard
				match = re.search(r'\.custom\.([a-zA-Z_][a-zA-Z0-9_]*)', pattern)
				if match:
					prop_name = match.group(1)
					self.used_properties.add(f"*.custom.{prop_name}")
			else:
				# Specific component reference
				match = re.search(r'([^.]+)\.custom\.([a-zA-Z_][a-zA-Z0-9_]*)', pattern)
				if match:
					component_name = match.group(1)
					prop_name = match.group(2)
					self.used_properties.add(f"{component_name}.custom.{prop_name}")
