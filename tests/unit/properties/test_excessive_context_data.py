# pylint: disable=import-error
"""
Tests for ExcessiveContextDataRule.

Covers the large-value detection method: a single scalar string stored in a
custom property (e.g. embedded markup, an encoded image, or a serialized
dataset) flattens to one path-value pair, so it is invisible to the
structure-based detectors (array size, breadth, depth, data points). The
rule must also measure the size of individual values.
"""
import json

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config

RULE_NAME = "ExcessiveContextDataRule"

# Mirrors the rule's default max_value_length; tests build strings relative to it.
DEFAULT_MAX_VALUE_LENGTH = 10000


def _build_view(custom=None, component_props=None):
	"""Build a minimal view with the given custom properties dict."""
	view = {
		"custom": custom or {},
		"params": {},
		"props": {
			"defaultSize": {
				"height": 100,
				"width": 200
			}
		},
		"root": {
			"children": [{
				"meta": {
					"name": "Placeholder"
				},
				"props": component_props or {
					"text": "placeholder"
				},
				"type": "ia.display.label",
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord",
		},
	}
	return json.dumps(view)


class TestLargeValueDetection(BaseRuleTest):
	"""A custom property holding one oversized string value must be flagged."""

	def test_long_string_value_flagged_with_defaults(self):
		"""A string exceeding the default max_value_length produces one error."""
		oversized = "x" * (DEFAULT_MAX_VALUE_LENGTH + 1)
		view = _build_view(custom={"embeddedContent": oversized})

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME))

		errors = self.get_errors_for_rule(RULE_NAME)
		self.assertEqual(len(errors), 1, f"Expected exactly one violation, got: {errors}")
		self.assertIn("custom.embeddedContent", errors[0])
		self.assertIn(str(DEFAULT_MAX_VALUE_LENGTH + 1), errors[0])

	def test_string_at_threshold_passes(self):
		"""A string exactly at the threshold is allowed (limit is exclusive)."""
		view = _build_view(custom={"embeddedContent": "x" * DEFAULT_MAX_VALUE_LENGTH})

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME))

		self.assert_no_issues(RULE_NAME)

	def test_threshold_is_configurable(self):
		"""max_value_length kwarg lowers/raises the limit."""
		view = _build_view(custom={"note": "x" * 150})

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME, max_value_length=100))
		self.assertEqual(self.get_error_count(RULE_NAME), 1)

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME, max_value_length=200))
		self.assert_no_issues(RULE_NAME)

	def test_nested_long_string_flagged(self):
		"""Oversized values nested inside custom objects are still detected."""
		oversized = "x" * (DEFAULT_MAX_VALUE_LENGTH + 1)
		view = _build_view(custom={"config": {"template": oversized}})

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME))

		errors = self.get_errors_for_rule(RULE_NAME)
		self.assertEqual(len(errors), 1, f"Expected exactly one violation, got: {errors}")
		self.assertIn("custom.config.template", errors[0])

	def test_each_oversized_value_reported_separately(self):
		"""Two oversized values produce two violations."""
		oversized = "x" * (DEFAULT_MAX_VALUE_LENGTH + 1)
		view = _build_view(custom={"first": oversized, "second": oversized})

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME))

		self.assertEqual(self.get_error_count(RULE_NAME), 2)

	def test_long_string_outside_custom_ignored(self):
		"""The rule only inspects custom.* — long component prop values are out of scope."""
		oversized = "x" * (DEFAULT_MAX_VALUE_LENGTH + 1)
		view = _build_view(component_props={"text": oversized})

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME))

		self.assert_no_issues(RULE_NAME)

	def test_non_string_values_ignored(self):
		"""Numbers and booleans have no meaningful character length."""
		view = _build_view(custom={"bigNumber": 10**100, "flag": True})

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME))

		self.assert_no_issues(RULE_NAME)

	def test_severity_warning_downgrade(self):
		"""severity='warning' reports the violation as a warning instead of an error."""
		oversized = "x" * (DEFAULT_MAX_VALUE_LENGTH + 1)
		view = _build_view(custom={"embeddedContent": oversized})

		self.run_lint_on_mock_view(view, get_test_config(RULE_NAME, severity="warning"))

		self.assertEqual(self.get_error_count(RULE_NAME), 0)
		self.assertEqual(self.get_warning_count(RULE_NAME), 1)


if __name__ == "__main__":
	import unittest
	unittest.main()
