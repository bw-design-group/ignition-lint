"""
Data model for auto-fix operations.

Fixes are declarative data objects describing JSON path modifications.
This makes them serializable, reviewable in dry-run mode, and testable.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, List, Optional


class FixOperationType(Enum):
	"""Types of fix operations that can be applied to JSON data."""
	SET_VALUE = "set_value"
	STRING_REPLACE = "string_replace"


@dataclass
class FixOperation:
	"""
	A single atomic operation to apply to JSON data.

	For SET_VALUE: replaces the value at json_path with new_value.
	For STRING_REPLACE: replaces old_substring with new_substring in the string at json_path.
	"""
	operation: FixOperationType
	json_path: list  # e.g., ["root", "children", 0, "meta", "name"]
	old_value: Any = None
	new_value: Any = None
	old_substring: str = ""
	new_substring: str = ""
	description: str = ""

	def format_path(self) -> str:
		"""Format json_path as a human-readable string."""
		parts = []
		for segment in self.json_path:
			if isinstance(segment, int):
				parts.append(f"[{segment}]")
			else:
				if parts:
					parts.append(f" > {segment}")
				else:
					parts.append(str(segment))
		return "".join(parts)


@dataclass
class Fix:
	"""
	A collection of operations that together fix a single violation.

	Attributes:
		rule_name: Name of the rule that generated this fix.
		violation_message: The original violation message this fix addresses.
		description: Human-readable description of what the fix does.
		operations: List of operations to apply.
		is_safe: True if fix only modifies the violating node (no reference updates).
		safety_notes: Explanation of why a fix is unsafe (e.g., what references are updated).
	"""
	rule_name: str
	violation_message: str
	description: str
	operations: List[FixOperation] = field(default_factory=list)
	is_safe: bool = True
	safety_notes: Optional[str] = None
