# pylint: disable=import-error
"""
Tests for UnusedCustomPropertiesRule auto-fix generation.

The rule generates Fix objects that remove unused property definitions:
- the value entry in the owning custom object
- the propConfig entry (plus nested-children entries for object properties)

The rule emits ONLY safe fixes (unused custom properties, view- and component-level).
No fix is ever generated - not even an unsafe one - for:
- view parameters (the view's public interface; callers are invisible to the linter)
- properties with an onChange property-change script (removal deletes its side effects)
- properties whose propConfig entry still contains a binding (detection blind spot)
- definitions that cannot be located unambiguously in the JSON
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


def _load_view(view_dict) -> OrderedDict:
	"""Round-trip through JSON to get an OrderedDict like read_json_file produces."""
	return json.loads(json.dumps(view_dict), object_pairs_hook=OrderedDict)


def _make_engine() -> LintEngine:
	"""Create a LintEngine with an UnusedCustomPropertiesRule."""
	rule = RULES_MAP['UnusedCustomPropertiesRule'].create_from_config({})
	return LintEngine([rule])


def _lint_with_fix_context(view_dict):
	"""Run the rule in fix mode. Returns (results, json_data, translator)."""
	json_data = _load_view(view_dict)
	translator = PathTranslator(json_data)
	flattened = flatten_json(json_data)
	engine = _make_engine()
	results = engine.process(flattened, json_data=json_data, path_translator=translator)
	return results, json_data, translator


def _delete_paths(fix):
	"""Return the set of json_paths (as tuples) deleted by a fix."""
	return {tuple(op.json_path) for op in fix.operations}


class TestUnusedCustomPropertiesFixGeneration(unittest.TestCase):
	"""Fix objects generated for unused properties."""

	def test_safe_fix_for_unused_view_custom_property(self):
		"""Unused view custom property gets a safe fix deleting value + propConfig entries."""
		view = {
			"custom": {
				"unusedProp": "value"
			},
			"propConfig": {
				"custom.unusedProp": {
					"access": "PRIVATE",
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
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(len(results.fixes), 1)
		fix = results.fixes[0]
		self.assertTrue(fix.is_safe)
		self.assertEqual(fix.rule_name, 'UnusedCustomPropertiesRule')
		self.assertIn('unusedProp', fix.description)
		self.assertTrue(all(op.operation == FixOperationType.DELETE_KEY for op in fix.operations))
		self.assertEqual(_delete_paths(fix), {('custom', 'unusedProp'), ('propConfig', 'custom.unusedProp')})

	def test_fix_for_propconfig_only_property(self):
		"""Non-persistent (propConfig-only) property gets a fix that only touches propConfig."""
		view = {
			"propConfig": {
				"custom.ghostProp": {
					"access": "PRIVATE",
					"persistent": False
				}
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(len(results.fixes), 1)
		fix = results.fixes[0]
		self.assertTrue(fix.is_safe)
		self.assertEqual(_delete_paths(fix), {('propConfig', 'custom.ghostProp')})

	def test_no_fix_for_unused_view_parameter(self):
		"""Unused view parameters get NO fix, not even an unsafe one: they are the view's
		public interface, and callers passing them are invisible to the linter. The
		violation still reports so a human can decide."""
		view = {
			"params": {
				"unusedParam": ""
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(len(results.errors.get('UnusedCustomPropertiesRule', [])), 1)
		self.assertEqual(len(results.fixes), 0)

	def test_fix_for_component_custom_property_resolves_child_index(self):
		"""Component custom fix targets the component's real JSON path (with list index)."""
		view = {
			"root": {
				"children": [
					{
						"meta": {
							"name": "FirstLabel"
						},
						"type": "ia.display.label"
					},
					{
						"meta": {
							"name": "TestButton"
						},
						"type": "ia.input.button",
						"custom": {
							"compUnused": 5
						},
						"propConfig": {
							"custom.compUnused": {
								"persistent": True
							}
						},
					},
				],
				"meta": {
					"name": "root"
				},
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(len(results.fixes), 1)
		fix = results.fixes[0]
		self.assertTrue(fix.is_safe)
		self.assertEqual(
			_delete_paths(fix), {
				('root', 'children', 1, 'custom', 'compUnused'),
				('root', 'children', 1, 'propConfig', 'custom.compUnused'),
			}
		)

	def test_fix_deletes_nested_propconfig_children(self):
		"""Unused object property removal includes propConfig entries for its children."""
		view = {
			"custom": {
				"unusedObj": {
					"child": 5
				}
			},
			"propConfig": {
				"custom.unusedObj": {
					"persistent": True
				},
				"custom.unusedObj.child": {
					"persistent": False
				},
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(len(results.fixes), 1)
		self.assertEqual(
			_delete_paths(results.fixes[0]), {
				('custom', 'unusedObj'),
				('propConfig', 'custom.unusedObj'),
				('propConfig', 'custom.unusedObj.child'),
			}
		)

	def test_prefix_named_sibling_property_is_untouched(self):
		"""Deleting 'custom.prop' must not touch the distinct sibling 'custom.propLonger'."""
		view = {
			"custom": {
				"prop": 1,
				"propLonger": 2
			},
			"propConfig": {
				"custom.prop": {
					"persistent": True
				},
				"custom.propLonger": {
					"persistent": True
				},
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(len(results.fixes), 2)
		fix_by_name = {fix.description.split("'")[1]: fix for fix in results.fixes}
		self.assertEqual(
			_delete_paths(fix_by_name['prop']),
			{('custom', 'prop'), ('propConfig', 'custom.prop')},
		)
		self.assertEqual(
			_delete_paths(fix_by_name['propLonger']),
			{('custom', 'propLonger'), ('propConfig', 'custom.propLonger')},
		)

	def test_no_fix_when_property_has_onchange_script(self):
		"""Property with an onChange property-change script gets NO fix — removal would
		delete the script and whatever side effects it carried."""
		view = {
			"custom": {
				"watched": 1
			},
			"propConfig": {
				"custom.watched": {
					"persistent": True,
					"onChange": {
						"enabled": True,
						"script": "\tsystem.perspective.print('hi')"
					},
				}
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(len(results.errors.get('UnusedCustomPropertiesRule', [])), 1)
		self.assertEqual(len(results.fixes), 0)

	def test_no_fix_when_propconfig_entry_still_has_binding(self):
		"""Defense in depth: a flagged property whose propConfig entry contains a binding
		gets NO fix — the flag means detection missed the binding, and deleting would
		destroy live configuration. (An empty binding dict vanishes in flattening, so it
		is never credited: the one shape that reaches the guard today.)"""
		view = {
			"custom": {
				"weird": 1
			},
			"propConfig": {
				"custom.weird": {
					"persistent": True,
					"binding": {}
				}
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(len(results.errors.get('UnusedCustomPropertiesRule', [])), 1)
		self.assertEqual(len(results.fixes), 0)

	def test_bound_properties_get_no_violations_and_no_fixes(self):
		"""Properties bound by types without model nodes (query, http, tag-history,
		expr-struct) are credited as used — no violation, nothing to delete."""
		view = {
			"propConfig": {
				"custom.queryBound": {
					"persistent": False,
					"binding": {
						"type": "query",
						"config": {
							"queryPath": "GetStuff"
						}
					}
				},
				"custom.httpBound": {
					"persistent": False,
					"binding": {
						"type": "http",
						"config": {
							"url": "http://example/api"
						}
					}
				},
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(results.errors.get('UnusedCustomPropertiesRule', []), [])
		self.assertEqual(len(results.fixes), 0)

	def test_props_subtree_with_literal_custom_key_never_fixed(self):
		"""A normal component property subtree containing a literal 'custom' key must
		never produce a deletion — it is not a component custom-property container."""
		view = {
			"root": {
				"children": [{
					"meta": {
						"name": "Chart"
					},
					"type": "ia.chart.xy",
					"props": {
						"seriesStyle": {
							"custom": {
								"strokeWidth": 2
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				},
			},
		}
		results, json_data, translator = _lint_with_fix_context(view)

		# The (pre-existing, over-broad) definition regex may still flag it, but the
		# fixer must not resolve it to a component and must not emit any operations.
		self.assertEqual(len(results.fixes), 0)

		FixEngine(translator).apply_fixes(results.fixes, safe_only=False)
		self.assertEqual(
			json_data['root']['children'][0]['props']['seriesStyle']['custom']['strokeWidth'], 2,
			"Normal component props must never be touched by this rule's fixes."
		)

	def test_embedded_view_pass_on_params_never_deleted(self):
		"""Params an embedded view passes to its child (static props.params.X or bound
		propConfig['props.params.X']) are not definitions of this view: no violation,
		no fix. Only the view's own unused param gets a (param-unsafe) fix."""
		view = {
			"params": {
				"reallyUnused": ""
			},
			"root": {
				"children": [{
					"meta": {
						"name": "EmbeddedView"
					},
					"type": "ia.display.view",
					"propConfig": {
						"props.params.color": {
							"binding": {
								"type": "expr",
								"config": {
									"expression": "\"red\""
								}
							}
						}
					},
					"props": {
						"params": {
							"unusedRef": False
						},
						"path": "TestCases/Pipes"
					}
				}],
				"meta": {
					"name": "root"
				},
			},
		}
		results, json_data, translator = _lint_with_fix_context(view)

		# The view's own unused param is flagged but gets no fix (params are never
		# auto-deleted); the pass-on params produce neither violations nor fixes.
		self.assertEqual(len(results.errors.get('UnusedCustomPropertiesRule', [])), 1)
		self.assertEqual(len(results.fixes), 0)

		FixEngine(translator).apply_fixes(results.fixes, safe_only=False)
		embedded = json_data['root']['children'][0]
		self.assertEqual(embedded['props']['params'], {'unusedRef': False})
		self.assertIn('props.params.color', embedded['propConfig'])
		self.assertIn('reallyUnused', json_data['params'])

	def test_no_fixes_without_fix_context(self):
		"""No fixes are generated when fix context is not provided."""
		view = {
			"custom": {
				"unusedProp": "value"
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		json_data = _load_view(view)
		flattened = flatten_json(json_data)
		engine = _make_engine()

		results = engine.process(flattened)

		self.assertGreater(len(results.errors.get('UnusedCustomPropertiesRule', [])), 0)
		self.assertEqual(len(results.fixes), 0)

	def test_no_fixes_for_used_properties(self):
		"""Used properties produce neither violations nor fixes."""
		view = {
			"custom": {
				"usedProp": "value"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "Lbl"
					},
					"type": "ia.display.label",
					"props": {
						"text": {
							"binding": {
								"type": "expression",
								"config": {
									"expression": "{view.custom.usedProp}"
								},
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				},
			},
		}
		results, _, _ = _lint_with_fix_context(view)

		self.assertEqual(results.errors.get('UnusedCustomPropertiesRule', []), [])
		self.assertEqual(len(results.fixes), 0)


class TestUnusedCustomPropertiesFixApplication(unittest.TestCase):
	"""End-to-end: applying generated fixes removes the properties and re-lints clean."""

	def test_apply_fixes_and_relint_clean(self):
		"""Applying all fixes removes every unused definition; re-lint reports nothing."""
		view = {
			"custom": {
				"unusedProp": "v",
				"usedProp": 1
			},
			"params": {
				"unusedParam": ""
			},
			"propConfig": {
				"custom.unusedProp": {
					"access": "PRIVATE",
					"persistent": True
				},
				"custom.ghostProp": {
					"access": "PRIVATE",
					"persistent": False
				},
				"params.unusedParam": {
					"paramDirection": "input"
				},
			},
			"root": {
				"children": [{
					"meta": {
						"name": "Btn"
					},
					"type": "ia.input.button",
					"custom": {
						"compUnused": 5
					},
					"propConfig": {
						"custom.compUnused": {
							"persistent": True
						}
					},
					"props": {
						"text": {
							"binding": {
								"type": "expression",
								"config": {
									"expression": "{view.custom.usedProp}"
								},
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				},
			},
		}
		results, json_data, translator = _lint_with_fix_context(view)
		# 3 custom-property fixes; the unused param gets no fix by policy.
		self.assertEqual(len(results.fixes), 3)
		self.assertTrue(all(fix.is_safe for fix in results.fixes))

		fix_engine = FixEngine(translator)
		fix_result = fix_engine.apply_fixes(results.fixes, safe_only=True)

		self.assertEqual(fix_result.applied_count, 3)
		self.assertEqual(fix_result.skipped_count, 0)
		self.assertEqual(len(fix_result.conflicts), 0)

		self.assertNotIn('unusedProp', json_data['custom'])
		self.assertIn('usedProp', json_data['custom'])
		self.assertIn('unusedParam', json_data['params'])
		self.assertEqual(list(json_data['propConfig']), ['params.unusedParam'])
		self.assertNotIn('compUnused', json_data['root']['children'][0]['custom'])

		# The param violation remains for a human to resolve; everything else is clean.
		relint = _make_engine().process(flatten_json(json_data))
		remaining = relint.errors.get('UnusedCustomPropertiesRule', [])
		self.assertEqual(len(remaining), 1)
		self.assertIn('unusedParam', remaining[0])

	def test_all_generated_fixes_are_safe(self):
		"""The rule must never emit an unsafe fix — params and onChange props get none."""
		view = {
			"custom": {
				"unusedProp": "v"
			},
			"params": {
				"unusedParam": ""
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			},
		}
		results, json_data, translator = _lint_with_fix_context(view)

		self.assertEqual(len(results.fixes), 1)
		self.assertTrue(results.fixes[0].is_safe)

		fix_result = FixEngine(translator).apply_fixes(results.fixes, safe_only=False)

		self.assertEqual(fix_result.applied_count, 1)
		self.assertNotIn('unusedProp', json_data['custom'])
		self.assertIn('unusedParam', json_data['params'], "Params must survive even --fix-unsafe.")


if __name__ == '__main__':
	unittest.main()
