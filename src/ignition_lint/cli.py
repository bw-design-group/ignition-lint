"""
Command-line interface for ignition-lint.
"""

import json
import os
import sys
import argparse
import glob
import shutil
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
	from importlib.metadata import version, PackageNotFoundError
except ImportError:
	# Python < 3.8
	from importlib_metadata import version, PackageNotFoundError

LINE_WIDTH = 120


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
	from .common.flatten_json import read_json_file, write_json_file, flatten_json
	from .common.timing import PerformanceTimer, TimingCollector, FileTimings
	from .common.path_translator import PathTranslator
	from .common.fix_engine import FixEngine
	from .common.fix_operations import FixOperationType
	from .common.domain import DomainSpec, LintDomain
	from .domains import classify_file, default_globs, get_spec
	from .linter import (
		LintEngine, LintResults, merge_lint_results, DEBUG_OUTPUT_MARKER, read_debug_output_manifest,
		write_debug_output_manifest
	)
	from .rules import RULES_MAP
	from .rules.registry import get_rules_for_domain, resolve_rule_name
except ImportError:
	# Fall back to absolute imports (when run directly or from tests)
	current_dir = Path(__file__).parent
	src_dir = current_dir.parent
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from ignition_lint.common.flatten_json import read_json_file, write_json_file, flatten_json
	from ignition_lint.common.timing import PerformanceTimer, TimingCollector, FileTimings
	from ignition_lint.common.path_translator import PathTranslator
	from ignition_lint.common.fix_engine import FixEngine
	from ignition_lint.common.fix_operations import FixOperationType
	from ignition_lint.common.domain import DomainSpec, LintDomain
	from ignition_lint.domains import classify_file, default_globs, get_spec
	from ignition_lint.linter import (
		LintEngine, LintResults, merge_lint_results, DEBUG_OUTPUT_MARKER, read_debug_output_manifest,
		write_debug_output_manifest
	)
	from ignition_lint.rules import RULES_MAP
	from ignition_lint.rules.registry import get_rules_for_domain, resolve_rule_name


def cleanup_debug_files() -> None:
	"""
	Clean up old debug files from previous runs to prevent unbounded growth.

	Debug files are Python scripts saved by PylintScriptRule for troubleshooting.
	This removes files from previous runs (different PIDs) while preserving recent files.
	"""
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


def _prune_empty_parents(path: Path, root: Path) -> None:
	"""Remove now-empty ancestors of ``path`` up to, but excluding, ``root``."""
	current = path
	while current != root and root in current.parents:
		try:
			current.rmdir()
		except OSError:
			return
		current = current.parent


def cleanup_debug_output_dir(debug_output_dir: str, min_age_seconds: float = 5.0) -> int:
	"""
	Remove the previous run's folders from a --debug-output directory.

	Only folders listed in the marker manifest, i.e. ones ign-lint itself wrote, are
	removed; nothing else in the directory is ever touched. Folders written within
	``min_age_seconds`` are kept and carried over to the next run, since they belong to a
	parallel batch (pre-commit runs several processes against the same directory).
	Returns the number of folders removed.
	"""
	root = Path(debug_output_dir)
	marker = root / DEBUG_OUTPUT_MARKER
	if not root.is_dir() or not marker.exists():
		return 0

	root_resolved = root.resolve()
	now = time.time()
	kept: List[str] = []
	removed = 0
	for entry in read_debug_output_manifest(marker):
		target = root / entry
		try:
			if target.is_symlink() or not target.is_dir():
				continue
			resolved = target.resolve()
			if root_resolved not in resolved.parents:
				continue
			if now - target.stat().st_mtime < min_age_seconds:
				kept.append(entry)
				continue
			shutil.rmtree(target)
			removed += 1
			_prune_empty_parents(resolved.parent, root_resolved)
		except OSError:
			continue
	write_debug_output_manifest(marker, kept)
	return removed


def cleanup_old_batch_files(output_path: Path) -> None:
	"""
	Clean up old batch files from previous runs to prevent unbounded growth.

	This function is called at the start of a run, before any results are written.
	It removes batch files from previous runs (identified by different PIDs) but
	preserves files from the current run (same PID or very recent).
	"""
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

	# Check aggregated summary file (e.g., results_AGGREGATED_SUMMARY.txt)
	# These have no PID in the name, so age-based check only.
	# Stale summaries pollute new runs by reporting old totals (see
	# aggregate_batch_results: it reads an existing summary for non-batch paths).
	summary_file = output_path.parent / f"{base_name}_AGGREGATED_SUMMARY.txt"
	if summary_file.exists():
		try:
			file_age = current_time - summary_file.stat().st_mtime
			if file_age >= 5:
				files_to_clean.append(summary_file)
		except OSError:
			pass

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


BUNDLED_CONFIG_DIR = Path(__file__).parent / '.config'
DEFAULT_PRECOMMIT_CONFIG_NAME = '.ignition-lint-precommit.json'


def load_config(config_path: str) -> Optional[dict]:
	"""
	Load configuration from a JSON file.

	Returns the parsed dict on success (which may legitimately be empty when
	the user wants to run all rules with default kwargs), or None if the file
	cannot be read or parsed. When the requested file is the default pre-commit
	config and does not exist in the working directory, the copy bundled with
	the package is used, so the shipped hooks work in any consumer repository.
	"""
	path = Path(config_path)
	if not path.exists() and path.name == DEFAULT_PRECOMMIT_CONFIG_NAME:
		bundled = BUNDLED_CONFIG_DIR / DEFAULT_PRECOMMIT_CONFIG_NAME
		if bundled.exists():
			print(f"ℹ️  {config_path} not found; using the bundled default {bundled}")
			path = bundled
	try:
		with open(path, 'r', encoding='utf-8') as f:
			return json.load(f)
	except (FileNotFoundError, json.JSONDecodeError) as e:
		print(f"Error loading config file {config_path}: {e}")
		return None


def load_whitelist(whitelist_path: str) -> set:
	"""
	Load whitelist file containing paths to ignore.

	Args:
		whitelist_path: Path to whitelist text file

	Returns:
		Set of absolute file paths to ignore (empty set if file doesn't exist)
	"""
	whitelist = set()

	try:
		whitelist_file = Path(whitelist_path)
		if not whitelist_file.exists():
			return whitelist

		with open(whitelist_file, 'r', encoding='utf-8') as f:
			for line in f:
				# Strip whitespace
				line = line.strip()

				# Skip empty lines and comments
				if not line or line.startswith('#'):
					continue

				# Convert relative path to absolute
				try:
					file_path = Path(line).resolve()
					whitelist.add(file_path)
				except (ValueError, OSError) as e:
					print(f"⚠️  Warning: Invalid path in whitelist '{line}': {e}")
					continue

		return whitelist

	except (OSError, IOError) as e:
		print(f"⚠️  Warning: Could not read whitelist file {whitelist_path}: {e}")
		return set()


def generate_whitelist(patterns: List[str], output_file: str, append: bool = False, dry_run: bool = False) -> None:
	"""
	Generate whitelist file from glob patterns.

	Args:
		patterns: List of glob patterns to match files
		output_file: Path to output whitelist file
		append: If True, append to existing file; if False, overwrite
		dry_run: If True, print matched files without writing
	"""
	# Collect all matching files
	all_files = []
	for pattern in patterns:
		matching_files = glob.glob(pattern, recursive=True)
		all_files.extend(matching_files)

	# Convert to relative paths and sort
	relative_paths = []
	cwd = Path.cwd()
	for file_path in all_files:
		try:
			abs_path = Path(file_path).resolve()
			relative_path = abs_path.relative_to(cwd)
			relative_paths.append(str(relative_path))
		except (ValueError, OSError):
			# If path can't be made relative, use absolute
			relative_paths.append(file_path)

	# Remove duplicates and sort
	relative_paths = sorted(set(relative_paths))

	if dry_run:
		print(f"🔍 Would add {len(relative_paths)} files to whitelist:")
		for path in relative_paths[:20]:  # Show first 20
			print(f"  {path}")
		if len(relative_paths) > 20:
			print(f"  ... and {len(relative_paths) - 20} more files")
		return

	# Handle append mode
	existing_paths = set()
	if append and Path(output_file).exists():
		try:
			with open(output_file, 'r', encoding='utf-8') as f:
				for line in f:
					line = line.strip()
					if line and not line.startswith('#'):
						existing_paths.add(line)
		except (OSError, IOError) as e:
			print(f"⚠️  Warning: Could not read existing whitelist: {e}")

	# Combine existing and new paths
	if append:
		all_paths = sorted(existing_paths.union(set(relative_paths)))
	else:
		all_paths = relative_paths

	# Write whitelist file
	try:
		output_path = Path(output_file)
		output_path.parent.mkdir(parents=True, exist_ok=True)

		with open(output_path, 'w', encoding='utf-8') as f:
			f.write("# Ignition-lint whitelist - files to ignore during linting\n")
			f.write("# Lines starting with # are comments\n")
			f.write("# One file path per line (relative to repository root)\n")
			f.write(f"# Generated: {len(relative_paths)} files added\n")
			if append and existing_paths:
				f.write(f"# Existing: {len(existing_paths)} files\n")
			f.write("\n")

			for path in all_paths:
				f.write(f"{path}\n")

		mode = "appended to" if append and existing_paths else "generated"
		print(f"✓ Whitelist {mode}: {output_path}")
		print(f"  Total files: {len(all_paths)}")
		if append and existing_paths:
			print(f"  New files: {len(relative_paths)}")
			print(f"  Existing files: {len(existing_paths)}")

	except (OSError, IOError) as e:
		print(f"❌ Error writing whitelist file {output_file}: {e}")
		sys.exit(1)


def _resolve_alias_keys(config: dict) -> dict:
	"""
	Return ``config`` with deprecated rule names replaced by their canonical names.

	Prints one deprecation line per alias. When both the alias and the canonical
	name are present the canonical entry wins and the alias entry is dropped.
	"""
	resolved = {}
	for rule_name, rule_config in config.items():
		canonical, was_alias = resolve_rule_name(rule_name)
		if not was_alias:
			resolved.setdefault(canonical, rule_config)
			continue
		if canonical in config:
			print(
				f"⚠️  Config: '{rule_name}' is a deprecated alias of '{canonical}' and both are present; "
				f"using '{canonical}' and ignoring '{rule_name}'"
			)
			continue
		print(f"⚠️  Config: rule name '{rule_name}' is deprecated; use '{canonical}' instead")
		resolved[canonical] = rule_config
	return resolved


def _split_config_by_domain(config: dict) -> Dict[LintDomain, dict]:
	"""
	Route each rule entry of a flat config to the domain its rule class declares.

	Rule names are unique across domains, so the config file needs no domain
	grouping. Keys starting with ``_`` are comments and skipped; deprecated rule
	names are resolved with a deprecation notice; unknown rule names are reported.
	"""
	per_domain: Dict[LintDomain, dict] = {domain: {} for domain in LintDomain}
	for rule_name, rule_config in _resolve_alias_keys(config).items():
		if rule_name.startswith("_") or not isinstance(rule_config, dict):
			continue
		rule_class = RULES_MAP.get(rule_name)
		if rule_class is None:
			print(f"Unknown rule in config: {rule_name}")
			continue
		per_domain[rule_class.domain][rule_name] = rule_config
	return per_domain


def create_rules_from_config(config: dict, domain: Optional[LintDomain] = None) -> tuple:
	"""
	Create rule instances for every registered rule (of one domain, when given).

	All registered rules run by default. The user's config provides per-rule
	overrides: `kwargs` to customize behavior, `enabled: false` to opt out, or
	`allow_fix: false` to keep a fixable rule's violations detection-only (the
	rule still reports, but --fix and --fix-dry-run skip it). Rules absent from
	the config run with default kwargs and allow_fix=true. An explicit
	--fix-rules on the CLI overrides allow_fix (applied in setup_linter).

	Args:
		config: Rule-config dictionary (already routed per domain by
			_split_config_by_domain when ``domain`` is given; may be empty)
		domain: Restrict to rules of this domain. None (legacy callers) means every
			registered rule; alias/unknown keys are then reported here.

	Returns:
		Tuple of (rules, statuses):
			rules    -- list of instantiated LintingRule objects
			statuses -- list of dicts describing every registered rule, one per
						rule, with keys:
						  name   : rule class name
						  state  : "loaded" | "disabled" | "error"
						  source : "config" if user supplied kwargs, else "defaults"
						  detail : optional error/skip detail (str or None)
	"""
	if domain is None:
		# Whole-registry callers: resolve aliases and report unknown rules here.
		config = _resolve_alias_keys(config)
		for rule_name, rule_config in config.items():
			if rule_name.startswith("_") or not isinstance(rule_config, dict):
				continue
			if rule_name not in RULES_MAP:
				print(f"Unknown rule in config: {rule_name}")
		candidates = dict(RULES_MAP)
	else:
		candidates = get_rules_for_domain(domain)

	rules = []
	statuses = []
	for rule_name, rule_class in candidates.items():
		rule_config = config.get(rule_name, {})
		if not isinstance(rule_config, dict):
			rule_config = {}

		has_user_kwargs = bool(rule_config.get('kwargs'))
		source = "config" if (rule_name in config or has_user_kwargs) else "defaults"

		if not rule_config.get('enabled', True):
			statuses.append({
				"name": rule_name,
				"state": "disabled",
				"source": source,
				"detail": "enabled=false",
			})
			continue

		kwargs = rule_config.get('kwargs', {})
		allow_fix = rule_config.get('allow_fix', True)

		try:
			if not isinstance(allow_fix, bool):
				raise ValueError(f"allow_fix must be true or false; got {allow_fix!r}")
			rule = rule_class.create_from_config(kwargs)
			if hasattr(rule, 'allow_fix'):
				rule.allow_fix = allow_fix
			elif 'allow_fix' in rule_config:
				print(f"Note: allow_fix has no effect on {rule_name} (rule does not support auto-fix)")
			rules.append(rule)
			statuses.append({
				"name": rule_name,
				"state": "loaded",
				"source": source,
				"detail": "allow_fix=false" if not allow_fix else None,
			})
		except (TypeError, ValueError, AttributeError) as e:
			print(f"Error creating rule {rule_name}: {e}")
			statuses.append({
				"name": rule_name,
				"state": "error",
				"source": source,
				"detail": str(e),
			})
			continue

	return rules, statuses


def _print_rule_breakdown(statuses: list, config_path: str, domain_label: Optional[str] = None) -> None:
	"""
	Print a per-rule breakdown showing each registered rule's source.

	Called from setup_linter() under --verbose. Loaded rules are shown with
	their kwargs source (the config file or "defaults"); disabled rules are
	shown with the reason; rules that failed to instantiate are shown with
	the error.
	"""
	loaded = [s for s in statuses if s["state"] == "loaded"]
	disabled = [s for s in statuses if s["state"] == "disabled"]
	errored = [s for s in statuses if s["state"] == "error"]

	name_width = max((len(s["name"]) for s in statuses), default=0)
	scope = f" for {domain_label} files" if domain_label else ""
	print(f"✅ Loaded {len(loaded)} rules{scope}:")
	for status in loaded:
		source = f"config: {config_path}" if status["source"] == "config" else "defaults"
		extra = f", {status['detail']}" if status["detail"] else ""
		print(f"  • {status['name']:<{name_width}}  ({source}{extra})")

	for status in disabled:
		print(f"  ⊘ {status['name']:<{name_width}}  (skipped: {status['detail']})")

	for status in errored:
		print(f"  ✗ {status['name']:<{name_width}}  (error: {status['detail']})")


def get_view_file(file_path: Path) -> Dict[str, Any]:
	"""Read and flatten a JSON file."""
	try:
		json_data = read_json_file(file_path)
		return flatten_json(json_data)
	except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError) as e:
		print(f"Error reading or parsing file {file_path}: {e}")
		return {}


def flatten_collected_files(files_by_domain: Dict[LintDomain, List[Path]]) -> List[Path]:
	"""All collected paths across domains, in domain then collection order."""
	return [path for paths in files_by_domain.values() for path in paths]


def collect_files(args, whitelist: set) -> tuple[Dict[LintDomain, List[Path]], List[Path]]:
	"""
	Collect files to process, grouped by the lint domain each file belongs to.

	Explicit paths are classified through the domain registry; a path no domain
	recognises is reported and skipped. In glob mode the user's globs (or, on a bare
	run, the union of every domain's default globs) are expanded and filtered the
	same way.

	Args:
		args: Command-line arguments
		whitelist: Set of absolute file paths to ignore

	Returns:
		Tuple of (files_by_domain, whitelisted_files). ``files_by_domain`` only has
		keys for domains that received at least one file.
	"""
	files_by_domain: Dict[LintDomain, List[Path]] = {}
	files_ignored = []
	seen: set = set()

	def record(file_path: Path, *, warn_unknown: bool):
		"""Classify, whitelist-check and de-duplicate a file, recording it under its domain."""
		abs_path = file_path.resolve()
		if abs_path in seen:
			return
		seen.add(abs_path)
		spec = classify_file(file_path)
		if spec is None:
			if warn_unknown:
				print(
					f"⚠️  Skipped {file_path}: not a recognised Ignition resource "
					f"(view.json, script-python code.py)"
				)
			return
		if abs_path in whitelist:
			files_ignored.append(file_path)
			# Always print when a file is skipped (not just verbose mode)
			print(f"🔒 Skipped (whitelisted): {file_path}")
			return
		files_by_domain.setdefault(spec.domain, []).append(file_path)

	# Explicit file paths arrive via two argparse destinations that MUST be merged, not
	# treated as either/or. When pre-commit invokes `--files PATH1 PATH2 PATH3`, argparse
	# binds PATH1 to the single-value --files option and PATH2.. to the variadic `filenames`
	# positional. The old `if filenames: ... elif files: ...` dispatch discarded PATH1
	# whenever filenames was non-empty (i.e. for every multi-file commit). args.files is the
	# default glob sentinel (None) only on a bare run; any other value is an explicit path
	# argparse peeled off the --files list.
	explicit_paths = list(args.filenames)
	if args.filenames and args.files:
		# `--files A B C`: argparse bound A to the single-value --files option and B.. to the
		# positional. We still lint all of them, but the space-separated multi-file form is
		# ambiguous - warn and point users at the supported invocations.
		print(
			"⚠️  Deprecation: '--files' takes a single value (a glob or comma-separated list), so "
			"passing multiple space-separated paths after it is ambiguous and is deprecated.\n"
			"   All paths are still linted for now. Prefer one of:\n"
			"     • positional arguments:     ignition-lint FILE1 FILE2 ...\n"
			"     • a single --files value:   --files \"FILE1,FILE2\"   (or a glob, e.g. --files \"**/view.json\")\n"
			"   For pre-commit, drop the trailing '--files' from the hook args so staged files are "
			"passed positionally."
		)
		explicit_paths.insert(0, args.files)

	if explicit_paths:
		for filename in explicit_paths:
			file_path = Path(filename)
			if not file_path.exists():
				print(f"Warning: File {filename} does not exist")
				continue
			record(file_path, warn_unknown=True)
	else:
		# Glob mode: args.files is a comma-separated list of globs, or every domain's defaults.
		patterns = args.files if args.files else ",".join(default_globs())
		for file_pattern in patterns.split(","):
			pattern = file_pattern.strip()
			if not pattern:
				continue
			for file_path_str in glob.glob(pattern, recursive=True):
				file_path = Path(file_path_str)
				if not file_path.is_file():
					continue
				# Globs may match anything; only files some domain recognises are linted.
				record(file_path, warn_unknown=False)

	# Print summary if verbose mode
	if files_ignored and args.verbose:
		print(f"\n📊 Whitelist Summary: {len(files_ignored)} files skipped")

	return files_by_domain, files_ignored


def print_rule_violations(rule_name: str, violations: list, custom_formatted_output: str = None):
	"""
	Print violations for a rule, using custom formatting if available.

	Args:
		rule_name: Name of the rule
		violations: List of violation strings
		custom_formatted_output: Pre-captured custom formatted output for this severity
	"""
	if not violations and not custom_formatted_output:
		return

	print(f"\n  {rule_name}:")

	# Show regular violations first (e.g., indentation errors, data quality issues)
	# Filter out empty placeholders (used for counting only)
	if violations:
		for violation in violations:
			if violation.strip():  # Only show non-empty violations
				print(f"    • {violation}")

	# Then show custom formatted output (e.g., category-grouped pylint violations)
	if custom_formatted_output:
		print(custom_formatted_output)

	print()  # Extra blank line between rules


def print_file_results(lint_results, lint_engine=None) -> tuple[int, int]:
	"""
	Print warnings and errors for a file and return the counts.

	Args:
		lint_results: LintResults object containing warnings and errors
		lint_engine: Optional LintEngine instance (needed for custom rule formatting)

	Returns:
		tuple[int, int]: (warning_count, error_count)
	"""
	warning_count = sum(len(warning_list) for warning_list in lint_results.warnings.values())
	error_count = sum(len(error_list) for error_list in lint_results.errors.values())

	# Get custom formatted outputs if available
	custom_formatted_warnings = lint_results.custom_formatted_warnings if hasattr(
		lint_results, 'custom_formatted_warnings'
	) else {}
	custom_formatted_errors = lint_results.custom_formatted_errors if hasattr(
		lint_results, 'custom_formatted_errors'
	) else {}

	# Print errors first (more critical)
	# Show errors if there are regular violations OR custom formatted errors
	if error_count > 0 or custom_formatted_errors:
		print(f"\n❌ Found {error_count} errors:")
		for rule_name, error_list in lint_results.errors.items():
			custom_output = custom_formatted_errors.get(rule_name)
			print_rule_violations(rule_name, error_list, custom_formatted_output=custom_output)
		# Handle rules that only have custom formatted errors (no regular violations)
		for rule_name, custom_output in custom_formatted_errors.items():
			if rule_name not in lint_results.errors:
				print_rule_violations(rule_name, [], custom_formatted_output=custom_output)

	# Print warnings second
	# Show warnings if there are regular violations OR custom formatted warnings
	if warning_count > 0 or custom_formatted_warnings:
		print(f"\n⚠️  Found {warning_count} warnings:")
		for rule_name, warning_list in lint_results.warnings.items():
			custom_output = custom_formatted_warnings.get(rule_name)
			print_rule_violations(rule_name, warning_list, custom_formatted_output=custom_output)
		# Handle rules that only have custom formatted warnings (no regular violations)
		for rule_name, custom_output in custom_formatted_warnings.items():
			if rule_name not in lint_results.warnings:
				print_rule_violations(rule_name, [], custom_formatted_output=custom_output)

	return warning_count, error_count


def report_file_results(lint_results, lint_engine=None) -> tuple[int, int]:
	"""
	Print a file's warnings/errors plus a clean-result message, and return counts.

	Thin wrapper over print_file_results that also emits the "No issues found"
	message when a file is clean, so callers don't repeat that branch.
	"""
	warning_count, error_count = print_file_results(lint_results, lint_engine)
	if error_count == 0 and warning_count == 0:
		print("✅ No issues found")
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


def print_rule_analysis(lint_engine: LintEngine):
	"""Print detailed rule impact analysis for the engine's most recently loaded file."""
	analysis = lint_engine.analyze_rule_impact()

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


def print_debug_nodes(lint_engine: LintEngine, debug_node_types: List[str]):
	"""Print debug information for specific node types of the most recently loaded file."""
	debug_nodes = lint_engine.debug_nodes(None, debug_node_types or [])
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


def _apply_fix_rules_override(args, rules: list) -> None:
	"""Explicit --fix-rules overrides allow_fix=false for the rules it names."""
	fix_rules_arg = getattr(args, 'fix_rules', None)
	if not fix_rules_arg:
		return
	requested = set()
	for raw_name in (name.strip() for name in fix_rules_arg.split(',')):
		if not raw_name:
			continue
		canonical, was_alias = resolve_rule_name(raw_name)
		if was_alias:
			print(f"⚠️  --fix-rules: rule name '{raw_name}' is deprecated; use '{canonical}' instead")
		requested.add(canonical)
	loaded_names = {rule.__class__.__name__ for rule in rules}
	for rule in rules:
		if rule.__class__.__name__ in requested and hasattr(rule, 'allow_fix'):
			rule.allow_fix = True
	for name in sorted(requested - loaded_names):
		print(f"⚠️  --fix-rules: '{name}' does not match any loaded rule; its fixes cannot apply")
	for name in sorted(requested & loaded_names):
		rule = next(r for r in rules if r.__class__.__name__ == name)
		if not hasattr(rule, 'allow_fix'):
			print(f"⚠️  --fix-rules: '{name}' does not support auto-fix")


def setup_linter(args, domains: List[LintDomain]) -> Dict[LintDomain, LintEngine]:
	"""
	Build one LintEngine per domain that has files to lint.

	Exits when the configuration cannot be read, or when no domain ends up with any
	rule. A domain with zero configured rules is skipped with a note when other
	domains still have rules.
	"""
	engines: Dict[LintDomain, LintEngine] = {}

	if args.debug_output and Path(args.debug_output).exists() and not Path(args.debug_output).is_dir():
		print(f"❌ --debug-output target is not a directory: {args.debug_output}")
		sys.exit(1)

	if args.stats_only:
		for domain in domains:
			engines[domain] = LintEngine([], debug_output_dir=args.debug_output)
	else:
		config = load_config(args.config)
		if config is None:
			print("❌ No valid configuration found")
			sys.exit(1)

		print(f"🔧 Loaded configuration from {args.config}")
		sections = _split_config_by_domain(config)

		for domain in domains:
			display_name = get_spec(domain).display_name
			rules, rule_statuses = create_rules_from_config(sections.get(domain, {}), domain)
			if not rules:
				print(
					f"ℹ️  No rules configured for {display_name} files; they will be listed as skipped"
				)
				continue
			_apply_fix_rules_override(args, rules)
			engines[domain] = LintEngine(rules, debug_output_dir=args.debug_output)
			if args.verbose:
				_print_rule_breakdown(rule_statuses, args.config, display_name)

		if not engines:
			print("❌ No valid rules configured")
			sys.exit(1)

	# Inform about debug output
	if args.debug_output:
		print(f"🔍 Debug output will be saved to: {args.debug_output}")

	return engines


_FIX_UNAVAILABLE_NOTED: set = set()


def _fix_rule_filter(args) -> Optional[List[str]]:
	"""Canonical rule names from --fix-rules, or None when not given."""
	fix_rules_arg = getattr(args, 'fix_rules', None)
	if not fix_rules_arg:
		return None
	return [resolve_rule_name(name.strip())[0] for name in fix_rules_arg.split(',') if name.strip()]


def _note_fix_unavailable(spec: DomainSpec) -> None:
	"""Print, once per domain per run, that fix mode does nothing for non-JSON files."""
	if spec.domain not in _FIX_UNAVAILABLE_NOTED:
		_FIX_UNAVAILABLE_NOTED.add(spec.domain)
		print(f"ℹ️  Auto-fix is not available for {spec.display_name} files; linting only")


def _handle_fixes(lint_results, loaded, file_path: Path, spec: DomainSpec, *, lint_engine: LintEngine, args):
	"""
	Apply or preview fixes for a file and return the results to report.

	Fixes are applied BEFORE reporting so the reported results reflect the post-fix
	state rather than the violations we just fixed (see issue #94). Only JSON-backed
	domains support fixes; others get a one-time note per run.
	"""
	if loaded.json_data is None:
		_note_fix_unavailable(spec)
		return lint_results

	dry_run = getattr(args, 'fix_dry_run', False)
	safe_only = not getattr(args, 'fix_unsafe', False)
	rule_filter = _fix_rule_filter(args)

	if dry_run:
		# Dry run: nothing is mutated, so the pre-fix results stand.
		# Report them first, then preview what would be fixed.
		report_file_results(lint_results, lint_engine)
		print_fix_dry_run(lint_results.fixes, file_path, safe_only, rule_filter)
		return None

	# Apply fixes, then re-evaluate ONCE on the fixed document to produce accurate
	# output. The re-evaluation collects no fixes (fix_mode=False) and never calls
	# apply_fixes again, so there is no multi-pass fix loop.
	fix_engine = FixEngine(PathTranslator(loaded.json_data))
	fix_result = fix_engine.apply_fixes(lint_results.fixes, safe_only=safe_only, rule_filter=rule_filter)
	apply_and_report_fixes(fix_result, loaded.json_data, file_path)
	if fix_result.applied_count > 0:
		_, lint_results = lint_engine.process_file(file_path, spec, enable_timing=False, fix_mode=False)
	return lint_results


def process_single_file(
	file_path: Path, spec: DomainSpec, lint_engine: LintEngine, args, timer: Optional[PerformanceTimer] = None
) -> tuple[int, int, Optional[FileTimings], Optional[Any]]:
	"""
	Lint one file of any domain and return (warnings, errors, timings, lint_results).

	The domain spec loads the file; everything after that is generic. Fix handling is
	gated on the loader having produced a JSON document, never on the domain's name.
	"""
	if not file_path.exists():
		print(f"⚠️  File {file_path} does not exist, skipping")
		return 0, 0, None, None

	# Print file header before any processing
	print(f"\n📄 Evaluating file:\n    {file_path}")

	file_timer = PerformanceTimer() if timer else None
	if file_timer:
		file_timer.start()
		timer.start()

	# --fix-unsafe (and --fix-dry-run) imply fix mode on their own, so the flags act as
	# a choice between "safe only" (--fix) and "include unsafe" (--fix-unsafe).
	fix_mode = not args.stats_only and (
		getattr(args, 'fix_dry_run', False) or getattr(args, 'fix', False) or
		getattr(args, 'fix_unsafe', False)
	)

	try:
		loaded, lint_results = lint_engine.process_file(
			file_path, spec, enable_timing=bool(file_timer), fix_mode=fix_mode
		)
	except (OSError, ValueError, json.JSONDecodeError) as e:
		print(f"❌ Failed to read file, skipping: {e}")
		return 0, 0, None, None
	load_and_rules_ms = timer.stop() if file_timer else 0.0

	if not loaded.nodes and spec.domain == LintDomain.PERSPECTIVE and not loaded.flattened_json:
		print("❌ Failed to parse file, skipping")
		return 0, 0, None, None

	print_statistics(file_path, lint_engine.get_model_statistics(loaded), args.verbose or args.stats_only)

	if args.analyze_rules and not args.stats_only:
		print_rule_analysis(lint_engine)
	if args.debug_nodes is not None:
		print_debug_nodes(lint_engine, args.debug_nodes)

	if args.stats_only:
		return 0, 0, None, None

	# Preserve the first-pass rule timings; any post-fix re-evaluation runs
	# without timing so it would otherwise clobber the profiling record.
	rule_timings = lint_results.rule_timings

	if fix_mode and loaded.json_data is None:
		_note_fix_unavailable(spec)

	if fix_mode and lint_results.fixes:
		reported = _handle_fixes(lint_results, loaded, file_path, spec, lint_engine=lint_engine, args=args)
		if reported is None:
			# Dry run already printed the pre-fix results.
			file_warnings = sum(len(v) for v in lint_results.warnings.values())
			file_errors = sum(len(v) for v in lint_results.errors.values())
		else:
			lint_results = reported
			file_warnings, file_errors = report_file_results(lint_results, lint_engine)
	else:
		file_warnings, file_errors = report_file_results(lint_results, lint_engine)

	file_timings = None
	if file_timer:
		load_ms = loaded.timings
		rule_exec_ms = sum(rule_timings.values())
		model_build_ms = load_ms.get('model_build_ms')
		if model_build_ms is None:
			# Loader without JSON phases: attribute the whole load to model building.
			model_build_ms = max(load_and_rules_ms - rule_exec_ms, 0.0)
		file_timings = FileTimings(
			file_path=str(file_path), total_duration_ms=file_timer.stop(),
			file_read_ms=load_ms.get('file_read_ms',
							0.0), json_flatten_ms=load_ms.get('json_flatten_ms', 0.0),
			model_build_ms=model_build_ms, rule_execution_ms=rule_exec_ms, rule_timings=rule_timings
		)

	return file_warnings, file_errors, file_timings, lint_results


def format_rule_violations_for_file(rule_name: str, violations: list, custom_formatted_output: str = None) -> str:
	"""
	Format violations for a rule for file output, using custom formatting if available.

	Args:
		rule_name: Name of the rule
		violations: List of violation strings
		custom_formatted_output: Pre-captured custom formatted output from LintResults

	Returns:
		Formatted string for file output
	"""
	if not violations and not custom_formatted_output:
		return ""

	lines = []
	lines.append(f"  {rule_name}:")

	# Show regular violations first (e.g., indentation errors, data quality issues)
	# Filter out empty placeholders (used for counting only)
	if violations:
		for violation in violations:
			if violation.strip():  # Only show non-empty violations
				lines.append(f"    • {violation}")

	# Then show custom formatted output (e.g., category-grouped pylint violations)
	if custom_formatted_output:
		lines.append(custom_formatted_output)

	lines.append("")  # Extra blank line between rules
	lines.append("")

	return '\n'.join(lines)


def write_results_file(
	output_path: Path, results: List[Dict], total_warnings: int, total_errors: int, processed_files: int,
	files_with_issues: int, finalize_results=None, whitelisted_files: List[Path] = None
):
	"""Write linting results to an output file with detailed warnings and errors."""
	# Ensure parent directory exists
	output_path.parent.mkdir(parents=True, exist_ok=True)

	with open(output_path, 'w', encoding='utf-8') as f:
		f.write("=" * LINE_WIDTH + "\n")
		f.write("IGNITION-LINT RESULTS\n")
		f.write("=" * LINE_WIDTH + "\n\n")

		# Summary
		f.write("SUMMARY\n")
		f.write("-" * LINE_WIDTH + "\n")
		f.write(f"Files processed: {processed_files}\n")
		f.write(f"Total warnings:  {total_warnings}\n")
		f.write(f"Total errors:    {total_errors}\n")
		f.write(f"Files with issues: {files_with_issues}\n")
		f.write(f"Clean files:     {processed_files - files_with_issues}\n")
		if whitelisted_files:
			f.write(f"Files whitelisted: {len(whitelisted_files)}\n")
		f.write("\n")

		# Whitelisted files section
		if whitelisted_files:
			f.write("WHITELISTED FILES (SKIPPED)\n")
			f.write("-" * LINE_WIDTH + "\n")
			f.write(f"The following {len(whitelisted_files)} file(s) were skipped due to whitelist:\n\n")
			for file_path in whitelisted_files:
				f.write(f"  🔒 {file_path}\n")
			f.write("\n")

		# Per-file results
		f.write("PER-FILE RESULTS\n")
		f.write("=" * LINE_WIDTH + "\n\n")

		for result in results:
			# Determine status icon
			if result['errors'] > 0:
				status_icon = "❌"
			elif result['warnings'] > 0:
				status_icon = "⚠️"
			else:
				status_icon = "✅"

			# Separator line before filename for clear blocks
			f.write("-" * LINE_WIDTH + "\n")
			f.write(f"{status_icon} {result['file']}\n")
			f.write("-" * LINE_WIDTH + "\n")

			lint_results = result.get('lint_results')
			if lint_results:
				# Get custom formatted outputs if available
				custom_formatted_warnings = lint_results.custom_formatted_warnings if hasattr(
					lint_results, 'custom_formatted_warnings'
				) else {}
				custom_formatted_errors = lint_results.custom_formatted_errors if hasattr(
					lint_results, 'custom_formatted_errors'
				) else {}

				# Write errors first (more critical)
				if lint_results.errors:
					f.write(f"\nERRORS ({result['errors']} total):\n\n")
					for rule_name, error_list in lint_results.errors.items():
						if error_list:
							custom_output = custom_formatted_errors.get(rule_name)
							formatted = format_rule_violations_for_file(
								rule_name, error_list,
								custom_formatted_output=custom_output
							)
							f.write(formatted)

				# Write warnings second
				if lint_results.warnings:
					f.write(f"\nWARNINGS ({result['warnings']} total):\n\n")
					for rule_name, warning_list in lint_results.warnings.items():
						if warning_list:
							custom_output = custom_formatted_warnings.get(rule_name)
							formatted = format_rule_violations_for_file(
								rule_name, warning_list,
								custom_formatted_output=custom_output
							)
							f.write(formatted)
			else:
				# Fallback to just counts if lint_results not available
				if result['warnings'] > 0:
					f.write(f"  ⚠️  Warnings: {result['warnings']}\n")
				if result['errors'] > 0:
					f.write(f"  ❌ Errors:   {result['errors']}\n")

			f.write("\n")

		# Batch finalization results (if any)
		if finalize_results and (finalize_results.warnings or finalize_results.errors):
			f.write("=" * LINE_WIDTH + "\n")
			f.write("📦 BATCH RULE FINALIZATION RESULTS\n")
			f.write("=" * LINE_WIDTH + "\n\n")

			# Get custom formatted outputs if available
			finalize_custom_formatted_warnings = finalize_results.custom_formatted_warnings if hasattr(
				finalize_results, 'custom_formatted_warnings'
			) else {}
			finalize_custom_formatted_errors = finalize_results.custom_formatted_errors if hasattr(
				finalize_results, 'custom_formatted_errors'
			) else {}

			# Write finalization errors first (more critical)
			if finalize_results.errors:
				error_count = sum(len(e) for e in finalize_results.errors.values())
				f.write(f"\nERRORS ({error_count} total):\n\n")
				for rule_name, error_list in finalize_results.errors.items():
					if error_list:
						custom_output = finalize_custom_formatted_errors.get(rule_name)
						formatted = format_rule_violations_for_file(
							rule_name, error_list, custom_formatted_output=custom_output
						)
						f.write(formatted)

			# Write finalization warnings second
			if finalize_results.warnings:
				warning_count = sum(len(w) for w in finalize_results.warnings.values())
				f.write(f"\nWARNINGS ({warning_count} total):\n\n")
				for rule_name, warning_list in finalize_results.warnings.items():
					if warning_list:
						custom_output = finalize_custom_formatted_warnings.get(rule_name)
						formatted = format_rule_violations_for_file(
							rule_name, warning_list, custom_formatted_output=custom_output
						)
						f.write(formatted)

		f.write("=" * LINE_WIDTH + "\n")
		f.write("END OF RESULTS\n")
		f.write("=" * LINE_WIDTH + "\n")


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

	# Only aggregate when this invocation produced a batch file (has _pid and _batch).
	# A non-batch path means this is a standalone or first-batch run; its own totals
	# are already correct and the caller no longer overrides them from the summary.
	is_batch_file = '_pid' in results_path.name and '_batch' in results_path.name
	if not is_batch_file:
		return None

	# Find all related files to aggregate (base file + batch files)
	result_files = []

	# Check if base file exists (e.g., results.txt from first batch)
	base_file = parent_dir / f"{base_name}.txt"
	if base_file.exists():
		result_files.append(base_file)

	# Find all batch files (e.g., results_pid*_batch*.txt)
	pattern = f"{base_name}_pid*.txt"
	batch_files = [f for f in parent_dir.glob(pattern) if 'AGGREGATED_SUMMARY' not in f.name]
	result_files.extend(batch_files)

	# Sort for consistent ordering
	result_files = sorted(result_files)

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


def print_fix_dry_run(fixes, file_path, safe_only, rule_filter):
	"""Show proposed fixes without applying them."""
	print(f"\n{'=' * LINE_WIDTH}")
	print(f"Proposed Fixes for {file_path}:")
	print(f"{'=' * LINE_WIDTH}")

	safe_count = 0
	unsafe_count = 0
	filtered_count = 0

	for i, fix in enumerate(fixes, 1):
		# Check rule filter
		if rule_filter and fix.rule_name not in rule_filter:
			filtered_count += 1
			continue

		if fix.is_safe:
			safe_count += 1
			safety_label = "SAFE"
		else:
			unsafe_count += 1
			safety_label = f"UNSAFE - {fix.safety_notes}" if fix.safety_notes else "UNSAFE"

		print(f"\n  Fix {i} ({fix.rule_name}) [{safety_label}]:")
		print(f"    {fix.description}")
		print(f"    Operations:")
		for op in fix.operations:
			if op.operation == FixOperationType.SET_VALUE:
				print(f"      SET {op.format_path()}: '{op.old_value}' -> '{op.new_value}'")
			elif op.operation == FixOperationType.STRING_REPLACE:
				print(f"      REPLACE in {op.format_path()}:")
				print(f"              '{op.old_substring}' -> '{op.new_substring}'")
			elif op.operation == FixOperationType.DELETE_KEY:
				print(f"      DELETE {op.format_path()}")

	total = safe_count + unsafe_count
	print(f"\nSummary: {total} fixes ({safe_count} safe, {unsafe_count} unsafe)")
	if filtered_count:
		print(f"  Filtered out: {filtered_count} (not in --fix-rules)")
	if safe_only and unsafe_count > 0:
		print(f"  --fix would apply: {safe_count} safe fix(es)")
		print(f"  --fix --fix-unsafe would apply: {total} fix(es)")
	else:
		print(f"  Would apply: {total} fix(es)")


def apply_and_report_fixes(fix_result, json_data, file_path):
	"""Apply fixes and report results, writing modified JSON back to file."""
	if fix_result.applied_count > 0:
		print(f"\nApplying fixes to {file_path}:")
		for applied_fix in fix_result.applied:
			print(f"  Applied: {applied_fix.fix.description}")

		# Write modified JSON back to file
		write_json_file(file_path, json_data)
		print(f"  File updated: {file_path}")

	if fix_result.skipped_count > 0:
		for skipped_fix in fix_result.skipped:
			print(f"  Skipped: {skipped_fix.fix.description} ({skipped_fix.skip_reason})")

	print(f"\nApplied: {fix_result.applied_count} fix(es) | "
		f"Skipped: {fix_result.skipped_count} fix(es)")


def print_final_summary(
	processed_files: int, total_warnings: int, total_errors: int, files_with_issues: int, stats_only: bool,
	ignore_warnings: bool = False, skipped_files: int = 0
):
	"""Print the final summary of the linting process."""
	print("\n📈 Summary:")
	print(f"  Files processed: {processed_files}")
	if skipped_files:
		print(f"  ⏭️  Files skipped (no rules for their domain): {skipped_files}")

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


def _report_finalize_results(finalize_results: LintResults, file_count: int) -> tuple[int, int]:
	"""
	Print batch-finalization results and return (warnings, errors) counted.

	Only non-empty when rules ran in batch mode. With a single file the results are
	shown in the standard per-file format (the file header was already printed);
	with several files they get their own section.
	"""
	if not (finalize_results.warnings or finalize_results.errors):
		return 0, 0

	warning_count = sum(len(w) for w in finalize_results.warnings.values())
	error_count = sum(len(e) for e in finalize_results.errors.values())

	if file_count == 1:
		if warning_count > 0:
			print(f"\n⚠️ Found {warning_count} warnings:")
			for rule_name, warning_list in finalize_results.warnings.items():
				if warning_list:
					print(f"  📋 {rule_name} (warning):")
					for warning in warning_list:
						print(f"    • {warning}")
		if error_count > 0:
			print(f"\n❌ Found {error_count} errors:")
			for rule_name, error_list in finalize_results.errors.items():
				if error_list:
					print(f"  📋 {rule_name} (error):")
					for error in error_list:
						print(f"    • {error}")
	else:
		print("\n" + "=" * 80)
		print("📦 Batch Rule Results (All Files)")
		print("=" * 80)
		for rule_name, warning_list in finalize_results.warnings.items():
			for warning in warning_list:
				print(f"⚠️ {rule_name}: {warning}")
		for rule_name, error_list in finalize_results.errors.items():
			for error in error_list:
				print(f"❌ {rule_name}: {error}")

	return warning_count, error_count


def main():
	"""Main function to lint Ignition resource files for style inconsistencies."""
	parser = argparse.ArgumentParser(
		description="Lint Ignition Perspective views and project script library modules"
	)
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
		default=None,
		help=(
			"A SINGLE value: one file, a glob, or a comma-separated list of them "
			"(e.g. --files \"**/view.json\", --files \"**/script-python/**/code.py\" or "
			"--files \"a/view.json,b/view.json\"; default: **/view.json). To lint several files, "
			"prefer positional arguments "
			"(ignition-lint FILE1 FILE2 ...). Passing multiple space-separated paths after "
			"--files is deprecated."
		),
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
		help="Files to check: Perspective view.json and/or script-python code.py (pre-commit passes these)",
	)
	parser.add_argument(
		"--timing-output",
		help="File path to write detailed timing/profiling report (e.g., timing.txt)",
	)
	parser.add_argument(
		"--results-output",
		help="File path to write linting results (e.g., results.txt)",
	)
	parser.add_argument(
		"--whitelist",
		default=None,
		help="Path to whitelist file containing files to ignore (e.g., .whitelist.txt)",
	)
	parser.add_argument(
		"--no-whitelist",
		action="store_true",
		help="Disable whitelist even if --whitelist is specified (overrides --whitelist)",
	)
	parser.add_argument(
		"--generate-whitelist",
		nargs="+",
		metavar="PATTERN",
		help="Generate whitelist from glob patterns (e.g., 'views/legacy/**/*.json')",
	)
	parser.add_argument(
		"--whitelist-output",
		default=".whitelist.txt",
		help="Output file for generated whitelist (default: .whitelist.txt)",
	)
	parser.add_argument(
		"--append",
		action="store_true",
		help="Append to existing whitelist instead of overwriting (use with --generate-whitelist)",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Show what would be added to whitelist without writing file (use with --generate-whitelist)",
	)
	parser.add_argument(
		"--fix",
		action="store_true",
		help="Apply safe auto-fixes to view.json files",
	)
	parser.add_argument(
		"--fix-unsafe",
		action="store_true",
		help="Apply fixes, including unsafe ones that update references",
	)
	parser.add_argument(
		"--fix-dry-run",
		action="store_true",
		help="Show what fixes would be applied without modifying files",
	)
	parser.add_argument(
		"--fix-rules",
		default=None,
		help="Comma-separated list of rules to apply fixes from (default: all fixable rules)",
	)
	args = parser.parse_args()

	# Handle whitelist generation mode
	if args.generate_whitelist:
		generate_whitelist(
			patterns=args.generate_whitelist, output_file=args.whitelist_output, append=args.append,
			dry_run=args.dry_run
		)
		sys.exit(0)  # Exit after generating whitelist

	# Clean up old batch files from previous runs (prevents unbounded growth)
	if args.results_output:
		cleanup_old_batch_files(Path(args.results_output))
	if args.timing_output:
		cleanup_old_batch_files(Path(args.timing_output))

	# Clean up old debug files from previous runs
	cleanup_debug_files()
	if args.debug_output:
		removed = cleanup_debug_output_dir(args.debug_output)
		if removed and args.verbose:
			print(f"🧹 Removed {removed} stale debug-output entries from {args.debug_output}")

	# Load whitelist if specified and not disabled
	whitelist = set()
	if args.whitelist and not args.no_whitelist:
		whitelist = load_whitelist(args.whitelist)
		if whitelist and args.verbose:
			print(f"🔒 Loaded whitelist with {len(whitelist)} files")
		elif not whitelist and args.verbose:
			print(f"⚠️  Whitelist file specified but empty or not found: {args.whitelist}")
	elif args.no_whitelist and args.verbose:
		print("ℹ️  Whitelist disabled via --no-whitelist")

	# Collect files to process (excludes whitelisted files), grouped by domain
	files_by_domain, whitelisted_files = collect_files(args, whitelist)
	file_paths = flatten_collected_files(files_by_domain)
	if not file_paths:
		print("❌ No files specified or found")
		sys.exit(0)

	# One engine per domain that has files
	engines = setup_linter(args, list(files_by_domain))

	if args.verbose:
		print(f"📁 Processing {len(file_paths)} files")
		for domain, paths in files_by_domain.items():
			print(f"   • {get_spec(domain).display_name}: {len(paths)}")

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
	skipped_files = 0
	results_buffer = []  # Collect results for file output

	for domain, domain_paths in files_by_domain.items():
		spec = get_spec(domain)
		if domain not in engines:
			for file_path in domain_paths:
				print(f"⏭️  Skipped (no rules configured for {spec.display_name} files): {file_path}")
			skipped_files += len(domain_paths)
			continue
		for file_path in domain_paths:
			file_warnings, file_errors, file_timings, lint_results = process_single_file(
				file_path, spec, engines[domain], args, performance_timer
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

	# Finalize batch rules (e.g., PerspectiveScriptPylintRule in batch mode) across every engine.
	# NOTE: In non-batch mode (default), rules process per-file and finalize() returns empty results.
	finalize_results = None
	if not args.stats_only:
		finalize_results = merge_lint_results([
			engine.finalize_batch_rules(enable_timing=bool(performance_timer))
			for engine in engines.values()
		])
		finalize_warnings, finalize_errors = _report_finalize_results(finalize_results, len(file_paths))
		total_warnings += finalize_warnings
		total_errors += finalize_errors
		if finalize_warnings or finalize_errors:
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
			finalize_results, whitelisted_files
		)
		print("\n" + f"📝 Results written to: {results_path}")

		# Write _AGGREGATED_SUMMARY.txt across batch files (CI/disk artifact only).
		# Each invocation prints its own honest totals; we no longer override the
		# terminal summary with aggregated values, since pre-commit runs N separate
		# processes and the escalating per-batch overrides were confusing.
		aggregate_batch_results(results_path)

	# Print final summary
	print_final_summary(
		processed_files, total_warnings, total_errors, files_with_issues, args.stats_only, args.ignore_warnings,
		skipped_files
	)


if __name__ == "__main__":
	main()
