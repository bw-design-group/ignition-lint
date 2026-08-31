# pylint: disable=import-error
"""
Tests for PropertyAccessRule.

The rule validates the `access` mode of USER-CONFIGURED custom properties only
(view-level `custom.*` and component-level `<component>.custom.*`). It is inert
unless `expected_access` is configured.

The auto-fix is deliberately tightly scoped: it may only ever touch `custom.*`
propConfig entries. Setting access on anything else - especially component
`props.*` like a table's `props.data` - would break component rendering, so a
large portion of this file asserts what the fix must NEVER touch.
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

RULE_NAME = 'PropertyAccessRule'


def _load_view(view_dict) -> OrderedDict:
	"""Round-trip through JSON to get an OrderedDict like read_json_file produces."""
	return json.loads(json.dumps(view_dict), object_pairs_hook=OrderedDict)


def _make_engine(**kwargs) -> LintEngine:
	"""Create a LintEngine with a PropertyAccessRule configured via kwargs."""
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


def _all_op_paths(fixes):
	"""Return every FixOperation json_path (as a tuple) across a list of fixes."""
	return {tuple(op.json_path) for fix in fixes for op in fix.operations}


def _diff_paths(original, fixed, path=()):
	"""Return the set of JSON paths (as tuples) where two structures differ."""
	changed = set()
	if isinstance(original, dict) and isinstance(fixed, dict):
		for key in set(original) | set(fixed):
			if key not in original or key not in fixed:
				changed.add(path + (key,))
			else:
				changed |= _diff_paths(original[key], fixed[key], path + (key,))
	elif isinstance(original, list) and isinstance(fixed, list):
		if len(original) != len(fixed):
			changed.add(path)
		else:
			for index, (item_a, item_b) in enumerate(zip(original, fixed)):
				changed |= _diff_paths(item_a, item_b, path + (index,))
	elif original != fixed:
		changed.add(path)
	return changed


class TestAccessDetection(unittest.TestCase):
	"""Detection behavior."""

	def test_inert_by_default(self):
		"""Without expected_access, the rule never flags anything."""
		view = _view(custom={"a": 1})
		results = _lint(view)
		self.assertEqual(results.errors, {})
		self.assertEqual(results.warnings, {})

	def test_undeclared_access_is_public_and_flagged(self):
		"""A custom prop with no propConfig entry defaults to PUBLIC and is flagged."""
		view = _view(custom={"a": 1})
		results = _lint(view, expected_access="PRIVATE")
		errors = results.errors.get(RULE_NAME, [])
		self.assertEqual(len(errors), 1)
		self.assertIn("custom.a", errors[0])
		self.assertIn("PUBLIC", errors[0])

	def test_protected_flagged_when_private_expected(self):
		"""PROTECTED does not satisfy an expected PRIVATE."""
		view = _view(custom={"a": 1}, propconfig={"custom.a": {"access": "PROTECTED"}})
		results = _lint(view, expected_access="PRIVATE")
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)

	def test_private_passes_when_private_expected(self):
		"""PRIVATE satisfies an expected PRIVATE."""
		view = _view(custom={"a": 1}, propconfig={"custom.a": {"access": "PRIVATE"}})
		results = _lint(view, expected_access="PRIVATE")
		self.assertEqual(results.errors, {})

	def test_private_flagged_when_public_expected(self):
		"""expected_access=PUBLIC flags declared non-PUBLIC modes, not undeclared props."""
		view = _view(
			custom={
				"declared": 1,
				"undeclared": 2
			}, propconfig={"custom.declared": {
				"access": "PRIVATE"
			}}
		)
		results = _lint(view, expected_access="PUBLIC")
		errors = results.errors.get(RULE_NAME, [])
		self.assertEqual(len(errors), 1)
		self.assertIn("custom.declared", errors[0])

	def test_params_and_props_never_flagged(self):
		"""params and component props are outside the rule's scope entirely."""
		child = _component(
			"Table", props={"data": []},
			propconfig={"props.data": {
				"binding": {
					"config": {},
					"type": "expr"
				}
			}}
		)
		view = _view(
			params={"pageId": "x"}, propconfig={"params.pageId": {
				"paramDirection": "input"
			}}, children=[child]
		)
		results = _lint(view, expected_access="PRIVATE")
		self.assertEqual(results.errors, {})

	def test_component_custom_property_flagged(self):
		"""Component-level custom props are checked, with the full path in the message."""
		child = _component("Chart", custom={"theme": "dark"})
		results = _lint(_view(children=[child]), expected_access="PRIVATE")
		errors = results.errors.get(RULE_NAME, [])
		self.assertEqual(len(errors), 1)
		self.assertIn("root.root.children[0].Chart.custom.theme", errors[0])

	def test_propconfig_only_custom_property_flagged(self):
		"""A custom prop that exists only as a propConfig entry is still evaluated."""
		view = _view(propconfig={"custom.transient": {"persistent": False}})
		results = _lint(view, expected_access="PRIVATE")
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)

	def test_exempt_props_bare_and_qualified(self):
		"""exempt_props matches bare keys at any level and fully-qualified paths."""
		child = _component("Chart", custom={"theme": "dark", "other": 1})
		view = _view(custom={"theme": "light"}, children=[child])
		results = _lint(
			view, expected_access="PRIVATE",
			exempt_props=["custom.theme", "root.root.children[0].Chart.custom.other"]
		)
		self.assertEqual(results.errors, {})

	def test_exempt_props_by_bare_name(self):
		"""A bare property name exempts that prop at the view and on every component."""
		child = _component("Chart", custom={"data": [], "theme": "dark"})
		view = _view(custom={"data": []}, children=[child])
		results = _lint(view, expected_access="PRIVATE", exempt_props=["data"])
		errors = results.errors.get(RULE_NAME, [])
		self.assertEqual(len(errors), 1)
		self.assertIn("Chart.custom.theme", errors[0])

	def test_exempt_props_wildcards(self):
		"""'*' and '?' wildcards work in names, prop keys, and full paths."""
		child = _component("Chart", custom={"kpiHourly": 1, "kpiDaily": 2, "other": 3})
		view = _view(custom={"kpiTotals": 0}, children=[child])
		# Name wildcard exempts every kpi* prop at every level; path wildcard with a
		# literal-bracket index exempts the component's 'other'.
		results = _lint(
			view, expected_access="PRIVATE",
			exempt_props=["kpi*", "root.root.children[?].Chart.custom.other"]
		)
		self.assertEqual(results.errors, {})

	def test_exempt_props_name_does_not_match_substring(self):
		"""Patterns are anchored: 'data' does not exempt 'kpiData' or 'dataSet'."""
		view = _view(custom={"kpiData": 1, "dataSet": 2})
		results = _lint(view, expected_access="PRIVATE", exempt_props=["data"])
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 2)

	def test_component_named_custom_not_misread(self):
		"""A component literally named 'custom' is not misread as a custom-prop scope."""
		child = _component("custom", props={"text": "hello"})
		results = _lint(_view(children=[child]), expected_access="PRIVATE")
		self.assertEqual(results.errors, {})

	def test_lowercase_expected_access_accepted(self):
		"""expected_access is case-insensitive."""
		view = _view(custom={"a": 1})
		results = _lint(view, expected_access="private")
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)

	def test_invalid_expected_access_raises(self):
		"""Unknown access modes raise ValueError at configuration time."""
		with self.assertRaises(ValueError):
			RULES_MAP[RULE_NAME].create_from_config({"expected_access": "HIDDEN"})

	def test_severity_warning_downgrade(self):
		"""severity=warning moves violations from errors to warnings."""
		view = _view(custom={"a": 1})
		results = _lint(view, expected_access="PRIVATE", severity="warning")
		self.assertEqual(results.errors, {})
		self.assertEqual(len(results.warnings.get(RULE_NAME, [])), 1)


class TestAccessFixGeneration(unittest.TestCase):
	"""Positive auto-fix cases."""

	def test_fix_sets_access_on_existing_entry(self):
		"""An existing propConfig entry gets an access SET_VALUE operation."""
		view = _view(custom={"a": 1}, propconfig={"custom.a": {"persistent": False}})
		results, json_data, translator = _lint_with_fix_context(view, expected_access="PRIVATE")

		self.assertEqual(len(results.fixes), 1)
		fix = results.fixes[0]
		self.assertTrue(fix.is_safe)
		self.assertEqual(_all_op_paths([fix]), {('propConfig', 'custom.a', 'access')})
		self.assertEqual(fix.operations[0].operation, FixOperationType.SET_VALUE)
		self.assertEqual(fix.operations[0].new_value, 'PRIVATE')

		FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(json_data['propConfig']['custom.a']['access'], 'PRIVATE')
		self.assertIs(json_data['propConfig']['custom.a']['persistent'], False)

	def test_fix_creates_entry_for_plain_custom_prop(self):
		"""A custom prop with no propConfig entry gets one created."""
		view = _view(custom={"a": 1}, propconfig={"custom.other": {"persistent": False}})
		results, json_data, translator = _lint_with_fix_context(view, expected_access="PRIVATE")

		paths = _all_op_paths([f for f in results.fixes if 'custom.a' in f.description])
		self.assertEqual(paths, {('propConfig', 'custom.a')})

		FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(json_data['propConfig']['custom.a'], {'access': 'PRIVATE'})

	def test_fix_creates_propconfig_when_owner_has_none(self):
		"""An owner with no propConfig dict at all gets one created, fixes applied in order."""
		child = _component("Chart", custom={"a": 1, "b": 2})
		results, json_data, translator = _lint_with_fix_context(
			_view(children=[child]), expected_access="PRIVATE"
		)

		self.assertEqual(len(results.fixes), 2)
		result = FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(len(result.applied), 2)
		self.assertEqual(
			json_data['root']['children'][0]['propConfig'], {
				'custom.a': {
					'access': 'PRIVATE'
				},
				'custom.b': {
					'access': 'PRIVATE'
				}
			}
		)

	def test_public_expected_removes_access_key(self):
		"""expected_access=PUBLIC deletes the access declaration, keeping other config."""
		view = _view(custom={"a": 1}, propconfig={"custom.a": {"access": "PRIVATE", "persistent": False}})
		results, json_data, translator = _lint_with_fix_context(view, expected_access="PUBLIC")

		self.assertEqual(_all_op_paths(results.fixes), {('propConfig', 'custom.a', 'access')})
		FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(json_data['propConfig']['custom.a'], {'persistent': False})

	def test_public_expected_removes_access_only_entry(self):
		"""An access-only propConfig entry is removed entirely (PUBLIC is the default)."""
		view = _view(custom={"a": 1}, propconfig={"custom.a": {"access": "PRIVATE"}})
		results, json_data, translator = _lint_with_fix_context(view, expected_access="PUBLIC")

		self.assertEqual(_all_op_paths(results.fixes), {('propConfig', 'custom.a')})
		FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(json_data['propConfig'], {})

	def test_no_fixes_without_fix_context(self):
		"""Detection-only runs produce violations but no fixes."""
		results = _lint(_view(custom={"a": 1}), expected_access="PRIVATE")
		self.assertEqual(len(results.errors.get(RULE_NAME, [])), 1)
		self.assertEqual(results.fixes, [])

	def test_fixed_view_lints_clean(self):
		"""Applying the fixes and re-linting produces no violations."""
		child = _component("Chart", custom={"theme": "dark"})
		view = _view(custom={"a": 1}, children=[child])
		results, json_data, translator = _lint_with_fix_context(view, expected_access="PRIVATE")
		FixEngine(translator).apply_fixes(results.fixes)

		rerun = _lint(json.loads(json.dumps(json_data)), expected_access="PRIVATE")
		self.assertEqual(rerun.errors, {})


class TestAccessFixScoping(unittest.TestCase):
	"""
	The fix must NEVER touch anything but custom.* propConfig entries.

	These tests build views full of near-miss structures and assert on the exact
	set of operation paths and on the full post-fix JSON diff.
	"""

	@staticmethod
	def _kitchen_sink_view():
		"""A view mixing every structure the fix must not touch with real violations."""
		table = _component(
			"DataTable", props={"data": [{
				"col": 1
			}]}, custom={"stagingData": []}, propconfig={
				"props.data": {
					"binding": {
						"config": {
							"path": "view.custom.stagingData"
						},
						"type": "property"
					},
					"persistent": False
				},
				"props.params.configuring": {
					"persistent": False
				},
				"custom.stagingData": {
					"persistent": False
				},
			}
		)
		custom_named_component = _component("custom", props={"text": "hello"})
		deep_child = _component("DeepLabel", custom={"deepProp": 1})
		container = {
			"meta": {
				"name": "Container"
			},
			"type": "ia.container.flex",
			"children": [deep_child],
		}
		return _view(
			custom={"viewProp": 1},
			params={"pageId": "x"},
			propconfig={
				"params.pageId": {
					"paramDirection": "input",
					"persistent": True
				},
				"custom.viewProp": {
					"persistent": False
				},
			},
			children=[table, custom_named_component, container],
		)

	def test_every_operation_targets_custom_propconfig(self):
		"""Every generated operation path lands on a custom.* propConfig entry."""
		results, _, _ = _lint_with_fix_context(self._kitchen_sink_view(), expected_access="PRIVATE")

		self.assertGreater(len(results.fixes), 0)
		for fix in results.fixes:
			for operation in fix.operations:
				path = tuple(operation.json_path)
				self.assertIn('propConfig', path, f"operation outside propConfig: {path}")
				remainder = path[path.index('propConfig') + 1:]
				if remainder:
					self.assertTrue(
						str(remainder[0]).startswith('custom.'),
						f"operation not scoped to a custom.* entry: {path}"
					)
				else:
					# Creating a propConfig dict is allowed only when every key
					# it introduces is a custom.* entry.
					self.assertIsInstance(operation.new_value, dict)
					self.assertTrue(operation.new_value)
					for key in operation.new_value:
						self.assertTrue(
							key.startswith('custom.'),
							f"created propConfig introduces non-custom key '{key}': {path}"
						)

	def test_end_to_end_fix_only_changes_custom_propconfig_entries(self):
		"""After applying every fix, the only JSON differences are custom.* propConfig entries."""
		view = self._kitchen_sink_view()
		original = json.loads(json.dumps(view))
		results, json_data, translator = _lint_with_fix_context(view, expected_access="PRIVATE")

		result = FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(result.skipped, [])
		self.assertGreater(len(result.applied), 0)

		fixed = json.loads(json.dumps(json_data))
		for path in _diff_paths(original, fixed):
			self.assertIn('propConfig', path, f"unexpected change outside propConfig: {path}")
			remainder = path[path.index('propConfig') + 1:]
			if remainder:
				self.assertTrue(
					str(remainder[0]).startswith('custom.'),
					f"unexpected change outside a custom.* entry: {path}"
				)
			else:
				# A newly created propConfig dict may only contain custom.* entries.
				created = fixed
				for segment in path:
					created = created[segment]
				self.assertTrue(
					all(key.startswith('custom.') for key in created),
					f"created {created} at {path}"
				)

		# The structures that must survive untouched, verified explicitly.
		self.assertEqual(fixed['params'], original['params'])
		self.assertEqual(fixed['custom'], original['custom'])
		table = fixed['root']['children'][0]
		self.assertEqual(table['props'], original['root']['children'][0]['props'])
		self.assertEqual(
			table['propConfig']['props.data'], original['root']['children'][0]['propConfig']['props.data']
		)
		self.assertEqual(
			table['propConfig']['props.params.configuring'],
			original['root']['children'][0]['propConfig']['props.params.configuring']
		)
		self.assertEqual(fixed['root']['children'][1], original['root']['children'][1])
		self.assertEqual(fixed['propConfig']['params.pageId'], original['propConfig']['params.pageId'])

	def test_no_fix_for_already_compliant_entries(self):
		"""Entries already at the expected access produce no violation and no fix."""
		view = _view(custom={"a": 1}, propconfig={"custom.a": {"access": "PRIVATE"}})
		results, _, _ = _lint_with_fix_context(view, expected_access="PRIVATE")
		self.assertEqual(results.errors, {})
		self.assertEqual(results.fixes, [])

	def test_no_fix_for_exempt_props(self):
		"""Exempted props produce neither violations nor fixes."""
		view = _view(custom={"a": 1})
		results, _, _ = _lint_with_fix_context(view, expected_access="PRIVATE", exempt_props=["custom.a"])
		self.assertEqual(results.errors, {})
		self.assertEqual(results.fixes, [])

	def test_public_expected_never_touches_params_or_props_declarations(self):
		"""expected_access=PUBLIC only removes access from custom.* entries."""
		child = _component("Table", props={"data": []}, propconfig={"props.data": {"access": "PRIVATE"}})
		view = _view(
			custom={"a": 1},
			propconfig={"custom.a": {
				"access": "PRIVATE"
			}},
			children=[child],
		)
		results, json_data, translator = _lint_with_fix_context(view, expected_access="PUBLIC")

		self.assertEqual(_all_op_paths(results.fixes), {('propConfig', 'custom.a')})
		FixEngine(translator).apply_fixes(results.fixes)
		self.assertEqual(json_data['root']['children'][0]['propConfig']['props.data'], {'access': 'PRIVATE'})


if __name__ == '__main__':
	unittest.main()
