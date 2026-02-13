"""
Command-line interface for ignition-lint.
"""

import json
import os
import sys
import argparse
import glob
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
	from importlib.metadata import version, PackageNotFoundError
except ImportError:
	# Python < 3.8
	from importlib_metadata import version, PackageNotFoundError


def get_version() -> str:
	"""Get package version, with fallback for development/testing."""
	try:
		return version('ignition-lint')
	except PackageNotFoundError:
		# Package not installed (development/testing mode)
		# Try to read version from pyproject.toml
		try:
			# Python 3.11+ has tomllib built-in
			try:
				import tomllib
			except ImportError:
				# Python < 3.11, try tomli if available
				try:
					import tomli as tomllib
				except ImportError:
					# No TOML parser available, return dev
					return 'dev'

			pyproject_path = Path(__file__).parent.parent.parent / 'pyproject.toml'
			if pyproject_path.exists():
				with open(pyproject_path, 'rb') as f:
					data = tomllib.load(f)
					return data.get('tool', {}).get('poetry', {}).get('version', 'dev')
		except Exception:
			pass
		return 'dev'


# Handle both relative and absolute imports
try:
	# Try relative imports first (when run as module)
	from .common.flatten_json import read_json_file, flatten_json
	from .common.timing import PerformanceTimer, TimingCollector, FileTimings
	from .linter import LintEngine
	from .rules import RULES_MAP
except ImportError:
	# Fall back to absolute imports (when run directly or from tests)
	current_dir = Path(__file__).parent
	src_dir = current_dir.parent
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from ignition_lint.common.flatten_json import read_json_file, flatten_json
	from ignition_lint.common.timing import PerformanceTimer, TimingCollector, FileTimings
	from ignition_lint.linter import LintEngine
	from ignition_lint.rules import RULES_MAP


def cleanup_debug_files() -> None:
	"""
	Clean up old debug files from previous runs to prevent unbounded growth.

	Debug files are Python scripts saved by PylintScriptRule for troubleshooting.
	This removes files from previous runs (different PIDs) while preserving recent files.
	"""
	import time

	# Determine debug directory using same logic as PylintScriptRule
	cwd = os.getcwd()
	debug_dir = None

	# Check if we're in test environment (same logic as _get_debug_directory)
	current_path = cwd
	while current_path != os.path.dirname(current_path):
		if os.path.basename(current_path) == 'tests':
			debug_dir = os.path.join(current_path, "debug")
			break
		elif os.path.exists(os.path.join(current_path, 'tests')):
			debug_dir = os.path.join(current_path, "tests", "debug")
			break
		current_path = os.path.dirname(current_path)

	# Fallback to .ignition-lint/debug
	if not debug_dir:
		debug_dir = os.path.join(cwd, ".ignition-lint", "debug")

	# Only clean if directory exists
	if not os.path.exists(debug_dir):
		return

	current_pid = os.getpid()
	current_time = time.time()

	# Find all .py debug files (format: HHMMSS_pid{PID}_{random}.py)
	files_to_clean = []
	for file_path in Path(debug_dir).glob("*_pid*_*.py"):
		# Extract PID from filename
		if f'_pid{current_pid}_' in file_path.name:
			# Same PID as current run - skip
			continue

		# Check if file is recent (less than 5 seconds old)
		try:
			file_age = current_time - file_path.stat().st_mtime
			if file_age < 5:
				# Very recent file, likely from parallel process - skip
				continue
		except OSError:
			pass

		# Old debug file from previous run - mark for deletion
		files_to_clean.append(file_path)

	# Clean up old files
	if files_to_clean:
		for file_path in files_to_clean:
			try:
				file_path.unlink()
			except OSError:
				# Silently ignore errors
				pass


def cleanup_old_batch_files(output_path: Path) -> None:
	"""
	Clean up old batch files from previous runs to prevent unbounded growth.

	This function is called at the start of a run, before any results are written.
	It removes batch files from previous runs (identified by different PIDs) but
	preserves files from the current run (same PID or very recent).
	"""
	import time

	if not output_path.parent.exists():
		return

	# Get current PID
	current_pid = os.getpid()
	current_time = time.time()

	# Find all related files (both base file and batch files)
	base_name = output_path.stem

	files_to_clean = []

	# Check the base file (e.g., results.txt)
	if output_path.exists():
		try:
			file_age = current_time - output_path.stat().st_mtime
			if file_age >= 5:
				# Old base file from previous run - mark for deletion
				files_to_clean.append(output_path)
		except OSError:
			pass

	# Check batch files (e.g., results_pid*_batch*.txt)
	pattern = f"{base_name}*batch*.txt"
	for file_path in output_path.parent.glob(pattern):
		# Skip aggregated summary files
		if 'AGGREGATED_SUMMARY' in file_path.name:
			continue

		# Extract PID from filename (e.g., results_pid12345_batch1.txt)
		if f'_pid{current_pid}_' in file_path.name:
			# Same PID as current run - skip
			continue

		# Check if file is recent (less than 5 seconds old)
		# This protects against race conditions with parallel processes
		try:
			file_age = current_time - file_path.stat().st_mtime
			if file_age < 5:
				# Very recent file, likely from parallel process - skip
				continue
		except OSError:
			pass

		# Old batch file from previous run - mark for deletion
		files_to_clean.append(file_path)

	# Clean up old files
	if files_to_clean:
		for file_path in files_to_clean:
			try:
				file_path.unlink()
			except OSError as e:
				# Silently ignore errors (file might be in use or already deleted)
				pass


def make_unique_output_path(original_path: Path) -> Path:
	"""
	Generate a unique output file path to prevent overwriting in batch processing.

	When pre-commit or other tools run ignition-lint in multiple batches,
	each batch would overwrite the same output file. This function ensures
	uniqueness by appending PID and batch number if the file already exists.

	Examples:
		results.txt -> results.txt (if doesn't exist)
		results.txt -> results_pid12345_batch1.txt (if exists)
		results.txt -> results_pid12345_batch2.txt (if batch1 also exists)
	"""
	if not original_path.exists():
		return original_path

	# File exists - make it unique with PID and batch number
	pid = os.getpid()
	stem = original_path.stem  # filename without extension
	suffix = original_path.suffix  # .txt, .json, etc.
	parent = original_path.parent

	# Try adding batch numbers until we find one that doesn't exist
	batch_num = 1
	while True:
		new_name = f"{stem}_pid{pid}_batch{batch_num}{suffix}"
		new_path = parent / new_name
		if not new_path.exists():
			return new_path
		batch_num += 1


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
		print(f"\n⚠️  Found {warning_count} warnings:")
		for rule_name, warning_list in lint_results.warnings.items():
			if warning_list:
				print(f"\n  📋 {rule_name} (warning):")
				for warning in warning_list:
					print(f"    • {warning}")

	# Print errors
	if error_count > 0:
		print(f"\n❌ Found {error_count} errors:")
		for rule_name, error_list in lint_results.errors.items():
			if error_list:
				print(f"\n  📋 {rule_name} (error):")
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


def process_single_file(
	file_path: Path, lint_engine: LintEngine, args, timer: Optional[PerformanceTimer] = None
) -> tuple[int, int, Optional[FileTimings], Optional[Any]]:
	"""Process a single view file and return the warning and error counts plus lint results."""
	if not file_path.exists():
		print(f"⚠️  File {file_path} does not exist, skipping")
		return 0, 0, None, None

	# Print file header before any processing
	print(f"\n📄 Evaluating file:\n    {file_path}")

	# Initialize timers if profiling is enabled
	file_timer = PerformanceTimer() if timer else None
	file_read_ms = 0.0
	flatten_ms = 0.0
	model_build_ms = 0.0
	rule_exec_ms = 0.0

	# Start overall file timing
	if file_timer:
		file_timer.start()

	# Time file reading
	if file_timer:
		timer.start()
	json_data = read_json_file(file_path)
	if file_timer:
		file_read_ms = timer.stop()

	if not json_data:
		print(f"❌ Failed to read file, skipping")
		return 0, 0, None, None

	# Time JSON flattening
	if file_timer:
		timer.start()
	flattened_json = flatten_json(json_data)
	if file_timer:
		flatten_ms = timer.stop()

	if not flattened_json:
		print(f"❌ Failed to parse file, skipping")
		return 0, 0, None, None

	# Time model building
	if file_timer:
		timer.start()
	stats = lint_engine.get_model_statistics(flattened_json)
	if file_timer:
		model_build_ms = timer.stop()

	print_statistics(file_path, stats, args.verbose or args.stats_only)

	# Show rule analysis if requested
	if args.analyze_rules and not args.stats_only:
		print_rule_analysis(lint_engine, flattened_json)

	# Show debug node info if requested
	if args.debug_nodes is not None:
		print_debug_nodes(lint_engine, flattened_json, args.debug_nodes)

	# Run linting (unless stats-only mode)
	file_timings = None
	if not args.stats_only:
		# Time rule execution
		if file_timer:
			timer.start()
		lint_results = lint_engine.process(
			flattened_json, source_file_path=str(file_path), enable_timing=bool(file_timer)
		)
		if file_timer:
			rule_exec_ms = timer.stop()

		file_warnings, file_errors = print_file_results(file_path, lint_results)

		if file_errors == 0 and file_warnings == 0:
			print(f"✅ No issues found")

		# Create timing record if profiling
		if file_timer:
			total_duration = file_timer.stop()
			file_timings = FileTimings(
				file_path=str(file_path), total_duration_ms=total_duration, file_read_ms=file_read_ms,
				json_flatten_ms=flatten_ms, model_build_ms=model_build_ms,
				rule_execution_ms=rule_exec_ms, rule_timings=lint_results.rule_timings
			)

		return file_warnings, file_errors, file_timings, lint_results

	return 0, 0, None, None


def write_results_file(
	output_path: Path, results: List[Dict], total_warnings: int, total_errors: int, processed_files: int,
	files_with_issues: int, finalize_results=None
):
	"""Write linting results to an output file with detailed warnings and errors."""
	# Ensure parent directory exists
	output_path.parent.mkdir(parents=True, exist_ok=True)

	with open(output_path, 'w', encoding='utf-8') as f:
		f.write("=" * 80 + "\n")
		f.write("IGNITION-LINT RESULTS\n")
		f.write("=" * 80 + "\n\n")

		# Summary
		f.write("SUMMARY\n")
		f.write("-" * 80 + "\n")
		f.write(f"Files processed: {processed_files}\n")
		f.write(f"Total warnings:  {total_warnings}\n")
		f.write(f"Total errors:    {total_errors}\n")
		f.write(f"Files with issues: {files_with_issues}\n")
		f.write(f"Clean files:     {processed_files - files_with_issues}\n\n")

		# Per-file results
		f.write("PER-FILE RESULTS\n")
		f.write("=" * 80 + "\n\n")

		for result in results:
			status = "✅ CLEAN" if result['warnings'] == 0 and result['errors'] == 0 else "⚠️  ISSUES"
			f.write(f"{status} - {result['file']}\n")
			f.write("-" * 80 + "\n")

			lint_results = result.get('lint_results')
			if lint_results:
				# Write warnings with details
				if lint_results.warnings:
					f.write(f"⚠️  WARNINGS ({result['warnings']} total):\n\n")
					for rule_name, warning_list in lint_results.warnings.items():
						if warning_list:
							f.write(f"  📋 {rule_name}:\n")
							for warning in warning_list:
								f.write(f"    • {warning}\n")
							f.write("\n")

				# Write errors with details
				if lint_results.errors:
					f.write(f"❌ ERRORS ({result['errors']} total):\n\n")
					for rule_name, error_list in lint_results.errors.items():
						if error_list:
							f.write(f"  📋 {rule_name}:\n")
							for error in error_list:
								f.write(f"    • {error}\n")
							f.write("\n")
			else:
				# Fallback to just counts if lint_results not available
				if result['warnings'] > 0:
					f.write(f"  ⚠️  Warnings: {result['warnings']}\n")
				if result['errors'] > 0:
					f.write(f"  ❌ Errors:   {result['errors']}\n")

			f.write("\n")

		# Batch finalization results (if any)
		if finalize_results and (finalize_results.warnings or finalize_results.errors):
			f.write("=" * 80 + "\n")
			f.write("📦 BATCH RULE FINALIZATION RESULTS\n")
			f.write("=" * 80 + "\n\n")

			# Write finalization warnings
			if finalize_results.warnings:
				warning_count = sum(len(w) for w in finalize_results.warnings.values())
				f.write(f"⚠️  WARNINGS ({warning_count} total):\n\n")
				for rule_name, warning_list in finalize_results.warnings.items():
					if warning_list:
						f.write(f"  📋 {rule_name}:\n")
						for warning in warning_list:
							f.write(f"    • {warning}\n")
						f.write("\n")

			# Write finalization errors
			if finalize_results.errors:
				error_count = sum(len(e) for e in finalize_results.errors.values())
				f.write(f"❌ ERRORS ({error_count} total):\n\n")
				for rule_name, error_list in finalize_results.errors.items():
					if error_list:
						f.write(f"  📋 {rule_name}:\n")
						for error in error_list:
							f.write(f"    • {error}\n")
						f.write("\n")

		f.write("=" * 80 + "\n")
		f.write("END OF RESULTS\n")
		f.write("=" * 80 + "\n")


def aggregate_batch_results(results_path: Path) -> Optional[Dict[str, int]]:
	"""
	Aggregate results from multiple batch files into a summary file.

	When ignition-lint runs in batches (e.g., via pre-commit), multiple result files
	are created. This function aggregates them into a single summary for easy review.

	Returns:
		Dictionary with aggregated totals if multiple batches exist, None otherwise.
		Keys: 'files', 'warnings', 'errors', 'issues', 'clean'
	"""
	import re
	from datetime import datetime

	# Find base name and directory
	parent_dir = results_path.parent
	if '_pid' in results_path.name:
		base_name = results_path.stem.split('_pid')[0]
	else:
		base_name = results_path.stem

	# First check if an aggregated summary already exists
	summary_path = parent_dir / f"{base_name}_AGGREGATED_SUMMARY.txt"
	if summary_path.exists():
		# Read and return totals from existing aggregated summary
		try:
			with open(summary_path, 'r', encoding='utf-8') as f:
				content = f.read()
				files_match = re.search(r'Files processed:\s+(\d+)', content)
				warnings_match = re.search(r'Total warnings:\s+(\d+)', content)
				errors_match = re.search(r'Total errors:\s+(\d+)', content)
				issues_match = re.search(r'Files with issues:\s+(\d+)', content)
				clean_match = re.search(r'Clean files:\s+(\d+)', content)

				if files_match:
					return {
						'files': int(files_match.group(1)),
						'warnings': int(warnings_match.group(1)) if warnings_match else 0,
						'errors': int(errors_match.group(1)) if errors_match else 0,
						'issues': int(issues_match.group(1)) if issues_match else 0,
						'clean': int(clean_match.group(1)) if clean_match else 0,
					}
		except (OSError, IOError):
			pass  # If we can't read it, fall through to aggregation logic

	# Check if this is a batched result (has _pid and _batch in name)
	if '_pid' not in results_path.name or '_batch' not in results_path.name:
		# Not a batch file, no aggregation needed
		return None

	# Find all related batch files
	pattern = f"{base_name}_pid*.txt"  # Only match batch files with _pid pattern

	# Find all matching result files (excluding aggregated summary)
	result_files = sorted([f for f in parent_dir.glob(pattern) if 'AGGREGATED_SUMMARY' not in f.name])
	if len(result_files) <= 1:
		# Only one file, no need to aggregate
		return None

	# Parse each result file and collect totals
	total_files = 0
	total_warnings = 0
	total_errors = 0
	total_issues = 0
	total_clean = 0
	batch_details = []

	for file_path in result_files:
		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				content = f.read()

				# Extract metrics using regex
				files_match = re.search(r'Files processed:\s+(\d+)', content)
				warnings_match = re.search(r'Total warnings:\s+(\d+)', content)
				errors_match = re.search(r'Total errors:\s+(\d+)', content)
				issues_match = re.search(r'Files with issues:\s+(\d+)', content)
				clean_match = re.search(r'Clean files:\s+(\d+)', content)

				if files_match:
					files = int(files_match.group(1))
					warnings = int(warnings_match.group(1)) if warnings_match else 0
					errors = int(errors_match.group(1)) if errors_match else 0
					issues = int(issues_match.group(1)) if issues_match else 0
					clean = int(clean_match.group(1)) if clean_match else 0

					total_files += files
					total_warnings += warnings
					total_errors += errors
					total_issues += issues
					total_clean += clean

					batch_details.append({
						'filename': file_path.name,
						'files': files,
						'warnings': warnings,
						'errors': errors,
						'issues': issues,
						'clean': clean
					})
		except (OSError, IOError) as e:
			print(f"⚠️  Warning: Could not read {file_path.name}: {e}")
			continue

	# Write aggregated summary
	if batch_details:
		summary_path = parent_dir / f"{base_name}_AGGREGATED_SUMMARY.txt"
		try:
			with open(summary_path, 'w', encoding='utf-8') as f:
				f.write("=" * 80 + "\n")
				f.write("AGGREGATED IGNITION-LINT RESULTS SUMMARY\n")
				f.write("=" * 80 + "\n")
				f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
				f.write(f"Total batches: {len(batch_details)}\n")
				f.write("\n")

				# Overall summary
				f.write("TOTAL SUMMARY ACROSS ALL BATCHES\n")
				f.write("-" * 80 + "\n")
				f.write(f"Files processed:      {total_files}\n")
				f.write(f"Total warnings:       {total_warnings:,}\n")
				f.write(f"Total errors:         {total_errors:,}\n")
				f.write(f"Files with issues:    {total_issues}\n")
				f.write(f"Clean files:          {total_clean}\n")
				f.write("\n")

				# Breakdown by batch
				f.write("BREAKDOWN BY BATCH\n")
				f.write("-" * 80 + "\n")
				for batch in batch_details:
					f.write(
						f"{batch['filename']:<45} "
						f"Files: {batch['files']:>3}  "
						f"Warnings: {batch['warnings']:>4}  "
						f"Errors: {batch['errors']:>4}  "
						f"Issues: {batch['issues']:>3}  "
						f"Clean: {batch['clean']:>3}\n"
					)

				f.write("\n")
				f.write("=" * 80 + "\n")
				f.write("END OF AGGREGATED SUMMARY\n")
				f.write("=" * 80 + "\n")

			print(f"\n📊 Aggregated summary written to: {summary_path}")

			# Return aggregated totals for final summary display
			return {
				'files': total_files,
				'warnings': total_warnings,
				'errors': total_errors,
				'issues': total_issues,
				'clean': total_clean
			}
		except (OSError, IOError) as e:
			print(f"⚠️  Warning: Could not write aggregated summary: {e}")

	return None


def print_final_summary(
	processed_files: int, total_warnings: int, total_errors: int, files_with_issues: int, stats_only: bool,
	ignore_warnings: bool = False
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

			# Exit with appropriate code based on ignore-warnings mode
			if ignore_warnings and total_errors == 0:
				print("  ✅ No errors found (ignoring warnings)")
				sys.exit(0)
			elif total_errors > 0:
				sys.exit(1)
			else:
				# Has warnings but no errors, and not ignoring warnings
				sys.exit(1)
	else:
		print("  📊 Statistics analysis complete")
		sys.exit(0)


def main():
	"""Main function to lint Ignition view.json files for style inconsistencies."""
	parser = argparse.ArgumentParser(description="Lint Ignition JSON files")
	parser.add_argument(
		"--version",
		action="version",
		version=f"%(prog)s {get_version()}",
	)
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
		"--ignore-warnings",
		action="store_true",
		help="Don't fail on warnings, only on errors (warnings are still displayed)",
	)
	parser.add_argument(
		"filenames",
		nargs="*",
		help="Filenames to check (from pre-commit)",
	)
	parser.add_argument(
		"--timing-output",
		help="File path to write detailed timing/profiling report (e.g., timing.txt)",
	)
	parser.add_argument(
		"--results-output",
		help="File path to write linting results (e.g., results.txt)",
	)
	args = parser.parse_args()

	# Clean up old batch files from previous runs (prevents unbounded growth)
	if args.results_output:
		cleanup_old_batch_files(Path(args.results_output))
	if args.timing_output:
		cleanup_old_batch_files(Path(args.timing_output))

	# Clean up old debug files from previous runs
	cleanup_debug_files()

	# Set up the linting engine
	lint_engine = setup_linter(args)

	# Collect files to process
	file_paths = collect_files(args)
	if not file_paths:
		print("❌ No files specified or found")
		sys.exit(0)

	if args.verbose:
		print(f"📁 Processing {len(file_paths)} files")

	# Initialize timing collector if timing output is requested
	timing_collector = TimingCollector() if args.timing_output else None
	performance_timer = PerformanceTimer() if args.timing_output else None

	if timing_collector:
		timing_collector.start_total_timing()
		print(f"🔍 Performance profiling enabled (output: {args.timing_output})")

	# Process each file
	total_warnings = 0
	total_errors = 0
	files_with_issues = 0
	processed_files = 0
	results_buffer = []  # Collect results for file output

	for file_path in file_paths:
		file_warnings, file_errors, file_timings, lint_results = process_single_file(
			file_path, lint_engine, args, performance_timer
		)

		# Track timing if enabled
		if timing_collector and file_timings:
			timing_collector.add_file_timing(file_timings)

		# Collect results for output file if specified
		if args.results_output and not args.stats_only:
			results_buffer.append({
				'file': str(file_path),
				'warnings': file_warnings,
				'errors': file_errors,
				'lint_results': lint_results  # Include detailed messages
			})

		# All functions now return tuples, no need to check for -1
		processed_files += 1
		total_warnings += file_warnings
		total_errors += file_errors
		if file_warnings > 0 or file_errors > 0:
			files_with_issues += 1

	# Finalize batch rules (e.g., PylintScriptRule in batch mode)
	# NOTE: In non-batch mode (default), rules process per-file and finalize() returns empty results
	# This section only produces output for rules running in batch mode (processing all files together)
	finalize_results = None
	if not args.stats_only:
		finalize_results = lint_engine.finalize_batch_rules(enable_timing=bool(performance_timer))

		# Process finalization results (only non-empty when rules run in batch mode)
		if finalize_results.warnings or finalize_results.errors:
			finalize_warning_count = sum(len(w) for w in finalize_results.warnings.values())
			finalize_error_count = sum(len(e) for e in finalize_results.errors.values())

			# If only one file was processed, show batch results in standard format
			# (File path already shown in file header)
			if len(file_paths) == 1:
				# Print warnings
				if finalize_warning_count > 0:
					print(f"\n⚠️  Found {finalize_warning_count} warnings:")
					for rule_name, warning_list in finalize_results.warnings.items():
						if warning_list:
							print(f"  📋 {rule_name} (warning):")
							for warning in warning_list:
								print(f"    • {warning}")
								total_warnings += 1

				# Print errors
				if finalize_error_count > 0:
					print(f"\n❌ Found {finalize_error_count} errors:")
					for rule_name, error_list in finalize_results.errors.items():
						if error_list:
							print(f"  📋 {rule_name} (error):")
							for error in error_list:
								print(f"    • {error}")
								total_errors += 1
			else:
				# Multiple files: show batch results in separate section
				print("\n" + "=" * 80)
				print("📦 Batch Rule Results (All Files)")
				print("=" * 80)

				# Print warnings and errors
				for rule_name, warning_list in finalize_results.warnings.items():
					for warning in warning_list:
						print(f"⚠️  {rule_name}: {warning}")
						total_warnings += 1

				for rule_name, error_list in finalize_results.errors.items():
					for error in error_list:
						print(f"❌ {rule_name}: {error}")
						total_errors += 1

			# Update files_with_issues count if finalization found issues
			if finalize_results.has_errors or finalize_results.warnings:
				files_with_issues = max(files_with_issues, 1)  # At least one file had issues

	# Stop timing if enabled
	if timing_collector:
		timing_collector.stop_total_timing()

	# Write timing report if requested
	if args.timing_output and timing_collector:
		timing_path = make_unique_output_path(Path(args.timing_output))
		timing_collector.write_timing_report(timing_path)

		print("\n" + f"📊 Timing report written to: {timing_path}")

	# Write results file if requested
	if args.results_output and results_buffer:
		results_path = make_unique_output_path(Path(args.results_output))
		write_results_file(
			results_path, results_buffer, total_warnings, total_errors, processed_files, files_with_issues,
			finalize_results
		)
		print("\n" + f"📝 Results written to: {results_path}")

		# Aggregate batch results if multiple batches exist
		aggregated_totals = aggregate_batch_results(results_path)

		# Use aggregated totals for final summary if available
		if aggregated_totals:
			total_warnings = aggregated_totals['warnings']
			total_errors = aggregated_totals['errors']
			processed_files = aggregated_totals['files']
			files_with_issues = aggregated_totals['issues']

	# Print final summary
	print_final_summary(
		processed_files, total_warnings, total_errors, files_with_issues, args.stats_only, args.ignore_warnings
	)


if __name__ == "__main__":
	main()
