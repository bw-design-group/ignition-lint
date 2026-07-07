"""
Finds references to component names within view.json data.

Detection and rewriting are grammar-driven by common.reference_parser — the
same grammar the validation rules consume — covering:
  - Expressions: {./Child.props.x}, {../Sibling.props.x}, {.../Up/Two.props.x}
	and absolute {/root/Container/Component.props.x}
  - Property binding paths: the same forms as whole values
  - Scripts: self.getSibling('Name') / .getChild('Name') via tokenization

Used by the fix framework to determine whether renaming a component requires
updating references (unsafe fix) or is self-contained (safe fix), and to
build the reference-update operations for --fix-unsafe.

Rewrites use maximal-context replacement (issue #115): each operation's
old_substring is the entire reference text, never the bare component name,
so renaming 'data label' can never corrupt '{../data label 2.props.text}',
the display literal 'data label: ', or a comment mentioning the name.
"""

from dataclasses import dataclass
from typing import List
from .fix_operations import FixOperation, FixOperationType
from .path_translator import PathTranslator
from .reference_parser import (
	free_text_mentions_component,
	is_script_key,
	parse_expression_references,
	parse_property_path,
	parse_script_references,
)


@dataclass
class ComponentReference:
	"""A reference to a component name found in the view data."""
	json_path: list  # Path to the value containing the reference
	ref_type: str  # "expression", "property_binding", "script" or "free_text"
	context: str  # The full string value containing the reference
	old_text: str = ''  # Exact reference text to replace (maximal context)
	new_text: str = ''  # Replacement text with the component renamed
	rewritable: bool = True  # False -> counts for safety only, never rewritten


class ComponentReferenceFinder:
	"""
	Finds all references to a given component name in the flattened JSON.

	Searches every string value in the view — scripts are recognized by key
	(so bodies in unmodeled locations such as extensionFunctions are still
	seen) and everything else is checked against the path-reference grammar.
	"""

	def __init__(self, flattened_json: dict, path_translator: PathTranslator):
		self.flattened_json = flattened_json
		self.path_translator = path_translator

	def find_references(self, component_name: str) -> List[ComponentReference]:
		"""
		Find all references to a component name in the view.

		Args:
			component_name: The current component name to search for.

		Returns:
			List of ComponentReference objects describing where the name is
			used. References marked rewritable=False make a rename unsafe but
			cannot be auto-updated.
		"""
		references = []
		for model_path, value in self.flattened_json.items():
			if not isinstance(value, str) or not value:
				continue
			if is_script_key(model_path):
				references.extend(self._script_references(model_path, value, component_name))
			else:
				references.extend(self._value_references(model_path, value, component_name))
		return references

	def _script_references(self, model_path: str, script: str, component_name: str) -> List[ComponentReference]:
		"""Collect navigation-call references from a script body."""
		references = []
		json_path = None
		for script_ref in parse_script_references(script):
			if script_ref.component_name != component_name:
				continue
			if json_path is None:
				json_path = self.path_translator.model_path_to_json_path(model_path)
				if not json_path:
					return references
			references.append(
				ComponentReference(
					json_path=json_path, ref_type="script", context=script,
					old_text=script_ref.full_text, new_text='', rewritable=script_ref.rewritable
				)
			)
		return references

	def _value_references(self, model_path: str, value: str, component_name: str) -> List[ComponentReference]:
		"""Collect path-grammar references (and conservative free-text hits)."""
		references = []
		json_path = None

		def resolve_path():
			nonlocal json_path
			if json_path is None:
				json_path = self.path_translator.model_path_to_json_path(model_path)
			return json_path

		property_ref = parse_property_path(value)
		if property_ref and property_ref.mentions(component_name):
			if resolve_path():
				references.append(
					ComponentReference(
						json_path=json_path, ref_type="property_binding", context=value,
						old_text=property_ref.full_text
					)
				)
			return references

		for expr_ref in parse_expression_references(value):
			if not expr_ref.mentions(component_name):
				continue
			if not resolve_path():
				return references
			references.append(
				ComponentReference(
					json_path=json_path, ref_type="expression", context=value,
					old_text=expr_ref.full_text
				)
			)
		if references:
			return references

		# Not a script key and not a recognized reference: navigation-call
		# patterns or runScript() payloads here still make a rename unsafe,
		# but are never rewritten (defense in depth, issues #114/#115).
		if free_text_mentions_component(value, component_name):
			if resolve_path():
				references.append(
					ComponentReference(
						json_path=json_path, ref_type="free_text", context=value,
						rewritable=False
					)
				)
		return references

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
		Generate STRING_REPLACE operations for each rewritable reference.

		Every operation replaces the full reference text (maximal context),
		with the component's path segments or quoted argument renamed inside
		it — never a bare-name substring (issue #115).

		Args:
			old_name: Current component name.
			new_name: New component name.
			references: References found by find_references().

		Returns:
			List of FixOperation objects for STRING_REPLACE.
		"""
		operations = []
		seen = set()
		for ref in references:
			if not ref.rewritable or not ref.old_text:
				continue
			new_text = self._renamed_reference_text(ref, old_name, new_name)
			if new_text == ref.old_text:
				continue
			key = (str(ref.json_path), ref.old_text, new_text)
			if key in seen:
				continue
			seen.add(key)
			operations.append(
				FixOperation(
					operation=FixOperationType.STRING_REPLACE, json_path=ref.json_path,
					old_substring=ref.old_text, new_substring=new_text,
					description=f"Update {ref.ref_type} reference: '{old_name}' -> '{new_name}'"
				)
			)
		return operations

	@staticmethod
	def _renamed_reference_text(ref: ComponentReference, old_name: str, new_name: str) -> str:
		"""Rebuild a reference's text with the component renamed in place."""
		if ref.ref_type == "script":
			for script_ref in parse_script_references(ref.old_text):
				if script_ref.component_name == old_name:
					return script_ref.renamed_text(old_name, new_name)
			return ref.old_text
		parsed = parse_property_path(ref.old_text)
		if parsed is None:
			expressions = parse_expression_references(ref.old_text)
			parsed = expressions[0] if expressions else None
		if parsed is None:
			return ref.old_text
		return parsed.renamed_text(old_name, new_name)
