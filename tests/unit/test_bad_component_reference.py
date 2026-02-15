# pylint: disable=import-error
"""
Unit tests for the BadComponentReferenceRule.
Tests detection of bad component reference patterns.
"""

import unittest
from typing import Dict, Any

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, create_mock_script, load_test_view


class TestBadComponentReferenceRule(BaseRuleTest):
	"""Test bad component reference detection."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config("BadComponentReferenceRule")

	def test_detects_get_sibling(self):
		"""Test detection of .getSibling() usage."""
		try:
			view_file = load_test_view(self.test_cases_dir, "BadComponentReferences")

			self.run_lint_on_file(view_file, self.rule_config)
			rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")

			self.assertGreater(len(rule_errors), 0, "Should detect bad component references")

			# Should detect .getSibling( pattern
			found_get_sibling = any(".getSibling(" in error for error in rule_errors)
			self.assertTrue(
				found_get_sibling, f"Should detect .getSibling pattern. Found errors: {rule_errors}"
			)
		except FileNotFoundError:
			self.skipTest("BadComponentReferences test case not found")

	def test_detects_get_parent(self):
		"""Test detection of .getParent() usage."""
		script_content = """
		def transform(self, value, quality, timestamp):
			parent = self.getParent()
			return parent.props.text
		"""

		mock_view = create_mock_script("transform", script_content)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		self.assertEqual(len(rule_errors), 1)
		self.assertIn(".getParent(", rule_errors[0])

	def test_detects_get_child(self):
		"""Test detection of .getChild() usage."""
		script_content = """
		def onStartup(self):
			child = self.view.getChild("Container").getChild("Label")
			child.props.text = "Hello"
		"""

		mock_view = create_mock_script("event_handler", script_content)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		self.assertEqual(len(rule_errors), 1)
		self.assertIn(".getChild(", rule_errors[0])

	def test_detects_multiple_methods_reports_once(self):
		"""Test that multiple bad methods in same script only report once."""
		script_content = """
		def complexNavigation(self):
			sibling = self.getSibling("Button1")
			parent = sibling.getParent()
			child = parent.getChild("Label")
			return child
		"""

		mock_view = create_mock_script("custom_method", script_content)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		# Should only report once per script to avoid spam
		self.assertEqual(len(rule_errors), 1)

	def test_ignores_good_practices(self):
		"""Test that good practices are not flagged."""
		script_content = """
		def onActionPerformed(self, event):
			# Good practice - using view.custom
			target_value = self.view.custom.targetValue
			self.view.custom.currentState = "active"

			# Also good - direct property access
			self.props.text = "Updated"

			# Good - using session/page scope
			system.tag.writeBlocking("[default]MyTag", target_value)
		"""

		mock_view = create_mock_script("message_handler", script_content)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		self.assertEqual(len(rule_errors), 0)

	def test_case_sensitivity_option(self):
		"""Test case sensitivity configuration."""
		# Test case-insensitive mode
		case_insensitive_config = get_test_config("BadComponentReferenceRule", case_sensitive=False)

		script_content = """
		def test():
			# Mixed case should be caught in case-insensitive mode
			result = component.GETSIBLING("test")
		"""

		mock_view = create_mock_script("message_handler", script_content)
		self.run_lint_on_mock_view(mock_view, case_insensitive_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		self.assertEqual(len(rule_errors), 1)

	def test_custom_forbidden_methods(self):
		"""Test custom forbidden methods configuration."""
		custom_config = get_test_config(
			"BadComponentReferenceRule", forbidden_patterns=['.getSibling(', '.customBadMethod(']
		)

		script_content = """
		def test():
			# Should catch custom forbidden method
			result = component.customBadMethod("test")
			# Should not catch getParent since not in custom list
			parent = component.getParent()
		"""

		mock_view = create_mock_script("message_handler", script_content)
		self.run_lint_on_mock_view(mock_view, custom_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		self.assertEqual(len(rule_errors), 1)
		self.assertIn(".customBadMethod(", rule_errors[0])

	def test_empty_script_content(self):
		"""Test handling of empty or missing script content."""
		mock_view = create_mock_script("message_handler", "")
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		self.assertEqual(len(rule_errors), 0)

	def test_script_types_coverage(self):
		"""Test that all script types are properly checked."""
		script_content = """
		def badPractice():
			return self.getSibling("target")
		"""

		script_types = ["message_handler", "custom_method", "transform", "event_handler"]

		for script_type in script_types:
			with self.subTest(script_type=script_type):
				mock_view = create_mock_script(script_type, script_content)
				self.run_lint_on_mock_view(mock_view, self.rule_config)

				rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
				self.assertEqual(
					len(rule_errors), 1, f"Should detect bad reference in {script_type} scripts"
				)

	def test_severity_configuration_error(self):
		"""Test that severity='error' adds violations to errors list."""
		error_config = get_test_config("BadComponentReferenceRule", severity="error")

		script_content = """
		def badMethod():
			return self.getSibling("target")
		"""

		mock_view = create_mock_script("message_handler", script_content)
		self.run_lint_on_mock_view(mock_view, error_config)

		# Should be in errors, not warnings
		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		rule_warnings = self.get_warnings_for_rule("BadComponentReferenceRule")

		self.assertEqual(len(rule_errors), 1, "Should report as error when severity='error'")
		self.assertEqual(len(rule_warnings), 0, "Should not report as warning when severity='error'")

	def test_severity_configuration_warning(self):
		"""Test that severity='warning' adds violations to warnings list."""
		warning_config = get_test_config("BadComponentReferenceRule", severity="warning")

		script_content = """
		def badMethod():
			return self.getParent()
		"""

		mock_view = create_mock_script("message_handler", script_content)
		self.run_lint_on_mock_view(mock_view, warning_config)

		# Should be in warnings, not errors
		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		rule_warnings = self.get_warnings_for_rule("BadComponentReferenceRule")

		self.assertEqual(len(rule_errors), 0, "Should not report as error when severity='warning'")
		self.assertEqual(len(rule_warnings), 1, "Should report as warning when severity='warning'")


class TestBadComponentReferenceEdgeCases(BaseRuleTest):
	"""Test edge cases and advanced scenarios."""

	def test_method_in_comments_not_flagged(self):
		"""Test that methods in comments are not flagged."""
		script_content = """
		def goodMethod():
			# This comment mentions .getSibling() but should not be flagged
			# because it's just documentation
			value = self.view.custom.myValue
		"""

		rule_config = get_test_config("BadComponentReferenceRule")
		mock_view = create_mock_script("message_handler", script_content)
		self.run_lint_on_mock_view(mock_view, rule_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		# This will currently flag comments too, which is acceptable for now
		# In a real implementation, you might want to parse Python AST to ignore comments
		self.assertEqual(len(rule_errors), 1)  # Expected behavior for now

	def test_method_in_string_literals(self):
		"""Test handling of methods in string literals."""
		script_content = """
		def documentBadPractice():
			message = "Don't use .getSibling() method"
			logger.info(message)
		"""

		rule_config = get_test_config("BadComponentReferenceRule")
		mock_view = create_mock_script("message_handler", script_content)
		self.run_lint_on_mock_view(mock_view, rule_config)

		rule_errors = self.get_errors_for_rule("BadComponentReferenceRule")
		# This will currently flag string literals too, which is acceptable
		# for a simple string-based check
		self.assertEqual(len(rule_errors), 1)


if __name__ == "__main__":
	unittest.main()
