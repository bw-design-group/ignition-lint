"""
Command-line interface for ignition-lint.
"""

import json
import sys
import argparse
import glob
from pathlib import Path
from typing import List, Dict, Any

# Handle both relative and absolute imports
try:
	# Try relative imports first (when run as module)
	from .common.flatten_json import read_json_file, flatten_json
	from .linter import LintEngine
	from .rules import RULES_MAP
except ImportError:
	# Fall back to absolute imports (when run directly or from tests)
	current_dir = Path(__file__).parent
	src_dir = current_dir.parent
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from ignition_lint.common.flatten_json import read_json_file, flatten_json
	from ignition_lint.linter import LintEngine
	from ignition_lint.rules import RULES_MAP


def load_config(config_path: str) -> dict:
	"""Load configuration from a JSON file."""
	try:
		with open(config_path, 'r', encoding='utf-8') as f:
			return json.load(f)
	except (FileNotFoundError, json.JSONDecodeError) as e:
		print(f"Error loading config file {config_path}: {e}")
		return {}


def create_rules_from_config(config: dict) -> list:
	"""
	Create rule instances from config dictionary using self-processing rules.

	Args:
		config: Configuration dictionary from config file
	"""
	rules = []
	for rule_name, rule_config in config.items():
		# Skip private keys or invalid configurations
		if rule_name.startswith("_") or not isinstance(rule_config, dict):
			continue

		if not rule_config.get('enabled', True):
			print(f"Skipping rule {rule_name} (config['enabled'] == False)")
			continue

		if rule_name not in RULES_MAP:
			print(f"Unknown rule: {rule_name}")
			continue

		rule_class = RULES_MAP[rule_name]
		kwargs = rule_config.get('kwargs', {})

		try:
			rules.append(rule_class.create_from_config(kwargs))
		except (TypeError, ValueError, AttributeError) as e:
			print(f"Error creating rule {rule_name}: {e}")
			continue

	return rules


def get_view_file(file_path: Path) -> Dict[str, Any]:
	"""Read and flatten a JSON file."""
	try:
		json_data = read_json_file(file_path)
		return flatten_json(json_data)
	except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError) as e:
		print(f"Error reading or parsing file {file_path}: {e}")
		return {}


def collect_files(args) -> List[Path]:
	"""Collect files to process based on arguments."""
	files_to_process = []

	# If filenames are provided directly (e.g., from pre-commit), use them
	if args.filenames:
		for filename in args.filenames:
			file_path = Path(filename)
			if file_path.exists():
				files_to_process.append(file_path)
			else:
				print(f"Warning: File {filename} does not exist")

	# Otherwise, use glob patterns
	elif args.files:
		for file_pattern in args.files.split(","):
			pattern = file_pattern.strip()
			matching_files = glob.glob(pattern, recursive=True)

			for file_path_str in matching_files:
				file_path = Path(file_path_str)
				# Only include view.json files specifically
				if file_path.exists() and file_path.name == "view.json":
					files_to_process.append(file_path)

	return files_to_process


def print_file_results(file_path: Path, lint_results) -> tuple[int, int]:
	"""
	Print warnings and errors for a file and return the counts.

	Args:
		file_path: Path to the file with results
		lint_results: LintResults object containing warnings and errors

	Returns:
		tuple[int, int]: (warning_count, error_count)
	"""
	warning_count = sum(len(warning_list) for warning_list in lint_results.warnings.values())
	error_count = sum(len(error_list) for error_list in lint_results.errors.values())

	# Print warnings first
	if warning_count > 0:
		print(f"\n⚠️  Found {warning_count} warnings in {file_path}:")
		for rule_name, warning_list in lint_results.warnings.items():
			if warning_list:
				print(f"  📋 {rule_name} (warning):")
				for warning in warning_list:
					print(f"    • {warning}")

	# Print errors
	if error_count > 0:
		print(f"\n❌ Found {error_count} errors in {file_path}:")
		for rule_name, error_list in lint_results.errors.items():
			if error_list:
				print(f"  📋 {rule_name} (error):")
				for error in error_list:
					print(f"    • {error}")

	return warning_count, error_count


def print_statistics(file_path: Path, stats: Dict[str, Any], verbose: bool = False):
	"""Print model statistics for a file."""
	if verbose:
		print(f"\n📊 Model statistics for {file_path}:")
		print(f"  Total nodes: {stats['total_nodes']}")

		print("  Node types found:")
		for node_type, count in stats['node_type_counts'].items():
			print(f"    {node_type}: {count}")

		if stats['components_by_type']:
			print("  Components by type:")
			for comp_type, count in stats['components_by_type'].items():
				print(f"    {comp_type}: {count}")

		if stats.get('rule_coverage'):
			print("  Rule coverage:")
			for rule_name, coverage in stats['rule_coverage'].items():
				target_types = ', '.join(coverage['target_types'])
				print(f"    {rule_name}: {coverage['applicable_node_count']} nodes ({target_types})")


def print_rule_analysis(lint_engine: LintEngine, flattened_json: Dict[str, Any]):
	"""Print detailed rule impact analysis."""
	analysis = lint_engine.analyze_rule_impact(flattened_json)

	print("\n🔍 Rule Impact Analysis:")
	for rule_name, rule_data in analysis.items():
		print(f"  📋 {rule_name}:")
		print(f"    Targets: {', '.join(rule_data['target_types'])}")
		print(f"    Will process: {rule_data['applicable_nodes']} nodes")

		if rule_data['node_details']:
			print("    Sample nodes:")
			for detail in rule_data['node_details']:
				print(f"      • {detail['path']}: {detail['summary']}")
		elif rule_data['sample_paths']:
			print(f"    Sample paths: {', '.join(rule_data['sample_paths'][:3])}")
		print()


def print_debug_nodes(lint_engine: LintEngine, flattened_json: Dict[str, Any], debug_node_types: List[str]):
	"""Print debug information for specific node types."""
	debug_nodes = lint_engine.debug_nodes(flattened_json, debug_node_types or [])
	if debug_node_types:
		print(f"\n🔧 Debug info for node types: {', '.join(debug_node_types)}")
	else:
		print("\n🔧 Debug info for all nodes:")

	for i, node_info in enumerate(debug_nodes[:10]):  # Limit to first 10
		print(f"  {i+1}. {node_info['path']} ({node_info['node_type']})")
		if 'summary' in node_info:
			print(f"     {node_info['summary']}")

	if len(debug_nodes) > 10:
		print(f"     ... and {len(debug_nodes) - 10} more nodes")


def setup_linter(args) -> LintEngine:
	"""Set up the linting engine with rules from configuration."""
	if args.stats_only:
		lint_engine = LintEngine([], debug_output_dir=args.debug_output)
	else:
		config = load_config(args.config)
		if not config:
			print("❌ No valid configuration found")
			sys.exit(1)

		print(f"🔧 Loaded configuration from {args.config}")
		rules = create_rules_from_config(config)
		if not rules:
			print("❌ No valid rules configured")
			sys.exit(1)

		lint_engine = LintEngine(rules, debug_output_dir=args.debug_output)

		if args.verbose:
			print(f"✅ Loaded {len(rules)} rules: {[rule.__class__.__name__ for rule in rules]}")

	# Inform about debug output
	if args.debug_output:
		print(f"🔍 Debug output will be saved to: {args.debug_output}")

	return lint_engine


def process_single_file(file_path: Path, lint_engine: LintEngine, args) -> tuple[int, int]:
	"""Process a single view file and return the warning and error counts."""
	if not file_path.exists():
		print(f"⚠️  File {file_path} does not exist, skipping")
		return 0, 0

	# Read and flatten the JSON file
	flattened_json = get_view_file(file_path)
	if not flattened_json:
		print(f"❌ Failed to read or parse {file_path}, skipping")
		return 0, 0

	# Get statistics
	stats = lint_engine.get_model_statistics(flattened_json)
	print_statistics(file_path, stats, args.verbose or args.stats_only)

	# Show rule analysis if requested
	if args.analyze_rules and not args.stats_only:
		print_rule_analysis(lint_engine, flattened_json)

	# Show debug node info if requested
	if args.debug_nodes is not None:
		print_debug_nodes(lint_engine, flattened_json, args.debug_nodes)

	# Run linting (unless stats-only mode)
	if not args.stats_only:
		lint_results = lint_engine.process(flattened_json, source_file_path=str(file_path))
		file_warnings, file_errors = print_file_results(file_path, lint_results)

		if file_errors == 0 and file_warnings == 0:
			print(f"✅ No issues found in {file_path}")
		elif file_errors == 0 and file_warnings > 0:
			print(f"✅ No errors found in {file_path} (warnings only)")

		return file_warnings, file_errors

	return 0, 0


def print_final_summary(
	processed_files: int, total_warnings: int, total_errors: int, files_with_issues: int, stats_only: bool,
	warnings_only_mode: bool = False
):
	"""Print the final summary of the linting process."""
	print("\n📈 Summary:")
	print(f"  Files processed: {processed_files}")

	if not stats_only:
		total_issues = total_warnings + total_errors
		if total_issues == 0:
			print("  ✅ No style inconsistencies found!")
			sys.exit(0)
		else:
			if total_warnings > 0:
				print(f"  ⚠️  Total warnings: {total_warnings}")
			if total_errors > 0:
				print(f"  ❌ Total errors: {total_errors}")
			print(f"  📁 Files with issues: {files_with_issues}")
			print(f"  📁 Clean files: {processed_files - files_with_issues}")

			# Exit with appropriate code based on warnings-only mode
			if warnings_only_mode and total_errors == 0:
				print("  ✅ No errors found (warnings only - allowing commit)")
				sys.exit(0)
			elif total_errors > 0:
				sys.exit(1)
			else:
				sys.exit(0)
	else:
		print("  📊 Statistics analysis complete")
		sys.exit(0)


def main():
	"""Main function to lint Ignition view.json files for style inconsistencies."""
	parser = argparse.ArgumentParser(description="Lint Ignition JSON files")
	parser.add_argument(
		"--config",
		default="rule_config.json",
		help="Path to configuration JSON file",
	)
	parser.add_argument(
		"--files",
		default="**/view.json",
		help="Comma-separated list of files or glob patterns to lint",
	)
	parser.add_argument(
		"--verbose",
		"-v",
		action="store_true",
		help="Show detailed statistics and information",
	)
	parser.add_argument(
		"--stats-only",
		action="store_true",
		help="Only show statistics, don't run linting rules",
	)
	parser.add_argument(
		"--debug-nodes",
		nargs="*",
		help="Show detailed info for specific node types (e.g., --debug-nodes tag_binding expression_binding)",
	)
	parser.add_argument(
		"--analyze-rules",
		action="store_true",
		help="Show detailed rule impact analysis",
	)
	parser.add_argument(
		"--debug-output",
		help="Directory to save debug files (flattened JSON, model state, statistics)",
	)
	parser.add_argument(
		"--warnings-only",
		action="store_true",
		help="Exit with code 0 when only warnings are found (useful for pre-commit hooks)",
	)
	parser.add_argument(
		"filenames",
		nargs="*",
		help="Filenames to check (from pre-commit)",
	)
	args = parser.parse_args()

	# Set up the linting engine
	lint_engine = setup_linter(args)

	# Collect files to process
	file_paths = collect_files(args)
	if not file_paths:
		print("❌ No files specified or found")
		sys.exit(0)

	if args.verbose:
		print(f"📁 Processing {len(file_paths)} files")

	# Process each file
	total_warnings = 0
	total_errors = 0
	files_with_issues = 0
	processed_files = 0

	for file_path in file_paths:
		file_warnings, file_errors = process_single_file(file_path, lint_engine, args)

		# All functions now return tuples, no need to check for -1
		processed_files += 1
		total_warnings += file_warnings
		total_errors += file_errors
		if file_warnings > 0 or file_errors > 0:
			files_with_issues += 1

	# Print final summary
	print_final_summary(
		processed_files, total_warnings, total_errors, files_with_issues, args.stats_only, args.warnings_only
	)


if __name__ == "__main__":
	main()
