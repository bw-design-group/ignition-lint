# pylint: disable=import-error
"""
Test cases for UnusedCustomPropertiesRule.

This rule detects custom properties and view parameters that are defined but never referenced.

SUPPORTED FEATURES:
- ✅ Detects view-level custom properties (custom.*)
- ✅ Detects view parameters (params.*)
- ✅ Detects component-level custom properties (*.custom.*)
- ✅ Detects when properties are used in expression bindings
- ✅ Correctly handles persistent vs non-persistent properties

REMAINING LIMITATIONS:
- Does not detect when properties are used in scripts (scripts not processed by model builder)
"""

import json
from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, create_temp_view_file
from ignition_lint.common.flatten_json import flatten_file


class TestUnusedCustomPropertiesRule(BaseRuleTest):  # pylint: disable=too-many-public-methods
	"""Test the UnusedCustomPropertiesRule to detect unused custom properties and view parameters."""

	def test_unused_view_custom_property(self):
		"""Test that unused view-level custom properties are detected."""
		# Create a view with unused view-level custom property
		view_data = {"custom": {"unusedViewProp": "value"}, "root": {"children": [], "meta": {"name": "root"}}}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should detect the unused view-level custom property
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["unusedViewProp", "never referenced"]
		)

	def test_unused_component_custom_property(self):
		"""Test that unused component-level custom properties are detected."""
		# Create a view with unused component custom property
		view_data = {
			"root": {
				"children": [{
					"meta": {
						"name": "TestButton"
					},
					"type": "ia.input.button",
					"custom": {
						"unusedComponentProp": "value"
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should detect the unused component custom property
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["unusedComponentProp", "never referenced"]
		)

	def test_used_custom_property_in_binding(self):
		"""Test that custom properties referenced in bindings are not flagged."""
		# Create a view with custom properties used in bindings
		view_data = {
			"custom": {
				"usedProp": "value"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestLabel"
					},
					"type": "ia.display.label",
					"custom": {
						"usedComponentProp": "value"
					},
					"props": {
						"text": {
							"binding": {
								"type": "expression",
								"config": {
									"expression":
										"{view.custom.usedProp} + {this.custom.usedComponentProp}"
								}
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should not flag properties that are used in bindings
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_used_custom_property_in_script(self):
		"""Test that custom properties referenced in scripts are not flagged."""
		# Create a view with a custom property used in a script
		view_data = {
			"custom": {
				"scriptProp": "test value"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestButton"
					},
					"events": {
						"onClick": {
							"script":
								"# Use the custom property\nlogger.info('Value: ' + str(self.view.custom.scriptProp))"
						}
					}
				}]
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should not flag properties that are used in scripts
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_mixed_used_and_unused_properties(self):
		"""Test a view with both used and unused custom properties."""
		# Create a view with mixed usage
		view_data = {
			"custom": {
				"usedProp": "used",
				"unusedProp": "unused"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestLabel"
					},
					"type": "ia.display.label",
					"custom": {
						"usedComponentProp": "used in binding",
						"unusedComponentProp": "never used"
					},
					"props": {
						"text": {
							"binding": {
								"type": "expression",
								"config": {
									"expression":
										"{view.custom.usedProp} + {this.custom.usedComponentProp}"
								}
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should detect 2 unused properties
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=2,
			error_patterns=["unusedProp", "unusedComponentProp"]
		)

	def test_view_parameters_usage(self):
		"""Test detection of unused view parameters (params)."""
		# Create a view with unused view parameter
		view_data = {
			"params": {
				"unusedViewParam": "default value"
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should detect the unused view parameter
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["unusedViewParam", "never referenced"]
		)

	def test_state_reset_between_files(self):
		"""Test that rule state is properly reset when processing multiple files."""
		# Create first view with unused property "fileOneProp"
		view_data_1 = {
			"custom": {
				"fileOneProp": "value from file 1"
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_1 = create_temp_view_file(json.dumps(view_data_1, indent=2))

		# Create second view with a completely different unused property "fileTwoProp"
		view_data_2 = {
			"custom": {
				"fileTwoProp": "value from file 2"
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_2 = create_temp_view_file(json.dumps(view_data_2, indent=2))

		# Create a SINGLE lint engine that will be reused for both files (mimics CLI behavior)
		rule_config = get_test_config("UnusedCustomPropertiesRule")
		lint_engine = self.create_lint_engine(rule_config)

		# Process first file with the lint engine
		flattened_1 = flatten_file(mock_view_1)
		results_1 = lint_engine.process(flattened_1)
		errors_1 = results_1.errors.get("UnusedCustomPropertiesRule", [])
		self.assertEqual(len(errors_1), 1, "First file should have exactly 1 error")
		self.assertIn("fileOneProp", errors_1[0], "First file error should mention fileOneProp")
		self.assertNotIn("fileTwoProp", errors_1[0], "First file error should NOT mention fileTwoProp")

		# Process second file with the SAME lint engine (this is where the bug manifests)
		flattened_2 = flatten_file(mock_view_2)
		results_2 = lint_engine.process(flattened_2)
		errors_2 = results_2.errors.get("UnusedCustomPropertiesRule", [])
		self.assertEqual(len(errors_2), 1, "Second file should have exactly 1 error")
		self.assertIn("fileTwoProp", errors_2[0], "Second file error should mention fileTwoProp")
		# This assertion will FAIL if state is not reset properly:
		self.assertNotIn(
			"fileOneProp", errors_2[0],
			"Second file error should NOT mention fileOneProp from first file (state not reset!)"
		)

	def test_view_param_used_in_script_transform_with_self_params(self):
		"""Test that view params accessed via self.params in script transforms are recognized as used."""
		# Create a view with a view parameter used in a script transform as self.params.scriptValue
		view_data = {
			"params": {
				"scriptValue": "default value"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestLabel"
					},
					"type": "ia.display.label",
					"props": {
						"text": {
							"binding": {
								"config": {
									"expression": "None"
								},
								"transforms": [{
									"type": "script",
									"code": "return str(self.params.scriptValue)"
								}],
								"type": "expr"
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should NOT flag the view parameter as unused since it's referenced in the script transform
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_view_param_used_in_script_transform_on_root(self):
		"""Test that view params accessed in script transforms on the root component are recognized."""
		# Create a view where the root component has a script transform using self.params
		view_data = {
			"params": {
				"rootParam": "root value"
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"props": {
					"custom.displayValue": {
						"binding": {
							"config": {
								"expression": "None"
							},
							"transforms": [{
								"type": "script",
								"code": "# Access root param via self.params\nreturn self.params.rootParam"
							}],
							"type": "expr"
						}
					}
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should NOT flag the root parameter as unused
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_multiple_view_params_mixed_usage_in_scripts(self):
		"""Test detection of mixed used/unused view params in various script contexts."""
		view_data = {
			"params": {
				"usedInTransform": "value1",
				"usedInEventHandler": "value2",
				"unusedParam": "value3"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestButton"
					},
					"type": "ia.input.button",
					"props": {
						"text": {
							"binding": {
								"config": {
									"expression": "None"
								},
								"transforms": [{
									"type": "script",
									"code": "return self.params.usedInTransform"
								}],
								"type": "expr"
							}
						}
					},
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script": "logger.info(self.params.usedInEventHandler)"
								},
								"scope": "G",
								"type": "script"
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should detect only the unused param
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["unusedParam", "never referenced"]
		)

	def test_custom_property_used_in_tag_binding(self):
		"""Test that custom properties used in tag bindings are not flagged."""
		view_data = {
			"custom": {
				"tagPrefix": "[default]MyTag"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestLabel"
					},
					"type": "ia.display.label",
					"props": {
						"text": {
							"binding": {
								"config": {
									"tagPath": "{view.custom.tagPrefix}/Value"
								},
								"type": "tag"
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should NOT flag the custom property used in tag binding
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_custom_property_used_in_message_handler(self):
		"""Test that custom properties used in message handler scripts are not flagged."""
		view_data = {
			"custom": {
				"messageValue": "test"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestContainer"
					},
					"type": "ia.container.flex",
					"scripts": {
						"messageHandlers": [{
							"messageType": "testMessage",
							"script": "logger.info(self.view.custom.messageValue)"
						}]
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should NOT flag the custom property used in message handler
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_custom_property_used_in_custom_method(self):
		"""Test that custom properties used in custom component methods are not flagged."""
		view_data = {
			"custom": {
				"methodValue": "custom data"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestComponent"
					},
					"type": "ia.container.flex",
					"custom": {
						"myProp": "value"
					},
					"scripts": {
						"customMethods": [{
							"name": "myMethod",
							"script": "return self.view.custom.methodValue + str(self.custom.myProp)"
						}]
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should NOT flag either custom property as they're both used in custom method
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_custom_property_used_in_property_binding(self):
		"""Test that custom properties used in property binding source paths are not flagged."""
		view_data = {
			"custom": {
				"sourceValue": "binding source"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestLabel"
					},
					"type": "ia.display.label",
					"props": {
						"text": {
							"binding": {
								"config": {
									"path": "view.custom.sourceValue"
								},
								"type": "property"
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should NOT flag the custom property used in property binding
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_custom_property_with_self_view_pattern_in_expression(self):
		"""Test that custom properties with {self.view.custom.prop} pattern in expressions are recognized."""
		view_data = {
			"custom": {
				"selfViewProp": "test value"
			},
			"params": {
				"selfViewParam": "param value"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestLabel"
					},
					"type": "ia.display.label",
					"props": {
						"text": {
							"binding": {
								"type": "expression",
								"config": {
									"expression": "{self.view.custom.selfViewProp} + {self.view.params.selfViewParam}"
								}
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should NOT flag properties used with self.view pattern in expressions
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_output_param_with_binding(self):
		"""Test that output params with bindings are not flagged as unused."""
		view_data = {
			"custom": {
				"dataSource": "test data"
			},
			"params": {
				"outputData": None
			},
			"propConfig": {
				"custom.dataSource": {
					"binding": {
						"config": {
							"expression": "'test'"
						},
						"type": "expr"
					},
					"persistent": True
				},
				"params.outputData": {
					"binding": {
						"config": {
							"path": "view.custom.dataSource"
						},
						"type": "property"
					},
					"paramDirection": "output",
					"persistent": True
				}
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Output param with binding should NOT be flagged - it's actively populated
		# Custom property with binding should NOT be flagged - it has a binding
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_output_param_without_binding(self):
		"""Test that output params without bindings or references are flagged as unused."""
		view_data = {
			"params": {
				"outputWithoutBinding": None
			},
			"propConfig": {
				"params.outputWithoutBinding": {
					"paramDirection": "output",
					"persistent": True
				}
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Output param without binding or references should be flagged
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["outputWithoutBinding", "never referenced"]
		)

	def test_output_param_with_tag_binding(self):
		"""Test that output params with tag bindings are not flagged as unused."""
		view_data = {
			"params": {
				"tagPath": "[default]MyTag",
				"outputValue": None
			},
			"propConfig": {
				"params.tagPath": {
					"paramDirection": "input",
					"persistent": True
				},
				"params.outputValue": {
					"binding": {
						"config": {
							"fallbackDelay": 2.5,
							"mode": "indirect",
							"references": {
								"tagPath": "{view.params.tagPath}"
							},
							"tagPath": "{tagPath}/Value"
						},
						"type": "tag"
					},
					"paramDirection": "output",
					"persistent": True
				}
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Output param with tag binding should NOT be flagged
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_custom_property_with_binding_not_referenced(self):
		"""Test that custom properties with bindings are not flagged even if not referenced elsewhere."""
		view_data = {
			"custom": {
				"calculatedValue": None
			},
			"params": {
				"inputA": 5,
				"inputB": 10
			},
			"propConfig": {
				"custom.calculatedValue": {
					"binding": {
						"config": {
							"expression": "{view.params.inputA} + {view.params.inputB}"
						},
						"type": "expr"
					},
					"persistent": True
				},
				"params.inputA": {
					"paramDirection": "input",
					"persistent": True
				},
				"params.inputB": {
					"paramDirection": "input",
					"persistent": True
				}
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Custom property with binding should NOT be flagged even if not referenced
		# It's actively managed and could be used by parent views or future changes
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_unused_input_param(self):
		"""Test that unused input params are correctly flagged."""
		view_data = {
			"params": {
				"usedInput": "value1",
				"unusedInput": "value2"
			},
			"propConfig": {
				"params.usedInput": {
					"paramDirection": "input",
					"persistent": True
				},
				"params.unusedInput": {
					"paramDirection": "input",
					"persistent": True
				}
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestLabel"
					},
					"type": "ia.display.label",
					"propConfig": {
						"props.text": {
							"binding": {
								"config": {
									"expression": "{view.params.usedInput}"
								},
								"type": "expr"
							}
						}
					}
				}],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Only unusedInput should be flagged
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["unusedInput", "never referenced"]
		)

	def test_mixed_param_scenarios(self):
		"""Test comprehensive mix of param scenarios."""
		view_data = {
			"custom": {
				"dataSource": "test",
				"unusedCustom": "not used"
			},
			"params": {
				"usedInput": "value",
				"unusedInput": "not used",
				"outputWithBinding": None,
				"outputWithoutBinding": None
			},
			"propConfig": {
				"custom.dataSource": {
					"binding": {
						"config": {
							"expression": "{view.params.usedInput}"
						},
						"type": "expr"
					},
					"persistent": True
				},
				"custom.unusedCustom": {
					"persistent": True
				},
				"params.usedInput": {
					"paramDirection": "input",
					"persistent": True
				},
				"params.unusedInput": {
					"paramDirection": "input",
					"persistent": True
				},
				"params.outputWithBinding": {
					"binding": {
						"config": {
							"path": "view.custom.dataSource"
						},
						"type": "property"
					},
					"paramDirection": "output",
					"persistent": True
				},
				"params.outputWithoutBinding": {
					"paramDirection": "output",
					"persistent": True
				}
			},
			"root": {
				"children": [],
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Should flag: unusedInput, unusedCustom, outputWithoutBinding
		# Should NOT flag: usedInput (referenced), dataSource (has binding), outputWithBinding (has binding)
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=3,
			error_patterns=["unusedInput", "unusedCustom", "outputWithoutBinding"]
		)
