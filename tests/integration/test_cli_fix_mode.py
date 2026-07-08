# pylint: disable=import-error
"""
Integration tests for CLI fix-mode behavior.

Covers two related issues in the `--fix` flow (see GitHub issues #93 and #94):

  * #93: `--fix-unsafe` alone should enable fix mode (currently a no-op unless
    `--fix` is also passed).
  * #94: When fixes are applied, the CLI should re-evaluate rules once on the
    fixed view and report the post-fix results, instead of reporting the stale
    pre-fix violations.

These tests drive the real CLI via subprocess so they exercise the full
argument-parsing -> lint -> fix -> report pipeline.
"""

import json
import sys
import unittest
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
MAIN_PY = REPO_ROOT / "src" / "ignition_lint" / "__main__.py"

import subprocess  # noqa: E402  pylint: disable=wrong-import-position


def make_view(children):
	"""Build a minimal Ignition view.json structure as a dict."""
	return {
		"root": {
			"children": children,
			"meta": {
				"name": "root"
			},
			"props": {},
			"type": "ia.container.flex",
		}
	}


def make_component(name, comp_type="ia.display.label", props=None):
	"""Build a single component dict for a view's children list."""
	return {
		"meta": {
			"name": name
		},
		"props": props or {},
		"type": comp_type,
	}


PASCAL_CASE_CONFIG = {
	"NamePatternRule": {
		"enabled": True,
		"kwargs": {
			"convention": "PascalCase",
			"target_node_types": ["component"],
			"severity": "warning",
		},
	}
}

UNUSED_PROPS_CONFIG = {
	"UnusedCustomPropertiesRule": {
		"enabled": True,
		"kwargs": {
			"severity": "error",
		},
	}
}


class TestCLIFixMode(unittest.TestCase):
	"""End-to-end CLI tests for fix-mode flag handling and post-fix reporting."""

	def __init__(self, method_name="runTest"):
		super().__init__(method_name)
		self._tmp = None
		self.tmp_dir = None

	def setUp(self):  # pylint: disable=invalid-name
		"""Create a temp working directory for view + config files."""
		if not MAIN_PY.exists():
			self.skipTest(f"CLI entry point not found: {MAIN_PY}")
		self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
		self.tmp_dir = Path(self._tmp.name)

	def tearDown(self):  # pylint: disable=invalid-name
		"""Clean up the temp directory."""
		self._tmp.cleanup()

	def _write(self, name, data):
		"""Write a dict to a JSON file in the temp dir and return its path."""
		path = self.tmp_dir / name
		with open(path, "w", encoding="utf-8") as f:
			json.dump(data, f, indent=2)
		return path

	def _run(self, extra_args, timeout=60):
		"""Run the CLI with the given args, returning the CompletedProcess."""
		cmd = [sys.executable, str(MAIN_PY)] + extra_args
		return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False, cwd=REPO_ROOT)

	def _read(self, path):
		"""Read a JSON file back into a dict."""
		with open(path, "r", encoding="utf-8") as f:
			return json.load(f)

	# ------------------------------------------------------------------
	# Issue #93: --fix-unsafe alone should enable fix mode
	# ------------------------------------------------------------------
	def test_fix_unsafe_alone_applies_safe_fixes(self):
		"""`--fix-unsafe` without `--fix` should still apply (safe) fixes."""
		view = make_view([make_component("badButton", "ia.input.button")])
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", PASCAL_CASE_CONFIG)

		result = self._run(["--config", str(config_path), "--fix-unsafe", "--files", str(view_path)])

		fixed = self._read(view_path)
		self.assertEqual(
			fixed["root"]["children"][0]["meta"]["name"], "BadButton",
			f"--fix-unsafe alone should have renamed badButton -> BadButton.\n"
			f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
		)

	def test_fix_unsafe_alone_applies_unsafe_fixes(self):
		"""`--fix-unsafe` alone should apply unsafe fixes and update references."""
		view = make_view([
			make_component("badButton", "ia.input.button"),
			make_component("MyLabel", "ia.display.label", props={"text": "{../badButton.props.text}"}),
		])
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", PASCAL_CASE_CONFIG)

		result = self._run(["--config", str(config_path), "--fix-unsafe", "--files", str(view_path)])

		fixed = self._read(view_path)
		self.assertEqual(
			fixed["root"]["children"][0]["meta"]["name"], "BadButton",
			f"--fix-unsafe alone should rename the referenced component.\n"
			f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
		)
		self.assertIn(
			"BadButton", fixed["root"]["children"][1]["props"]["text"],
			"--fix-unsafe alone should update the reference to the renamed component."
		)

	def test_fix_unsafe_help_text_drops_use_with_fix(self):
		"""The --fix-unsafe help text should no longer say 'use with --fix'."""
		result = self._run(["--help"])
		self.assertIn("--fix-unsafe", result.stdout)
		# argparse wraps help text across lines, so collapse whitespace before
		# checking for the phrase.
		normalized = " ".join(result.stdout.split())
		self.assertNotIn(
			"use with --fix", normalized,
			"--fix-unsafe help text should not instruct users to combine it with --fix"
		)

	# ------------------------------------------------------------------
	# Issue #94: report post-fix results, not stale pre-fix violations
	# ------------------------------------------------------------------
	def test_fix_reports_post_fix_clean_exit(self):
		"""After `--fix` clears the only violation, the run should exit clean (0)."""
		view = make_view([make_component("badButton", "ia.input.button")])
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", PASCAL_CASE_CONFIG)

		result = self._run(["--config", str(config_path), "--fix", "--files", str(view_path)])

		# Sanity: the fix was actually applied.
		fixed = self._read(view_path)
		self.assertEqual(fixed["root"]["children"][0]["meta"]["name"], "BadButton")

		# The reported result should reflect the post-fix (clean) state.
		self.assertEqual(
			result.returncode, 0, f"After --fix removed the only violation, exit code should be 0 "
			f"(no remaining issues), got {result.returncode}.\n"
			f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
		)
		self.assertIn(
			"No style inconsistencies found", result.stdout,
			"Post-fix summary should report a clean result, not the pre-fix violation."
		)

	def test_fix_applies_exactly_once(self):
		"""The fix should be applied exactly once (no multi-pass fix loop)."""
		view = make_view([make_component("badButton", "ia.input.button")])
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", PASCAL_CASE_CONFIG)

		result = self._run(["--config", str(config_path), "--fix", "--files", str(view_path)])

		# The "Applied: N fix(es) | Skipped: ..." summary line is printed once per
		# apply pass. It should appear exactly once, proving fixes are not
		# re-applied on the re-evaluation pass (no multi-pass fix loop).
		summary_lines = [line for line in result.stdout.splitlines() if "| Skipped:" in line]
		self.assertEqual(
			len(summary_lines), 1, f"Fixes should be applied exactly once. Found {len(summary_lines)} "
			f"fix-summary lines.\nSTDOUT:\n{result.stdout}"
		)

	# ------------------------------------------------------------------
	# UnusedCustomPropertiesRule fix support
	# ------------------------------------------------------------------
	def test_fix_removes_unused_custom_property(self):
		"""`--fix` should delete an unused custom property (value + propConfig entry)."""
		view = make_view([make_component("MyLabel")])
		view["custom"] = {"unusedProp": "value"}
		view["propConfig"] = {"custom.unusedProp": {"access": "PRIVATE", "persistent": True}}
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", UNUSED_PROPS_CONFIG)

		result = self._run(["--config", str(config_path), "--fix", "--files", str(view_path)])

		fixed = self._read(view_path)
		self.assertNotIn("unusedProp", fixed.get("custom", {}))
		self.assertNotIn("custom.unusedProp", fixed.get("propConfig", {}))
		self.assertEqual(
			result.returncode, 0, f"After --fix removed the only violation, exit code should be 0.\n"
			f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
		)

	def test_fix_keeps_unused_parameter_without_fix_unsafe(self):
		"""Removing a view parameter is unsafe: plain `--fix` must leave it in place."""
		view = make_view([make_component("MyLabel")])
		view["params"] = {"unusedParam": ""}
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", UNUSED_PROPS_CONFIG)

		result = self._run(["--config", str(config_path), "--fix", "--files", str(view_path)])

		unchanged = self._read(view_path)
		self.assertIn(
			"unusedParam", unchanged.get("params", {}),
			"Plain --fix must not remove view parameters (interface change is unsafe)."
		)
		# The violation is still present, so the run should not exit clean.
		self.assertNotEqual(
			result.returncode, 0, f"Unsafe fix was skipped, so the violation should still report.\n"
			f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
		)

	def test_fix_unsafe_removes_unused_parameter(self):
		"""`--fix-unsafe` should delete an unused view parameter."""
		view = make_view([make_component("MyLabel")])
		view["params"] = {"unusedParam": ""}
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", UNUSED_PROPS_CONFIG)

		result = self._run(["--config", str(config_path), "--fix-unsafe", "--files", str(view_path)])

		fixed = self._read(view_path)
		self.assertNotIn("unusedParam", fixed.get("params", {}))
		self.assertEqual(
			result.returncode, 0, f"After --fix-unsafe removed the only violation, exit code should be 0.\n"
			f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
		)

	def test_fix_dry_run_previews_property_removal(self):
		"""`--fix-dry-run` should preview DELETE operations without modifying the file."""
		view = make_view([make_component("MyLabel")])
		view["custom"] = {"unusedProp": "value"}
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", UNUSED_PROPS_CONFIG)

		result = self._run(["--config", str(config_path), "--fix-dry-run", "--files", str(view_path)])

		unchanged = self._read(view_path)
		self.assertIn("unusedProp", unchanged.get("custom", {}), "--fix-dry-run must not modify the file.")
		self.assertIn("DELETE", result.stdout, "Dry run should preview the DELETE operation.")

	def test_fix_dry_run_does_not_reevaluate_or_modify(self):
		"""`--fix-dry-run` should not mutate the file and should still report the violation."""
		view = make_view([make_component("badButton", "ia.input.button")])
		view_path = self._write("view.json", view)
		config_path = self._write("config.json", PASCAL_CASE_CONFIG)

		result = self._run(["--config", str(config_path), "--fix-dry-run", "--files", str(view_path)])

		# File must be untouched by a dry run.
		unchanged = self._read(view_path)
		self.assertEqual(
			unchanged["root"]["children"][0]["meta"]["name"], "badButton",
			"--fix-dry-run must not modify the file."
		)
		# Dry run mutates nothing, so the pre-fix violation should still be reported.
		self.assertNotEqual(
			result.returncode, 0, f"--fix-dry-run should still report the (unfixed) violation.\n"
			f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
		)


if __name__ == "__main__":
	unittest.main()
