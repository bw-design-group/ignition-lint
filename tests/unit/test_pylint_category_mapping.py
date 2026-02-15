# pylint: disable=import-error
"""
Unit tests for PylintScriptRule category mapping feature.

Tests cover:
- Default category mapping (F/E → error, W/C/R → warning)
- Custom category mapping configurations
- Category-grouped output formatting
- Structured violation storage
- Backward compatibility
"""

import unittest
from unittest.mock import patch
from io import StringIO
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.ignition_lint.rules.scripts.lint_script import PylintScriptRule, PylintViolation


class TestPylintCategoryMapping(unittest.TestCase):
	"""Test suite for PylintScriptRule category mapping."""

	def test_default_category_mapping(self):
		"""Test that default category mapping is F/E → error, W/C/R → warning."""
		rule = PylintScriptRule()

		# Verify default mapping
		self.assertEqual(rule.category_mapping['F'], 'error')
		self.assertEqual(rule.category_mapping['E'], 'error')
		self.assertEqual(rule.category_mapping['W'], 'warning')
		self.assertEqual(rule.category_mapping['C'], 'warning')
		self.assertEqual(rule.category_mapping['R'], 'warning')

	def test_custom_category_mapping_strict(self):
		"""Test strict mode where all categories map to error."""
		custom_mapping = {
			'F': 'error',
			'E': 'error',
			'W': 'error',
			'C': 'error',
			'R': 'error',
		}
		rule = PylintScriptRule(category_mapping=custom_mapping)

		# Verify custom mapping
		self.assertEqual(rule.category_mapping['F'], 'error')
		self.assertEqual(rule.category_mapping['E'], 'error')
		self.assertEqual(rule.category_mapping['W'], 'error')
		self.assertEqual(rule.category_mapping['C'], 'error')
		self.assertEqual(rule.category_mapping['R'], 'error')

	def test_custom_category_mapping_lenient(self):
		"""Test lenient mode where only F/E are errors."""
		custom_mapping = {
			'F': 'error',
			'E': 'error',
			'W': 'warning',
			'C': 'warning',
			'R': 'warning',
		}
		rule = PylintScriptRule(category_mapping=custom_mapping)

		# Verify custom mapping
		self.assertEqual(rule.category_mapping['F'], 'error')
		self.assertEqual(rule.category_mapping['E'], 'error')
		self.assertEqual(rule.category_mapping['W'], 'warning')
		self.assertEqual(rule.category_mapping['C'], 'warning')
		self.assertEqual(rule.category_mapping['R'], 'warning')

	def test_pylint_violation_dataclass(self):
		"""Test that PylintViolation dataclass stores all required fields."""
		violation = PylintViolation(
			category='E', code='E0602', message="Undefined variable 'x'",
			path='root.Button.onActionPerformed', line=5
		)

		self.assertEqual(violation.category, 'E')
		self.assertEqual(violation.code, 'E0602')
		self.assertEqual(violation.message, "Undefined variable 'x'")
		self.assertEqual(violation.path, 'root.Button.onActionPerformed')
		self.assertEqual(violation.line, 5)

	def test_structured_violation_storage(self):
		"""Test that violations are stored in structured format."""
		rule = PylintScriptRule()

		# Create test violations
		violation1 = PylintViolation(
			category='E', code='E0602', message="Undefined variable 'x'", path='script1', line=5
		)
		violation2 = PylintViolation(
			category='W', code='W0611', message="Unused import 'json'", path='script2', line=2
		)

		rule.pylint_violations = [violation1, violation2]

		# Verify storage
		self.assertEqual(len(rule.pylint_violations), 2)
		self.assertEqual(rule.pylint_violations[0].category, 'E')
		self.assertEqual(rule.pylint_violations[1].category, 'W')

	def test_get_category_grouped_violations_empty(self):
		"""Test category grouping with no violations."""
		rule = PylintScriptRule()
		rule.pylint_violations = []

		grouped = rule.get_category_grouped_violations()

		self.assertEqual(grouped, {})

	def test_get_category_grouped_violations_single_category(self):
		"""Test category grouping with violations from one category."""
		rule = PylintScriptRule()
		rule.pylint_violations = [
			PylintViolation(
				category='E', code='E0602', message="Undefined variable 'x'", path='script1', line=5
			),
			PylintViolation(
				category='E', code='E1101', message="No member 'foo'", path='script2', line=10
			),
		]

		grouped = rule.get_category_grouped_violations()

		# Should have one category
		self.assertIn('E', grouped)
		self.assertEqual(grouped['E']['severity'], 'error')
		self.assertEqual(grouped['E']['name'], 'Error')
		self.assertEqual(len(grouped['E']['violations']), 2)

	def test_get_category_grouped_violations_multiple_categories(self):
		"""Test category grouping with violations from multiple categories."""
		rule = PylintScriptRule()
		rule.pylint_violations = [
			PylintViolation(category='F', code='F0401', message="Cannot import", path='s1', line=1),
			PylintViolation(category='E', code='E0602', message="Undefined", path='s2', line=2),
			PylintViolation(category='W', code='W0611', message="Unused import", path='s3', line=3),
			PylintViolation(category='C', code='C0114', message="Missing docstring", path='s4', line=4),
			PylintViolation(category='R', code='R0913', message="Too many args", path='s5', line=5),
		]

		grouped = rule.get_category_grouped_violations()

		# Should have all five categories in order
		categories = list(grouped.keys())
		self.assertEqual(categories, ['F', 'E', 'W', 'C', 'R'])

		# Verify each category has correct data
		self.assertEqual(grouped['F']['severity'], 'error')
		self.assertEqual(grouped['E']['severity'], 'error')
		self.assertEqual(grouped['W']['severity'], 'warning')
		self.assertEqual(grouped['C']['severity'], 'warning')
		self.assertEqual(grouped['R']['severity'], 'warning')

	def test_get_category_grouped_violations_custom_mapping(self):
		"""Test category grouping respects custom category mapping."""
		custom_mapping = {
			'F': 'error',
			'E': 'error',
			'W': 'error',  # Custom: W → error instead of warning
			'C': 'warning',
			'R': 'warning',
		}
		rule = PylintScriptRule(category_mapping=custom_mapping)
		rule.pylint_violations = [
			PylintViolation(category='W', code='W0611', message="Unused import", path='s1', line=1),
		]

		grouped = rule.get_category_grouped_violations()

		# W should map to error with custom mapping
		self.assertEqual(grouped['W']['severity'], 'error')

	def test_get_category_grouped_violations_formatting(self):
		"""Test that grouped violations format messages correctly."""
		rule = PylintScriptRule()
		rule.pylint_violations = [
			PylintViolation(
				category='E', code='E0602', message="Undefined variable 'x'",
				path='test_file::root.Button.onActionPerformed', line=5
			),
		]

		grouped = rule.get_category_grouped_violations()

		# Verify message format includes path, line, message, and code
		violation_msg = grouped['E']['violations'][0]
		self.assertIn('root.Button.onActionPerformed', violation_msg)
		self.assertIn('Line 5', violation_msg)
		self.assertIn("Undefined variable 'x'", violation_msg)
		self.assertIn('E0602', violation_msg)

	def test_category_order_in_grouped_output(self):
		"""Test that categories are ordered F, E, W, C, R in grouped output."""
		rule = PylintScriptRule()
		# Add violations in random order
		rule.pylint_violations = [
			PylintViolation(category='R', code='R0913', message="msg", path='s', line=1),
			PylintViolation(category='F', code='F0401', message="msg", path='s', line=1),
			PylintViolation(category='C', code='C0114', message="msg", path='s', line=1),
			PylintViolation(category='W', code='W0611', message="msg", path='s', line=1),
			PylintViolation(category='E', code='E0602', message="msg", path='s', line=1),
		]

		grouped = rule.get_category_grouped_violations()

		# Categories should be in F, E, W, C, R order
		categories = list(grouped.keys())
		self.assertEqual(categories, ['F', 'E', 'W', 'C', 'R'])

	def test_batch_mode_preserves_violations(self):
		"""Test that batch mode doesn't reset violations between files."""
		rule = PylintScriptRule(batch_mode=True)

		# Add violation from first file
		rule.pylint_violations = [
			PylintViolation(category='E', code='E0602', message="msg1", path='file1::s1', line=1),
		]

		# Simulate processing another file (in batch mode, violations should accumulate)
		rule.process_nodes([])  # Empty nodes, but shouldn't reset violations

		# Add violation from second file
		rule.pylint_violations.append(
			PylintViolation(category='E', code='E0602', message="msg2", path='file2::s2', line=1)
		)

		# Both violations should be present
		self.assertEqual(len(rule.pylint_violations), 2)

	def test_non_batch_mode_resets_violations(self):
		"""Test that non-batch mode resets violations between files."""
		rule = PylintScriptRule(batch_mode=False)

		# Add violation
		rule.pylint_violations = [
			PylintViolation(category='E', code='E0602', message="msg", path='s', line=1),
		]

		# Process nodes (should reset)
		rule.process_nodes([])

		# Violations should be reset
		self.assertEqual(len(rule.pylint_violations), 0)

	def test_backward_compatibility_errors_warnings_lists(self):
		"""Test that errors and warnings lists still work for backward compatibility."""
		rule = PylintScriptRule()

		# Manually add violations with different severities
		rule.add_violation("Error message", severity="error")
		rule.add_violation("Warning message", severity="warning")

		# Verify backward compatible lists are populated
		self.assertEqual(len(rule.errors), 1)
		self.assertEqual(len(rule.warnings), 1)
		self.assertIn("Error message", rule.errors)
		self.assertIn("Warning message", rule.warnings)

	def test_unknown_category_fallback(self):
		"""Test that unknown categories fall back to rule's default severity when used directly."""
		rule = PylintScriptRule(severity="warning")

		# Manually add a violation with unknown category using add_violation
		# (which should use the default severity)
		rule.add_violation("Unknown category message", severity=None)

		# Verify it was added to warnings (rule's default severity)
		self.assertEqual(len(rule.warnings), 1)

		# Note: Unknown categories won't appear in get_category_grouped_violations()
		# because that method only returns known categories (F, E, W, C, R)

	def test_multiple_violations_same_category(self):
		"""Test multiple violations in same category are grouped together."""
		rule = PylintScriptRule()
		rule.pylint_violations = [
			PylintViolation(category='E', code='E0602', message="Undefined 'x'", path='s1', line=1),
			PylintViolation(category='E', code='E1101', message="No member", path='s2', line=2),
			PylintViolation(category='E', code='E0602', message="Undefined 'y'", path='s3', line=3),
		]

		grouped = rule.get_category_grouped_violations()

		# All three violations should be in Error category
		self.assertEqual(len(grouped['E']['violations']), 3)

	def test_category_names_mapping(self):
		"""Test that category codes map to correct human-readable names."""
		rule = PylintScriptRule()
		rule.pylint_violations = [
			PylintViolation(category='F', code='F0001', message="msg", path='s', line=1),
			PylintViolation(category='E', code='E0001', message="msg", path='s', line=1),
			PylintViolation(category='W', code='W0001', message="msg", path='s', line=1),
			PylintViolation(category='C', code='C0001', message="msg", path='s', line=1),
			PylintViolation(category='R', code='R0001', message="msg", path='s', line=1),
		]

		grouped = rule.get_category_grouped_violations()

		# Verify human-readable names
		self.assertEqual(grouped['F']['name'], 'Fatal')
		self.assertEqual(grouped['E']['name'], 'Error')
		self.assertEqual(grouped['W']['name'], 'Warning')
		self.assertEqual(grouped['C']['name'], 'Convention')
		self.assertEqual(grouped['R']['name'], 'Refactor')


class TestPylintCategoryMappingIntegration(unittest.TestCase):
	"""Integration tests for category mapping with parsing and output."""

	def test_parse_pylint_output_extracts_category(self):
		"""Test that _parse_pylint_output extracts category and code correctly."""
		rule = PylintScriptRule()

		# Mock pylint output
		pylint_output = """test.py:5:10: E0602: Undefined variable 'x' (undefined-variable)
test.py:3:0: W0611: Unused import 'json' (unused-import)
test.py:1:0: C0114: Missing module docstring (missing-module-docstring)"""

		# Mock line map and path_to_issues
		line_map = {1: 'script1', 2: 'script1', 3: 'script1', 4: 'script1', 5: 'script1'}
		path_to_issues = {'script1': []}

		# Parse output
		rule._parse_pylint_output(pylint_output, line_map, path_to_issues)

		# Verify structured violations were created
		self.assertEqual(len(rule.pylint_violations), 3)
		self.assertEqual(rule.pylint_violations[0].category, 'E')
		self.assertEqual(rule.pylint_violations[0].code, 'E0602')
		self.assertEqual(rule.pylint_violations[1].category, 'W')
		self.assertEqual(rule.pylint_violations[1].code, 'W0611')
		self.assertEqual(rule.pylint_violations[2].category, 'C')
		self.assertEqual(rule.pylint_violations[2].code, 'C0114')

	@patch('sys.stdout', new_callable=StringIO)
	def test_print_category_grouped_output(self, mock_stdout):
		"""Test that category-grouped output prints correctly using format_violations_grouped."""
		# Create rule with violations
		rule = PylintScriptRule()
		rule.pylint_violations = [
			PylintViolation(
				category='E', code='E0602', message="Undefined variable 'x'", path='root.Button.script',
				line=5
			),
			PylintViolation(
				category='W', code='W0611', message="Unused import 'json'", path='root.Label.transform',
				line=2
			),
		]

		# Get formatted output
		output = rule.format_violations_grouped()

		# Verify output contains expected elements
		self.assertIsNotNone(output)
		self.assertIn("Error (E)", output)
		self.assertIn("Warning (W)", output)
		self.assertIn("E0602", output)
		self.assertIn("W0611", output)
		self.assertIn("root.Button.script", output)
		self.assertIn("root.Label.transform", output)

	@patch('sys.stdout', new_callable=StringIO)
	def test_print_category_grouped_output_severity_icons(self, mock_stdout):
		"""Test that correct severity icons are used in output."""
		# Create rule with error and warning
		rule = PylintScriptRule()
		rule.pylint_violations = [
			PylintViolation(category='E', code='E0602', message="Error", path='s', line=1),
			PylintViolation(category='W', code='W0611', message="Warning", path='s', line=2),
		]

		# Get formatted output
		output = rule.format_violations_grouped()

		# Should have error icon ❌ for E category
		self.assertIn("❌", output)
		# Should have warning icon ⚠️ for W category
		self.assertIn("⚠️", output)


if __name__ == '__main__':
	unittest.main()
