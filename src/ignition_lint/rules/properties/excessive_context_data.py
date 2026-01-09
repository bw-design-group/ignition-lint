"""
Rule to detect excessive context data stored in custom properties.

This rule identifies large arrays in custom properties that should be stored in databases
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

DETECTION:
- Scans flattened JSON for array patterns in custom.* properties
- Counts array indices per property path
- Flags properties exceeding the threshold
"""

import re
from typing import Dict, Any
from ..common import LintingRule
from ..registry import register_rule


@register_rule
class ExcessiveContextDataRule(LintingRule):
	"""Detects large arrays in custom properties that should be stored in databases."""

	def __init__(self, max_array_size=50, severity="error"):
		"""
		Initialize the rule.

		Args:
			max_array_size: Maximum allowed array size in custom properties (default: 50)
			severity: Severity level - "error" (default) or "warning"
		"""
		super().__init__(set(), severity)  # Empty set - we process flattened JSON directly
		self.max_array_size = max_array_size
		self.flattened_json: Dict[str, Any] = {}

	@property
	def error_message(self) -> str:
		return "Detection of excessive context data in custom properties"

	def set_flattened_json(self, flattened_json: Dict[str, Any]):
		"""Set the flattened JSON for analysis."""
		self.flattened_json = flattened_json

	def process_nodes(self, nodes):
		"""Process flattened JSON to detect large arrays in custom properties."""
		# Reset errors for this view
		self.errors = []
		self.warnings = []

		# Scan for large arrays
		self._detect_large_arrays()

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
