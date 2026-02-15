"""
Finds references to component names within view.json data.

Searches expression bindings, property bindings, and scripts for
patterns like:
  - Expression: {../ComponentName.props.x}
  - Property binding: ../ComponentName.props.x
  - Script: self.getSibling('ComponentName'), self.parent.getChild('ComponentName')

Used by the fix framework to determine whether renaming a component
requires updating references (unsafe fix) or is self-contained (safe fix).
"""

import re
from dataclasses import dataclass
from typing import List
from .fix_operations import FixOperation, FixOperationType
from .path_translator import PathTranslator


@dataclass
class ComponentReference:
	"""A reference to a component name found in the view data."""
	json_path: list  # Path to the value containing the reference
	ref_type: str  # "expression", "property_binding", or "script"
	context: str  # The full string value containing the reference


class ComponentReferenceFinder:
	"""
	Finds all references to a given component name in the flattened JSON.

	Searches through all string values in the JSON data for patterns
	that reference the component.
	"""

	# Expression patterns: {../Name.props.x} or {.../Container/Name.props.x}
	EXPRESSION_PATTERN = r'\{{1,2}(\.\.+)/([^}]+)\}{1,2}'

	# Property binding patterns: ../Name.props.x
	PROPERTY_BINDING_PATTERN = r'^(\.\.+)/(.+)$'

	# Script patterns
	SCRIPT_PATTERNS = [
		r"self\.getSibling\(['\"]({name})['\"]\)",
		r"self\.getChild\(['\"]({name})['\"]\)",
		r"\.getSibling\(['\"]({name})['\"]\)",
		r"\.getChild\(['\"]({name})['\"]\)",
	]

	def __init__(self, flattened_json: dict, path_translator: PathTranslator):
		self.flattened_json = flattened_json
		self.path_translator = path_translator

	def find_references(self, component_name: str) -> List[ComponentReference]:
		"""
		Find all references to a component name in the view.

		Args:
			component_name: The name to search for.

		Returns:
			List of ComponentReference objects describing where the name is used.
		"""
		references = []

		for model_path, value in self.flattened_json.items():
			if not isinstance(value, str):
				continue

			# Check expression bindings
			if self._has_expression_reference(value, component_name):
				json_path = self.path_translator.model_path_to_json_path(model_path)
				if json_path:
					references.append(
						ComponentReference(
							json_path=json_path, ref_type="expression", context=value
						)
					)
				continue

			# Check property binding paths
			if self._has_property_binding_reference(value, component_name):
				json_path = self.path_translator.model_path_to_json_path(model_path)
				if json_path:
					references.append(
						ComponentReference(
							json_path=json_path, ref_type="property_binding", context=value
						)
					)
				continue

			# Check script references
			if self._has_script_reference(value, component_name):
				json_path = self.path_translator.model_path_to_json_path(model_path)
				if json_path:
					references.append(
						ComponentReference(
							json_path=json_path, ref_type="script", context=value
						)
					)

		return references

	def _has_expression_reference(self, value: str, component_name: str) -> bool:
		"""Check if a string value contains an expression reference to the component."""
		for match in re.finditer(self.EXPRESSION_PATTERN, value):
			ref_path = match.group(2)
			# ref_path could be "ComponentName.props.x" or "Container/ComponentName.props.x"
			# Check if component_name appears as a path segment
			segments = re.split(r'[./]', ref_path)
			if component_name in segments:
				return True
		return False

	def _has_property_binding_reference(self, value: str, component_name: str) -> bool:
		"""Check if a string value is a property binding referencing the component."""
		match = re.match(self.PROPERTY_BINDING_PATTERN, value)
		if not match:
			return False
		ref_path = match.group(2)
		segments = re.split(r'[./]', ref_path)
		return component_name in segments

	def _has_script_reference(self, value: str, component_name: str) -> bool:
		"""Check if a string value contains script references to the component."""
		for pattern_template in self.SCRIPT_PATTERNS:
			pattern = pattern_template.replace('{name}', re.escape(component_name))
			if re.search(pattern, value):
				return True
		return False

	def has_self_name_binding(self, component_model_path: str) -> bool:
		"""
		Check if a component has any binding that uses 'this.meta.name'.

		Renaming such a component would change the runtime return value of
		this.meta.name, making the fix unsafe.

		Args:
			component_model_path: Model path of the component to check.

		Returns:
			True if the component has a this.meta.name binding.
		"""
		for model_path, value in self.flattened_json.items():
			if not model_path.startswith(component_model_path):
				continue
			if not isinstance(value, str):
				continue
			if 'this.meta.name' in value:
				return True
		return False

	def build_rename_operations(self, old_name: str, new_name: str,
					references: List[ComponentReference]) -> List[FixOperation]:
		"""
		Generate STRING_REPLACE operations for each reference found.

		Args:
			old_name: Current component name.
			new_name: New component name.
			references: References found by find_references().

		Returns:
			List of FixOperation objects for STRING_REPLACE.
		"""
		operations = []
		for ref in references:
			if ref.ref_type == "expression":
				# Replace component name in expression references
				# Patterns: ../OldName. or /OldName. or /OldName}
				operations.append(
					FixOperation(
						operation=FixOperationType.STRING_REPLACE, json_path=ref.json_path,
						old_substring=old_name, new_substring=new_name, description=
						f"Update {ref.ref_type} reference: '{old_name}' -> '{new_name}'"
					)
				)
			elif ref.ref_type == "property_binding":
				operations.append(
					FixOperation(
						operation=FixOperationType.STRING_REPLACE, json_path=ref.json_path,
						old_substring=old_name, new_substring=new_name, description=
						f"Update property binding reference: '{old_name}' -> '{new_name}'"
					)
				)
			elif ref.ref_type == "script":
				operations.append(
					FixOperation(
						operation=FixOperationType.STRING_REPLACE, json_path=ref.json_path,
						old_substring=old_name, new_substring=new_name,
						description=f"Update script reference: '{old_name}' -> '{new_name}'"
					)
				)
		return operations
