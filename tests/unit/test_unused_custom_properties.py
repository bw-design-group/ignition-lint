# pylint: disable=import-error
"""
Test cases for UnusedCustomPropertiesRule.

This rule detects custom properties and view parameters that are defined but never referenced.

SUPPORTED FEATURES:
- ✅ Detects view-level custom properties (custom.*)
- ✅ Detects view parameters (params.*)
- ✅ Detects component-level custom properties (*.custom.*)
- ✅ Detects when properties are used in expression bindings
- ✅ Detects when properties are referenced in scripts (location-independent string scan)
- ✅ Credits parent/container object properties when their nested children are bound or referenced
- ✅ Correctly handles persistent vs non-persistent properties
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
								"code":
									"# Access root param via self.params\nreturn self.params.rootParam"
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
									"script":
										"logger.info(self.params.usedInEventHandler)"
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
							"script":
								"return self.view.custom.methodValue + str(self.custom.myProp)"
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
									"expression":
										"{self.view.custom.selfViewProp} + {self.view.params.selfViewParam}"
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

	def test_object_custom_property_with_bound_children(self):
		"""Parent object custom property is used when its children have bindings (issue #97)."""
		# custom.network is an object whose nested children (nat1, nat2) have tag bindings
		# and are referenced in an onChange script. The parent must be considered used.
		view_data = {
			"custom": {
				"network": {}
			},
			"propConfig": {
				"custom.network": {
					"onChange": {
						"enabled": None,
						"script":
							"\tif self.custom.network.nat1 == \"0.0.0.0\" and "
							"self.custom.network.nat2 == \"0.0.0.0\":\n\t\tpass"
					},
					"persistent": True
				},
				"custom.network.nat1": {
					"binding": {
						"config": {
							"mode": "indirect",
							"tagPath": "[default]Path/IPAddressNat1"
						},
						"type": "tag"
					}
				},
				"custom.network.nat2": {
					"binding": {
						"config": {
							"mode": "indirect",
							"tagPath": "[default]Path/IPAddressNat2"
						},
						"type": "tag"
					}
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Parent custom.network should NOT be flagged - its children are bound and referenced
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_object_custom_property_with_referenced_child_only(self):
		"""Parent object custom property is used when a nested child is referenced in a script."""
		view_data = {
			"custom": {
				"settings": {
					"timeout": 5000
				}
			},
			"root": {
				"children": [{
					"meta": {
						"name": "TestButton"
					},
					"type": "ia.input.button",
					"events": {
						"onClick": {
							"script": "logger.info(self.view.custom.settings.timeout)"
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

		# Parent custom.settings should NOT be flagged - its child .timeout is referenced
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_object_component_custom_property_with_referenced_child(self):
		"""Parent object component custom property is used when a nested child is referenced."""
		view_data = {
			"root": {
				"children": [{
					"meta": {
						"name": "TestLabel"
					},
					"type": "ia.display.label",
					"custom": {
						"config": {
							"color": "red"
						}
					},
					"props": {
						"text": {
							"binding": {
								"type": "expression",
								"config": {
									"expression": "{this.custom.config.color}"
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

		# Parent component custom.config should NOT be flagged - its child .color is referenced
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_unused_object_custom_property_still_flagged(self):
		"""An object custom property with no referenced/bound children is still flagged as unused."""
		# Parent object is defined (via propConfig) and has a child (nat1) that is neither
		# bound nor referenced anywhere, so the parent must still be reported as unused.
		view_data = {
			"custom": {
				"unusedNetwork": {}
			},
			"propConfig": {
				"custom.unusedNetwork": {
					"persistent": True
				},
				"custom.unusedNetwork.nat1": {
					"persistent": True
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# No children are referenced or bound, so the object property is unused
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["unusedNetwork", "never referenced"]
		)

	def test_object_child_binding_does_not_credit_sibling_prefix(self):
		"""Crediting a parent for child usage must not leak to a name-prefix sibling."""
		# custom.net and custom.network share a name prefix. Only network has a bound child,
		# so custom.net must still be flagged (the trailing-dot guard prevents false crediting).
		view_data = {
			"custom": {
				"net": "x",
				"network": {}
			},
			"propConfig": {
				"custom.network": {
					"persistent": True
				},
				"custom.network.nat1": {
					"binding": {
						"config": {
							"tagPath": "[default]Path/Nat1"
						},
						"type": "tag"
					}
				}
			},
			"root": {
				"meta": {
					"name": "root"
				}
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Only custom.net should be flagged; custom.network is credited by its bound child.
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["net", "never referenced"]
		)

	def test_view_object_custom_nested_child_in_event_script(self):
		"""A view object custom prop is used when a nested child is read via self.custom in a script."""
		view_data = {
			"custom": {
				"network": {}
			},
			"propConfig": {
				"custom.network": {
					"persistent": True
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"children": [{
					"meta": {
						"name": "Btn"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script": "x = self.custom.network.nat1"
								},
								"type": "script"
							}
						}
					}
				}]
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# The nested child access credits the parent object property.
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_plain_self_custom_does_not_credit_view_level_scalar(self):
		"""A bare self.custom.X (no nested child) must not credit a view-level property."""
		# self.custom is component-relative; without a nested child access it should not
		# silently mark an unrelated view-level custom property as used.
		view_data = {
			"custom": {
				"network": "scalar"
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"children": [{
					"meta": {
						"name": "Btn"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script": "x = self.custom.network"
								},
								"type": "script"
							}
						}
					}
				}]
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# view.custom.network is a scalar referenced only via component-relative self.custom,
		# so it remains unused (strict view-level behavior is preserved).
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["network", "never referenced"]
		)

	def test_object_child_referenced_in_unmodeled_onchange_script(self):
		"""Reference detection is location-independent: a nested child read in an onChange script counts.

		Property-change (onChange) scripts are not modeled as their own script nodes, but their
		text is still scanned, so a self.custom.X.child reference there must credit the parent
		object property the same way it would in a transform or event handler.
		"""
		view_data = {
			"custom": {
				"network": {}
			},
			"propConfig": {
				"custom.network": {
					"onChange": {
						"enabled": None,
						"script": "\tif self.custom.network.nat1 == \"0.0.0.0\":\n\t\tpass"
					},
					"persistent": True
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# The nested child access in the onChange script credits the parent object property.
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_view_custom_referenced_via_self_custom_in_view_scope_onchange(self):
		"""A view-level custom read via bare self.custom.X in a view-scoped onChange is used.

		The onChange script lives on the view's own custom property (top-level propConfig.custom.*),
		so at runtime `self` IS the view and `self.custom.supervisor` is identical to
		`self.view.custom.supervisor`. The property must therefore be credited even though it is
		never written with the longer self.view.custom form. Regression test for the
		self.custom.X view-scope false positive.
		"""
		view_data = {
			"custom": {
				"supervisor": 0,
				"devices": []
			},
			"propConfig": {
				"custom.supervisor": {
					"onChange": {
						"enabled": None,
						"script":
							"\tfor i, device in enumerate(self.custom.devices):\n"
							"\t\tdevice['supervisor'] = (i == self.custom.supervisor)"
					},
					"persistent": True
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Both supervisor (read via self.custom.supervisor) and devices (read via self.custom.devices)
		# are referenced from a view-scoped script, so neither should be flagged.
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_view_param_referenced_via_self_params_in_view_scope_script(self):
		"""A view-level param read via bare self.params.X in a view-scoped script is used."""
		view_data = {
			"params": {
				"threshold": 10
			},
			"custom": {
				"derived": 0
			},
			"propConfig": {
				"custom.derived": {
					"binding": {
						"type": "expr",
						"config": {
							"expression": "now()"
						},
						"transforms": [{
							"type": "script",
							"code":
								"\tif self.params.threshold > 0:\n\t\treturn value\n\treturn None"
						}]
					}
				},
				"params.threshold": {
					"paramDirection": "input",
					"persistent": True
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# custom.derived is credited as a binding owner; view.params.threshold is read via
		# self.params.threshold in that binding's view-scoped transform script.
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_view_custom_referenced_via_self_custom_in_view_event_handler(self):
		"""A view-level custom read via self.custom.X in a top-level (view) event handler is used.

		Top-level events.* are the view's own event handlers, where `self` is the view.
		"""
		view_data = {
			"custom": {
				"startupFlag": False
			},
			"events": {
				"system": {
					"onStartup": {
						"config": {
							"script": "\tif self.custom.startupFlag:\n\t\tpass"
						},
						"scope": "G",
						"type": "script"
					}
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# view.custom.startupFlag is read via self.custom.startupFlag in a view event handler.
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_truly_unused_view_custom_still_flagged_with_view_scope_fix(self):
		"""Guard against over-correcting: a truly-unused view custom is still flagged.

		One view custom (used) is read via self.custom in a view-scoped script; another (unused)
		is never referenced anywhere. Only the unused one should be reported.
		"""
		view_data = {
			"custom": {
				"used": 1,
				"trulyUnused": 2
			},
			"propConfig": {
				"custom.used": {
					"onChange": {
						"enabled": None,
						"script": "\tx = self.custom.used"
					},
					"persistent": True
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}
		mock_view_content = json.dumps(view_data, indent=2)
		mock_view = create_temp_view_file(mock_view_content)

		rule_config = get_test_config("UnusedCustomPropertiesRule")

		# Only trulyUnused should be flagged; the view-scope fix must not blanket-credit customs.
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["trulyUnused", "never referenced"]
		)

	def test_whole_object_view_params_forwarding_credits_all(self):
		"""Whole-object self.view.params forwarding credits every view param.

		A button forwards the entire params object via sendMessage(payload=self.view.params);
		a different view consumes individual members via payload.get(...). The defining view
		never references any param by name, so name-based detection alone would falsely flag
		them. The whole-object sentinel must credit all params at view scope.
		"""
		view_data = {
			"params": {
				"sectionUuid": "abc",
				"rowIndex": 0,
				"tagPath": "[default]X"
			},
			"root": {
				"children": [{
					"meta": {
						"name": "MoveUpButton"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script":
										"system.perspective.sendMessage('onMoveUp', scope='page', payload=self.view.params)"
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

		# All three params are credited via whole-object forwarding -> no unused reports.
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_whole_object_view_custom_forwarding_credits_all(self):
		"""Whole-object self.view.custom forwarding credits every view custom property."""
		view_data = {
			"custom": {
				"alpha": 1,
				"beta": 2
			},
			"root": {
				"children": [{
					"meta": {
						"name": "ForwardButton"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script":
										"system.perspective.sendMessage('snapshot', payload=self.view.custom)"
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

		# Both customs are credited via whole-object forwarding -> no unused reports.
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)

	def test_subscript_view_params_access_credits_only_that_member(self):
		"""Subscript access self.view.params['name'] credits only that param."""
		view_data = {
			"params": {
				"sectionUuid": "abc",
				"rowIndex": 0
			},
			"root": {
				"children": [{
					"meta": {
						"name": "ReadButton"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script":
										"uuid = self.view.params['sectionUuid']"
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

		# Literal subscript access is a single-member read; rowIndex should still be flagged.
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["rowIndex", "never referenced"]
		)

	def test_single_member_access_still_credits_only_that_member(self):
		"""Regression guard: self.view.params.onlyThis credits only that param, not its siblings.

		The whole-object sentinel must not over-credit when a real member access is present;
		a sibling param that is never referenced must still be flagged.
		"""
		view_data = {
			"params": {
				"onlyThis": 1,
				"sibling": 2
			},
			"root": {
				"children": [{
					"meta": {
						"name": "ReadButton"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script": "value = self.view.params.onlyThis"
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

		# Only the unreferenced sibling should be flagged; onlyThis is credited by name.
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["sibling", "never referenced"]
		)

	def test_bare_self_params_at_component_scope_not_credited(self):
		"""Bare self.params (no `view`) at component scope does NOT credit view params.

		Only the explicit self.view.* whole-object forms are handled. A component-scope bare
		self.params reference is intentionally not treated as whole-object view-param use, so a
		view param referenced only this way is still flagged. This documents the deliberate
		scope boundary of the fix.
		"""
		view_data = {
			"params": {
				"forwarded": 1
			},
			"root": {
				"children": [{
					"meta": {
						"name": "ComponentButton"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script":
										"system.perspective.sendMessage('m', payload=self.params)"
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

		# Bare self.params at component scope is not handled -> param remains flagged.
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["forwarded", "never referenced"]
		)

	def test_subscript_view_params_access_with_whitespace_credits_only_that_member(self):
		"""self.view.params [ 'name' ] with surrounding whitespace credits only that member.

		Guards the whitespace handling in the literal-subscript detector and the sentinel
		lookahead. If this regresses, the wildcard may over-credit siblings.
		"""
		view_data = {
			"params": {
				"sectionUuid": "abc",
				"rowIndex": 0
			},
			"root": {
				"children": [{
					"meta": {
						"name": "ReadButton"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script":
										"uuid = self.view.params [ 'sectionUuid' ]"
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

		# Literal subscript with whitespace is still a single-member read; rowIndex still flagged.
		self.assert_rule_errors(
			mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=1,
			error_patterns=["rowIndex", "never referenced"]
		)

	def test_dynamic_subscript_view_params_access_credits_all(self):
		"""Dynamic subscript self.view.params[key] credits all params conservatively.

		The key is not statically knowable, so the whole-object wildcard sentinel fires
		rather than crediting nothing.
		"""
		view_data = {
			"params": {
				"alpha": 1,
				"beta": 2
			},
			"root": {
				"children": [{
					"meta": {
						"name": "ReadButton"
					},
					"type": "ia.input.button",
					"events": {
						"component": {
							"onActionPerformed": {
								"config": {
									"script":
										"key = 'alpha'\nvalue = self.view.params[key]"
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

		# Dynamic key -> conservative wildcard -> no params flagged.
		self.assert_rule_errors(mock_view, rule_config, "UnusedCustomPropertiesRule", expected_error_count=0)
