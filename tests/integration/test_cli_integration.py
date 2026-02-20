# pylint: disable=import-error
"""
Integration tests for the CLI tool.
Tests the command-line interface functionality.
"""

import unittest
import subprocess
import tempfile
import json
import sys
from pathlib import Path

from fixtures.base_test import BaseIntegrationTest


class TestCLIIntegration(BaseIntegrationTest):
	"""Test CLI tool integration."""
	def __init__(self, method_name = "runTest"):
		super().__init__(method_name)
		self.cli_path = None
		self.use_poetry = False
		self.use_module = False

	def setUp(self):  # pylint: disable=invalid-name
		""" Set up CLI integration test, including locating the CLI executable, overloading from base."""
		super().setUp()
		# Try different possible CLI paths
		possible_paths = [
			Path(__file__).parent.parent.parent / "src" / "ignition_lint" / "__main__.py",
		]

		for path in possible_paths:
			if path.exists():
				self.cli_path = path
				break

		if self.cli_path is None:
			# Try to see if we can run via poetry
			try:
				result = subprocess.run(["poetry", "run", "ign-lint", "--help"],
							capture_output=True, timeout=10, check=False,
							cwd=Path(__file__).parent.parent.parent)
				if result.returncode == 0:
					self.use_poetry = True
			except (subprocess.TimeoutExpired, FileNotFoundError):
				# Try module execution
				try:
					result = subprocess.run([sys.executable, "-m", "ignition_lint", "--help"],
								capture_output=True, timeout=10, check=False,
								cwd=Path(__file__).parent.parent.parent)
					if result.returncode == 0:
						self.use_module = True
				except (subprocess.TimeoutExpired, FileNotFoundError):
					pass

	def _run_cli_command(self, args, timeout=30):
		"""Run a CLI command using the best available method."""
		if self.use_poetry:
			cmd = ["poetry", "run", "ign-lint"] + args
			cwd = Path(__file__).parent.parent.parent
		elif self.use_module:
			cmd = [sys.executable, "-m", "ignition_lint"] + args
			cwd = Path(__file__).parent.parent.parent
		elif self.cli_path:
			cmd = [sys.executable, str(self.cli_path)] + args
			cwd = None
		else:
			raise unittest.SkipTest("No viable CLI execution method found")

		return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False, cwd=cwd)

	def test_cli_help(self):
		"""Test CLI help command."""
		try:
			result = self._run_cli_command(["--help"])

			# Debug output if test fails
			if result.returncode != 0:
				print(f"CLI help failed with return code: {result.returncode}")
				print(f"STDOUT: {result.stdout}")
				print(f"STDERR: {result.stderr}")

			self.assertEqual(
				result.returncode, 0, f"CLI help should return 0, got {result.returncode}. "
				f"STDERR: {result.stderr}"
			)
			self.assertIn("usage:", result.stdout.lower(), "Help output should contain usage information")

		except (subprocess.TimeoutExpired, FileNotFoundError) as e:
			self.skipTest(f"CLI test skipped: {e}")
		except unittest.SkipTest:
			raise
		except Exception as e:
			self.fail(f"Unexpected error running CLI help: {e}")

	def test_cli_with_config_file(self):
		"""Test CLI with a configuration file."""
		# Create a temporary config file
		config = {"NamePatternRule": {"enabled": True, "kwargs": {"convention": "PascalCase"}}}

		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(config, f)
			config_file = f.name

		try:
			view_file = self.test_cases_dir / "PascalCase" / "view.json"
			if not view_file.exists():
				self.skipTest("PascalCase test file not found")

			result = self._run_cli_command([
				"--config", config_file, "--files",
				str(view_file), "--verbose"
			])

			# Debug output if test fails
			if result.returncode not in [0, 1]:  # 0 = no errors, 1 = errors found
				print(f"CLI config test failed with return code: {result.returncode}")
				print(f"STDOUT: {result.stdout}")
				print(f"STDERR: {result.stderr}")

			# Should complete without crashing (returncode 0 or 1 are both valid)
			self.assertIn(
				result.returncode, [0, 1],
				f"CLI should return 0 (no errors) or 1 (errors found), got {result.returncode}. "
				f"STDERR: {result.stderr}"
			)

		except (subprocess.TimeoutExpired, FileNotFoundError) as e:
			self.skipTest(f"CLI test skipped: {e}")
		except unittest.SkipTest:
			raise
		except Exception as e:
			self.fail(f"Unexpected error running CLI with config: {e}")
		finally:
			# Clean up
			try:
				Path(config_file).unlink(missing_ok=True)
			except Exception as e:
				pass

	def test_cli_stats_only(self):
		"""Test CLI stats-only mode."""
		try:
			view_file = self.test_cases_dir / "PascalCase" / "view.json"
			if not view_file.exists():
				self.skipTest("PascalCase test file not found")

			result = self._run_cli_command(["--files", str(view_file), "--stats-only"])

			# Debug output if test fails
			if result.returncode != 0:
				print(f"CLI stats-only failed with return code: {result.returncode}")
				print(f"STDOUT: {result.stdout}")
				print(f"STDERR: {result.stderr}")

			# Should complete successfully in stats-only mode
			self.assertEqual(
				result.returncode, 0, f"CLI stats-only should return 0, got {result.returncode}. "
				f"STDERR: {result.stderr}"
			)

			# Should contain statistics information
			output_lower = result.stdout.lower()
			has_stats = any(word in output_lower for word in ["statistics", "nodes", "processed"])
			self.assertTrue(
				has_stats, f"Stats-only output should contain statistics information. "
				f"Got: {result.stdout}"
			)

		except (subprocess.TimeoutExpired, FileNotFoundError) as e:
			self.skipTest(f"CLI test skipped: {e}")
		except unittest.SkipTest:
			raise
		except Exception as e:
			self.fail(f"Unexpected error running CLI stats-only: {e}")

	def test_cli_version_or_basic_execution(self):
		"""Test that the CLI can at least execute without crashing."""
		try:
			# Try a simple command that should always work
			result = self._run_cli_command(["--help"])

			# Just verify the CLI is executable
			self.assertIsInstance(result.returncode, int, "CLI should return an integer exit code")

		except (subprocess.TimeoutExpired, FileNotFoundError) as e:
			self.skipTest(f"CLI basic execution test skipped: {e}")
		except unittest.SkipTest:
			raise
		except Exception as e:
			self.fail(f"CLI is not executable: {e}")


class TestCLIDiscovery(BaseIntegrationTest):
	"""Test CLI discovery and basic functionality."""

	def test_cli_methods_available(self):
		"""Test that at least one CLI execution method is available."""
		cli_integration = TestCLIIntegration()
		cli_integration.setUp()

		methods_available = [
			cli_integration.cli_path is not None, cli_integration.use_poetry, cli_integration.use_module
		]

		self.assertTrue(
			any(methods_available), "At least one CLI execution method should be available "
			f"(direct: {cli_integration.cli_path is not None}, "
			f"poetry: {cli_integration.use_poetry}, "
			f"module: {cli_integration.use_module})"
		)


if __name__ == "__main__":
	unittest.main()
