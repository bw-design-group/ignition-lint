# pylint: disable=import-error
"""
Tests for modeling property-change (onChange) scripts as first-class script nodes.

Regression coverage for issue #99: property-change scripts live under
``propConfig.<property>.onChange.script`` (view-level) and
``<component>.propConfig.<property>.onChange.script`` (component-level). The model
builder previously only collected event-handler scripts under ``.events.`` paths,
so these onChange bodies were never built into any script node. As a result,
script-oriented rules such as ``PylintScriptRule`` silently skipped them.

These tests assert that:
  1. The builder emits a script node for each onChange script and registers it in
     the generic ``model['scripts']`` collection so existing script visitors see it.
  2. ``PylintScriptRule`` actually lints onChange script bodies.
"""
import json

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, create_temp_view_file
from ignition_lint.common.flatten_json import flatten_file
from ignition_lint.model.builder import ViewModelBuilder
from ignition_lint.model.node_types import ScriptNode


def _build_view():
	"""View exercising both view-level and component-level onChange scripts."""
	return {
		"custom": {},
		"params": {},
		"propConfig": {
			# View-level custom property with an onChange handler.
			"custom.total": {
				"persistent": False,
				"onChange": {
					"enabled": True,
					# References onChange parameters (valid) plus an undefined name (invalid).
					"script": "\treturn previousValue.value + currentValue.value + undefinedTotal",
				},
			},
		},
		"props": {},
		"root": {
			"children": [{
				"meta": {
					"name": "Label"
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
				"propConfig": {
					# Component-level custom property with an onChange handler.
					"custom.flag": {
						"persistent": False,
						"onChange": {
							"enabled": True,
							"script": "\treturn currentValue.value and undefinedFlag",
						},
					},
				},
				"type": "ia.display.label",
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord",
		},
	}


class TestPropertyChangeScripts(BaseRuleTest):
	"""Property-change (onChange) scripts must be modeled as script nodes."""

	def _flatten(self):
		view_file = create_temp_view_file(json.dumps(_build_view(), indent=2))
		try:
			return flatten_file(view_file)
		finally:
			view_file.unlink(missing_ok=True)

	def test_builder_emits_script_nodes_for_onchange(self):
		"""ViewModelBuilder should build a script node for each onChange handler."""
		flattened = self._flatten()
		model = ViewModelBuilder().build_model(flattened)

		# Every onChange handler should surface in the generic scripts collection so
		# existing script visitors (e.g. PylintScriptRule) pick it up.
		onchange_scripts = [
			node for node in model['scripts'] if isinstance(node, ScriptNode) and '.onChange' in node.path
		]
		onchange_paths = sorted(node.path for node in onchange_scripts)

		self.assertIn(
			"propConfig.custom.total.onChange", onchange_paths,
			f"View-level onChange script not modeled. Got script paths: "
			f"{sorted(n.path for n in model['scripts'])}"
		)
		self.assertTrue(
			any(path.endswith("propConfig.custom.flag.onChange") for path in onchange_paths),
			f"Component-level onChange script not modeled. Got script paths: "
			f"{sorted(n.path for n in model['scripts'])}"
		)

	def test_pylint_rule_lints_onchange_script_bodies(self):
		"""PylintScriptRule must report violations found inside onChange bodies."""
		view_file = create_temp_view_file(json.dumps(_build_view(), indent=2))
		try:
			rule_config = get_test_config("PylintScriptRule")
			results = self.run_lint_on_file(view_file, rule_config)
		finally:
			view_file.unlink(missing_ok=True)

		# PylintScriptRule reports via custom-grouped output; undefined-variable
		# (E0602) maps to the "error" severity by default.
		formatted_errors = results.custom_formatted_errors.get("PylintScriptRule", "")

		self.assertIn(
			"E0602", formatted_errors,
			f"Expected an undefined-variable (E0602) violation from an onChange body. "
			f"Formatted errors: {formatted_errors!r}"
		)
		self.assertIn(
			"onChange", formatted_errors, f"Expected the violation to reference an onChange script path. "
			f"Formatted errors: {formatted_errors!r}"
		)


if __name__ == "__main__":
	import unittest
	unittest.main()
