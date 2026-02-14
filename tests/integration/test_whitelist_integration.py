"""
Integration tests for whitelist feature.

Tests end-to-end workflows including CLI invocation and file filtering.
"""

import unittest
import tempfile
import subprocess
import sys
from pathlib import Path

# Add parent directory to path for imports
current_dir = Path(__file__).parent
tests_dir = current_dir.parent
project_root = tests_dir.parent
sys.path.insert(0, str(project_root / "src"))


class TestWhitelistIntegration(unittest.TestCase):
	"""End-to-end tests for whitelist feature."""

	def setUp(self):
		"""Set up temporary directory and test files."""
		self.temp_dir = tempfile.mkdtemp()
		self.temp_path = Path(self.temp_dir)

		# Create test view files
		self.create_test_view("view1/view.json", valid=True)
		self.create_test_view("view2/view.json", valid=True)
		self.create_test_view("view3/view.json", valid=False)  # Has issues

		# Create simple rule config
		self.config_file = self.temp_path / "rule_config.json"
		self.config_file.write_text('{"NamePatternRule": {"enabled": true, "kwargs": {"convention": "PascalCase"}}}')

	def tearDown(self):
		"""Clean up temporary files."""
		import shutil
		shutil.rmtree(self.temp_dir, ignore_errors=True)

	def create_test_view(self, relative_path: str, valid: bool = True):
		"""Create a test view.json file."""
		file_path = self.temp_path / relative_path
		file_path.parent.mkdir(parents=True, exist_ok=True)

		if valid:
			# Valid view with PascalCase component name
			content = '''
{
  "custom": {},
  "params": {},
  "props": {
    "children": [
      {
        "meta": {"name": "ValidComponent"},
        "type": "ia.display.label",
        "props": {"text": "Test"}
      }
    ]
  },
  "root": {
    "meta": {"name": "root"},
    "type": "ia.container.coord"
  }
}
'''
		else:
			# Invalid view with snake_case component name
			content = '''
{
  "custom": {},
  "params": {},
  "props": {
    "children": [
      {
        "meta": {"name": "invalid_component"},
        "type": "ia.display.label",
        "props": {"text": "Test"}
      }
    ]
  },
  "root": {
    "meta": {"name": "root"},
    "type": "ia.container.coord"
  }
}
'''
		file_path.write_text(content)

	def run_cli(self, args: list) -> subprocess.CompletedProcess:
		"""Run the CLI with the given arguments."""
		cmd = [
			sys.executable,
			"-m",
			"ignition_lint.cli",
		] + args

		return subprocess.run(
			cmd,
			cwd=self.temp_path,
			capture_output=True,
			text=True
		)

	def test_cli_with_whitelist_filters_files(self):
		"""CLI respects whitelist and filters files."""
		# Create whitelist with view3 (the invalid one)
		whitelist_file = self.temp_path / "whitelist.txt"
		whitelist_file.write_text("view3/view.json\n")

		# Run linter with whitelist
		result = self.run_cli([
			"--config", str(self.config_file),
			"--whitelist", str(whitelist_file),
			"--files", "**/view.json"
		])

		# Should succeed because view3 is whitelisted
		self.assertEqual(result.returncode, 0)
		self.assertNotIn("invalid_component", result.stdout)

	def test_cli_without_whitelist_processes_all(self):
		"""CLI without whitelist processes all files."""
		# Run linter without whitelist
		result = self.run_cli([
			"--config", str(self.config_file),
			"--files", "**/view.json"
		])

		# Should fail because view3 has issues
		self.assertNotEqual(result.returncode, 0)
		self.assertIn("invalid_component", result.stdout)

	def test_verbose_reports_ignored_files(self):
		"""Verbose mode reports whitelisted files."""
		# Create whitelist with view1
		whitelist_file = self.temp_path / "whitelist.txt"
		whitelist_file.write_text("view1/view.json\n")

		# Run with verbose mode
		result = self.run_cli([
			"--config", str(self.config_file),
			"--whitelist", str(whitelist_file),
			"--files", "**/view.json",
			"--verbose"
		])

		# Should mention skipped files
		self.assertIn("skipped", result.stdout.lower())

	def test_generate_whitelist_creates_file(self):
		"""Generate whitelist command creates file."""
		# Generate whitelist
		result = self.run_cli([
			"--generate-whitelist", "view1/view.json", "view2/view.json",
			"--whitelist-output", "test_whitelist.txt"
		])

		# Should succeed
		self.assertEqual(result.returncode, 0)

		# Check file was created
		whitelist_file = self.temp_path / "test_whitelist.txt"
		self.assertTrue(whitelist_file.exists())

		# Check content
		content = whitelist_file.read_text()
		self.assertIn("view1/view.json", content)
		self.assertIn("view2/view.json", content)

	def test_generate_and_use_whitelist_workflow(self):
		"""Complete workflow: generate whitelist, then lint with it."""
		# Step 1: Generate whitelist from invalid file
		result = self.run_cli([
			"--generate-whitelist", "view3/view.json",
			"--whitelist-output", "generated_whitelist.txt"
		])
		self.assertEqual(result.returncode, 0)

		# Step 2: Lint with generated whitelist
		result = self.run_cli([
			"--config", str(self.config_file),
			"--whitelist", "generated_whitelist.txt",
			"--files", "**/view.json"
		])

		# Should succeed because invalid file is whitelisted
		self.assertEqual(result.returncode, 0)

	def test_no_whitelist_flag_overrides(self):
		"""--no-whitelist flag disables whitelist."""
		# Create whitelist with view3 (the invalid one)
		whitelist_file = self.temp_path / "whitelist.txt"
		whitelist_file.write_text("view3/view.json\n")

		# Run with whitelist but also --no-whitelist
		result = self.run_cli([
			"--config", str(self.config_file),
			"--whitelist", str(whitelist_file),
			"--no-whitelist",
			"--files", "**/view.json"
		])

		# Should fail because whitelist is disabled
		self.assertNotEqual(result.returncode, 0)
		self.assertIn("invalid_component", result.stdout)

	def test_dry_run_does_not_create_file(self):
		"""--dry-run flag prevents file creation."""
		# Try to generate whitelist with dry-run
		result = self.run_cli([
			"--generate-whitelist", "view1/view.json",
			"--whitelist-output", "dryrun_whitelist.txt",
			"--dry-run"
		])

		# Should succeed
		self.assertEqual(result.returncode, 0)

		# File should not exist
		whitelist_file = self.temp_path / "dryrun_whitelist.txt"
		self.assertFalse(whitelist_file.exists())

	def test_append_mode_preserves_existing(self):
		"""--append flag preserves existing whitelist entries."""
		# Create initial whitelist
		whitelist_file = self.temp_path / "append_whitelist.txt"
		whitelist_file.write_text("view1/view.json\n")

		# Append more files
		result = self.run_cli([
			"--generate-whitelist", "view2/view.json",
			"--whitelist-output", str(whitelist_file),
			"--append"
		])

		# Should succeed
		self.assertEqual(result.returncode, 0)

		# Check both files are in whitelist
		content = whitelist_file.read_text()
		self.assertIn("view1/view.json", content)
		self.assertIn("view2/view.json", content)


if __name__ == '__main__':
	unittest.main()
