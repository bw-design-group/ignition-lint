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

	def __init__(self, severity="error", pylintrc=None):
		super().__init__(severity=severity)  # Targets all script types by default
		self.debug = True
		self.pylintrc = self._resolve_pylintrc_path(pylintrc)

	def _resolve_pylintrc_path(self, pylintrc: Optional[str]) -> Optional[str]:
		"""Resolve the pylintrc file path with fallback to standard location."""
		# If a specific pylintrc is provided, use it if it exists
		if pylintrc:
			if os.path.isabs(pylintrc):
				if os.path.exists(pylintrc):
					return pylintrc
			else:
				# Try relative to current working directory
				abs_path = os.path.join(os.getcwd(), pylintrc)
				if os.path.exists(abs_path):
					return abs_path

		# Fall back to standard location: .config/ignition.pylintrc
		# Search from current directory up to find the project root
		current_path = os.getcwd()
		while current_path != os.path.dirname(current_path):  # Until we reach root
			standard_pylintrc = os.path.join(current_path, ".config", "ignition.pylintrc")
			if os.path.exists(standard_pylintrc):
				return standard_pylintrc
			current_path = os.path.dirname(current_path)

		# No pylintrc found - will use pylint defaults or inline config
		return None

	@property
	def error_message(self) -> str:
		return "Pylint detected issues in script"

	def process_scripts(self, scripts: Dict[str, ScriptNode]):
		"""Process all collected scripts with pylint."""
		if not scripts:
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
		"""Create and return debug directory path."""
		# Try to detect if we're in a test environment and use tests/debug
		cwd = os.getcwd()
		tests_debug_dir = None

		# Look for tests directory in current working directory or parent directories
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

		# Use tests/debug if found, otherwise fall back to debug
		debug_dir = tests_debug_dir if tests_debug_dir else os.path.join(cwd, "debug")
		os.makedirs(debug_dir, exist_ok=True)
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
		if self.debug:
			_save_debug_file(temp_file_path, debug_dir)

		pylint_output = StringIO()

		# Build pylint arguments
		args = []

		# Use custom or standard pylintrc if available
		if self.pylintrc:
			args.extend(['--rcfile', self.pylintrc])
			if self.debug:
				with open(os.path.join(debug_dir, "pylintrc_used.txt"), 'w', encoding='utf-8') as f:
					f.write(f"Using pylintrc: {self.pylintrc}\n")
		else:
			# Fallback to inline configuration if no pylintrc found
			args.extend([
				'--disable=all',
				'--enable=unused-import,undefined-variable,syntax-error,invalid-name',
			])
			if self.debug:
				with open(os.path.join(debug_dir, "pylintrc_used.txt"), 'w', encoding='utf-8') as f:
					f.write("No pylintrc found - using inline configuration\n")

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

		if self.debug:
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
		with open(os.path.join(debug_dir, "pylint_error.txt"), 'w', encoding='utf-8') as f:
			f.write(error_msg)
		for path in path_to_issues:
			path_to_issues[path].append(error_msg)

	def _cleanup_temp_file(self, temp_file_path: str, debug_dir: str, path_to_issues: Dict[str, List[str]]) -> None:
		"""Clean up temporary file, keeping it for debug if there were issues."""
		if temp_file_path and os.path.exists(temp_file_path):
			if any(issues for issues in path_to_issues.values()):
				shutil.copy(temp_file_path, os.path.join(debug_dir, "pylint_input_temp.py"))
				print(f"Pylint encountered issues. Debug files saved to: {debug_dir}")
			else:
				os.remove(temp_file_path)


def _save_debug_file(temp_file_path: str, debug_dir: str):
	"""Helper function to save temporary file to debug directory."""
	debug_file_path = os.path.join(debug_dir, os.path.basename(temp_file_path))
	shutil.copy2(temp_file_path, debug_file_path)

	# Keep only the 5 most recent debug files
	try:
		file_prefix = os.path.basename(temp_file_path).split('_')[0]
		# Get all .py files in the debug directory
		debug_files = [
			f for f in os.listdir(debug_dir)
			if f.endswith('.py') and os.path.basename(f).split('_')[0] != file_prefix
		]

		# Sort by modification time (newest first)
		debug_files.sort(key=lambda f: os.path.getmtime(os.path.join(debug_dir, f)), reverse=True)

		# Remove files beyond the 5 most recent
		for file_to_remove in debug_files[5:]:
			file_path = os.path.join(debug_dir, file_to_remove)
			os.remove(file_path)

	except OSError as e:
		# Handle potential file system errors gracefully
		print(f"Warning: Could not clean up old debug files: {e}")
