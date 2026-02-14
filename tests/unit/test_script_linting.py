# pylint: disable=import-error
"""
Unit tests for the PylintScriptRule.
Tests script linting functionality.
"""

import unittest
from typing import Dict, Any

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, load_test_view


class TestPylintScriptRule(BaseRuleTest):
	"""Test script linting with pylint."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config("PylintScriptRule")

	def test_basic_script_linting(self):
		"""Test basic script linting functionality."""
		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, self.rule_config)

		# Just verify the rule runs without crashing
		script_errors = self.get_errors_for_rule("PylintScriptRule")
		self.assertIsInstance(script_errors, list)

	def test_multiple_view_files(self):
		"""Test script linting on multiple view files."""
		test_cases = ["PascalCase", "camelCase", "ExpressionBindings"]

		for case in test_cases:
			with self.subTest(case=case):
				try:
					view_file = load_test_view(self.test_cases_dir, case)
					self.run_lint_on_file(view_file, self.rule_config)
					script_errors = self.get_errors_for_rule("PylintScriptRule")
					self.assertIsInstance(script_errors, list)
				except FileNotFoundError:
					self.skipTest(f"Test case {case} not found")

	def test_script_with_commented_first_line(self):
		"""Test that scripts with commented first lines are indented correctly."""
		from ignition_lint.model.node_types import TransformScript

		# Script with comment as first line (NOT indented - this is the problematic case)
		# The comment and code both have no leading tabs/spaces
		script_content = """#    datasetPath = '[default]DeviceNames'
dataset = value
dataset = system.dataset.toPyDataSet(dataset)

for row in range(dataset.rowCount):
    if dataset[row][0] == self.view.params.row:
        return dataset[row][1]

#    return value"""

		# Create a TransformScript node
		script_node = TransformScript(path="test.path", script=script_content)

		# Get formatted script
		formatted = script_node.get_formatted_script()

		# Verify the function definition is present
		self.assertIn("def transform(self, value):", formatted)

		# Split into lines and check indentation
		lines = formatted.split('\n')

		# Find the first comment line (after function def)
		comment_line = next((line for line in lines[1:] if line.strip().startswith('#')), None)
		self.assertIsNotNone(comment_line, "Comment line should be present")

		# Comment should be indented with exactly one tab (not double-tabbed)
		self.assertTrue(
			comment_line.startswith('\t#'),
			f"Comment should be indented with one tab, got: {repr(comment_line)}"
		)

		# Verify subsequent code line is also properly indented (and not double-indented)
		code_line = next((line for line in lines if 'dataset = value' in line), None)
		self.assertIsNotNone(code_line, "Code line should be present")
		self.assertTrue(
			code_line.startswith('\tdataset'),
			f"Code line should be indented with one tab, got: {repr(code_line)}"
		)

		# Verify nested code maintains relative indentation
		nested_line = next((line for line in lines if 'if dataset[row][0]' in line), None)
		self.assertIsNotNone(nested_line, "Nested code line should be present")
		# Should have base tab + 4 spaces for nested indentation
		self.assertTrue(
			nested_line.startswith('\t    if') or nested_line.count('\t') == 1,
			f"Nested code should maintain relative indentation, got: {repr(nested_line)}"
		)

	def test_script_already_indented_with_comment_first(self):
		"""Test that already-indented scripts with commented first lines are preserved."""
		from ignition_lint.model.node_types import TransformScript

		# Script with comment as first line (already properly indented with tabs)
		script_content = """\t#    datasetPath = '[default]DeviceNames'
\tdataset = value
\tdataset = system.dataset.toPyDataSet(dataset)

\tfor row in range(dataset.rowCount):
\t    if dataset[row][0] == self.view.params.row:
\t        return dataset[row][1]

\t#    return value"""

		# Create a TransformScript node
		script_node = TransformScript(path="test.path", script=script_content)

		# Get formatted script
		formatted = script_node.get_formatted_script()

		# Verify the function definition is present
		self.assertIn("def transform(self, value):", formatted)

		# Split into lines and check indentation
		lines = formatted.split('\n')

		# Find the first comment line (after function def)
		comment_line = next((line for line in lines[1:] if line.strip().startswith('#')), None)
		self.assertIsNotNone(comment_line, "Comment line should be present")

		# Comment should still be indented with one tab (not double-tabbed)
		self.assertEqual(
			comment_line.count('\t'), 1, f"Comment should have exactly one tab, got: {repr(comment_line)}"
		)

		# Verify subsequent code line also has correct indentation
		code_line = next((line for line in lines if 'dataset = value' in line), None)
		self.assertIsNotNone(code_line, "Code line should be present")
		self.assertEqual(
			code_line.count('\t'), 1, f"Code line should have exactly one tab, got: {repr(code_line)}"
		)

	def test_script_with_blank_lines_and_comments(self):
		"""Test that scripts with blank lines followed by comments are handled correctly."""
		from ignition_lint.model.node_types import TransformScript

		# Script with blank line, then comment, then blank line, then comment, then code
		# This tests that the logic traverses multiple iterations to find the first real code line
		script_content = """
# First comment

# Second comment

dataset = value
dataset = system.dataset.toPyDataSet(dataset)

for row in range(dataset.rowCount):
    if dataset[row][0] == self.view.params.row:
        return dataset[row][1]"""

		# Create a TransformScript node
		script_node = TransformScript(path="test.path", script=script_content)

		# Get formatted script
		formatted = script_node.get_formatted_script()

		# Verify the function definition is present
		self.assertIn("def transform(self, value):", formatted)

		# Split into lines and check indentation
		lines = formatted.split('\n')

		# Find the first comment line (after function def)
		comment_line = next((line for line in lines[1:] if line.strip().startswith('#')), None)
		self.assertIsNotNone(comment_line, "Comment line should be present")

		# Comment should be indented with exactly one tab
		self.assertTrue(
			comment_line.startswith('\t#'),
			f"Comment should be indented with one tab, got: {repr(comment_line)}"
		)

		# Verify code line is properly indented (not double-indented)
		code_line = next((line for line in lines if 'dataset = value' in line), None)
		self.assertIsNotNone(code_line, "Code line should be present")
		self.assertTrue(
			code_line.startswith('\tdataset'),
			f"Code line should be indented with one tab, got: {repr(code_line)}"
		)


if __name__ == "__main__":
	unittest.main()
