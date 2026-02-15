# pylint: disable=import-error
"""
Rule to validate that component references resolve to actual components.

This rule validates that component object traversal patterns (expressions, property bindings,
and scripts) reference components that actually exist in the view hierarchy. It complements
BadComponentReferenceRule by ensuring that if developers DO use these patterns (despite best
practices), they at least work correctly and won't cause runtime errors.

Validates three types of component references:
1. Expression bindings: {../Sibling.props.text} or {.../Container/Child.props.value}
2. Property bindings: ../Sibling.props.enabled or .../Container/Button.position.display
3. Script references: self.getSibling('Name'), self.getChild('Name'), chained calls

Based on official Ignition documentation:
- Dot counting: Each dot beyond the first = one level up (.. = 1 level, ... = 2 levels, .... = 3 levels)
- Forward slashes: Used to drill DOWN into containers after going up
- Example: .../ParentContainer/ChildComponent.props.text means "go up 2 levels, find ParentContainer, drill down to ChildComponent"

Official Documentation:
- Binding Property Path Reference:
  https://www.docs.inductiveautomation.com/docs/8.1/ignition-modules/perspective/working-with-perspective-components/
  bindings-in-perspective/binding-property-path-reference
- Perspective Component Methods:
  https://www.docs.inductiveautomation.com/docs/8.1/ignition-modules/perspective/scripting-in-perspective/
  perspective-component-methods
"""

import re
from typing import Dict, List, Optional, Tuple
from ..common import LintingRule
from ..registry import register_rule
from ...model.node_types import NodeType


@register_rule
class ComponentReferenceValidationRule(LintingRule):
	"""
	Validates that component references resolve to actual components.

	Checks:
	- Expression bindings: {../Sibling.props.text} or {.../Parent/Child.props.value}
	- Property bindings: ../Sibling.props.enabled or .../Container/Button.position.display
	- Script methods: self.getSibling('Name'), self.getChild('Name'), chained calls

	This rule ensures component references are functionally correct, preventing runtime errors.
	It complements BadComponentReferenceRule which flags these patterns as bad practice.
	"""

	def __init__(
		self, severity="error", validate_expressions=True, validate_property_bindings=True,
		validate_scripts=True
	):
		"""
		Initialize the rule targeting all relevant node types.

		Args:
			severity: Severity level for violations ("error" or "warning")
			validate_expressions: Enable expression binding validation
			validate_property_bindings: Enable property binding validation
			validate_scripts: Enable script reference validation
		"""
		# Target all relevant node types
		target_types = {
			NodeType.COMPONENT,  # Build component index
			NodeType.EXPRESSION_BINDING,  # Check {../references}
			NodeType.PROPERTY_BINDING,  # Check ../references
			NodeType.EVENT_HANDLER,  # Check scripts
			NodeType.MESSAGE_HANDLER,
			NodeType.CUSTOM_METHOD,
			NodeType.TRANSFORM
		}
		super().__init__(target_types, severity)

		# Configuration
		self.validate_expressions = validate_expressions
		self.validate_property_bindings = validate_property_bindings
		self.validate_scripts = validate_scripts

		# Component tree structures (built during processing)
		self.component_tree: Dict[str, 'Component'] = {}  # path -> Component node
		self.component_by_name: Dict[str, List['Component']] = {}  # name -> [Component nodes]
		self.parent_map: Dict[str, str] = {}  # component_path -> parent_path
		self.children_map: Dict[str, List[str]] = {}  # parent_path -> [child_paths]

	@property
	def error_message(self) -> str:
		"""Return the error message for this rule."""
		return (
			"Validates that component references (expressions, property bindings, scripts) "
			"resolve to components that actually exist in the view hierarchy"
		)

	def process_nodes(self, nodes):
		"""Build index, then validate references."""
		self.errors = []
		self.warnings = []

		# Reset component structures
		self.component_tree = {}
		self.component_by_name = {}
		self.parent_map = {}
		self.children_map = {}

		# Phase 1: Build component index
		components = [n for n in nodes if n.node_type == NodeType.COMPONENT]
		self._build_component_index(components)

		# Phase 2: Validate references
		for node in nodes:
			if self.applies_to(node):
				node.accept(self)

	def _build_component_index(self, components):
		"""Build lookup structures for component tree navigation."""
		for component in components:
			# Store by path for direct lookup
			self.component_tree[component.path] = component

			# Index by name (multiple components can share names)
			if component.name not in self.component_by_name:
				self.component_by_name[component.name] = []
			self.component_by_name[component.name].append(component)

			# Build parent-child relationships
			parent_path = self._extract_parent_path(component.path)
			if parent_path:
				self.parent_map[component.path] = parent_path
				if parent_path not in self.children_map:
					self.children_map[parent_path] = []
				self.children_map[parent_path].append(component.path)

	def _extract_parent_path(self, component_path: str) -> Optional[str]:
		"""
		Extract parent path from component path.

		Examples:
			root.root.children[0].BadButton -> root.root
			root.root.children[0].Container.children[1].Button -> root.root.children[0].Container
			root.root -> None
		"""
		if '.children[' not in component_path:
			return None

		# Find the last .children[N].ComponentName segment
		# Pattern: .children[N].ComponentName
		# We want to remove this entire segment to get the parent
		match = re.search(r'(.*?)\.children\[\d+\]\.[^.]+$', component_path)
		if match:
			return match.group(1)

		return None

	def visit_expression_binding(self, node):
		"""Check expression bindings for component references."""
		if not self.validate_expressions:
			return

		expression = node.expression
		if not expression:
			return

		# Match {../path} or {.../path} patterns
		pattern = r'\{(\.\.+)/([^}]+)\}'

		for match in re.finditer(pattern, expression):
			dots = match.group(1)  # .. or ... or ....
			ref_path = match.group(2)  # Component.props.value or Path/To/Component.props.value

			# CRITICAL: Each dot beyond the first = one level up
			levels_up = len(dots) - 1

			# Extract component path (before .props or .position)
			component_ref = self._extract_component_reference(ref_path)

			# Validate
			self._validate_relative_reference(
				node.path, component_ref, levels_up, full_ref=expression, ref_type="expression"
			)

	def visit_property_binding(self, node):
		"""Check property bindings for component references."""
		if not self.validate_property_bindings:
			return

		target_path = node.target_path
		if not target_path or not target_path.startswith('.'):
			return  # Not a relative path

		# Match ../path or .../path patterns
		match = re.match(r'^(\.\.+)/(.+)$', target_path)
		if not match:
			return

		dots = match.group(1)
		ref_path = match.group(2)

		# CRITICAL: Each dot beyond the first = one level up
		levels_up = len(dots) - 1
		component_ref = self._extract_component_reference(ref_path)

		self._validate_relative_reference(
			node.path, component_ref, levels_up, full_ref=target_path, ref_type="property binding"
		)

	def _extract_component_reference(self, ref_path: str) -> str:
		"""
		Extract component path from reference.

		Examples:
			Button.props.enabled -> Button
			Container/Child.props.text -> Container/Child
			Component.position.display -> Component
			Switch1.custom.energized -> Switch1
		"""
		# Remove property access suffix
		for suffix in ['.props.', '.position.', '.meta.', '.custom.']:
			if suffix in ref_path:
				return ref_path.split(suffix)[0]

		return ref_path

	def visit_event_handler(self, node):
		"""Check event handler scripts for component references."""
		self._validate_script_references(node)

	def visit_message_handler(self, node):
		"""Check message handler scripts for component references."""
		self._validate_script_references(node)

	def visit_custom_method(self, node):
		"""Check custom method scripts for component references."""
		self._validate_script_references(node)

	def visit_transform(self, node):
		"""Check transform scripts for component references."""
		self._validate_script_references(node)

	def _validate_script_references(self, script_node):
		"""Validate component references in scripts."""
		if not self.validate_scripts:
			return

		script = script_node.script
		if not script:
			return

		# Pattern 1: self.getSibling('ComponentName')
		sibling_pattern = r"self\.getSibling\(['\"]([^'\"]+)['\"]\)"
		for match in re.finditer(sibling_pattern, script):
			name = match.group(1)
			self._validate_sibling_reference(script_node.path, name, script)

		# Pattern 2: .getChild('ComponentName') - includes chained calls
		self._validate_chained_navigation(script_node.path, script)

	def _validate_sibling_reference(self, script_path: str, sibling_name: str, _script: str):
		"""Validate a simple getSibling() reference."""
		component_path = self._get_component_path_from_source(script_path)
		resolved = self._find_sibling(component_path, sibling_name)

		if not resolved:
			self.add_violation(
				f"{script_path}: Script references non-existent sibling component "
				f"'{sibling_name}'"
			)

	def _validate_chained_navigation(self, script_path: str, script: str):
		"""Parse and validate chained navigation calls."""
		# Match chains starting with self
		chain_pattern = r'(self(?:\.parent)*(?:\.[a-zA-Z]+\([^)]*\))+)'

		for match in re.finditer(chain_pattern, script):
			chain = match.group(1)

			# Count parent references
			parent_count = chain.count('.parent')

			# Remove parent references to get method calls
			chain_without_parents = chain.replace('.parent', '')

			# Parse method calls
			method_pattern = r'\.([a-zA-Z]+)\(["\']([^"\']+)["\']\)'
			methods = list(re.finditer(method_pattern, chain_without_parents))

			if not methods:
				continue

			# Start navigation
			component_path = self._get_component_path_from_source(script_path)
			current_path = component_path

			# Navigate up for each .parent
			for _ in range(parent_count):
				current_path = self.parent_map.get(current_path)
				if not current_path:
					self.add_violation(f"{script_path}: Navigation chain goes beyond root: {chain}")
					break

			if not current_path:
				continue

			# Process method calls
			for method_match in methods:
				method = method_match.group(1)
				arg = method_match.group(2)

				if method == 'getSibling':
					current_path = self._find_sibling(current_path, arg)
					if not current_path:
						self.add_violation(
							f"{script_path}: Component '{arg}' not found as sibling in: {chain}"
						)
						break

				elif method == 'getChild':
					current_path = self._find_child(current_path, arg)
					if not current_path:
						self.add_violation(
							f"{script_path}: Component '{arg}' not found as child in: {chain}"
						)
						break

	def _parse_chain_steps(self, chain: str) -> List[Tuple[str, Optional[str]]]:
		"""
		Parse chain into steps.

		Examples:
			self.parent.getChild('A') -> [('parent', None), ('getChild', 'A')]
			self.getSibling('B').getChild('C') -> [('getSibling', 'B'), ('getChild', 'C')]
		"""
		steps = []

		# Match .parent
		parent_count = chain.count('.parent')
		steps.extend([('parent', None)] * parent_count)

		# Match method calls with arguments
		method_pattern = r'\.([a-zA-Z]+)\(["\']([^"\']+)["\']\)'
		for match in re.finditer(method_pattern, chain):
			method = match.group(1)
			arg = match.group(2)
			steps.append((method, arg))

		return steps

	def _validate_relative_reference(
		self, source_path: str, component_ref: str, levels_up: int, *, full_ref: str, ref_type: str
	):
		"""
		Validate a relative component reference.

		Args:
			source_path: Path of binding/script making the reference
			component_ref: Component reference (may contain / for nested paths)
			levels_up: Number of levels up (.. = 1, ... = 2, etc.)
			full_ref: Full reference string for error reporting (keyword-only)
			ref_type: Type of reference (keyword-only, e.g., "expression", "property binding")
		"""
		# Get component path from binding/script path
		component_path = self._get_component_path_from_source(source_path)

		# Navigate up the tree
		current_path = component_path
		for _ in range(levels_up):
			parent = self.parent_map.get(current_path)
			if not parent:
				self.add_violation(
					f"{source_path}: Relative {ref_type} '{full_ref}' "
					f"navigates above root component"
				)
				return
			current_path = parent

		# At this point, current_path is the parent context we want to search in
		# Parse reference path (may contain / for nested navigation)
		if '/' in component_ref:
			# Navigate down through path segments
			segments = component_ref.split('/')
			resolved = self._navigate_down_path(current_path, segments)
		else:
			# Single component name - find as child of the current (parent) context
			resolved = self._find_child(current_path, component_ref)

		if not resolved:
			self.add_violation(
				f"{source_path}: {ref_type.title()} references non-existent "
				f"component '{component_ref}' in: {full_ref}"
			)

	def _navigate_down_path(self, parent_path: str, segments: List[str]) -> Optional[str]:
		"""
		Navigate down the component tree through path segments.

		Example: segments = ['Container', 'Button']
			1. Find child 'Container' under parent_path
			2. Find child 'Button' under Container
		"""
		current_path = parent_path

		for segment in segments:
			# Find child with this name
			found = self._find_child(current_path, segment)
			if not found:
				return None
			current_path = found

		return current_path

	def _find_child(self, parent_path: str, child_name: str) -> Optional[str]:
		"""Find child component by name."""
		children = self.children_map.get(parent_path, [])
		for child_path in children:
			component = self.component_tree.get(child_path)
			if component and component.name == child_name:
				return child_path
		return None

	def _find_sibling(self, component_path: str, sibling_name: str) -> Optional[str]:
		"""Find sibling component by name."""
		parent = self.parent_map.get(component_path)
		if not parent:
			return None

		siblings = self.children_map.get(parent, [])
		for sibling_path in siblings:
			if sibling_path == component_path:
				continue  # Skip self
			component = self.component_tree.get(sibling_path)
			if component and component.name == sibling_name:
				return sibling_path
		return None

	def _get_component_path_from_source(self, source_path: str) -> str:
		"""
		Extract component path from binding or script path.

		Examples:
			propConfig.props.text.binding -> root
			root.children[0].events.component.onActionPerformed -> root.children[0]
			root.children[0].scripts.customMethods[0] -> root.children[0]
			root.root.children[1].Button2.propConfig.props.enabled -> root.root.children[1].Button2
		"""
		path = source_path

		# For propConfig paths, we need to find the component that owns this propConfig
		# The path structure is: root.root.children[N].ComponentName.propConfig.props.property
		# We need to extract: root.root.children[N].ComponentName
		if '.propConfig.' in path:
			# Split on .propConfig and take everything before it
			component_path = path.split('.propConfig.')[0]
			# This should be the full component path
			return component_path

		# For script paths (events, custom methods, etc.)
		# Find component path (before .props, .events, .scripts)
		for marker in ['.props.', '.events.', '.scripts.']:
			if marker in path:
				return path.split(marker)[0]

		# Fallback to longest matching component in tree
		for comp_path in sorted(self.component_tree.keys(), key=len, reverse=True):
			if path.startswith(comp_path):
				return comp_path

		# Ultimate fallback
		return 'root'
