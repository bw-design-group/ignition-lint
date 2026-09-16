# pylint: disable=import-error,wrong-import-position
"""
Golden file test for LintEngine model generation.

This test validates that the LintEngine produces consistent model output by comparing
generated models against golden reference files. This catches regressions in:
- JSON flattening logic
- Model building process
- Node creation and serialization
- Statistics generation

The test runs first (alphabetically) to catch model builder issues early.
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ignition_lint.common.flatten_json import read_json_file, flatten_json
from ignition_lint.linter import LintEngine
from ignition_lint.rules import RULES_MAP


class TestGoldenFiles(unittest.TestCase):
	"""Test model generation against golden reference files."""

	@classmethod
	def setUpClass(cls): # pylint: disable=invalid-name
		"""Set up the test class."""
		# Store rule classes for creating fresh engines
		cls.rule_classes = []
		for rule_name, rule_class in RULES_MAP.items():
			try:
				# Test that we can create the rule
				rule_class.create_from_config({})
				cls.rule_classes.append(rule_class)
			except (TypeError, ValueError, AttributeError) as e:
				print(f"Warning: Could not create rule {rule_name}: {e}")

		# Get test cases directory
		cls.test_cases_dir = Path(__file__).parent.parent / 'cases' / 'views'

		# Get all test cases and validate golden files exist for all
		tests_dir = Path(__file__).parent.parent
		debug_cases_dir = tests_dir / 'debug' / 'cases'

		all_test_cases = []
		cls.test_cases_with_golden_files = []

		for case_dir in cls.test_cases_dir.iterdir():
			if case_dir.is_dir() and (case_dir / 'view.json').exists():
				all_test_cases.append(case_dir)
				if (debug_cases_dir / case_dir.name).exists():
					cls.test_cases_with_golden_files.append(case_dir)

		all_test_cases.sort()
		cls.test_cases_with_golden_files.sort()  # Ensure consistent order

		# Validate that we have golden files for ALL test cases
		missing_golden_files = [case.name for case in all_test_cases if case not in cls.test_cases_with_golden_files]
		if missing_golden_files:
			raise RuntimeError(
				f"Missing golden files for {len(missing_golden_files)} test case(s): {missing_golden_files}\n"
				f"Generate them with: python scripts/generate_debug_files.py {' '.join(missing_golden_files)}\n"
				"run `./scripts/generate_debug_files.py` to generate for all cases."
			)

	def _create_fresh_lint_engine(self) -> LintEngine:
		"""Create a fresh LintEngine instance to avoid state accumulation."""
		rules = []
		for rule_class in self.rule_classes:
			rules.append(rule_class.create_from_config({}))
		return LintEngine(rules)

	def test_00_golden_files_can_be_generated(self):
		"""Test that we can generate golden files for key test cases."""
		# Define test cases that should have golden reference files
		key_test_cases = ['PascalCase']  # Start with just one simple case

		for case_name in key_test_cases:
			case_dir = self.test_cases_dir / case_name
			if not case_dir.exists() or not (case_dir / 'view.json').exists():
				self.fail(f"Test case directory missing: {case_dir}")

			# Test that we can successfully process this case
			view_file = case_dir / 'view.json'
			json_data = read_json_file(view_file)
			flattened_json = flatten_json(json_data)

			lint_engine = self._create_fresh_lint_engine()
			lint_engine.flattened_json = flattened_json
			lint_engine.view_model = lint_engine.get_view_model()
			model = lint_engine.serialize_view_model()
			stats = lint_engine.get_model_statistics(flattened_json)

			# Verify we got reasonable data
			self.assertGreater(len(flattened_json), 0, f"No flattened data for {case_name}")
			self.assertGreater(stats.get('total_nodes', 0), 0, f"No nodes found for {case_name}")
			self.assertIn('components', model, f"No components model for {case_name}")

	def test_01_flattened_json_matches_golden(self):
		"""Test that JSON flattening produces output matching golden files."""
		if not self.test_cases_with_golden_files:
			self.skipTest(
				"No test cases with golden files found. Run: python scripts/generate_debug_files.py"
			)

		for case_dir in self.test_cases_with_golden_files:
			with self.subTest(test_case=case_dir.name):
				self._assert_flattened_json_matches(case_dir)

	def test_02_model_matches_golden(self):
		"""Test that model building produces output matching golden files."""
		if not self.test_cases_with_golden_files:
			self.skipTest(
				"No test cases with golden files found. Run: python scripts/generate_debug_files.py"
			)

		for case_dir in self.test_cases_with_golden_files:
			with self.subTest(test_case=case_dir.name):
				self._assert_model_matches(case_dir)

	def test_03_stats_match_golden(self):
		"""Test that statistics generation produces output matching golden files."""
		if not self.test_cases_with_golden_files:
			self.skipTest(
				"No test cases with golden files found. Run: python scripts/generate_debug_files.py"
			)

		for case_dir in self.test_cases_with_golden_files:
			with self.subTest(test_case=case_dir.name):
				self._assert_stats_match(case_dir)

	def _assert_flattened_json_matches(self, case_dir: Path):
		"""Assert that flattened JSON matches the golden file."""
		view_file = case_dir / 'view.json'
		# Updated path to tests/debug/cases/{case_name}/flattened.json
		tests_dir = Path(__file__).parent.parent
		golden_file = tests_dir / 'debug' / 'cases' / case_dir.name / 'flattened.json'

		# Generate current flattened JSON
		json_data = read_json_file(view_file)
		current_flattened = flatten_json(json_data)

		# Load golden file
		try:
			with open(golden_file, 'r', encoding='utf-8') as f:
				expected_flattened = json.load(f)
		except FileNotFoundError:
			self.fail(
				f"Golden file missing: {golden_file}\n"
				f"Generate it with: python scripts/generate_debug_files.py {case_dir.name}"
			)

		# Compare
		self.assertEqual(
			current_flattened, expected_flattened, f"Flattened JSON mismatch for {case_dir.name}. "
			f"Regenerate golden files with: python scripts/generate_debug_files.py {case_dir.name}"
		)

	def _assert_model_matches(self, case_dir: Path):
		"""Assert that the model matches the golden file."""
		view_file = case_dir / 'view.json'
		# Updated path to tests/debug/cases/{case_name}/model.json
		tests_dir = Path(__file__).parent.parent
		golden_file = tests_dir / 'debug' / 'cases' / case_dir.name / 'model.json'

		# Generate current model with fresh lint engine
		json_data = read_json_file(view_file)
		flattened_json = flatten_json(json_data)

		lint_engine = self._create_fresh_lint_engine()
		lint_engine.flattened_json = flattened_json
		lint_engine.view_model = lint_engine.get_view_model()
		current_model = lint_engine.serialize_view_model()

		# Load golden file
		try:
			with open(golden_file, 'r', encoding='utf-8') as f:
				expected_model = json.load(f)
		except FileNotFoundError:
			self.fail(
				f"Golden file missing: {golden_file}\n"
				f"Generate it with: python scripts/generate_debug_files.py {case_dir.name}"
			)

		# Compare models - use detailed comparison for better error messages
		self._compare_models_detailed(current_model, expected_model, case_dir.name)

	def _assert_stats_match(self, case_dir: Path):
		"""Assert that statistics match the golden file."""
		view_file = case_dir / 'view.json'
		# Updated path to tests/debug/cases/{case_name}/stats.json
		tests_dir = Path(__file__).parent.parent
		golden_file = tests_dir / 'debug' / 'cases' / case_dir.name / 'stats.json'

		# Generate current stats with fresh lint engine
		json_data = read_json_file(view_file)
		flattened_json = flatten_json(json_data)

		lint_engine = self._create_fresh_lint_engine()
		current_stats = lint_engine.get_model_statistics(flattened_json)

		# Load golden file
		try:
			with open(golden_file, 'r', encoding='utf-8') as f:
				expected_stats = json.load(f)
		except FileNotFoundError:
			self.fail(
				f"Golden file missing: {golden_file}\n"
				f"Generate it with: python scripts/generate_debug_files.py {case_dir.name}"
			)

		# Compare key statistics (ignore rule_coverage which may vary with new rules)
		important_stats = ['total_nodes', 'node_type_counts', 'components_by_type', 'model_keys']

		for stat_key in important_stats:
			self.assertEqual(
				current_stats.get(stat_key), expected_stats.get(stat_key),
				f"Statistics mismatch for {case_dir.name}.{stat_key}. "
				f"Regenerate golden files with: python scripts/generate_debug_files.py {case_dir.name}"
			)

	def _compare_models_detailed(self, current: Dict[str, Any], expected: Dict[str, Any], case_name: str):
		"""Compare models with detailed error reporting."""
		# Check model keys
		current_keys = set(current.keys())
		expected_keys = set(expected.keys())

		if current_keys != expected_keys:
			missing_keys = expected_keys - current_keys
			extra_keys = current_keys - expected_keys

			error_msg = f"Model structure mismatch for {case_name}:"
			if missing_keys:
				error_msg += f"\n  Missing keys: {sorted(missing_keys)}"
			if extra_keys:
				error_msg += f"\n  Extra keys: {sorted(extra_keys)}"
			error_msg += f"\n  Regenerate with: python scripts/generate_debug_files.py {case_name}"
			self.fail(error_msg)

		# Check each model section
		for key in expected_keys:
			current_section = current[key]
			expected_section = expected[key]

			# Compare counts
			if current_section.get('count', 0) != expected_section.get('count', 0):
				self.fail(
					f"Model count mismatch for {case_name}.{key}: "
					f"got {current_section.get('count', 0)}, expected {expected_section.get('count', 0)}. "
					f"Regenerate with: python scripts/generate_debug_files.py {case_name}"
				)

			# Compare node structures (without comparing exact node details which may vary)
			current_nodes = current_section.get('nodes', [])
			expected_nodes = expected_section.get('nodes', [])

			if len(current_nodes) != len(expected_nodes):
				self.fail(
					f"Model node count mismatch for {case_name}.{key}: "
					f"got {len(current_nodes)}, expected {len(expected_nodes)}. "
					f"Regenerate with: python scripts/generate_debug_files.py {case_name}"
				)

			# Compare node paths (order-independent)
			if current_nodes and expected_nodes:
				current_paths = sorted([node.get('path', '') for node in current_nodes])
				expected_paths = sorted([node.get('path', '') for node in expected_nodes])

				if current_paths != expected_paths:
					self.fail(
						f"Model node paths mismatch for {case_name}.{key}. "
						f"Current: {current_paths[:3]}{'...' if len(current_paths) > 3 else ''}, "
						f"Expected: {expected_paths[:3]}{'...' if len(expected_paths) > 3 else ''}. "
						f"Regenerate with: python scripts/generate_debug_files.py {case_name}"
					)


if __name__ == '__main__':
	unittest.main()
