# pylint: disable=import-error
"""
Integration tests for the per-rule `allow_fix` config key (issue #124).

`allow_fix: false` keeps a rule detection-only: violations still report, but
--fix must not touch the file and --fix-dry-run must not propose its fixes.
An explicit --fix-rules on the CLI overrides the config for the rules it names,
and unknown --fix-rules names must warn instead of failing silently.

These tests drive the real CLI via subprocess so they exercise the full
argument-parsing -> config -> lint -> fix -> report pipeline.
"""

import json
import sys
import unittest
import tempfile
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
MAIN_PY = REPO_ROOT / "src" / "ignition_lint" / "__main__.py"

UNUSED_PROP_VIEW = {
	"custom": {
		"unusedProp": "value"
	},
	"propConfig": {
		"custom.unusedProp": {
			"persistent": True
		}
	},
	"root": {
		"children": [{
			"meta": {
				"name": "badButton"
			},
			"props": {},
			"type": "ia.input.button",
		}],
		"meta": {
			"name": "root"
		},
		"props": {},
		"type": "ia.container.flex",
	},
}


def _config(unused_allow_fix=None, with_naming=False, naming_allow_fix=None):
	"""Build a rule config with optional allow_fix keys."""
	config = {"UnusedCustomPropertiesRule": {"enabled": True, "kwargs": {"severity": "error"}}}
	if unused_allow_fix is not None:
		config["UnusedCustomPropertiesRule"]["allow_fix"] = unused_allow_fix
	if with_naming:
		config["NamePatternRule"] = {
			"enabled": True,
			"kwargs": {
				"convention": "PascalCase",
				"target_node_types": ["component"],
				"severity": "warning",
			},
		}
		if naming_allow_fix is not None:
			config["NamePatternRule"]["allow_fix"] = naming_allow_fix
	return config


class TestCLIAllowFix(unittest.TestCase):
	"""End-to-end CLI behavior of allow_fix and its --fix-rules override."""

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

	def test_allow_fix_false_reports_but_does_not_modify(self):
		"""--fix must not touch a file when the only violating rule has allow_fix=false."""
		view_path = self._write("view.json", UNUSED_PROP_VIEW)
		config_path = self._write("config.json", _config(unused_allow_fix=False))

		result = self._run(["--config", str(config_path), "--fix", "--files", str(view_path)])

		self.assertIn("unusedProp", result.stdout, "violation must still be reported")
		self.assertEqual(
			self._read(view_path), UNUSED_PROP_VIEW,
			f"file must be unchanged with allow_fix=false.\nSTDOUT:\n{result.stdout}"
		)

	def test_allow_fix_absent_defaults_to_fixing(self):
		"""Without the key, --fix behaves exactly as before (backward compatible)."""
		view_path = self._write("view.json", UNUSED_PROP_VIEW)
		config_path = self._write("config.json", _config())

		result = self._run(["--config", str(config_path), "--fix", "--files", str(view_path)])

		fixed = self._read(view_path)
		self.assertNotIn(
			"unusedProp", fixed.get("custom", {}),
			f"default allow_fix must keep --fix working.\nSTDOUT:\n{result.stdout}"
		)
		self.assertNotIn("custom.unusedProp", fixed.get("propConfig", {}))

	def test_dry_run_shows_no_fixes_for_disallowed_rule(self):
		"""--fix-dry-run must not propose fixes a real --fix would refuse to apply."""
		view_path = self._write("view.json", UNUSED_PROP_VIEW)
		config_path = self._write("config.json", _config(unused_allow_fix=False))

		result = self._run(["--config", str(config_path), "--fix-dry-run", "--files", str(view_path)])

		self.assertNotIn(
			"Remove unused", result.stdout,
			f"dry run must not advertise fixes from an allow_fix=false rule.\nSTDOUT:\n{result.stdout}"
		)
		self.assertEqual(self._read(view_path), UNUSED_PROP_VIEW)

	def test_fix_rules_cli_overrides_allow_fix_false(self):
		"""--fix-rules naming the rule wins over allow_fix=false in config."""
		view_path = self._write("view.json", UNUSED_PROP_VIEW)
		config_path = self._write("config.json", _config(unused_allow_fix=False))

		result = self._run([
			"--config",
			str(config_path), "--fix", "--fix-rules", "UnusedCustomPropertiesRule", "--files",
			str(view_path)
		])

		fixed = self._read(view_path)
		self.assertNotIn(
			"unusedProp", fixed.get("custom", {}),
			f"--fix-rules must override allow_fix=false.\nSTDOUT:\n{result.stdout}"
		)

	def test_mixed_rules_only_allowed_rule_fixes(self):
		"""With two fixable rules, only the allowed one's fixes apply."""
		view_path = self._write("view.json", UNUSED_PROP_VIEW)
		config_path = self._write("config.json", _config(unused_allow_fix=False, with_naming=True))

		result = self._run(["--config", str(config_path), "--fix", "--files", str(view_path)])

		fixed = self._read(view_path)
		self.assertEqual(
			fixed["root"]["children"][0]["meta"]["name"], "BadButton",
			f"allowed rule's rename must apply.\nSTDOUT:\n{result.stdout}"
		)
		self.assertIn(
			"unusedProp", fixed["custom"],
			f"disallowed rule's deletion must not apply.\nSTDOUT:\n{result.stdout}"
		)

	def test_unknown_fix_rules_name_warns_user(self):
		"""A typo'd --fix-rules name must warn instead of silently doing nothing."""
		view_path = self._write("view.json", UNUSED_PROP_VIEW)
		config_path = self._write("config.json", _config())

		result = self._run([
			"--config",
			str(config_path), "--fix", "--fix-rules", "UnusedCustomPropertysRule", "--files",
			str(view_path)
		])

		self.assertIn(
			"does not match any loaded rule", result.stdout,
			f"typo'd --fix-rules must alert the user.\nSTDOUT:\n{result.stdout}"
		)
		self.assertEqual(self._read(view_path), UNUSED_PROP_VIEW, "nothing should have been fixed")

	def test_invalid_allow_fix_value_alerts_user(self):
		"""A non-boolean allow_fix is reported as a rule config error on stdout."""
		view_path = self._write("view.json", UNUSED_PROP_VIEW)
		config_path = self._write("config.json", _config(unused_allow_fix="false"))

		result = self._run(["--config", str(config_path), "--files", str(view_path)])

		self.assertIn(
			"allow_fix", result.stdout,
			f"invalid allow_fix must be reported to the user.\nSTDOUT:\n{result.stdout}"
		)
		self.assertIn("Error creating rule UnusedCustomPropertiesRule", result.stdout)


if __name__ == '__main__':
	unittest.main()
