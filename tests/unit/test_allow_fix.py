# pylint: disable=import-error
"""
Tests for the per-rule `allow_fix` config key (issue #124).

`allow_fix` sits alongside `enabled` in rule config (default true). When false,
the rule still detects and reports violations, but refuses fix context - so it
generates no fixes at all, keeping --fix and --fix-dry-run honest. An explicit
CLI --fix-rules overrides the config for the rules it names.
"""

import contextlib
import io
import json
import os
import sys
import unittest
from collections import OrderedDict

# Add the src directory to the PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from ignition_lint.cli import create_rules_from_config
from ignition_lint.common.path_translator import PathTranslator
from ignition_lint.common.flatten_json import flatten_json
from ignition_lint.linter import LintEngine
from ignition_lint.rules import RULES_MAP

RULE_NAME = 'UnusedCustomPropertiesRule'

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
		"children": [],
		"meta": {
			"name": "root"
		}
	},
}


def _lint_with_fix_context(rule):
	"""Run one rule in fix mode over the unused-prop view. Returns LintResults."""
	json_data = json.loads(json.dumps(UNUSED_PROP_VIEW), object_pairs_hook=OrderedDict)
	translator = PathTranslator(json_data)
	flattened = flatten_json(json_data)
	return LintEngine([rule]).process(flattened, json_data=json_data, path_translator=translator)


class TestAllowFixGating(unittest.TestCase):
	"""FixableMixin-level behavior of the allow_fix flag."""

	def test_allow_fix_defaults_to_true(self):
		"""Fixable rules default to participating in --fix."""
		rule = RULES_MAP[RULE_NAME].create_from_config({})
		self.assertIs(rule.allow_fix, True)

	def test_fixes_generated_when_allowed(self):
		"""With allow_fix=True (default), violations come with fixes."""
		rule = RULES_MAP[RULE_NAME].create_from_config({})
		results = _lint_with_fix_context(rule)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertEqual(len(results.fixes), 1)

	def test_no_fixes_but_violations_still_reported_when_disallowed(self):
		"""allow_fix=False keeps detection intact but produces zero fixes."""
		rule = RULES_MAP[RULE_NAME].create_from_config({})
		rule.allow_fix = False
		results = _lint_with_fix_context(rule)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertEqual(results.fixes, [])

	def test_set_fix_context_refused_when_disallowed(self):
		"""A disallowed rule never stores fix context."""
		rule = RULES_MAP[RULE_NAME].create_from_config({})
		rule.allow_fix = False
		rule.set_fix_context({}, object())
		self.assertFalse(rule.has_fix_context)

	def test_reenabling_allow_fix_restores_fixes(self):
		"""Flipping allow_fix back to True restores fix generation."""
		rule = RULES_MAP[RULE_NAME].create_from_config({})
		rule.allow_fix = False
		rule.allow_fix = True
		results = _lint_with_fix_context(rule)
		self.assertEqual(len(results.fixes), 1)


class TestAllowFixConfigParsing(unittest.TestCase):
	"""create_rules_from_config handling of the allow_fix key."""

	@staticmethod
	def _rule_and_status(rules, statuses, name):
		rule = next((r for r in rules if r.__class__.__name__ == name), None)
		status = next(s for s in statuses if s["name"] == name)
		return rule, status

	def test_allow_fix_false_applied_to_instance(self):
		"""allow_fix: false in config lands on the rule instance and the status detail."""
		rules, statuses = create_rules_from_config({RULE_NAME: {"enabled": True, "allow_fix": False}})
		rule, status = self._rule_and_status(rules, statuses, RULE_NAME)
		self.assertIs(rule.allow_fix, False)
		self.assertEqual(status["state"], "loaded")
		self.assertEqual(status["detail"], "allow_fix=false")

	def test_allow_fix_defaults_true_when_absent(self):
		"""Rules absent from config (or without the key) default to allow_fix=True."""
		rules, statuses = create_rules_from_config({})
		rule, status = self._rule_and_status(rules, statuses, RULE_NAME)
		self.assertIs(rule.allow_fix, True)
		self.assertIsNone(status["detail"])

	def test_invalid_allow_fix_values_error_rule_and_alert_user(self):
		"""Every non-boolean allow_fix value is a loud config error for that rule.

		Notably "false"/"no" strings and 0/1 ints must NOT be silently coerced -
		a user writing "allow_fix": "false" means false, and silently treating it
		as anything else would either fix when they opted out or vice versa.
		"""
		for bad_value in ("no", "false", "true", 0, 1, None, [], {"on": True}):
			with self.subTest(value=bad_value):
				stdout = io.StringIO()
				with contextlib.redirect_stdout(stdout):
					rules, statuses = create_rules_from_config({
						RULE_NAME: {
							"enabled": True,
							"allow_fix": bad_value
						}
					})
				rule, status = self._rule_and_status(rules, statuses, RULE_NAME)
				self.assertIsNone(rule, f"rule must not load with allow_fix={bad_value!r}")
				self.assertEqual(status["state"], "error")
				self.assertIn("allow_fix", status["detail"])
				# The user must be told on stdout, not just in the status dict.
				self.assertIn("allow_fix", stdout.getvalue())
				self.assertIn(RULE_NAME, stdout.getvalue())

	def test_allow_fix_on_non_fixable_rule_loads_and_alerts_user(self):
		"""allow_fix on a rule without fix support loads fine but prints a notice."""
		stdout = io.StringIO()
		with contextlib.redirect_stdout(stdout):
			rules, statuses = create_rules_from_config({
				"PollingIntervalRule": {
					"enabled": True,
					"allow_fix": False
				}
			})
		rule, status = self._rule_and_status(rules, statuses, "PollingIntervalRule")
		self.assertIsNotNone(rule)
		self.assertEqual(status["state"], "loaded")
		self.assertIn("allow_fix has no effect", stdout.getvalue())
		self.assertIn("PollingIntervalRule", stdout.getvalue())

	def test_no_notice_for_non_fixable_rule_without_the_key(self):
		"""Rules that don't mention allow_fix produce no notice noise."""
		stdout = io.StringIO()
		with contextlib.redirect_stdout(stdout):
			create_rules_from_config({"PollingIntervalRule": {"enabled": True}})
		self.assertNotIn("allow_fix", stdout.getvalue())

	def test_other_rules_unaffected_by_one_rules_bad_allow_fix(self):
		"""A bad allow_fix on one rule doesn't take down the rest of the config."""
		stdout = io.StringIO()
		with contextlib.redirect_stdout(stdout):
			rules, statuses = create_rules_from_config({RULE_NAME: {"enabled": True, "allow_fix": "oops"}})
		other, other_status = self._rule_and_status(rules, statuses, "NamePatternRule")
		self.assertIsNotNone(other)
		self.assertEqual(other_status["state"], "loaded")
		self.assertIs(other.allow_fix, True)


if __name__ == '__main__':
	unittest.main()
