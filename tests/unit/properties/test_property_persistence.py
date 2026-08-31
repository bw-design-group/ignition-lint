# pylint: disable=import-error
"""
Tests for PropertyPersistenceRule.

The rule validates the `persistent` flag on BOUND properties (propConfig entries
that contain a binding). It is inert unless `expected_persistent` is configured.
Tag bindings are exempt by default because they may never create the property key
when the tag is missing.
"""

import json
import os
import sys
import unittest
from collections import OrderedDict

# Add the src directory to the PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from ignition_lint.common.fix_operations import FixOperationType
from ignition_lint.common.path_translator import PathTranslator
from ignition_lint.common.fix_engine import FixEngine
from ignition_lint.common.flatten_json import flatten_json
from ignition_lint.linter import LintEngine
from ignition_lint.rules import RULES_MAP

RULE_NAME = 'PropertyPersistenceRule'


def _load_view(view_dict) -> OrderedDict:
	"""Round-trip through JSON to get an OrderedDict like read_json_file produces."""
	return json.loads(json.dumps(view_dict), object_pairs_hook=OrderedDict)


def _make_engine(**kwargs) -> LintEngine:
	"""Create a LintEngine with a PropertyPersistenceRule configured via kwargs."""
	rule = RULES_MAP[RULE_NAME].create_from_config(kwargs)
	return LintEngine([rule])


def _lint(view_dict, **kwargs):
	"""Run the rule in detection-only mode. Returns LintResults."""
	flattened = flatten_json(_load_view(view_dict))
	return _make_engine(**kwargs).process(flattened)


def _lint_with_fix_context(view_dict, **kwargs):
	"""Run the rule in fix mode. Returns (results, json_data, translator)."""
	json_data = _load_view(view_dict)
	translator = PathTranslator(json_data)
	flattened = flatten_json(json_data)
	results = _make_engine(**kwargs).process(flattened, json_data=json_data, path_translator=translator)
	return results, json_data, translator


def _expr_binding():
	"""A minimal expression binding config."""
	return {"config": {"expression": "1 + 1"}, "type": "expr"}


def _tag_binding(mode="direct"):
	"""A minimal tag binding config with the given mode."""
	return {"config": {"mode": mode, "tagPath": "[default]Some/Tag"}, "type": "tag"}


def _view(propconfig=None, custom=None, params=None, children=None):
	"""Build a minimal view dict."""
	return {
		"custom": custom or {},
		"params": params or {},
		"propConfig": propconfig or {},
		"root": {
			"children": children or [],
			"meta": {
				"name": "root"
			}
		},
	}


def _component(name, propconfig=None, custom=None, props=None):
	"""Build a minimal component dict."""
	component = {"meta": {"name": name}, "type": "ia.display.label"}
	if propconfig is not None:
		component["propConfig"] = propconfig
	if custom is not None:
		component["custom"] = custom
	if props is not None:
		component["props"] = props
	return component


class TestPersistenceDetection(unittest.TestCase):
	"""Detection behavior for expected_persistent=false."""

	def test_inert_by_default(self):
		"""Without expected_persistent, the rule never flags anything."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding(), "persistent": True}})
		results = _lint(view)
		self.assertEqual(results.errors, {})
		self.assertEqual(results.warnings, {})

	def test_bound_persistent_property_flagged(self):
		"""A bound property with persistent=true is flagged."""
		view = _view(custom={"a": 1}, propconfig={"custom.a": {"binding": _expr_binding(), "persistent": True}})
		results = _lint(view, expected_persistent=False)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertIn("custom.a", results.errors[RULE_NAME][0])

	def test_absent_persistent_flag_treated_as_persistent(self):
		"""Absent persistent flag means persistent (the Ignition default) and is flagged."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding()}})
		results = _lint(view, expected_persistent=False)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)

	def test_bound_nonpersistent_property_passes(self):
		"""A bound property with persistent=false passes."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding(), "persistent": False}})
		results = _lint(view, expected_persistent=False)
		self.assertEqual(results.errors, {})

	def test_unbound_property_ignored(self):
		"""Persistence is only checked on bound properties."""
		view = _view(custom={"a": 1}, propconfig={"custom.a": {"persistent": True, "access": "PRIVATE"}})
		results = _lint(view, expected_persistent=False)
		self.assertEqual(results.errors, {})

	def test_component_level_binding_flagged(self):
		"""Component-level propConfig entries are checked too."""
		child = _component(
			"Label", propconfig={"custom.compProp": {
				"binding": _expr_binding(),
				"persistent": True
			}}
		)
		results = _lint(_view(children=[child]), expected_persistent=False)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertIn("root.root.children[0].Label.custom.compProp", results.errors[RULE_NAME][0])

	def test_severity_warning_downgrade(self):
		"""severity=warning moves violations from errors to warnings."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding(), "persistent": True}})
		results = _lint(view, expected_persistent=False, severity="warning")
		self.assertEqual(results.errors, {})
		self.assertEqual(len(results.warnings.get(RULE_NAME, [])), 1)


class TestBindingTypeExemptions(unittest.TestCase):
	"""exempt_binding_types behavior."""

	def test_tag_bindings_exempt_by_default(self):
		"""Direct, indirect, and expression tag bindings are all skipped by default."""
		view = _view(
			propconfig={
				"custom.a": {
					"binding": _tag_binding("direct"),
					"persistent": True
				},
				"custom.b": {
					"binding": _tag_binding("indirect"),
					"persistent": True
				},
				"custom.c": {
					"binding": _tag_binding("expression"),
					"persistent": True
				},
			}
		)
		results = _lint(view, expected_persistent=False)
		self.assertEqual(results.errors, {})

	def test_empty_exemptions_include_tag_bindings(self):
		"""exempt_binding_types=[] overrides the default and checks tag bindings."""
		view = _view(propconfig={"custom.a": {"binding": _tag_binding("indirect"), "persistent": True}})
		results = _lint(view, expected_persistent=False, exempt_binding_types=[])
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)

	def test_tag_mode_specific_exemption(self):
		"""tag.indirect exempts only indirect tag bindings."""
		view = _view(
			propconfig={
				"custom.direct": {
					"binding": _tag_binding("direct"),
					"persistent": True
				},
				"custom.indirect": {
					"binding": _tag_binding("indirect"),
					"persistent": True
				},
			}
		)
		results = _lint(view, expected_persistent=False, exempt_binding_types=["tag.indirect"])
		errors = results.errors.get(RULE_NAME, [])
		self.assertEqual(len(errors), 1)
		self.assertIn("custom.direct", errors[0])

	def test_other_binding_type_exemption(self):
		"""Non-tag binding types can be exempted as well."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding(), "persistent": True}})
		results = _lint(view, expected_persistent=False, exempt_binding_types=["expr"])
		self.assertEqual(results.errors, {})

	def test_unknown_exemption_token_raises(self):
		"""Unknown exemption tokens raise ValueError at configuration time."""
		with self.assertRaises(ValueError):
			RULES_MAP[RULE_NAME].create_from_config({
				"expected_persistent": False,
				"exempt_binding_types": ["indirect_tag"]
			})

	def test_invalid_expected_persistent_raises(self):
		"""Non-boolean expected_persistent raises ValueError."""
		with self.assertRaises(ValueError):
			RULES_MAP[RULE_NAME].create_from_config({"expected_persistent": "false"})


class TestScopes(unittest.TestCase):
	"""The rule is hard-scoped to custom.* entries."""

	def test_props_scope_never_checked(self):
		"""Bound component props entries are never checked."""
		child = _component("Label", propconfig={"props.text": {"binding": _expr_binding(), "persistent": True}})
		results = _lint(_view(children=[child]), expected_persistent=False)
		self.assertEqual(results.errors, {})

	def test_params_scope_never_checked(self):
		"""Bound view params entries are never checked."""
		view = _view(
			params={"pageId": "x"},
			propconfig={"params.pageId": {
				"binding": _expr_binding(),
				"persistent": True
			}}
		)
		results = _lint(view, expected_persistent=False)
		self.assertEqual(results.errors, {})


class TestExpectedPersistentTrue(unittest.TestCase):
	"""Detection behavior for expected_persistent=true."""

	def test_nonpersistent_bound_property_flagged(self):
		"""A bound property with persistent=false is flagged when persistence is expected."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding(), "persistent": False}})
		results = _lint(view, expected_persistent=True)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertIn("not persistent", results.errors[RULE_NAME][0])

	def test_persistent_without_default_value_flagged(self):
		"""A persistent bound property with no stored value is flagged (missing default)."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding(), "persistent": True}})
		results = _lint(view, expected_persistent=True)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertIn("no stored default value", results.errors[RULE_NAME][0])

	def test_persistent_with_default_value_passes(self):
		"""A persistent bound property with a stored value passes."""
		view = _view(
			custom={"a": 42}, propconfig={"custom.a": {
				"binding": _expr_binding(),
				"persistent": True
			}}
		)
		results = _lint(view, expected_persistent=True)
		self.assertEqual(results.errors, {})

	def test_no_fix_generated_for_expected_true(self):
		"""expected_persistent=true violations have no auto-fix (a default cannot be invented)."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding(), "persistent": False}})
		results, _, _ = _lint_with_fix_context(view, expected_persistent=True)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertEqual(results.fixes, [])


class TestPersistenceFixGeneration(unittest.TestCase):
	"""Auto-fix generation for expected_persistent=false."""

	def test_fix_sets_persistent_false_and_removes_stale_value(self):
		"""The fix flips persistent and deletes the stored designer value."""
		view = _view(
			custom={"a": "stale designer result"},
			propconfig={"custom.a": {
				"binding": _expr_binding(),
				"persistent": True
			}}
		)
		results, json_data, translator = _lint_with_fix_context(view, expected_persistent=False)

		self.assertEqual(len(results.fixes), 1)
		fix = results.fixes[0]
		self.assertTrue(fix.is_safe)
		self.assertEqual(fix.rule_name, RULE_NAME)
		ops = {tuple(op.json_path): op for op in fix.operations}
		self.assertEqual(set(ops), {('propConfig', 'custom.a', 'persistent'), ('custom', 'a')})
		self.assertEqual(ops[('propConfig', 'custom.a', 'persistent')].operation, FixOperationType.SET_VALUE)
		self.assertIs(ops[('propConfig', 'custom.a', 'persistent')].new_value, False)
		self.assertEqual(ops[('custom', 'a')].operation, FixOperationType.DELETE_KEY)

		result = FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(len(result.applied), 1)
		self.assertIs(json_data['propConfig']['custom.a']['persistent'], False)
		self.assertNotIn('a', json_data['custom'])

	def test_fix_without_stored_value_only_touches_propconfig(self):
		"""No value entry means the fix contains just the persistent SET_VALUE operation."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding()}})
		results, _, _ = _lint_with_fix_context(view, expected_persistent=False)

		self.assertEqual(len(results.fixes), 1)
		paths = {tuple(op.json_path) for op in results.fixes[0].operations}
		self.assertEqual(paths, {('propConfig', 'custom.a', 'persistent')})

	def test_component_level_fix_targets_component_propconfig(self):
		"""Component-level fixes resolve the component's JSON path correctly."""
		child = _component(
			"Label", custom={"compProp": 7},
			propconfig={"custom.compProp": {
				"binding": _expr_binding(),
				"persistent": True
			}}
		)
		results, json_data, translator = _lint_with_fix_context(
			_view(children=[child]), expected_persistent=False
		)

		self.assertEqual(len(results.fixes), 1)
		paths = {tuple(op.json_path) for op in results.fixes[0].operations}
		self.assertEqual(
			paths, {
				('root', 'children', 0, 'propConfig', 'custom.compProp', 'persistent'),
				('root', 'children', 0, 'custom', 'compProp'),
			}
		)

		FixEngine(translator).apply_fixes(results.fixes)
		component = json_data['root']['children'][0]
		self.assertIs(component['propConfig']['custom.compProp']['persistent'], False)
		self.assertNotIn('compProp', component['custom'])

	def test_nested_children_deleted_parent_kept_as_empty_dict(self):
		"""When every bound child of an object prop is fixed, the parent survives as {} —
		matching how the designer itself serializes non-persistent nested props."""
		view = _view(
			custom={"dates": {
				"startedDate": "2026-01-01",
				"completedDate": "2026-02-01"
			}}, propconfig={
				"custom.dates.startedDate": {
					"binding": _expr_binding(),
					"persistent": True
				},
				"custom.dates.completedDate": {
					"binding": _expr_binding(),
					"persistent": True
				},
			}
		)
		results, json_data, translator = _lint_with_fix_context(view, expected_persistent=False)

		result = FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(len(result.applied), 2)
		self.assertEqual(json_data['custom'], {'dates': {}})
		self.assertIs(json_data['propConfig']['custom.dates.startedDate']['persistent'], False)
		self.assertIs(json_data['propConfig']['custom.dates.completedDate']['persistent'], False)

	def test_nested_child_deletion_keeps_unbound_siblings(self):
		"""Deleting a bound child's stale value never touches its unbound siblings."""
		view = _view(
			custom={"dates": {
				"startedDate": "2026-01-01",
				"label": "Production Run"
			}}, propconfig={"custom.dates.startedDate": {
				"binding": _expr_binding(),
				"persistent": True
			}}
		)
		results, json_data, translator = _lint_with_fix_context(view, expected_persistent=False)

		FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(json_data['custom'], {'dates': {'label': 'Production Run'}})

	def test_no_fixes_without_fix_context(self):
		"""Detection-only runs produce violations but no fixes."""
		view = _view(propconfig={"custom.a": {"binding": _expr_binding(), "persistent": True}})
		results = _lint(view, expected_persistent=False)
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertEqual(results.fixes, [])

	def test_fixed_view_lints_clean(self):
		"""Applying the fixes and re-linting produces no violations."""
		view = _view(
			custom={
				"a": 1,
				"b": 2
			}, propconfig={
				"custom.a": {
					"binding": _expr_binding(),
					"persistent": True
				},
				"custom.b": {
					"binding": _expr_binding()
				},
			}
		)
		results, json_data, translator = _lint_with_fix_context(view, expected_persistent=False)
		FixEngine(translator).apply_fixes(results.fixes)

		rerun = _lint(json.loads(json.dumps(json_data)), expected_persistent=False)
		self.assertEqual(rerun.errors, {})
		self.assertEqual(rerun.warnings, {})


if __name__ == '__main__':
	unittest.main()
