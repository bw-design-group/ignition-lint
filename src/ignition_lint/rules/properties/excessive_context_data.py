"""
Rule to detect excessive context data stored in custom properties.

This rule identifies excessive data stored in custom properties that should be stored in databases
instead of the view JSON. Storing large datasets in view JSON causes:
- Performance issues (slow loading, slow model building)
- Memory bloat
- Poor maintainability
- Violates separation of concerns (data vs. presentation)

BEST PRACTICES:
- Custom properties should contain configuration, not data
- Arrays with > 50 items are considered excessive
- Use databases, named queries, or tag historian for large datasets
- Views should fetch data at runtime, not store it statically

DETECTION METHODS:
1. Array Size: Detects arrays with too many items (e.g., custom.filteredData[784])
2. Property Breadth: Detects too many sibling properties at the same level
3. Nesting Depth: Detects overly deep nesting structures
4. Data Points: Detects total volume of data stored in custom properties
"""

import re
from typing import Dict, Any, Set
from collections import defaultdict
from ..common import LintingRule
from ..registry import register_rule


@register_rule
class ExcessiveContextDataRule(LintingRule):
	"""Detects excessive context data in custom properties using multiple detection methods."""

	def __init__(
		self,
		max_array_size=50,
		max_sibling_properties=50,
		max_nesting_depth=5,
		max_data_points=1000,
		severity="error"
	):
		"""
		Initialize the rule.

		Args:
			max_array_size: Maximum allowed array size in custom properties (default: 50)
			max_sibling_properties: Maximum sibling properties at the same level (default: 50)
			max_nesting_depth: Maximum nesting depth in custom properties (default: 5)
			max_data_points: Maximum total data points in custom properties (default: 1000)
			severity: Severity level - "error" (default) or "warning"
		"""
		super().__init__(set(), severity)  # Empty set - we process flattened JSON directly
		self.max_array_size = max_array_size
		self.max_sibling_properties = max_sibling_properties
		self.max_nesting_depth = max_nesting_depth
		self.max_data_points = max_data_points
		self.flattened_json: Dict[str, Any] = {}

	@property
	def error_message(self) -> str:
		return "Detection of excessive context data in custom properties"

	def set_flattened_json(self, flattened_json: Dict[str, Any]):
		"""Set the flattened JSON for analysis."""
		self.flattened_json = flattened_json

	def process_nodes(self, nodes):
		"""Process flattened JSON to detect excessive context data."""
		# Reset errors for this view
		self.errors = []
		self.warnings = []

		# Run all detection methods
		self._detect_large_arrays()
		self._detect_excessive_breadth()
		self._detect_excessive_depth()
		self._detect_excessive_data_points()

	def _detect_large_arrays(self):
		"""Scan flattened JSON for large arrays in custom properties."""
		# Pattern to match array indices: custom.property[123]
		array_pattern = re.compile(r'^(custom\.[^\[]+)\[(\d+)\]')

		# Track maximum index found for each array property
		array_sizes: Dict[str, int] = {}

		for path in self.flattened_json.keys():
			match = array_pattern.match(path)
			if match:
				property_path = match.group(1)  # e.g., "custom.filteredData"
				index = int(match.group(2))     # e.g., 123

				# Track the maximum index seen (array size = max_index + 1)
				if property_path not in array_sizes:
					array_sizes[property_path] = index
				else:
					array_sizes[property_path] = max(array_sizes[property_path], index)

		# Check which arrays exceed the threshold
		for property_path, max_index in array_sizes.items():
			array_size = max_index + 1  # Array size is max_index + 1

			if array_size > self.max_array_size:
				# Extract just the property name for cleaner error message
				property_name = property_path.replace('custom.', '')

				message = (
					f"{property_path}: Custom property '{property_name}' contains {array_size} items. "
					f"Large datasets should be stored in databases, not view JSON. "
					f"Maximum recommended: {self.max_array_size} items."
				)
				self.add_violation(message)

	def _detect_excessive_breadth(self):
		"""Detect too many sibling properties at the same level."""
		# Count children for each parent path
		# E.g., custom.data.device1, custom.data.device2 -> custom.data has 2 children
		sibling_counts: Dict[str, Set[str]] = defaultdict(set)

		for path in self.flattened_json.keys():
			if not path.startswith('custom.'):
				continue

			# Strip array indices for grouping: custom.data[0].value -> custom.data.value
			normalized_path = re.sub(r'\[\d+\]', '', path)

			# Extract parent and child
			# custom.data.device1.name -> parent: custom.data, child: device1
			parts = normalized_path.split('.')
			if len(parts) > 2:  # At least custom.parent.child
				for i in range(2, len(parts)):  # Start from custom.X level
					parent = '.'.join(parts[:i])
					child = parts[i]
					sibling_counts[parent].add(child)

		# Check which parents exceed the threshold
		for parent_path, children in sibling_counts.items():
			child_count = len(children)
			if child_count > self.max_sibling_properties:
				message = (
					f"{parent_path}: Contains {child_count} sibling properties. "
					f"Large flat structures should be stored in databases, not view JSON. "
					f"Maximum recommended: {self.max_sibling_properties} siblings."
				)
				self.add_violation(message)

	def _detect_excessive_depth(self):
		"""Detect overly deep nesting in custom properties."""
		max_depth_found = 0
		deepest_path = ""

		for path in self.flattened_json.keys():
			if not path.startswith('custom.'):
				continue

			# Remove array indices for depth calculation: custom.data[0].value -> custom.data.value
			normalized_path = re.sub(r'\[\d+\]', '', path)

			# Count depth: custom.a.b.c = 3 levels deep (a=1, b=2, c=3)
			# Split and count parts after "custom"
			parts = normalized_path.split('.')
			depth = len(parts) - 1  # -1 because "custom" itself is the root

			if depth > max_depth_found:
				max_depth_found = depth
				deepest_path = normalized_path

		# Check if depth exceeds threshold
		if max_depth_found > self.max_nesting_depth:
			message = (
				f"{deepest_path}: Custom properties are nested {max_depth_found} levels deep. "
				f"Deeply nested structures indicate complex data that should be in databases. "
				f"Maximum recommended: {self.max_nesting_depth} levels."
			)
			self.add_violation(message)

	def _detect_excessive_data_points(self):
		"""Detect total volume of data stored in custom properties."""
		# Count all flattened paths under custom.*
		custom_paths = [path for path in self.flattened_json.keys() if path.startswith('custom.')]
		data_point_count = len(custom_paths)

		if data_point_count > self.max_data_points:
			message = (
				f"custom: Contains {data_point_count} total data points across all custom properties. "
				f"Large volumes of data should be stored in databases, not view JSON. "
				f"Maximum recommended: {self.max_data_points} data points."
			)
			self.add_violation(message)
