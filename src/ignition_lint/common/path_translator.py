"""
Translates between model paths (used by linting rules) and JSON dict paths
(used to access/modify the actual JSON data).

Model paths include component names from meta.name that don't exist as JSON
dict keys. For example:
    Model path: root.root.children[0].BadButton
    JSON path:  ["root", "children", 0]

This module bridges that gap so fix operations can target the correct
locations in the original JSON data.
"""

from collections import OrderedDict
from typing import Any, List, Optional


class PathTranslator:
	"""
	Builds bidirectional mappings between model paths and JSON dict access paths.

	Walks the JSON tree in the same order as flatten_json / _get_component_path
	to record both model paths and corresponding dict access paths.
	"""

	def __init__(self, json_data: OrderedDict):
		self.json_data = json_data
		# model_path -> json_path (list of keys/indices)
		self._model_to_json = {}
		# Also store component model_path -> json_path to its meta.name
		self._component_name_paths = {}
		self._build_mappings(json_data, "", [])

	def _build_mappings(self, data, model_path: str, json_path: list):
		"""
		Recursively walk the JSON tree, mirroring flatten_json logic,
		to build path mappings.
		"""
		if isinstance(data, dict):
			# Mirror _get_component_path: if dict has meta.name, include it in model path
			component_name = data.get('meta', {}).get('name')
			if component_name:
				new_model_path = f"{model_path}.{component_name}" if model_path else component_name
				# Record: this model path (with component name) maps to this json path
				self._model_to_json[new_model_path] = list(json_path)
				# Record where meta.name lives for this component
				self._component_name_paths[new_model_path] = list(json_path) + ['meta', 'name']
				model_path = new_model_path

			for key, value in data.items():
				child_model_path = f"{model_path}.{key}" if model_path else key
				child_json_path = json_path + [key]
				if isinstance(value, dict):
					self._build_mappings(value, child_model_path, child_json_path)
				elif isinstance(value, list):
					self._build_list_mappings(value, child_model_path, child_json_path)
				else:
					self._model_to_json[child_model_path] = child_json_path

		elif isinstance(data, list):
			self._build_list_mappings(data, model_path, json_path)

	def _build_list_mappings(self, items: list, model_path: str, json_path: list):
		"""Build mappings for list items."""
		for index, item in enumerate(items):
			item_model_path = f"{model_path}[{index}]"
			item_json_path = json_path + [index]
			if isinstance(item, (dict, list)):
				self._build_mappings(item, item_model_path, item_json_path)
			else:
				self._model_to_json[item_model_path] = item_json_path

	def model_path_to_json_path(self, model_path: str) -> Optional[list]:
		"""
		Convert a model path to a JSON dict access path.

		Returns None if the model path is not found.
		"""
		return self._model_to_json.get(model_path)

	def get_component_name_path(self, component_model_path: str) -> Optional[list]:
		"""
		Get the JSON path to a component's meta.name field.

		Args:
			component_model_path: Model path of the component
				(e.g., "root.root.children[0].BadButton")

		Returns:
			JSON path list to meta.name (e.g., ["root", "children", 0, "meta", "name"]),
			or None if not found.
		"""
		return self._component_name_paths.get(component_model_path)

	def get_value(self, json_path: list) -> Any:
		"""Read value at a JSON path from the original dict."""
		current = self.json_data
		for key in json_path:
			if isinstance(current, dict):
				current = current[key]
			elif isinstance(current, list):
				current = current[key]
			else:
				raise KeyError(f"Cannot navigate into {type(current)} at path {json_path}")
		return current

	def set_value(self, json_path: list, value: Any):
		"""Set value at a JSON path in the original dict."""
		current = self.json_data
		for key in json_path[:-1]:
			if isinstance(current, dict):
				current = current[key]
			elif isinstance(current, list):
				current = current[key]
			else:
				raise KeyError(f"Cannot navigate into {type(current)} at path {json_path}")
		last_key = json_path[-1]
		if isinstance(current, dict):
			current[last_key] = value
		elif isinstance(current, list):
			current[last_key] = value
		else:
			raise KeyError(f"Cannot set value in {type(current)} at path {json_path}")

	def find_model_paths_by_prefix(self, prefix: str) -> List[str]:
		"""Find all model paths that start with the given prefix."""
		return [path for path in self._model_to_json if path.startswith(prefix)]

	def get_all_component_paths(self) -> List[str]:
		"""Get all model paths that correspond to components (have meta.name)."""
		return list(self._component_name_paths.keys())

	def string_replace_at(self, json_path: list, old_substring: str, new_substring: str) -> bool:
		"""
		Replace a substring within a string value at the given JSON path.

		Returns True if replacement was made, False otherwise.
		"""
		value = self.get_value(json_path)
		if not isinstance(value, str):
			return False
		if old_substring not in value:
			return False
		new_value = value.replace(old_substring, new_substring)
		self.set_value(json_path, new_value)
		return True
