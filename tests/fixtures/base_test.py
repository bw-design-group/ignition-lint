# pylint: disable=wrong-import-position,import-error,attribute-defined-outside-init
"""
Base test classes providing common functionality for ign-lint tests.
"""

import unittest
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Any

# Add the src directory to the PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from ignition_lint.linter import LintEngine
from ignition_lint.rules import RULES_MAP
from ignition_lint.common.flatten_json import flatten_file


class BaseRuleTest(unittest.TestCase):
	"""Base class for testing individual linting rules."""
	test_cases_dir: Path
	configs_dir: Path
	rule_config: Dict[str, Dict[str, Any]] | None
	last_results: Any | None

	def __init__(self, methodName='runTest'):
		super().__init__(methodName)
		self.rule_config = None
		self.last_results = None  # Store results from last run_lint call

	def setUp(self): # pylint: disable=invalid-name
		"""Set up test fixtures."""
		# Get the tests directory (two levels up from fixtures)
		tests_dir = Path(__file__).parent.parent
		self.test_cases_dir = tests_dir / "cases"
		self.configs_dir = tests_dir / "configs"

	def create_lint_engine(self, rule_configs: Dict[str, Dict[str, Any]]) -> LintEngine:
		"""
		Create a lint engine with the specified rules.

		Args:
			rule_configs: Dictionary mapping rule names to their configurations

		Returns:
			Configured LintEngine instance
		"""
		rules = []
		for rule_name, config in rule_configs.items():
			if rule_name not in RULES_MAP:
				self.fail(f"Unknown rule: {rule_name}")

			rule_class = RULES_MAP[rule_name]
			kwargs = config.get('kwargs', {})

			try:
				# Use create_from_config to enable preprocessing
				rules.append(rule_class.create_from_config(kwargs))
			except Exception as e:
				self.fail(f"Failed to create rule {rule_name}: {e}")

		return LintEngine(rules)

	def run_lint_on_file(self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]]):
		"""
		Run linting on a view file and store results for access via convenience methods.

		Args:
			view_file: Path to the view.json file
			rule_configs: Rule configurations

		Returns:
			LintResults object with separate warnings and errors
		"""
		if not view_file.exists():
			self.skipTest(f"View file not found: {view_file}")

		lint_engine = self.create_lint_engine(rule_configs)
		flattened_json = flatten_file(view_file)
		self.last_results = lint_engine.process(flattened_json)
		return self.last_results

	def run_lint_on_mock_view(self, mock_view_content: str, rule_configs: Dict[str, Dict[str, Any]]):
		"""
		Run linting on mock view JSON content and store results for convenience method access.

		Args:
			mock_view_content: JSON string content for the mock view
			rule_configs: Rule configurations

		Returns:
			LintResults object with separate warnings and errors
		"""
		# Create a temporary file with the mock content
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			f.write(mock_view_content)
			temp_file = Path(f.name)

		try:
			return self.run_lint_on_file(temp_file, rule_configs)
		finally:
			# Clean up the temporary file
			temp_file.unlink(missing_ok=True)

	# Convenience methods for accessing results from last run_lint call
	def get_error_count(self, rule_name: str = None) -> int:
		"""Get total error count for all rules or a specific rule."""
		if not self.last_results:
			return 0
		if rule_name:
			return len(self.last_results.errors.get(rule_name, []))
		return sum(len(errors) for errors in self.last_results.errors.values())

	def get_warning_count(self, rule_name: str = None) -> int:
		"""Get total warning count for all rules or a specific rule."""
		if not self.last_results:
			return 0
		if rule_name:
			return len(self.last_results.warnings.get(rule_name, []))
		return sum(len(warnings) for warnings in self.last_results.warnings.values())

	def get_errors_for_rule(self, rule_name: str) -> List[str]:
		"""Get all error messages for a specific rule."""
		if not self.last_results:
			return []
		return self.last_results.errors.get(rule_name, [])

	def get_warnings_for_rule(self, rule_name: str) -> List[str]:
		"""Get all warning messages for a specific rule."""
		if not self.last_results:
			return []
		return self.last_results.warnings.get(rule_name, [])

	def has_errors(self, rule_name: str = None) -> bool:
		"""Check if there are any errors for all rules or a specific rule."""
		return self.get_error_count(rule_name) > 0

	def has_warnings(self, rule_name: str = None) -> bool:
		"""Check if there are any warnings for all rules or a specific rule."""
		return self.get_warning_count(rule_name) > 0

	def assert_no_issues(self, rule_name: str = None):
		"""Assert no warnings or errors for all rules or a specific rule."""
		error_count = self.get_error_count(rule_name)
		warning_count = self.get_warning_count(rule_name)
		scope = f"rule '{rule_name}'" if rule_name else "all rules"
		self.assertEqual(error_count + warning_count, 0,
			f"Expected no issues for {scope} but found {error_count} errors and {warning_count} warnings")

	def assert_rule_passes(self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]], rule_name: str):
		"""Assert that a rule passes (no errors) for a given view file. Warnings are allowed."""
		self.run_lint_on_file(view_file, rule_configs)

		error_count = self.get_error_count(rule_name)
		self.assertEqual(error_count, 0, f"Rule {rule_name} should pass but found {error_count} errors: {self.get_errors_for_rule(rule_name)}")

		if self.has_warnings(rule_name):
			print(f"Note: Rule {rule_name} passed but produced warnings: {self.get_warnings_for_rule(rule_name)}")

	def assert_rule_fails(
		self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]], rule_name: str,
		expected_error_count: int = None
	):
		"""Assert that a rule fails (has errors) for a given view file."""
		self.run_lint_on_file(view_file, rule_configs)

		error_count = self.get_error_count(rule_name)
		self.assertGreater(error_count, 0, f"Rule {rule_name} should fail but found no errors")

		if expected_error_count is not None:
			self.assertEqual(
				error_count, expected_error_count,
				f"Rule {rule_name} should have {expected_error_count} errors but found {error_count}: {self.get_errors_for_rule(rule_name)}"
			)

	def assert_error_contains(
		self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]], rule_name: str, error_pattern: str
	):
		"""Assert that rule errors contain a specific pattern."""
		self.run_lint_on_file(view_file, rule_configs)

		rule_errors = self.get_errors_for_rule(rule_name)
		matching_errors = [error for error in rule_errors if error_pattern in error]
		self.assertGreater(
			len(matching_errors), 0,
			f"Rule {rule_name} errors should contain '{error_pattern}'. Found errors: {rule_errors}"
		)

	# Detailed assertion methods for warnings and errors

	def assert_violations(
		self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]], rule_name: str,
		expected_warnings: int = 0, expected_errors: int = 0,
		warning_patterns: list = None, error_patterns: list = None
	):
		"""
		Assert the total warnings and errors count for a rule with optional pattern matching.
		Convenience method for comprehensive rule validation.
		"""
		self.run_lint_on_file(view_file, rule_configs)

		warning_count = self.get_warning_count(rule_name)
		error_count = self.get_error_count(rule_name)
		rule_warnings = self.get_warnings_for_rule(rule_name)
		rule_errors = self.get_errors_for_rule(rule_name)

		self.assertEqual(
			warning_count, expected_warnings,
			f"Rule {rule_name} should have {expected_warnings} warnings but found {warning_count}: {rule_warnings}"
		)
		self.assertEqual(
			error_count, expected_errors,
			f"Rule {rule_name} should have {expected_errors} errors but found {error_count}: {rule_errors}"
		)

		# Check warning patterns if provided
		if warning_patterns:
			for pattern in warning_patterns:
				matching_warnings = [warning for warning in rule_warnings if pattern in warning]
				self.assertGreater(
					len(matching_warnings), 0,
					f"Rule {rule_name} warnings should contain '{pattern}'. Found warnings: {rule_warnings}"
				)

		# Check error patterns if provided
		if error_patterns:
			for pattern in error_patterns:
				matching_errors = [error for error in rule_errors if pattern in error]
				self.assertGreater(
					len(matching_errors), 0,
					f"Rule {rule_name} errors should contain '{pattern}'. Found errors: {rule_errors}"
				)

	def assert_rule_warnings(
		self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]], rule_name: str,
		expected_warning_count: int, warning_patterns: list = None
	):
		"""Assert that a rule produces the expected number of warnings with optional pattern matching."""
		self.run_lint_on_file(view_file, rule_configs)

		warning_count = self.get_warning_count(rule_name)
		rule_warnings = self.get_warnings_for_rule(rule_name)

		self.assertEqual(
			warning_count, expected_warning_count,
			f"Rule {rule_name} should produce {expected_warning_count} warnings but produced {warning_count}: {rule_warnings}"
		)

		if warning_patterns:
			for pattern in warning_patterns:
				matching_warnings = [warning for warning in rule_warnings if pattern in warning]
				self.assertGreater(
					len(matching_warnings), 0,
					f"Rule {rule_name} warnings should contain '{pattern}'. Found warnings: {rule_warnings}"
				)

	def assert_rule_errors(
		self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]], rule_name: str,
		expected_error_count: int, error_patterns: list = None
	):
		"""Assert that a rule produces the expected number of errors with optional pattern matching."""
		self.run_lint_on_file(view_file, rule_configs)

		error_count = self.get_error_count(rule_name)
		rule_errors = self.get_errors_for_rule(rule_name)

		self.assertEqual(
			error_count, expected_error_count,
			f"Rule {rule_name} should produce {expected_error_count} errors but produced {error_count}: {rule_errors}"
		)

		if error_patterns:
			for pattern in error_patterns:
				matching_errors = [error for error in rule_errors if pattern in error]
				self.assertGreater(
					len(matching_errors), 0,
					f"Rule {rule_name} errors should contain '{pattern}'. Found errors: {rule_errors}"
				)

	def assert_rule_passes_completely(
		self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]], rule_name: str
	):
		"""Assert that a rule passes completely (no warnings or errors)."""
		self.run_lint_on_file(view_file, rule_configs)
		self.assert_no_issues(rule_name)

	def assert_rule_summary(
		self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]], rule_name: str,
		expected_warnings: int = 0, expected_errors: int = 0
	):
		"""Assert the total warnings and errors count for a rule."""
		self.run_lint_on_file(view_file, rule_configs)

		warning_count = self.get_warning_count(rule_name)
		error_count = self.get_error_count(rule_name)

		self.assertEqual(
			warning_count, expected_warnings,
			f"Rule {rule_name} should have {expected_warnings} warnings but found {warning_count}: {self.get_warnings_for_rule(rule_name)}"
		)
		self.assertEqual(
			error_count, expected_errors,
			f"Rule {rule_name} should have {expected_errors} errors but found {error_count}: {self.get_errors_for_rule(rule_name)}"
		)


class BaseIntegrationTest(unittest.TestCase):
	"""Base class for integration tests involving multiple components."""
	test_cases_dir: Path
	configs_dir: Path

	def setUp(self):
		"""Set up test fixtures."""
		# Get the tests directory (two levels up from fixtures)
		tests_dir = Path(__file__).parent.parent
		self.test_cases_dir = tests_dir / "cases"
		self.configs_dir = tests_dir / "configs"

	def run_multiple_rules(self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
		"""
		Run multiple rules on a view file.

		Args:
			view_file: Path to the view.json file
			rule_configs: Dictionary of rule configurations

		Returns:
			Dictionary of combined warnings and errors by rule name
		"""
		results = self.run_multiple_rules_detailed(view_file, rule_configs)

		# Combine warnings and errors
		combined_results = {}
		combined_results.update(results.warnings)
		combined_results.update(results.errors)

		return combined_results

	def run_multiple_rules_detailed(self, view_file: Path, rule_configs: Dict[str, Dict[str, Any]]):
		"""
		Run multiple rules on a view file and return detailed results.

		Args:
			view_file: Path to the view.json file
			rule_configs: Dictionary of rule configurations

		Returns:
			LintResults object with separate warnings and errors
		"""
		if not view_file.exists():
			self.skipTest(f"View file not found: {view_file}")

		# Create rules
		rules = []
		for rule_name, config in rule_configs.items():
			if rule_name not in RULES_MAP:
				continue

			rule_class = RULES_MAP[rule_name]
			kwargs = config.get('kwargs', {})

			try:
				# Use create_from_config to enable preprocessing
				rules.append(rule_class.create_from_config(kwargs))
			except Exception as e:
				self.fail(f"Failed to create rule {rule_name}: {e}")

		# Run linting
		lint_engine = LintEngine(rules)
		flattened_json = flatten_file(view_file)
		return lint_engine.process(flattened_json)

	def assert_total_errors(self, errors: Dict[str, List[str]], expected_total: int):
		"""Assert the total number of errors across all rules."""
		total_errors = sum(len(rule_errors) for rule_errors in errors.values())
		self.assertEqual(
			total_errors, expected_total,
			f"Expected {expected_total} total errors but found {total_errors}. Errors: {errors}"
		)
