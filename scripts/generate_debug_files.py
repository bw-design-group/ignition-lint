#!/usr/bin/env python3
# pylint: disable=wrong-import-position
"""
Generate debug files for test cases.

This script processes all Perspective test cases in tests/cases/views/ and generates debug files
(flattened JSON, model state, statistics) in tests/debug/cases/{case_name}/ to avoid
conflicts with Ignition gateway overwriting files in the mounted test cases directory.

Usage:
  python scripts/generate_debug_files.py                    # Generate for all test cases
  python scripts/generate_debug_files.py PascalCase         # Generate for specific test case
  python scripts/generate_debug_files.py --clean            # Remove all debug directories
  python scripts/generate_debug_files.py --list             # List available test cases
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import List

# Add src to path (from scripts directory, go up one level to repo root)
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ignition_lint.common.flatten_json import read_json_file, flatten_json
from ignition_lint.linter import LintEngine
from ignition_lint.rules import RULES_MAP


def get_test_cases() -> List[Path]:
	"""Get all test case directories that contain view.json files."""
	# From scripts directory, go up one level to repo root, then to tests/cases
	cases_dir = Path(__file__).parent.parent / 'tests' / 'cases' / 'views'
	test_cases = []

	for case_dir in cases_dir.iterdir():
		if case_dir.is_dir() and (case_dir / 'view.json').exists():
			test_cases.append(case_dir)

	return sorted(test_cases)


def create_lint_engine() -> LintEngine:
	"""Create a lint engine exactly like the golden file test does."""
	# Store rule classes for creating fresh engines (same logic as test)
	rule_classes = []
	for rule_name, rule_class in RULES_MAP.items():
		try:
			# Test that we can create the rule (same as test)
			rule_class.create_from_config({})
			rule_classes.append(rule_class)
		except (TypeError, ValueError, AttributeError) as e:
			print(f"Warning: Could not create rule {rule_name}: {e}")

	# Create fresh rules (same as test)
	rules = []
	for rule_class in rule_classes:
		rules.append(rule_class.create_from_config({}))

	return LintEngine(rules)


def generate_debug_files_for_case(case_dir: Path, lint_engine: LintEngine) -> bool:
	"""Generate debug files for a specific test case."""
	view_file = case_dir / 'view.json'
	# Create debug files in tests/debug/cases/{case_name}/ instead of in the test case directory
	repo_root = Path(__file__).parent.parent
	debug_dir = repo_root / 'tests' / 'debug' / 'cases' / case_dir.name

	if not view_file.exists():
		print(f"❌ No view.json found in {case_dir.name}")
		return False

	try:
		# Read and flatten the JSON
		json_data = read_json_file(view_file)
		flattened_json = flatten_json(json_data)

		# Build the model
		lint_engine.flattened_json = flattened_json
		lint_engine.view_model = lint_engine.get_view_model()

		# Create debug directory (including parent directories)
		debug_dir.mkdir(parents=True, exist_ok=True)

		# Save flattened JSON
		with open(debug_dir / 'flattened.json', 'w', encoding='utf-8') as f:
			json.dump(flattened_json, f, indent=2, sort_keys=True)

		# Save serialized model
		serialized_model = lint_engine.serialize_view_model()
		with open(debug_dir / 'model.json', 'w', encoding='utf-8') as f:
			json.dump(serialized_model, f, indent=2, sort_keys=True)

		# Save statistics
		stats = lint_engine.get_model_statistics(flattened_json)
		with open(debug_dir / 'stats.json', 'w', encoding='utf-8') as f:
			json.dump(stats, f, indent=2, sort_keys=True)

		# Save a README explaining the debug files
		readme_content = f"""# Debug Golden Output Files for {case_dir.name}
Regenerate these files whenever the view.json is updated or when model builder logic changes.
These files help developers diagnose issues with the model building and rule application processes.

This directory contains debug information generated from `tests/cases/views/{case_dir.name}/view.json`:

## Files

- **`flattened.json`**: The flattened path-value representation of the original JSON
- **`model.json`**: The serialized object model with all nodes organized by type
- **`stats.json`**: Comprehensive statistics including node counts and rule coverage

## Generation

These files were generated using:
```bash
python scripts/generate_debug_files.py {case_dir.name}
```

## Usage

These files help developers understand:
1. How the JSON flattening process works
2. What nodes the model builder creates
3. Which rules apply to which nodes
4. Statistics about the view structure

"""

		with open(debug_dir / 'README.md', 'w', encoding='utf-8') as f:
			f.write(readme_content)

		print(f"✅ Generated debug files for {case_dir.name}")
		return True

	except (OSError, PermissionError, TypeError, ValueError, json.JSONDecodeError) as e:
		print(f"❌ Failed to generate debug files for {case_dir.name}: {e}")
		return False


def clean_debug_directories():
	"""Remove all debug directories."""
	repo_root = Path(__file__).parent.parent
	debug_cases_dir = repo_root / 'tests' / 'debug' / 'cases'

	if debug_cases_dir.exists():
		shutil.rmtree(debug_cases_dir)
		print("🗑️  Removed tests/debug/cases directory")
	else:
		print("No tests/debug/cases directory found to remove")


def list_test_cases():
	"""List all available test cases."""
	test_cases = get_test_cases()
	repo_root = Path(__file__).parent.parent
	debug_cases_dir = repo_root / 'tests' / 'debug' / 'cases'

	print(f"Available test cases ({len(test_cases)}):")
	for case_dir in test_cases:
		debug_exists = (debug_cases_dir / case_dir.name).exists()
		status = "🔍" if debug_exists else "  "
		print(f"  {status} {case_dir.name}")

	print("\n🔍 = has debug files")


def main():
	"""Main entry point."""
	parser = argparse.ArgumentParser(description="Generate debug files for test cases")
	parser.add_argument('test_cases', nargs='*', help='Specific test case names to process (default: all)')
	parser.add_argument('--clean', action='store_true', help='Remove all debug directories')
	parser.add_argument('--list', action='store_true', help='List available test cases')

	args = parser.parse_args()

	if args.clean:
		clean_debug_directories()
		return 0

	if args.list:
		list_test_cases()
		return 0

	# Get test cases to process
	all_test_cases = get_test_cases()

	if args.test_cases:
		# Process specific test cases
		test_cases_to_process = []
		for case_name in args.test_cases:
			case_dir = Path(__file__).parent.parent / 'tests' / 'cases' / case_name
			if case_dir in all_test_cases:
				test_cases_to_process.append(case_dir)
			else:
				print(f"❌ Test case '{case_name}' not found")
				print("Available test cases:")
				for tc in all_test_cases:
					print(f"  - {tc.name}")
				return 1
	else:
		# Process all test cases
		test_cases_to_process = all_test_cases

	print(f"Generating debug files for {len(test_cases_to_process)} test case(s)...")

	# Create lint engine
	lint_engine = create_lint_engine()
	print(f"Created lint engine with {len(lint_engine.rules)} rules")

	# Process each test case
	success_count = 0
	for case_dir in test_cases_to_process:
		if generate_debug_files_for_case(case_dir, lint_engine):
			success_count += 1

	print(f"\n📈 Summary: {success_count}/{len(test_cases_to_process)} test cases processed successfully")

	if success_count < len(test_cases_to_process):
		return 1

	return 0


if __name__ == "__main__":
	sys.exit(main())
