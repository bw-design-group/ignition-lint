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

	def test_script_with_mixed_tabs_and_spaces(self):
		"""Test that scripts mixing tabs and spaces are detected with clear error message."""
		# Create a test view with a script that mixes tabs and spaces
		view_content = {
			"custom": {},
			"params": {},
			"propConfig": {
				"custom.testProp": {
					"binding": {
						"type": "tag",
						"config": {
							"tagPath": "[default]TestTag"
						},
						"transforms": [{
							"type": "script",
							# Script with mixed tabs and spaces: base tab + spaces for nested indentation
							"code":
								"\tdataset = value\n\t    if True:\n\t        return dataset"
						}]
					}
				}
			},
			"props": {},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.flex"
			}
		}

		import json
		import tempfile
		from pathlib import Path
		view_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
		json.dump(view_content, view_file)
		view_file.close()

		try:
			# Run linting
			self.run_lint_on_file(Path(view_file.name), self.rule_config)
			errors = self.get_errors_for_rule("PylintScriptRule")

			# Should have at least one error
			self.assertGreater(len(errors), 0, "Expected errors for mixed tabs/spaces")

			# Check that the explicit mixed tabs/spaces error is present
			mixed_tabs_error_found = any(
				"mixes tabs and spaces for indentation" in error for error in errors
			)
			self.assertTrue(
				mixed_tabs_error_found, f"Expected 'mixes tabs and spaces' error message. Got: {errors}"
			)

			# Verify the error message is clear and actionable
			mixed_error = next((error for error in errors if "mixes tabs and spaces" in error), None)
			self.assertIn(
				"Use either tabs OR spaces consistently", mixed_error,
				"Error message should provide clear guidance"
			)

		finally:
			import os
			os.unlink(view_file.name)

	def test_script_with_only_tabs(self):
		"""Test that scripts using only tabs don't trigger mixed indentation error."""
		# Create a test view with a script that uses only tabs
		view_content = {
			"custom": {},
			"params": {},
			"propConfig": {
				"custom.testProp": {
					"binding": {
						"type": "tag",
						"config": {
							"tagPath": "[default]TestTag"
						},
						"transforms": [{
							"type": "script",
							# Script with only tabs
							"code": "\tdataset = value\n\tif True:\n\t\treturn dataset"
						}]
					}
				}
			},
			"props": {},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.flex"
			}
		}

		import json
		import tempfile
		from pathlib import Path
		view_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
		json.dump(view_content, view_file)
		view_file.close()

		try:
			# Run linting
			self.run_lint_on_file(Path(view_file.name), self.rule_config)
			errors = self.get_errors_for_rule("PylintScriptRule")

			# Should NOT have mixed tabs/spaces error
			mixed_tabs_error_found = any(
				"mixes tabs and spaces for indentation" in error for error in errors
			)
			self.assertFalse(
				mixed_tabs_error_found,
				f"Should not report mixed indentation for tabs-only script. Got: {errors}"
			)

		finally:
			import os
			os.unlink(view_file.name)


if __name__ == "__main__":
	unittest.main()
