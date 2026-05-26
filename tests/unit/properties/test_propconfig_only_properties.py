# pylint: disable=import-error
"""
Tests for collection of custom/param properties that exist only in propConfig.

Regression coverage for issue #91: when a custom property is defined only via a
propConfig binding (e.g. a non-persistent bound property, or a persistent property
whose parent object is empty), the model builder must still emit a Property node
for it so rules like NamePatternRule can visit it. Previously these properties
were silently skipped because the builder iterated the flattened JSON, which only
contains entries for properties that have a concrete value in the custom/params
tree.
"""
import json

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, create_temp_view_file
from ignition_lint.common.flatten_json import flatten_file
from ignition_lint.model.builder import ViewModelBuilder


def _build_view():
	"""Minimal view exercising the propConfig-only property cases from issue #91."""
	return {
		"custom": {
			"chillers": {},
			"showFlow": {
				"D": False,
				"FWR_1": True,
			},
		},
		"params": {
			"baseTagPath": "",
		},
		"propConfig": {
			# Persistent parent, but the child below has no value in custom.chillers.
			# Only appears via the binding entry in propConfig.
			"custom.chillers": {
				"persistent": True,
			},
			"custom.chillers.WingOrCore": {
				"binding": {
					"config": {
						"path": "view.params.baseTagPath"
					},
					"type": "property",
				}
			},
			# Non-persistent component-style prop defined only via binding.
			"custom.deviceName": {
				"binding": {
					"config": {
						"path": "view.params.baseTagPath"
					},
					"type": "property",
				},
				"persistent": False,
			},
			# Persistent parent with binding-only child whose name is too short.
			"custom.showFlow": {
				"persistent": True,
			},
			"custom.showFlow.A": {
				"binding": {
					"config": {
						"expression": "true"
					},
					"type": "expr",
				}
			},
			"params.baseTagPath": {
				"paramDirection": "input",
				"persistent": True,
			},
		},
		"props": {
			"defaultSize": {
				"height": 100,
				"width": 200
			},
		},
		"root": {
			"children": [{
				"meta": {
					"name": "Placeholder"
				},
				"position": {
					"height": 32,
					"width": 200,
					"x": 0,
					"y": 0
				},
				"props": {
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


class TestPropConfigOnlyProperties(BaseRuleTest):
	"""Custom/param properties that exist only in propConfig must be collected."""

	def _flatten(self):
		view_file = create_temp_view_file(json.dumps(_build_view(), indent=2))
		try:
			return flatten_file(view_file)
		finally:
			view_file.unlink(missing_ok=True)

	def test_model_emits_property_nodes_for_propconfig_only_paths(self):
		"""ViewModelBuilder should produce Property nodes for binding-only custom props."""
		flattened = self._flatten()
		model = ViewModelBuilder().build_model(flattened)

		property_paths = {prop.path for prop in model['properties']}

		# These exist only as propConfig binding entries — they must still be modeled.
		self.assertIn(
			"custom.chillers.WingOrCore", property_paths,
			f"Missing propConfig-only property 'custom.chillers.WingOrCore'. Got: {sorted(property_paths)}"
		)
		self.assertIn(
			"custom.deviceName", property_paths,
			f"Missing non-persistent bound property 'custom.deviceName'. Got: {sorted(property_paths)}"
		)
		self.assertIn(
			"custom.showFlow.A", property_paths,
			f"Missing propConfig-only property 'custom.showFlow.A'. Got: {sorted(property_paths)}"
		)

		# Sanity: properties that already had concrete values are still collected.
		self.assertIn("custom.showFlow.D", property_paths)
		self.assertIn("custom.showFlow.FWR_1", property_paths)

	def test_name_pattern_rule_flags_propconfig_only_properties(self):
		"""NamePatternRule must visit propConfig-only properties and report violations."""
		view_file = create_temp_view_file(json.dumps(_build_view(), indent=2))
		try:
			rule_config = get_test_config(
				"NamePatternRule",
				node_type_specific_rules={
					"property": {
						"convention": "camelCase",
						"min_length": 2,
						"severity": "warning",
					},
				},
			)
			self.run_lint_on_file(view_file, rule_config)
		finally:
			view_file.unlink(missing_ok=True)

		warnings = self.get_warnings_for_rule("NamePatternRule")

		# PascalCase under a camelCase convention → must be flagged.
		self.assertTrue(
			any("custom.chillers.WingOrCore" in w for w in warnings),
			f"Expected violation for 'custom.chillers.WingOrCore' but got: {warnings}"
		)
		# Single-character name under min_length=2 → must be flagged.
		self.assertTrue(
			any("custom.showFlow.A" in w for w in warnings),
			f"Expected violation for 'custom.showFlow.A' but got: {warnings}"
		)


if __name__ == "__main__":
	import unittest
	unittest.main()
