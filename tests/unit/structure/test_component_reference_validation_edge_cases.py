# pylint: disable=import-error,no-name-in-module
"""
Edge-case unit tests for ComponentReferenceValidationRule and its alignment with
BadComponentReferenceRule.

Kept separate from test_component_reference_validation.py so neither file grows
past the module/line limits. These focus on the single-dot './' (current
container) idiom used by the Pipes test case, expression-struct bindings, and the
requirement that both reference rules inspect the same nodes.
"""

import unittest
import json
from typing import Dict, Any

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config
from ignition_lint.rules.structure.bad_component_reference import BadComponentReferenceRule
from ignition_lint.rules.structure.component_reference_validation import ComponentReferenceValidationRule
from ignition_lint.model.node_types import COMPONENT_REFERENCE_NODES, NodeType


def _wrap_view(root: Dict[str, Any]) -> str:
	"""Wrap a root component dict in the surrounding view envelope."""
	view = {"custom": {}, "params": {}, "propConfig": {}, "props": {}, "root": root}
	return json.dumps(view, indent=2)


def _container_with_binding(binding_config: Dict, binding_type: str, prop: str = "props.style") -> str:
	"""
	Build a view where Container1 owns a binding and has a child InnerButton.

	The binding lives on Container1, so a single-dot './InnerButton' reference
	(current container, drill down into its own child) resolves correctly.
	"""
	root = {
		"children": [{
			"meta": {
				"name": "Container1"
			},
			"type": "ia.container.flex",
			"propConfig": {
				prop: {
					"binding": {
						"config": binding_config,
						"type": binding_type
					}
				}
			},
			"children": [{
				"meta": {
					"name": "InnerButton"
				},
				"type": "ia.input.button",
				"props": {
					"text": "Inner"
				}
			}]
		}],
		"meta": {
			"name": "root"
		},
		"type": "ia.container.coord"
	}
	return _wrap_view(root)


class TestSingleDotReferences(BaseRuleTest):
	"""Single-dot './' references (current container) in every binding form."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config("ComponentReferenceValidationRule")

	def _errors(self):
		return self.get_errors_for_rule("ComponentReferenceValidationRule")

	def test_valid_current_container_reference_in_expression(self):
		"""Single-dot './Child' expression that resolves to an existing child should pass."""
		view = _container_with_binding({"expression": "{./InnerButton.props.text}"}, "expr")
		self.run_lint_on_mock_view(view, self.rule_config)
		self.assertEqual(len(self._errors()), 0, f"Valid './' expression should pass. Errors: {self._errors()}")

	def test_invalid_current_container_reference_in_expression(self):
		"""Single-dot './Child' expression to a non-existent child must be detected."""
		view = _container_with_binding({"expression": "{./MissingButton.props.text}"}, "expr")
		self.run_lint_on_mock_view(view, self.rule_config)

		errors = self._errors()
		self.assertEqual(len(errors), 1, f"Broken './' expression should be caught. Errors: {errors}")
		self.assertIn("MissingButton", errors[0])

	def test_valid_current_container_reference_in_property_binding(self):
		"""Single-dot './Child' property binding that resolves should pass."""
		view = _container_with_binding({"path": "./InnerButton.props.text"}, "property")
		self.run_lint_on_mock_view(view, self.rule_config)
		self.assertEqual(
			len(self._errors()), 0, f"Valid './' property binding should pass. Errors: {self._errors()}"
		)

	def test_invalid_current_container_reference_in_property_binding(self):
		"""Single-dot './Child' property binding to a non-existent child must be detected.

		This is the exact gap behind the Pipes test case: a broken reference written as a
		single-dot property binding path previously sailed through undetected.
		"""
		view = _container_with_binding({"path": "./MissingButton.props.text"}, "property")
		self.run_lint_on_mock_view(view, self.rule_config)

		errors = self._errors()
		self.assertEqual(len(errors), 1, f"Broken './' property binding should be caught. Errors: {errors}")
		self.assertIn("MissingButton", errors[0])
		self.assertIn("property binding", errors[0].lower())

	def test_valid_reference_in_expression_struct_binding(self):
		"""Expression-struct binding referencing an existing child should pass."""
		view = _container_with_binding({
			"struct": {
				"label": "{./InnerButton.props.text}"
			},
			"waitOnAll": True
		}, "expr-struct", prop="props.data")
		self.run_lint_on_mock_view(view, self.rule_config)
		self.assertEqual(
			len(self._errors()), 0, f"Valid expr-struct reference should pass. Errors: {self._errors()}"
		)

	def test_invalid_reference_in_expression_struct_binding(self):
		"""Expression-struct binding referencing a non-existent component must be detected."""
		view = _container_with_binding({
			"struct": {
				"label": "{./MissingButton.props.text}"
			},
			"waitOnAll": True
		}, "expr-struct", prop="props.data")
		self.run_lint_on_mock_view(view, self.rule_config)

		errors = self._errors()
		self.assertEqual(len(errors), 1, f"Broken expr-struct reference should be caught. Errors: {errors}")
		self.assertIn("MissingButton", errors[0])


class TestReferenceRulesNodeAlignment(unittest.TestCase):
	"""
	The two complementary reference rules must inspect the SAME nodes.

	BadComponentReferenceRule says "you are doing a bad job" (brittle pattern);
	ComponentReferenceValidationRule says "something is broken" (does not resolve).
	If they disagree on which nodes to inspect, one rule has a blind spot the other
	silently covers - exactly the bug that let a './' property binding through.
	"""

	def test_both_rules_cover_same_reference_nodes(self):
		"""Both rules target the shared reference-bearing node set."""
		bad_rule = BadComponentReferenceRule()
		validation_rule = ComponentReferenceValidationRule()

		# BadComponentReferenceRule targets exactly the reference-bearing nodes.
		self.assertEqual(bad_rule.target_node_types, COMPONENT_REFERENCE_NODES)

		# ComponentReferenceValidationRule needs COMPONENT too (to build its index),
		# but otherwise covers the identical set.
		self.assertEqual(validation_rule.target_node_types - {NodeType.COMPONENT}, COMPONENT_REFERENCE_NODES)


class TestComponentReferenceValidationEdgeCases(BaseRuleTest):
	"""
	Extra edge cases ensuring the rule confirms broken references in every form.

	These complement the Pipes integration test with isolated, deterministic
	scenarios that the real view does not (yet) exercise.
	"""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config("ComponentReferenceValidationRule")

	def _container_view(self, *, propconfig=None, events=None, extra_children=None) -> str:
		"""Build a view with Container1 (owning the binding/script) and a child InnerButton."""
		container: Dict[str, Any] = {
			"meta": {
				"name": "Container1"
			},
			"type": "ia.container.flex",
			"children": [{
				"meta": {
					"name": "InnerButton"
				},
				"type": "ia.input.button",
				"props": {
					"text": "Inner"
				}
			}]
		}
		if extra_children:
			container["children"].extend(extra_children)
		if propconfig:
			container["propConfig"] = propconfig
		if events:
			container["events"] = events
		root = {"meta": {"name": "root"}, "type": "ia.container.coord", "children": [container]}
		return _wrap_view(root)

	def _expr_binding(self, expression: str, prop: str = "props.style") -> Dict:
		return {prop: {"binding": {"config": {"expression": expression}, "type": "expr"}}}

	def _onchange(self, script: str, prop: str = "custom.total") -> Dict:
		return {prop: {"onChange": {"script": script}}}

	def _event_script(self, script: str) -> Dict:
		return {
			"component": {
				"onActionPerformed": {
					"config": {
						"script": script
					},
					"scope": "G",
					"type": "script"
				}
			}
		}

	def _errors(self):
		return self.get_errors_for_rule("ComponentReferenceValidationRule")

	def test_multiple_references_in_one_expression_flags_only_broken(self):
		"""An expression with several './' refs flags only the unresolved one."""
		view = self._container_view(
			propconfig=self._expr_binding("{./InnerButton.props.text} + {./Missing.props.text}")
		)
		self.run_lint_on_mock_view(view, self.rule_config)

		errors = self._errors()
		self.assertEqual(len(errors), 1, f"Only the broken reference should be flagged. Errors: {errors}")
		self.assertIn("Missing", errors[0])

	def test_expression_struct_reports_only_broken_member(self):
		"""An expr-struct with one valid and one broken member flags only the broken member."""
		binding = {
			"props.data": {
				"binding": {
					"config": {
						"struct": {
							"good": "{./InnerButton.props.text}",
							"bad": "{./Missing.props.text}"
						},
						"waitOnAll": True
					},
					"type": "expr-struct"
				}
			}
		}
		view = self._container_view(propconfig=binding)
		self.run_lint_on_mock_view(view, self.rule_config)

		errors = self._errors()
		self.assertEqual(len(errors), 1, f"Only the broken struct member should be flagged. Errors: {errors}")
		self.assertIn("Missing", errors[0])

	def test_standalone_getchild_to_own_child_resolves(self):
		"""self.getChild('InnerButton') on the owning container resolves - no error."""
		view = self._container_view(events=self._event_script("value = self.getChild('InnerButton')"))
		self.run_lint_on_mock_view(view, self.rule_config)

		self.assertEqual(len(self._errors()), 0, f"Valid getChild should pass. Errors: {self._errors()}")

	def test_standalone_getchild_to_missing_child_detected(self):
		"""self.getChild('Missing') is reported as a broken child reference."""
		view = self._container_view(events=self._event_script("value = self.getChild('Missing')"))
		self.run_lint_on_mock_view(view, self.rule_config)

		errors = self._errors()
		self.assertEqual(len(errors), 1, f"Broken getChild should be caught. Errors: {errors}")
		self.assertIn("Missing", errors[0])
		self.assertIn("child", errors[0].lower())

	def test_nested_single_dot_path_resolves(self):
		"""Single-dot nested path './SubContainer/Deep' resolves through the tree."""
		sub = {
			"meta": {
				"name": "SubContainer"
			},
			"type": "ia.container.flex",
			"children": [{
				"meta": {
					"name": "Deep"
				},
				"type": "ia.input.button",
				"props": {
					"text": "d"
				}
			}]
		}
		view = self._container_view(
			propconfig=self._expr_binding("{./SubContainer/Deep.props.text}"), extra_children=[sub]
		)
		self.run_lint_on_mock_view(view, self.rule_config)

		self.assertEqual(
			len(self._errors()), 0, f"Valid nested './' path should pass. Errors: {self._errors()}"
		)

	def test_nested_single_dot_path_with_missing_leaf_detected(self):
		"""Single-dot nested path './SubContainer/Missing' is reported when the leaf is absent."""
		sub = {
			"meta": {
				"name": "SubContainer"
			},
			"type": "ia.container.flex",
			"children": [{
				"meta": {
					"name": "Deep"
				},
				"type": "ia.input.button",
				"props": {
					"text": "d"
				}
			}]
		}
		view = self._container_view(
			propconfig=self._expr_binding("{./SubContainer/Missing.props.text}"), extra_children=[sub]
		)
		self.run_lint_on_mock_view(view, self.rule_config)

		errors = self._errors()
		self.assertEqual(len(errors), 1, f"Broken nested './' leaf should be caught. Errors: {errors}")
		self.assertIn("SubContainer/Missing", errors[0])

	def test_property_change_script_broken_reference_detected(self):
		"""A getChild('Missing') in a property-change (onChange) script is validated and flagged."""
		view = self._container_view(propconfig=self._onchange("value = self.getChild('Missing')"))
		self.run_lint_on_mock_view(view, self.rule_config)

		errors = self._errors()
		self.assertEqual(len(errors), 1, f"Broken onChange reference should be caught. Errors: {errors}")
		self.assertIn("Missing", errors[0])

	def test_property_change_script_valid_reference_passes(self):
		"""A getChild('InnerButton') in a property-change script resolves - no error."""
		view = self._container_view(propconfig=self._onchange("value = self.getChild('InnerButton')"))
		self.run_lint_on_mock_view(view, self.rule_config)

		self.assertEqual(
			len(self._errors()), 0, f"Valid onChange reference should pass. Errors: {self._errors()}"
		)

	def test_view_scoped_bindings_never_flagged(self):
		"""view.custom / view.params references are not component references - never flagged."""
		propconfig = {
			"props.style": {
				"binding": {
					"config": {
						"expression": "{view.params.color}"
					},
					"type": "expr"
				}
			},
			"props.enabled": {
				"binding": {
					"config": {
						"path": "view.custom.enabled"
					},
					"type": "property"
				}
			}
		}
		view = self._container_view(propconfig=propconfig)
		self.run_lint_on_mock_view(view, self.rule_config)

		self.assertEqual(
			len(self._errors()), 0, f"view-scoped bindings must not be flagged. Errors: {self._errors()}"
		)


if __name__ == '__main__':
	unittest.main()
