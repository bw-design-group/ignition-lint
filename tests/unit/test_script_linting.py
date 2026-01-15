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


if __name__ == "__main__":
	unittest.main()
