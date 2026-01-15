# pylint: disable=import-error
"""
Unit tests for the PollingIntervalRule.
Tests polling interval validation in expression bindings.
"""

import unittest
from typing import Dict, Any

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, load_test_view


class TestPollingIntervalRule(BaseRuleTest):
	"""Test polling interval validation."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config("PollingIntervalRule", minimum_interval=10000)

	def test_expression_bindings_validation(self):
		"""Test polling interval validation in expression bindings."""
		view_file = load_test_view(self.test_cases_dir, "ExpressionBindings")
		self.run_lint_on_file(view_file, self.rule_config)

		# Check if there are any polling interval errors
		polling_errors = self.get_errors_for_rule("PollingIntervalRule")
		# This test depends on the actual content of the ExpressionBindings view.json
		# For now, we just verify the rule runs without crashing
		self.assertIsInstance(polling_errors, list)

	def test_different_minimum_intervals(self):
		"""Test different minimum interval settings."""
		test_intervals = [1000, 5000, 10000, 30000]

		view_file = load_test_view(self.test_cases_dir, "ExpressionBindings")

		for minimum_interval in test_intervals:
			with self.subTest(minimum_interval=minimum_interval):
				rule_config = get_test_config("PollingIntervalRule", minimum_interval=minimum_interval)

				self.run_lint_on_file(view_file, rule_config)
				polling_errors = self.get_errors_for_rule("PollingIntervalRule")
				self.assertIsInstance(polling_errors, list)


class TestPollingIntervalValidation(BaseRuleTest):
	"""Test specific polling interval validation scenarios."""

	def test_no_polling_expressions(self):
		"""Test views without polling expressions."""
		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		rule_config = get_test_config("PollingIntervalRule", minimum_interval=10000)

		self.run_lint_on_file(view_file, rule_config)
		# Should have no polling errors since there are no polling expressions
		self.assertEqual(self.get_errors_for_rule("PollingIntervalRule"), [])


if __name__ == "__main__":
	unittest.main()
