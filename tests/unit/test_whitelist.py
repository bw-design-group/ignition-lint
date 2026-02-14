"""
Unit tests for whitelist functionality.
"""

import unittest
import tempfile
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
current_dir = Path(__file__).parent
tests_dir = current_dir.parent
project_root = tests_dir.parent
sys.path.insert(0, str(project_root / "src"))

from ignition_lint.cli import load_whitelist, generate_whitelist, collect_files
from argparse import Namespace


class TestWhitelistLoading(unittest.TestCase):
	"""Tests for load_whitelist() function."""

	def setUp(self):
		"""Set up temporary directory for test files."""
		self.temp_dir = tempfile.mkdtemp()
		self.temp_path = Path(self.temp_dir)

	def tearDown(self):
		"""Clean up temporary files."""
		import shutil
		shutil.rmtree(self.temp_dir, ignore_errors=True)

	def test_load_valid_whitelist(self):
		"""Valid whitelist loads correctly."""
		whitelist_file = self.temp_path / "test_whitelist.txt"
		whitelist_file.write_text(
			"views/legacy/Dashboard/view.json\n"
			"views/deprecated/OldWidget/view.json\n"
		)

		whitelist = load_whitelist(str(whitelist_file))

		self.assertEqual(len(whitelist), 2)
		# Check that paths are converted to absolute
		for path in whitelist:
			self.assertIsInstance(path, Path)
			self.assertTrue(path.is_absolute())

	def test_whitelist_file_not_found(self):
		"""Non-existent whitelist returns empty set."""
		whitelist = load_whitelist("nonexistent_file.txt")
		self.assertEqual(whitelist, set())

	def test_comments_ignored(self):
		"""Lines starting with # are ignored."""
		whitelist_file = self.temp_path / "test_whitelist.txt"
		whitelist_file.write_text(
			"# This is a comment\n"
			"views/legacy/Dashboard/view.json\n"
			"# Another comment\n"
			"views/deprecated/OldWidget/view.json\n"
		)

		whitelist = load_whitelist(str(whitelist_file))
		self.assertEqual(len(whitelist), 2)

	def test_blank_lines_ignored(self):
		"""Empty lines are ignored."""
		whitelist_file = self.temp_path / "test_whitelist.txt"
		whitelist_file.write_text(
			"views/legacy/Dashboard/view.json\n"
			"\n"
			"  \n"
			"views/deprecated/OldWidget/view.json\n"
			"\n"
		)

		whitelist = load_whitelist(str(whitelist_file))
		self.assertEqual(len(whitelist), 2)

	def test_whitespace_trimmed(self):
		"""Leading/trailing whitespace is trimmed."""
		whitelist_file = self.temp_path / "test_whitelist.txt"
		whitelist_file.write_text(
			"  views/legacy/Dashboard/view.json  \n"
			"\tviews/deprecated/OldWidget/view.json\t\n"
		)

		whitelist = load_whitelist(str(whitelist_file))
		self.assertEqual(len(whitelist), 2)

	def test_paths_normalized_to_absolute(self):
		"""Relative paths converted to absolute."""
		whitelist_file = self.temp_path / "test_whitelist.txt"
		whitelist_file.write_text("views/legacy/Dashboard/view.json\n")

		whitelist = load_whitelist(str(whitelist_file))

		self.assertEqual(len(whitelist), 1)
		path = list(whitelist)[0]
		self.assertTrue(path.is_absolute())

	def test_io_error_returns_empty_set(self):
		"""IO errors print warning and return empty set."""
		# Use a directory path instead of file (will cause permission/IO error)
		whitelist = load_whitelist(str(self.temp_path))
		self.assertEqual(whitelist, set())


class TestFileFiltering(unittest.TestCase):
	"""Tests for collect_files() with whitelist."""

	def setUp(self):
		"""Set up temporary directory and test files."""
		self.temp_dir = tempfile.mkdtemp()
		self.temp_path = Path(self.temp_dir)

		# Create test view files
		self.view1 = self.temp_path / "view1" / "view.json"
		self.view1.parent.mkdir(parents=True)
		self.view1.write_text('{"test": "data"}')

		self.view2 = self.temp_path / "view2" / "view.json"
		self.view2.parent.mkdir(parents=True)
		self.view2.write_text('{"test": "data"}')

		self.view3 = self.temp_path / "view3" / "view.json"
		self.view3.parent.mkdir(parents=True)
		self.view3.write_text('{"test": "data"}')

	def tearDown(self):
		"""Clean up temporary files."""
		import shutil
		shutil.rmtree(self.temp_dir, ignore_errors=True)

	def test_whitelist_filters_precommit_files(self):
		"""Whitelisted files excluded from pre-commit filenames."""
		# Create whitelist with view1
		whitelist = {self.view1.resolve()}

		# Create args with filenames (simulates pre-commit)
		args = Namespace(
			filenames=[str(self.view1), str(self.view2)],
			files=None,
			verbose=False
		)

		files, _ = collect_files(args, whitelist)

		# Only view2 should be collected (view1 is whitelisted)
		self.assertEqual(len(files), 1)
		self.assertEqual(files[0].resolve(), self.view2.resolve())

	def test_whitelist_filters_glob_files(self):
		"""Whitelisted files excluded from glob patterns."""
		# Create whitelist with view1 and view2
		whitelist = {self.view1.resolve(), self.view2.resolve()}

		# Create args with glob pattern
		args = Namespace(
			filenames=[],
			files=str(self.temp_path / "**" / "view.json"),
			verbose=False
		)

		files, _ = collect_files(args, whitelist)

		# Only view3 should be collected (view1 and view2 are whitelisted)
		self.assertEqual(len(files), 1)
		self.assertEqual(files[0].resolve(), self.view3.resolve())

	def test_empty_whitelist_includes_all(self):
		"""Empty whitelist processes all files."""
		whitelist = set()

		args = Namespace(
			filenames=[str(self.view1), str(self.view2)],
			files=None,
			verbose=False
		)

		files, _ = collect_files(args, whitelist)

		# All files should be collected
		self.assertEqual(len(files), 2)

	def test_path_matching_works_with_relative_input(self):
		"""Relative input paths matched against absolute whitelist."""
		# Create whitelist with absolute path
		whitelist = {self.view1.resolve()}

		# Use relative path in args
		cwd = os.getcwd()
		try:
			os.chdir(self.temp_path)
			args = Namespace(
				filenames=["view1/view.json"],
				files=None,
				verbose=False
			)

			files, _ = collect_files(args, whitelist)

			# view1 should be filtered out
			self.assertEqual(len(files), 0)
		finally:
			os.chdir(cwd)

	def test_path_matching_works_with_absolute_input(self):
		"""Absolute input paths matched against absolute whitelist."""
		# Create whitelist with absolute path
		whitelist = {self.view1.resolve()}

		# Use absolute path in args
		args = Namespace(
			filenames=[str(self.view1.resolve())],
			files=None,
			verbose=False
		)

		files, _ = collect_files(args, whitelist)

		# view1 should be filtered out
		self.assertEqual(len(files), 0)

	def test_verbose_reports_ignored_files(self):
		"""Verbose mode reports whitelisted files."""
		whitelist = {self.view1.resolve()}

		args = Namespace(
			filenames=[str(self.view1), str(self.view2)],
			files=None,
			verbose=True
		)

		# Capture output (don't test exact message, just ensure it runs)
		files, _ = collect_files(args, whitelist)

		# Only view2 should be collected
		self.assertEqual(len(files), 1)


class TestGenerateWhitelist(unittest.TestCase):
	"""Tests for generate_whitelist() function."""

	def setUp(self):
		"""Set up temporary directory and test files."""
		self.temp_dir = tempfile.mkdtemp()
		self.temp_path = Path(self.temp_dir)

		# Create test directory structure
		(self.temp_path / "views" / "legacy").mkdir(parents=True)
		(self.temp_path / "views" / "deprecated").mkdir(parents=True)

		# Create test view files
		(self.temp_path / "views" / "legacy" / "view1.json").write_text('{}')
		(self.temp_path / "views" / "legacy" / "view2.json").write_text('{}')
		(self.temp_path / "views" / "deprecated" / "view3.json").write_text('{}')

	def tearDown(self):
		"""Clean up temporary files."""
		import shutil
		shutil.rmtree(self.temp_dir, ignore_errors=True)

	def test_generate_from_single_pattern(self):
		"""Single glob pattern generates correct whitelist."""
		output_file = self.temp_path / "whitelist.txt"

		cwd = os.getcwd()
		try:
			os.chdir(self.temp_path)
			generate_whitelist(
				patterns=["views/legacy/*.json"],
				output_file=str(output_file),
				append=False,
				dry_run=False
			)

			# Check file was created
			self.assertTrue(output_file.exists())

			# Check content
			content = output_file.read_text()
			self.assertIn("view1.json", content)
			self.assertIn("view2.json", content)
			self.assertNotIn("view3.json", content)
		finally:
			os.chdir(cwd)

	def test_generate_from_multiple_patterns(self):
		"""Multiple glob patterns combined in whitelist."""
		output_file = self.temp_path / "whitelist.txt"

		cwd = os.getcwd()
		try:
			os.chdir(self.temp_path)
			generate_whitelist(
				patterns=["views/legacy/*.json", "views/deprecated/*.json"],
				output_file=str(output_file),
				append=False,
				dry_run=False
			)

			# Check file was created
			self.assertTrue(output_file.exists())

			# Check content
			content = output_file.read_text()
			self.assertIn("view1.json", content)
			self.assertIn("view2.json", content)
			self.assertIn("view3.json", content)
		finally:
			os.chdir(cwd)

	def test_append_mode_adds_to_existing(self):
		"""Append mode adds to existing whitelist."""
		output_file = self.temp_path / "whitelist.txt"

		cwd = os.getcwd()
		try:
			os.chdir(self.temp_path)

			# Create initial whitelist
			output_file.write_text("views/existing/file.json\n")

			# Append to it
			generate_whitelist(
				patterns=["views/legacy/*.json"],
				output_file=str(output_file),
				append=True,
				dry_run=False
			)

			# Check content includes both old and new
			content = output_file.read_text()
			self.assertIn("views/existing/file.json", content)
			self.assertIn("view1.json", content)
		finally:
			os.chdir(cwd)

	def test_append_mode_deduplicates(self):
		"""Append mode removes duplicate paths."""
		output_file = self.temp_path / "whitelist.txt"

		cwd = os.getcwd()
		try:
			os.chdir(self.temp_path)

			# Create initial whitelist with view1
			output_file.write_text("views/legacy/view1.json\n")

			# Append same pattern
			generate_whitelist(
				patterns=["views/legacy/*.json"],
				output_file=str(output_file),
				append=True,
				dry_run=False
			)

			# Check that view1 only appears once
			content = output_file.read_text()
			count = content.count("views/legacy/view1.json")
			self.assertEqual(count, 1)
		finally:
			os.chdir(cwd)

	def test_dry_run_does_not_write_file(self):
		"""Dry run prints paths but doesn't write file."""
		output_file = self.temp_path / "whitelist.txt"

		cwd = os.getcwd()
		try:
			os.chdir(self.temp_path)
			generate_whitelist(
				patterns=["views/legacy/*.json"],
				output_file=str(output_file),
				append=False,
				dry_run=True
			)

			# File should not be created
			self.assertFalse(output_file.exists())
		finally:
			os.chdir(cwd)

	def test_paths_are_relative(self):
		"""Generated paths are relative to repo root."""
		output_file = self.temp_path / "whitelist.txt"

		cwd = os.getcwd()
		try:
			os.chdir(self.temp_path)
			generate_whitelist(
				patterns=["views/legacy/*.json"],
				output_file=str(output_file),
				append=False,
				dry_run=False
			)

			content = output_file.read_text()

			# Paths should be relative (not absolute)
			self.assertNotIn(str(self.temp_path), content)
			self.assertIn("views/legacy/", content)
		finally:
			os.chdir(cwd)

	def test_paths_are_sorted(self):
		"""Generated paths are sorted alphabetically."""
		output_file = self.temp_path / "whitelist.txt"

		cwd = os.getcwd()
		try:
			os.chdir(self.temp_path)
			generate_whitelist(
				patterns=["views/**/*.json"],
				output_file=str(output_file),
				append=False,
				dry_run=False
			)

			# Read paths (skip comments and blank lines)
			paths = []
			for line in output_file.read_text().split('\n'):
				line = line.strip()
				if line and not line.startswith('#'):
					paths.append(line)

			# Check that paths are sorted
			self.assertEqual(paths, sorted(paths))
		finally:
			os.chdir(cwd)


if __name__ == '__main__':
	unittest.main()
