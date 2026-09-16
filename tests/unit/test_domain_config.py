# pylint: disable=import-error,wrong-import-position
"""Unit tests for per-domain routing of the flat rule config, alias resolution and per-domain rule creation."""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from ignition_lint.cli import _split_config_by_domain, create_rules_from_config
from ignition_lint.common.domain import LintDomain
from ignition_lint.rules import RULES_MAP
from ignition_lint.rules.registry import get_rules_for_domain, resolve_rule_name


def _capture(func, *args, **kwargs):
	buf = io.StringIO()
	with contextlib.redirect_stdout(buf):
		result = func(*args, **kwargs)
	return result, buf.getvalue()


class TestSplitConfigByDomain(unittest.TestCase):
	"""A flat config is routed to domains by each rule's declared domain."""

	def test_flat_config_routes_by_rule_domain(self):
		"""Flat config routes by rule domain."""
		config = {
			"_comment": "x",
			"NamePatternRule": {
				"enabled": True
			},
			"LibraryNamePatternRule": {
				"enabled": False
			},
			"LibraryScriptPylintRule": {
				"enabled": True,
				"kwargs": {
					"debug": False
				}
			},
		}
		sections, out = _capture(_split_config_by_domain, config)
		self.assertEqual(list(sections[LintDomain.PERSPECTIVE]), ["NamePatternRule"])
		self.assertEqual(
			sorted(sections[LintDomain.SCRIPTING]), ["LibraryNamePatternRule", "LibraryScriptPylintRule"]
		)
		self.assertEqual(out, "")

	def test_domain_names_are_not_special_keys(self):
		"""Domain names are not special keys."""
		_, out = _capture(_split_config_by_domain, {"perspective": {"NamePatternRule": {}}})
		self.assertIn("Unknown rule in config: perspective", out)

	def test_unknown_rule_reported(self):
		"""Unknown rule reported."""
		_, out = _capture(_split_config_by_domain, {"NopeRule": {}})
		self.assertIn("Unknown rule in config: NopeRule", out)

	def test_alias_resolves_with_one_deprecation_line(self):
		"""Alias resolves with one deprecation line."""
		kwargs = {"category_mapping": {"E": "warning"}}
		sections, out = _capture(
			_split_config_by_domain, {"PylintScriptRule": {
				"enabled": True,
				"kwargs": kwargs
			}}
		)
		entry = sections[LintDomain.PERSPECTIVE]["PerspectiveScriptPylintRule"]
		self.assertEqual(entry["kwargs"], kwargs)
		self.assertEqual(out.count("deprecated"), 1)
		self.assertIn("use 'PerspectiveScriptPylintRule' instead", out)

	def test_alias_and_canonical_together_canonical_wins(self):
		"""Alias and canonical together: canonical wins."""
		config = {
			"PylintScriptRule": {
				"enabled": False
			},
			"PerspectiveScriptPylintRule": {
				"enabled": True
			},
		}
		sections, out = _capture(_split_config_by_domain, config)
		self.assertTrue(sections[LintDomain.PERSPECTIVE]["PerspectiveScriptPylintRule"]["enabled"])
		self.assertIn("both are present", out)


class TestCreateRulesPerDomain(unittest.TestCase):
	"""create_rules_from_config restricted to one domain never instantiates the other's rules."""

	def test_scripting_domain_only_builds_scripting_rules(self):
		"""Test scripting domain only builds scripting rules."""
		rules, statuses = create_rules_from_config({}, LintDomain.SCRIPTING)
		names = {r.__class__.__name__ for r in rules}
		self.assertEqual(names, set(get_rules_for_domain(LintDomain.SCRIPTING)))
		self.assertEqual({s["name"] for s in statuses}, names)
		self.assertNotIn("NamePatternRule", names)

	def test_perspective_domain_excludes_scripting_rules(self):
		"""Test perspective domain excludes scripting rules."""
		rules, _ = create_rules_from_config({}, LintDomain.PERSPECTIVE)
		names = {r.__class__.__name__ for r in rules}
		self.assertIn("PerspectiveScriptPylintRule", names)
		self.assertNotIn("LibraryScriptPylintRule", names)
		self.assertNotIn("LibraryNamePatternRule", names)

	def test_legacy_call_without_domain_accepts_alias(self):
		"""Test legacy call without domain accepts alias."""
		config = {"PylintScriptRule": {"enabled": True, "kwargs": {"severity": "warning"}}}
		(rules, statuses), out = _capture(create_rules_from_config, config)
		rule = next(r for r in rules if r.__class__.__name__ == "PerspectiveScriptPylintRule")
		self.assertEqual(rule.severity, "warning")
		status = next(s for s in statuses if s["name"] == "PerspectiveScriptPylintRule")
		self.assertEqual(status["source"], "config")
		self.assertIn("deprecated", out)
		self.assertNotIn("Unknown rule", out)

	def test_every_registered_rule_has_a_domain(self):
		"""Test every registered rule has a domain."""
		for name, cls in RULES_MAP.items():
			with self.subTest(rule=name):
				self.assertIsInstance(cls.domain, LintDomain)

	def test_resolve_rule_name(self):
		"""Test resolve rule name."""
		self.assertEqual(resolve_rule_name("PylintScriptRule"), ("PerspectiveScriptPylintRule", True))
		self.assertEqual(resolve_rule_name("NamePatternRule"), ("NamePatternRule", False))
		self.assertNotIn("PylintScriptRule", RULES_MAP)


if __name__ == '__main__':
	unittest.main()
