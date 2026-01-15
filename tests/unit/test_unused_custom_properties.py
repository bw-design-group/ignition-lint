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


class TestUnusedCustomPropertiesRule(BaseRuleTest):
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
