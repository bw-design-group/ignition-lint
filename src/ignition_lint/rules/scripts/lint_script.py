"""
This module defines a PylintScriptRule class that runs pylint on the scripts contained within a Perspective View.
It collects all script nodes, combines them into a single temporary file, and runs pylint on that file.
"""

import datetime
import os
import re
import shutil
import sys
import tempfile
from typing import Dict, List, Optional, Tuple

from io import StringIO
from pylint import lint
from pylint.reporters.text import TextReporter

from ..common import ScriptRule
from ...model.node_types import ScriptNode


class PylintScriptRule(ScriptRule):
	"""Rule to run pylint on all script types using the simplified interface."""

	def __init__(self, severity="error", pylintrc=None, debug=False, batch_mode=True, debug_dir=None):
		super().__init__(severity=severity)  # Targets all script types by default
		self.debug = debug  # Debug mode disabled by default for performance
		self.batch_mode = batch_mode  # Batch mode enabled by default for performance
		self.debug_dir_config = debug_dir  # User-configured debug directory
		self.pylintrc = self._resolve_pylintrc_path(pylintrc)
		if self.debug:
			if self.pylintrc:
				print(f"🔍 PylintScriptRule: Using pylintrc: {self.pylintrc}")
			else:
				print("🔍 PylintScriptRule: No pylintrc found, using inline configuration")

	def _resolve_pylintrc_path(self, pylintrc: Optional[str]) -> Optional[str]:
		"""Resolve the pylintrc file path with fallback to standard location."""
		# If a specific pylintrc is provided, use it if it exists
		if pylintrc:
			if os.path.isabs(pylintrc):
				if os.path.exists(pylintrc):
					return pylintrc
				else:
					print(f"⚠️  Warning: Specified pylintrc not found: {pylintrc}")
					print(f"   Falling back to standard location search...")
			else:
				# Try relative to current working directory
				abs_path = os.path.join(os.getcwd(), pylintrc)
				if os.path.exists(abs_path):
					return abs_path
				else:
					print(f"⚠️  Warning: Specified pylintrc not found: {pylintrc}")
					print(f"   Tried: {abs_path}")
					print(f"   Current directory: {os.getcwd()}")
					print(f"   Falling back to standard location search...")

		# Fall back to standard location: .config/ignition.pylintrc
		# First, search from current directory up to find the project root (user's custom config)
		current_path = os.getcwd()
		while current_path != os.path.dirname(current_path):  # Until we reach root
			standard_pylintrc = os.path.join(current_path, ".config", "ignition.pylintrc")
			if os.path.exists(standard_pylintrc):
				return standard_pylintrc
			current_path = os.path.dirname(current_path)

		# If not found in user's repo, check the package installation directory
		# This is where the bundled default config will be when installed via pip/poetry
		# __file__ is: site-packages/ignition_lint/rules/scripts/lint_script.py
		# We need to go up to: site-packages/.config/ignition.pylintrc
		package_dir = os.path.dirname(
			os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		)
		bundled_pylintrc = os.path.join(package_dir, ".config", "ignition.pylintrc")
		if os.path.exists(bundled_pylintrc):
			return bundled_pylintrc

		# No pylintrc found - will use pylint defaults or inline config
		return None

	@property
	def error_message(self) -> str:
		return "Pylint detected issues in script"

	def process_nodes(self, nodes):
		"""Override to handle batch mode - don't reset scripts when batching across files."""
		if not self.batch_mode:
			# Non-batch mode: reset everything per file and process immediately
			self.errors = []
			self.warnings = []
			self.collected_scripts = {}
		# In batch mode: don't reset anything - accumulate across all files

		# Filter nodes that this rule applies to
		applicable_nodes = [node for node in nodes if self.applies_to(node)]

		# Visit each applicable node (collect scripts)
		for node in applicable_nodes:
			node.accept(self)

		# Call post_process (in batch mode this does nothing)
		self.post_process()

	def post_process(self):
		"""Override to skip processing in batch mode - wait for finalize() instead."""
		if not self.batch_mode:
			# Non-batch mode: process immediately
			if self.collected_scripts:
				self.process_scripts(self.collected_scripts)
				self.collected_scripts = {}

	def finalize(self):
		"""Process all accumulated scripts across all files (batch mode only)."""
		if self.batch_mode and self.collected_scripts:
			self.process_scripts(self.collected_scripts)
			self.collected_scripts = {}

	def process_scripts(self, scripts: Dict[str, ScriptNode]):
		"""Process all collected scripts with pylint."""
		# Quick exit: Skip processing if there are no scripts
		if not scripts:
			return

		# Quick exit: Skip if all scripts are empty
		if all(not script.script.strip() for script in scripts.values()):
			return

		# Run pylint on all scripts at once
		path_to_issues = self._run_pylint_batch(scripts)

		# Add issues to our errors list
		for path, issues in path_to_issues.items():
			for issue in issues:
				# Pylint issues (syntax errors, undefined variables, etc.) - use configured severity
				self.add_violation(f"{path}: {issue}")

	def _run_pylint_batch(self, scripts: Dict[str, ScriptNode]) -> Dict[str, List[str]]:
		"""Run pylint on multiple scripts at once."""
		# Always create debug directory (for automatic error reporting)
		debug_dir = self._setup_debug_directory()
		combined_content, line_map = self._combine_scripts(scripts)
		path_to_issues = {path: [] for path in scripts.keys()}
		temp_file_path = None
		try:
			temp_file_path = self._create_temp_file(combined_content)
			pylint_output = self._run_pylint_on_file(temp_file_path, debug_dir)
			self._parse_pylint_output(pylint_output, line_map, path_to_issues, debug_dir)
		except (OSError, IOError) as e:
			error_msg = f"Error with file operations during pylint: {str(e)}"
			self._handle_pylint_error(error_msg, debug_dir, path_to_issues)
		except ImportError as e:
			error_msg = f"Error importing pylint modules: {str(e)}"
			self._handle_pylint_error(error_msg, debug_dir, path_to_issues)
		finally:
			self._cleanup_temp_file(temp_file_path, debug_dir, path_to_issues)

		return path_to_issues

	def _setup_debug_directory(self) -> str:
		"""Create and return debug directory path. Always creates directory for error reporting."""
		cwd = os.getcwd()

		# Priority 1: User-configured debug directory
		if self.debug_dir_config:
			if os.path.isabs(self.debug_dir_config):
				debug_dir = self.debug_dir_config
			else:
				debug_dir = os.path.join(cwd, self.debug_dir_config)
		else:
			# Priority 2: Try to detect if we're in a test environment and use tests/debug
			tests_debug_dir = None
			current_path = cwd
			while current_path != os.path.dirname(current_path):  # Until we reach root
				if os.path.basename(current_path) == 'tests':
					# We're in tests directory
					tests_debug_dir = os.path.join(current_path, "debug")
					break
				elif os.path.exists(os.path.join(current_path, 'tests')):
					# Tests directory exists in current path
					tests_debug_dir = os.path.join(current_path, "tests", "debug")
					break
				current_path = os.path.dirname(current_path)

			# Priority 3: Use .ignition-lint/debug as standard location for user repos
			debug_dir = tests_debug_dir if tests_debug_dir else os.path.join(cwd, ".ignition-lint", "debug")

		os.makedirs(debug_dir, exist_ok=True)

		# Show debug directory location in debug mode
		if self.debug:
			print(f"🔍 PylintScriptRule: Debug directory: {debug_dir}")

		# Clean up old debug .py files to keep things fresh each run
		try:
			for filename in os.listdir(debug_dir):
				if filename.endswith('.py'):
					file_path = os.path.join(debug_dir, filename)
					os.remove(file_path)
		except OSError:
			# Silently ignore cleanup errors - debug directory may not be writable
			pass

		return debug_dir

	def _combine_scripts(self, scripts: Dict[str, ScriptNode]) -> Tuple[str, Dict[int, str]]:
		"""Combine all scripts into a single string with line mapping."""
		line_map = {}
		line_count = 1

		combined_scripts = [
			"#pylint: disable=unused-argument,missing-docstring,redefined-outer-name,function-redefined",
			"# Stub for common globals, and to simulate the Ignition environment",
			"# Note: function-redefined is disabled because multiple scripts may define the same function names",
			"system = None  # Simulated Ignition system object",
			"self = {} # Simulated self object for script context",
			"event = {}  # Simulated event object",
			"",
		]
		line_count += len(combined_scripts)

		for i, (path, script_obj) in enumerate(scripts.items()):
			header = f"# Script {i+1}: {path}"
			combined_scripts.append(header)
			line_count += 1

			formatted_script = script_obj.get_formatted_script()
			script_lines = formatted_script.count('\n') + 1

			# Record line numbers for this script
			for line_num in range(line_count, line_count + script_lines):
				line_map[line_num] = path

			combined_scripts.append(formatted_script)
			line_count += script_lines

			combined_scripts.append("")  # Blank line separator
			line_count += 1

		return "\n".join(combined_scripts), line_map

	def _create_temp_file(self, content: str) -> str:
		"""Create temporary file with script content."""
		timestamp = datetime.datetime.now().strftime("%H%M%S")
		with tempfile.NamedTemporaryFile(prefix=f"{timestamp}_", suffix=".py", delete=False) as temp_file:
			temp_file.write(content.encode('utf-8'))
			return temp_file.name

	def _run_pylint_on_file(self, temp_file_path: str, debug_dir: str) -> str:
		"""Execute pylint on the temporary file and return output."""
		# Only save debug files if debug mode is enabled
		if self.debug and debug_dir:
			_save_debug_file(temp_file_path, debug_dir)

		# Always write pylintrc info in debug mode to help diagnose config issues
		if self.debug and debug_dir:
			with open(os.path.join(debug_dir, "pylintrc_used.txt"), 'w', encoding='utf-8') as f:
				if self.pylintrc:
					f.write(f"Using pylintrc: {self.pylintrc}\n")
				else:
					f.write("No pylintrc found - using inline configuration\n")

		pylint_output = StringIO()

		# Build pylint arguments
		args = []

		# Use custom or standard pylintrc if available
		if self.pylintrc:
			args.extend(['--rcfile', self.pylintrc])
		else:
			# Fallback to inline configuration if no pylintrc found
			args.extend([
				'--disable=all',
				'--enable=unused-import,undefined-variable,syntax-error,invalid-name',
			])

		# Common arguments
		args.extend([
			'--output-format=text',
			'--score=no',
			temp_file_path,
		])

		# Redirect stdout/stderr to capture all pylint output
		old_stdout = sys.stdout
		old_stderr = sys.stderr
		try:
			sys.stdout = pylint_output
			sys.stderr = pylint_output
			lint.Run(args, reporter=TextReporter(pylint_output), exit=False)
		finally:
			sys.stdout = old_stdout
			sys.stderr = old_stderr

		output = pylint_output.getvalue()

		# Only write debug output if debug mode is enabled
		if self.debug and debug_dir:
			with open(os.path.join(debug_dir, "pylint_output.txt"), 'w', encoding='utf-8') as f:
				f.write(output)

		return output

	def _parse_pylint_output(
		self, output: str, line_map: Dict[int, str], path_to_issues: Dict[str, List[str]], debug_dir: str
	) -> None:
		"""Parse pylint output and map issues back to original scripts."""
		pattern = r'.*:(\d+):\d+: .+: (.+)'
		for line in output.splitlines():
			match = re.match(pattern, line)
			if not match:
				continue

			try:
				line_num = int(match.group(1))
				message = match.group(2)
				script_path = self._find_script_for_line(line_num, line_map)

				if script_path and script_path in path_to_issues:
					relative_line = self._calculate_relative_line(line_num, script_path, line_map)
					path_to_issues[script_path].append(f"Line {relative_line}: {message}")

			except (ValueError, IndexError) as e:
				if self.debug and debug_dir:
					self._log_parse_error(line, e, debug_dir)

	def _find_script_for_line(self, line_num: int, line_map: Dict[int, str]) -> Optional[str]:
		"""Find which script a line number belongs to."""
		for ln in sorted(line_map.keys(), reverse=True):
			if ln <= line_num:
				return line_map[ln]
		return None

	def _calculate_relative_line(self, line_num: int, script_path: str, line_map: Dict[int, str]) -> int:
		"""Calculate the relative line number within the original script."""
		script_start_line = min(ln for ln, path in line_map.items() if path == script_path)
		return line_num - script_start_line + 1

	def _log_parse_error(self, line: str, error: Exception, debug_dir: str) -> None:
		"""Log parsing errors to debug file."""
		with open(os.path.join(debug_dir, "pylint_error.txt"), 'a', encoding='utf-8') as f:
			f.write(f"Error parsing line: {line}\nException: {str(error)}\n\n")

	def _handle_pylint_error(self, error_msg: str, debug_dir: str, path_to_issues: Dict[str, List[str]]) -> None:
		"""Handle and log pylint execution errors."""
		# Only write debug files if debug mode is enabled
		if self.debug and debug_dir:
			with open(os.path.join(debug_dir, "pylint_error.txt"), 'w', encoding='utf-8') as f:
				f.write(error_msg)
		for path in path_to_issues:
			path_to_issues[path].append(error_msg)

	def _cleanup_temp_file(self, temp_file_path: str, debug_dir: str, path_to_issues: Dict[str, List[str]]) -> None:
		"""Clean up temporary file, keeping it for debug if there were issues or debug mode is enabled."""
		if temp_file_path and os.path.exists(temp_file_path):
			has_issues = any(issues for issues in path_to_issues.values())

			# Save debug files if:
			# 1. There are issues (automatic error reporting), OR
			# 2. Debug mode is explicitly enabled (opt-in for development)
			should_save = has_issues or self.debug

			if should_save and debug_dir:
				# Preserve original temp filename (timestamp + random chars)
				original_filename = os.path.basename(temp_file_path)
				debug_file_path = os.path.join(debug_dir, original_filename)
				shutil.copy(temp_file_path, debug_file_path)

				if has_issues:
					print(f"🐛 Pylint found issues. Debug file saved to: {debug_file_path}")
				elif self.debug:
					print(f"🔍 Debug mode: Script saved to: {debug_file_path}")

			# Always clean up the temp file (was already copied to debug if needed)
			os.remove(temp_file_path)


def _save_debug_file(temp_file_path: str, debug_dir: str):
	"""Helper function to save temporary file to debug directory with original filename."""
	debug_file_path = os.path.join(debug_dir, os.path.basename(temp_file_path))
	shutil.copy2(temp_file_path, debug_file_path)
	# Note: Old .py files are cleaned up at the start of each run in _setup_debug_directory()
