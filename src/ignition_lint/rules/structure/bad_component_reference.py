# pylint: disable=import-error
"""
Rule to detect bad Perspective component references.

This rule identifies usage of object traversal methods and properties that create
brittle dependencies on view structure. Based on Ignition documentation, these patterns
should be avoided in favor of view.custom properties or message handling.
"""

from ..common import LintingRule
from ...model.node_types import NodeType, ALL_SCRIPTS


class BadComponentReferenceRule(LintingRule):
	"""
	Detects bad component object traversal patterns in scripts and expressions.

	Flags usage of:
	- .getSibling() / .getSibling(string)
	- .getParent() / .parent
	- .getChild(string) / .children / .getChildren()

	These create tight coupling to view structure. Use view.custom properties
	or message handling instead for better maintainability.
	"""

	def __init__(self, forbidden_patterns=None, case_sensitive=True, severity="error"):
		"""Initialize the rule targeting scripts and expression bindings."""
		# Target both script types and expression bindings
		target_types = ALL_SCRIPTS | {NodeType.EXPRESSION_BINDING}
		super().__init__(target_types, severity)
		# Configure patterns to detect (methods and properties)
		self.forbidden_patterns = forbidden_patterns or [
			# Method calls (with parentheses)
			'.getSibling(',
			'.getParent(',
			'.getChild(',
			'.getChildren(',
			# Property access (without parentheses) - more specific patterns
			'self.parent.',
			'self.children.',
			'self.parent)',
			'self.children)',
			'self.parent,',
			'self.children,',
			'self.parent\n',
			'self.children\n',
			'self.parent\r',
			'self.children\r',
			'../',  # Relative path traversal in expressions
			'./',  # Current path traversal in expressions
		]
		# Allow case-insensitive matching
		self.case_sensitive = case_sensitive

	@property
	def error_message(self) -> str:
		"""Return the error message for this rule."""
		return (
			"Avoid object traversal patterns (.getSibling, .getParent, .getChild, "
			".parent, .children) as they create brittle dependencies on view structure. "
			"Use view.custom properties or message handling for better maintainability."
		)

	def visit_message_handler(self, node):
		"""Check message handler scripts for bad component references."""
		self._check_content(node.script, node.path, "script")

	def visit_custom_method(self, node):
		"""Check custom method scripts for bad component references."""
		self._check_content(node.script, node.path, "script")

	def visit_transform(self, node):
		"""Check transform scripts for bad component references."""
		self._check_content(node.script, node.path, "script")

	def visit_event_handler(self, node):
		"""Check event handler scripts for bad component references."""
		self._check_content(node.script, node.path, "script")

	def visit_expression_binding(self, node):
		"""Check expression bindings for bad component references."""
		if hasattr(node, 'expression') and node.expression:
			self._check_content(node.expression, node.path, "expression")

	def _check_content(self, content, path, content_type):
		"""Check content for forbidden component reference patterns."""
		if not content:
			return

		# Prepare content for checking
		check_content = content
		if not self.case_sensitive:
			check_content = content.lower()
			patterns_to_check = [pattern.lower() for pattern in self.forbidden_patterns]
		else:
			patterns_to_check = self.forbidden_patterns

		# Find all matching patterns for better error reporting
		found_patterns = []
		for i, pattern in enumerate(patterns_to_check):
			if pattern in check_content:
				# Get the original pattern name for reporting
				original_pattern = self.forbidden_patterns[i]
				found_patterns.append(original_pattern)

		# Report findings (only once per content item)
		if found_patterns:
			# Show the first pattern found, but mention if there are multiple
			main_pattern = found_patterns[0]
			if len(found_patterns) > 1:
				pattern_msg = f"'{main_pattern}' and {len(found_patterns)-1} other object traversal pattern(s)"
			else:
				pattern_msg = f"'{main_pattern}'"

			self.add_violation(
				f"{path}: {content_type.title()} contains {pattern_msg} which creates "
				f"brittle view structure dependencies. Consider using view.custom "
				f"properties or message handling for component communication instead."
			)
