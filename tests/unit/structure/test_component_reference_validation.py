# pylint: disable=import-error
"""
Unit tests for the ComponentReferenceValidationRule.
Tests validation of component references in expressions, property bindings, and scripts.
"""

import unittest
import json
from typing import Dict, Any

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, load_test_view


class TestComponentReferenceValidationRule(BaseRuleTest):
	"""Test component reference validation."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config("ComponentReferenceValidationRule")

	def _create_mock_view_with_components(self, components_json: Dict) -> str:
		"""
		Create a mock view with specific component structure.

		Args:
			components_json: Dictionary representing the root component structure

		Returns:
			JSON string of the view
		"""
		view_data = {
			"custom": {},
			"params": {},
			"propConfig": components_json.get("propConfig", {}),
			"props": {
				"defaultSize": {
					"height": 600
				}
			},
			"root": components_json
		}
		return json.dumps(view_data, indent=2)

	def test_valid_sibling_reference_in_expression(self):
		"""Test that valid sibling references in expressions pass validation."""
		components = {
			"children": [{
				"meta": {
					"name": "Button1"
				},
				"type": "ia.input.button",
				"props": {
					"text": "Button 1"
				}
			}, {
				"meta": {
					"name": "Button2"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"expression": "{../Button1.props.text}"
							},
							"type": "expr"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 0, f"Valid sibling reference should pass. Errors: {rule_errors}")

	def test_invalid_sibling_reference_in_expression(self):
		"""Test that invalid sibling references in expressions are detected."""
		components = {
			"children": [{
				"meta": {
					"name": "Button1"
				},
				"type": "ia.input.button",
				"props": {
					"text": "Button 1"
				}
			}, {
				"meta": {
					"name": "Button2"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"expression": "{../NonExistentButton.props.text}"
							},
							"type": "expr"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 1)
		self.assertIn("NonExistentButton", rule_errors[0])
		self.assertIn("expression", rule_errors[0].lower())

	def test_valid_nested_path_in_expression(self):
		"""Test that valid nested path references (with /) in expressions pass validation."""
		components = {
			"children": [{
				"meta": {
					"name": "Container1"
				},
				"type": "ia.container.flex",
				"children": [{
					"meta": {
						"name": "NestedButton"
					},
					"type": "ia.input.button",
					"props": {
						"text": "Nested"
					}
				}]
			}, {
				"meta": {
					"name": "Button2"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"expression": "{../Container1/NestedButton.props.text}"
							},
							"type": "expr"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 0, f"Valid nested path should pass. Errors: {rule_errors}")

	def test_valid_property_binding_sibling(self):
		"""Test that valid sibling references in property bindings pass validation."""
		components = {
			"children": [{
				"meta": {
					"name": "SourceButton"
				},
				"type": "ia.input.button",
				"props": {
					"enabled": True
				}
			}, {
				"meta": {
					"name": "TargetButton"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"path": "../SourceButton.props.enabled"
							},
							"type": "property"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 0, f"Valid property binding should pass. Errors: {rule_errors}")

	def test_invalid_property_binding(self):
		"""Test that invalid property bindings are detected."""
		components = {
			"children": [{
				"meta": {
					"name": "TargetButton"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"path": "../MissingButton.props.enabled"
							},
							"type": "property"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 1)
		self.assertIn("MissingButton", rule_errors[0])
		self.assertIn("property binding", rule_errors[0].lower())

	def test_valid_get_sibling_script(self):
		"""Test that valid getSibling() references in scripts pass validation."""
		components = {
			"children": [{
				"meta": {
					"name": "StatusLabel"
				},
				"type": "ia.display.label",
				"props": {
					"text": "Status"
				}
			}, {
				"meta": {
					"name": "ActionButton"
				},
				"type": "ia.input.button",
				"events": {
					"component": {
						"onActionPerformed": {
							"config": {
								"script":
									"label = self.getSibling('StatusLabel')\nlabel.props.text = 'Updated'"
							},
							"scope": "G",
							"type": "script"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 0, f"Valid getSibling should pass. Errors: {rule_errors}")

	def test_invalid_get_sibling_script(self):
		"""Test that invalid getSibling() references in scripts are detected."""
		components = {
			"children": [{
				"meta": {
					"name": "ActionButton"
				},
				"type": "ia.input.button",
				"events": {
					"component": {
						"onActionPerformed": {
							"config": {
								"script":
									"label = self.getSibling('NonExistentLabel')\nlabel.props.text = 'Updated'"
							},
							"scope": "G",
							"type": "script"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# May detect error multiple times (simple pattern + chained pattern)
		self.assertGreaterEqual(len(rule_errors), 1)
		# At least one error should mention NonExistentLabel
		has_error = any("NonExistentLabel" in error for error in rule_errors)
		self.assertTrue(has_error, f"Should detect NonExistentLabel. Errors: {rule_errors}")

	def test_valid_chained_navigation(self):
		"""Test that valid chained navigation in scripts passes validation."""
		components = {
			"children": [{
				"meta": {
					"name": "Container1"
				},
				"type": "ia.container.flex",
				"children": [{
					"meta": {
						"name": "NestedButton"
					},
					"type": "ia.input.button",
					"props": {
						"text": "Nested"
					}
				}]
			}, {
				"meta": {
					"name": "ActionButton"
				},
				"type": "ia.input.button",
				"events": {
					"component": {
						"onActionPerformed": {
							"config": {
								"script":
									"nested = self.getSibling('Container1').getChild('NestedButton')\nnested.props.text = 'Updated'"
							},
							"scope": "G",
							"type": "script"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 0, f"Valid chained navigation should pass. Errors: {rule_errors}")

	def test_invalid_chained_navigation(self):
		"""Test that invalid chained navigation in scripts is detected."""
		components = {
			"children": [{
				"meta": {
					"name": "Container1"
				},
				"type": "ia.container.flex",
				"children": [{
					"meta": {
						"name": "NestedButton"
					},
					"type": "ia.input.button",
					"props": {
						"text": "Nested"
					}
				}]
			}, {
				"meta": {
					"name": "ActionButton"
				},
				"type": "ia.input.button",
				"events": {
					"component": {
						"onActionPerformed": {
							"config": {
								"script":
									"nested = self.getSibling('Container1').getChild('MissingButton')\nnested.props.text = 'Updated'"
							},
							"scope": "G",
							"type": "script"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 1)
		self.assertIn("MissingButton", rule_errors[0])
		self.assertIn("child", rule_errors[0].lower())

	def test_multiple_levels_up_three_dots(self):
		"""Test navigation with four dots (.... = 3 levels up)."""
		components = {
			"children": [{
				"meta": {
					"name": "TopContainer"
				},
				"type": "ia.container.flex",
				"children": [{
					"meta": {
						"name": "MiddleContainer"
					},
					"type": "ia.container.flex",
					"children": [{
						"meta": {
							"name": "DeepButton"
						},
						"type": "ia.input.button",
						"propConfig": {
							"props.enabled": {
								"binding": {
									"config": {
										"expression":
											"{..../TopContainer.props.style}"
									},
									"type": "expr"
								}
							}
						}
					}]
				}]
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should pass: DeepButton (3 levels up with ....) -> root, then down to child TopContainer
		self.assertEqual(len(rule_errors), 0, f"Four-dot navigation should pass. Errors: {rule_errors}")

	def test_navigate_above_root_error(self):
		"""Test that navigating above root component is detected as error."""
		components = {
			"children": [{
				"meta": {
					"name": "Button1"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"expression": "{.../SomethingAboveRoot.props.enabled}"
							},
							"type": "expr"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		self.assertEqual(len(rule_errors), 1)
		self.assertIn("above root", rule_errors[0].lower())

	def test_bad_component_references_test_case(self):
		"""Test against the BadComponentReferences test case to detect known invalid references."""
		try:
			view_file = load_test_view(self.test_cases_dir, "BadComponentReferences")

			self.run_lint_on_file(view_file, self.rule_config)
			rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")

			# Should detect some invalid references
			self.assertGreater(len(rule_errors), 0, "Should detect invalid references in test case")

			# Should specifically detect these known issues from the test case:
			# - Line 240/356: ../NestedButton4 (doesn't exist)
			# - Line 467: self.getSibling("UnknownButton") (doesn't exist)

			missing_nested_button4 = any("NestedButton4" in error for error in rule_errors)
			missing_unknown_button = any("UnknownButton" in error for error in rule_errors)

			self.assertTrue(
				missing_nested_button4,
				f"Should detect missing NestedButton4 reference. Found errors: {rule_errors}"
			)
			self.assertTrue(
				missing_unknown_button,
				f"Should detect missing UnknownButton reference. Found errors: {rule_errors}"
			)

		except FileNotFoundError:
			self.skipTest("BadComponentReferences test case not found")

	def test_configuration_flags_expression_disabled(self):
		"""Test that expression validation can be disabled via configuration."""
		# Create config with expression validation disabled
		config = get_test_config("ComponentReferenceValidationRule", validate_expressions=False)

		components = {
			"children": [{
				"meta": {
					"name": "Button1"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"expression": "{../NonExistentButton.props.text}"
							},
							"type": "expr"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should not detect error because expression validation is disabled
		self.assertEqual(len(rule_errors), 0)

	def test_configuration_flags_property_binding_disabled(self):
		"""Test that property binding validation can be disabled via configuration."""
		# Create config with property binding validation disabled
		config = get_test_config("ComponentReferenceValidationRule", validate_property_bindings=False)

		components = {
			"children": [{
				"meta": {
					"name": "Button1"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"path": "../NonExistentButton.props.enabled"
							},
							"type": "property"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should not detect error because property binding validation is disabled
		self.assertEqual(len(rule_errors), 0)

	def test_configuration_flags_script_disabled(self):
		"""Test that script validation can be disabled via configuration."""
		# Create config with script validation disabled
		config = get_test_config("ComponentReferenceValidationRule", validate_scripts=False)

		components = {
			"children": [{
				"meta": {
					"name": "ActionButton"
				},
				"type": "ia.input.button",
				"events": {
					"component": {
						"onActionPerformed": {
							"config": {
								"script": "label = self.getSibling('NonExistentLabel')"
							},
							"scope": "G",
							"type": "script"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should not detect error because script validation is disabled
		self.assertEqual(len(rule_errors), 0)

	def test_parent_navigation_in_chained_calls(self):
		"""Test self.parent.parent.getChild() pattern."""
		components = {
			"children": [{
				"meta": {
					"name": "Container1"
				},
				"type": "ia.container.flex",
				"children": [{
					"meta": {
						"name": "ChildButton"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script":
										"sibling = self.parent.parent.getChild('Container2')\nprint(sibling)"
								},
								"scope": "G",
								"type": "script"
							}
						}
					}
				}]
			}, {
				"meta": {
					"name": "Container2"
				},
				"type": "ia.container.flex"
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should pass: ChildButton.parent.parent -> root, root.getChild('Container2')
		self.assertEqual(
			len(rule_errors), 0, f"Valid parent.parent.getChild should pass. Errors: {rule_errors}"
		)

	def test_valid_expression_with_custom_property(self):
		"""Test valid expression binding referencing custom properties."""
		components = {
			"children": [{
				"meta": {
					"name": "Switch1"
				},
				"type": "ia.input.switch",
				"custom": {
					"energized": True
				}
			}, {
				"meta": {
					"name": "Button1"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"expression": "{../Switch1.custom.energized}"
							},
							"type": "expr"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should pass: Switch1 exists as sibling, .custom. should be stripped correctly
		self.assertEqual(
			len(rule_errors), 0, f"Valid custom property reference should pass. Errors: {rule_errors}"
		)

	def test_valid_property_binding_with_custom_property(self):
		"""Test valid property binding referencing custom properties."""
		components = {
			"children": [{
				"meta": {
					"name": "Sensor1"
				},
				"type": "ia.display.label",
				"custom": {
					"value": 42
				}
			}, {
				"meta": {
					"name": "Display1"
				},
				"type": "ia.display.label",
				"propConfig": {
					"props.text": {
						"binding": {
							"config": {
								"path": "../Sensor1.custom.value"
							},
							"type": "property"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should pass: Sensor1 exists as sibling
		self.assertEqual(
			len(rule_errors), 0, f"Valid custom property binding should pass. Errors: {rule_errors}"
		)

	def test_invalid_expression_with_custom_property(self):
		"""Test invalid expression binding with custom property - component doesn't exist."""
		components = {
			"children": [{
				"meta": {
					"name": "Button1"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"expression": "{../NonExistentSwitch.custom.energized}"
							},
							"type": "expr"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should error: NonExistentSwitch doesn't exist
		self.assertEqual(len(rule_errors), 1, "Invalid custom property reference should be detected")
		self.assertIn("NonExistentSwitch", rule_errors[0])

	def test_nested_custom_property_reference(self):
		"""Test custom property reference with nested path."""
		components = {
			"children": [{
				"meta": {
					"name": "Container1"
				},
				"type": "ia.container.flex",
				"children": [{
					"meta": {
						"name": "Switch1"
					},
					"type": "ia.input.switch",
					"custom": {
						"state": "on"
					}
				}]
			}, {
				"meta": {
					"name": "Button1"
				},
				"type": "ia.input.button",
				"propConfig": {
					"props.enabled": {
						"binding": {
							"config": {
								"expression": "{../Container1/Switch1.custom.state}"
							},
							"type": "expr"
						}
					}
				}
			}],
			"meta": {
				"name": "root"
			},
			"type": "ia.container.coord"
		}

		mock_view = self._create_mock_view_with_components(components)
		self.run_lint_on_mock_view(mock_view, self.rule_config)

		rule_errors = self.get_errors_for_rule("ComponentReferenceValidationRule")
		# Should pass: Container1/Switch1 is valid nested path with custom property
		self.assertEqual(
			len(rule_errors), 0,
			f"Valid nested custom property reference should pass. Errors: {rule_errors}"
		)


if __name__ == '__main__':
	unittest.main()
