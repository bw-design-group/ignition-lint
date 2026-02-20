# pylint: disable=wrong-import-position,import-error
"""
Configuration-driven test framework for ign-lint.
This module allows defining test cases in JSON configuration files
and automatically generates and runs the appropriate tests.
"""

import unittest
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

# Add the src directory to the PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from ignition_lint.linter import LintEngine
from ignition_lint.rules import RULES_MAP
from ignition_lint.common.flatten_json import flatten_file


@dataclass
class TestExpectation:
	"""Represents expected results for a test case."""
	rule_name: str
	error_count: int = 0
	warning_count: int = 0
	error_patterns: List[str] = None
	warning_patterns: List[str] = None
	should_pass: bool = None

	def __post_init__(self):
		if self.error_patterns is None:
			self.error_patterns = []
		if self.warning_patterns is None:
			self.warning_patterns = []
		if self.should_pass is None:
			# Rule passes if no errors (warnings are allowed for "pass")
			self.should_pass = self.error_count == 0


@dataclass
class ConfigurableTestCase:
	"""Represents a test case defined in configuration."""
	name: str
	description: str
	view_file: str
	rule_config: Dict[str, Any]
	expectations: List[TestExpectation]
	tags: List[str] = None
	skip: bool = False
	skip_reason: str = ""

	def __post_init__(self):
		if self.tags is None:
			self.tags = []


class ConfigurableTestFramework:
	"""Framework for running tests defined in configuration files."""

	def __init__(self, config_dir: Path = None, test_cases_dir: Path = None):
		"""
		Initialize the framework.

		Args:
			config_dir: Directory containing test configuration files
			test_cases_dir: Directory containing test case view.json files
		"""
		# Get the tests directory (parent of fixtures)
		tests_dir = Path(__file__).parent.parent

		if config_dir is None:
			config_dir = tests_dir / "integration" / "configs"
		if test_cases_dir is None:
			test_cases_dir = tests_dir / "cases"

		self.config_dir = config_dir
		self.test_cases_dir = test_cases_dir
		self.test_cases: List[ConfigurableTestCase] = []

	def load_test_configurations(self) -> List[ConfigurableTestCase]:
		"""
		Load test configurations from JSON files.

		Returns:
			List of configured test cases
		"""
		test_cases = []

		if not self.config_dir.exists():
			return test_cases

		for config_file in self.config_dir.rglob("*.json"):
			try:
				with open(config_file, 'r', encoding='utf-8') as f:
					config_data = json.load(f)

				# Parse test cases from configuration
				for case_data in config_data.get('test_cases', []):
					expectations = []
					for exp_data in case_data.get('expectations', []):
						expectations.append(
							TestExpectation(
								rule_name=exp_data['rule_name'],
								error_count=exp_data.get('error_count', 0),
								warning_count=exp_data.get('warning_count', 0),
								error_patterns=exp_data.get('error_patterns', []),
								warning_patterns=exp_data.get('warning_patterns', []),
								should_pass=exp_data.get('should_pass')
							)
						)

					test_case = ConfigurableTestCase(
						name=case_data['name'], description=case_data.get('description', ''),
						view_file=case_data['view_file'], rule_config=case_data['rule_config'],
						expectations=expectations, tags=case_data.get('tags', []),
						skip=case_data.get('skip', False),
						skip_reason=case_data.get('skip_reason', '')
					)
					test_cases.append(test_case)

			except Exception as e:
				print(f"Error loading config file {config_file}: {e}")

		return test_cases

	def run_single_test(self, test_case: ConfigurableTestCase) -> Dict[str, Any]:
		"""
		Run a single test case and return results.

		Args:
			test_case: The test case to run

		Returns:
			Dictionary containing test results
		"""
		if test_case.skip:
			return {
				'name': test_case.name,
				'status': 'skipped',
				'reason': test_case.skip_reason,
				'errors': [],
				'expectations_met': True
			}

		# Resolve view file path
		view_file_path = self.test_cases_dir / test_case.view_file
		if not view_file_path.exists():
			return {
				'name': test_case.name,
				'status': 'error',
				'reason': f"View file not found: {view_file_path}",
				'errors': [],
				'expectations_met': False
			}

		try:
			# Create rules from config
			rules = []
			for rule_name, rule_config in test_case.rule_config.items():
				if rule_name.startswith("_") or not isinstance(rule_config, dict):
					continue

				if not rule_config.get('enabled', True):
					continue

				if rule_name not in RULES_MAP:
					continue

				rule_class = RULES_MAP[rule_name]
				kwargs = rule_config.get('kwargs', {})

				try:
					rules.append(rule_class.create_from_config(kwargs))
				except Exception as e:
					print(f"Error creating rule {rule_name}: {e}")
					continue

			# Run linting
			lint_engine = LintEngine(rules)
			flattened_json = flatten_file(view_file_path)
			lint_results = lint_engine.process(flattened_json)

			# Combine warnings and errors for backward compatibility
			actual_errors = {}
			actual_errors.update(lint_results.warnings)
			actual_errors.update(lint_results.errors)

			# Check expectations
			expectations_met = True
			expectation_details = []

			for expectation in test_case.expectations:
				rule_warnings = lint_results.warnings.get(expectation.rule_name, [])
				rule_errors = lint_results.errors.get(expectation.rule_name, [])

				actual_warning_count = len(rule_warnings)
				actual_error_count = len(rule_errors)

				# Check counts
				warning_count_match = actual_warning_count == expectation.warning_count
				error_count_match = actual_error_count == expectation.error_count
				pass_match = (actual_error_count == 0) == expectation.should_pass

				# Check error patterns
				error_pattern_matches = []
				if expectation.error_patterns:
					for pattern in expectation.error_patterns:
						matches = [error for error in rule_errors if pattern in error]
						error_pattern_matches.append({
							'pattern': pattern,
							'matches': len(matches),
							'found': len(matches) > 0
						})

				# Check warning patterns
				warning_pattern_matches = []
				if expectation.warning_patterns:
					for pattern in expectation.warning_patterns:
						matches = [warning for warning in rule_warnings if pattern in warning]
						warning_pattern_matches.append({
							'pattern': pattern,
							'matches': len(matches),
							'found': len(matches) > 0
						})

				# Overall expectation check
				expectation_met = warning_count_match and error_count_match and pass_match
				if expectation.error_patterns:
					expectation_met = expectation_met and all(
						pm['found'] for pm in error_pattern_matches
					)
				if expectation.warning_patterns:
					expectation_met = expectation_met and all(
						pm['found'] for pm in warning_pattern_matches
					)

				expectations_met = expectations_met and expectation_met

				expectation_details.append({
					'rule_name': expectation.rule_name,
					'expected_warnings': expectation.warning_count,
					'actual_warnings': actual_warning_count,
					'expected_errors': expectation.error_count,
					'actual_errors': actual_error_count,
					'should_pass': expectation.should_pass,
					'warning_count_match': warning_count_match,
					'error_count_match': error_count_match,
					'pass_match': pass_match,
					'error_pattern_matches': error_pattern_matches,
					'warning_pattern_matches': warning_pattern_matches,
					'met': expectation_met
				})

			return {
				'name': test_case.name,
				'status': 'passed' if expectations_met else 'failed',
				'reason': '',
				'errors': actual_errors,
				'expectations_met': expectations_met,
				'expectation_details': expectation_details
			}

		except Exception as e:
			return {
				'name': test_case.name,
				'status': 'error',
				'reason': f"Test execution failed: {str(e)}",
				'errors': [],
				'expectations_met': False
			}

	def run_all_tests(self, tags: List[str] = None) -> Dict[str, Any]:
		"""
		Run all loaded test cases, optionally filtered by tags.

		Args:
			tags: Optional list of tags to filter tests

		Returns:
			Dictionary containing overall test results
		"""
		test_cases = self.load_test_configurations()

		# Filter by tags if specified
		if tags:
			test_cases = [tc for tc in test_cases if any(tag in tc.tags for tag in tags)]

		results = []
		passed = 0
		failed = 0
		skipped = 0
		errors = 0

		for test_case in test_cases:
			result = self.run_single_test(test_case)
			results.append(result)

			if result['status'] == 'passed':
				passed += 1
			elif result['status'] == 'failed':
				failed += 1
			elif result['status'] == 'skipped':
				skipped += 1
			else:  # error
				errors += 1

		return {
			'total': len(test_cases),
			'passed': passed,
			'failed': failed,
			'skipped': skipped,
			'errors': errors,
			'results': results
		}

	def generate_test_config_template(self, rule_name: str, output_file: str = None):
		"""
		Generate a template configuration file for a specific rule.

		Args:
			rule_name: Name of the rule to generate config for
			output_file: Optional output file path
		"""
		if rule_name not in RULES_MAP:
			raise ValueError(f"Unknown rule: {rule_name}")

		template = {
			"test_suite_name": f"{rule_name} Tests",
			"description": f"Test cases for the {rule_name} rule",
			"test_cases": [
				{
					"name": f"{rule_name}_positive_case",
					"description": "Test case that should pass the rule",
					"view_file": "cases/PascalCase/view.json",  # Example
					"rule_config": {
						rule_name: {
							"enabled": True,
							"kwargs": {}  # Add rule-specific kwargs here
						}
					},
					"expectations": [{
						"rule_name": rule_name,
						"error_count": 0,
						"should_pass": True,
						"error_patterns": []
					}],
					"tags": [rule_name.lower(), "positive"],
					"skip": False
				},
				{
					"name": f"{rule_name}_negative_case",
					"description": "Test case that should fail the rule",
					"view_file": "cases/camelCase/view.json",  # Example
					"rule_config": {
						rule_name: {
							"enabled": True,
							"kwargs": {}  # Add rule-specific kwargs here
						}
					},
					"expectations": [{
						"rule_name": rule_name,
						"error_count": 1,  # Adjust based on expected failures
						"should_pass": False,
						"error_patterns": ["doesn't follow"]  # Example pattern
					}],
					"tags": [rule_name.lower(), "negative"],
					"skip": False
				}
			]
		}

		if output_file is None:
			output_file = f"{rule_name.lower()}_tests.json"

		output_path = self.config_dir / output_file
		output_path.parent.mkdir(parents=True, exist_ok=True)

		with open(output_path, 'w', encoding='utf-8') as f:
			json.dump(template, f, indent=2)

		print(f"Generated template configuration: {output_path}")


class ConfigurableTestRunner(unittest.TestCase):
	"""Unit test class that runs configuration-driven tests."""

	def setUp(self):
		"""Set up the test framework."""
		self.framework = ConfigurableTestFramework()

	def test_run_configured_tests(self):
		"""Run all configured test cases."""
		test_results = self.framework.run_all_tests()

		# Print detailed results
		print("\nTest Results Summary:")
		print(f"Total: {test_results['total']}")
		print(f"Passed: {test_results['passed']}")
		print(f"Failed: {test_results['failed']}")
		print(f"Skipped: {test_results['skipped']}")
		print(f"Errors: {test_results['errors']}")

		# Print details for failed tests
		for test_result in test_results['results']:
			if test_result['status'] == 'failed':
				print(f"\nFAILED: {test_result['name']}")
				if 'expectation_details' in test_result:
					for detail in test_result['expectation_details']:
						if not detail['met']:
							print(f"  Rule: {detail['rule_name']}")
							print(
								f"    Expected count: {detail['expected_count']}, Got: {detail['actual_count']}"
							)
							print(f"    Should pass: {detail['should_pass']}")
			elif test_result['status'] == 'error':
				print(f"\nERROR: {test_result['name']} - {test_result['reason']}")

		# Assert that all tests passed (no failures or errors)
		self.assertEqual(results['failed'], 0, "Some tests failed. See details above.")
		self.assertEqual(results['errors'], 0, "Some tests had errors. See details above.")


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="Configuration-driven test framework for ign-lint")
	parser.add_argument("--run-tests", action="store_true", help="Run all configured tests")
	parser.add_argument("--tags", nargs="+", help="Filter tests by tags")
	parser.add_argument("--generate-template", help="Generate a template config for a specific rule")

	args = parser.parse_args()

	if args.generate_template:
		framework = ConfigurableTestFramework()
		framework.generate_test_config_template(args.generate_template)
	elif args.run_tests:
		framework = ConfigurableTestFramework()
		results = framework.run_all_tests(tags=args.tags)

		print("\nTest Results Summary:")
		print(f"Total: {results['total']}")
		print(f"Passed: {results['passed']}")
		print(f"Failed: {results['failed']}")
		print(f"Skipped: {results['skipped']}")
		print(f"Errors: {results['errors']}")

		if results['failed'] > 0 or results['errors'] > 0:
			print("\nDetailed Results:")
			for result in results['results']:
				if result['status'] in ['failed', 'error']:
					print(f"\n{result['status'].upper()}: {result['name']}")
					if result['reason']:
						print(f"  Reason: {result['reason']}")
					if 'expectation_details' in result:
						for detail in result['expectation_details']:
							if not detail['met']:
								print(f"  Rule {detail['rule_name']}:")
								print(
									f"    Expected {detail['expected_count']} errors, got {detail['actual_count']}"
								)

		sys.exit(0 if results['failed'] == 0 and results['errors'] == 0 else 1)
	else:
		# Run as unittest - use modern approach
		loader = unittest.TestLoader()
		suite = unittest.TestSuite()
		suite.addTests(loader.loadTestsFromTestCase(ConfigurableTestRunner))
		runner = unittest.TextTestRunner(verbosity=2)
		result = runner.run(suite)
		sys.exit(0 if result.wasSuccessful() else 1)
