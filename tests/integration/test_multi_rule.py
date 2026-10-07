# pylint: disable=import-error
"""
Integration tests for multiple rules working together.
Tests interactions between different linting rules.
"""

import unittest

from fixtures.base_test import BaseIntegrationTest
from fixtures.test_helpers import load_test_view


class TestMultipleRules(BaseIntegrationTest):
	"""Test multiple rules working together."""

	def test_name_pattern_and_polling_rules(self):
		"""Test NamePatternRule and PollingIntervalRule together."""
		rule_configs = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component"],
					"convention": "PascalCase"
				}
			},
			"PollingIntervalRule": {
				"enabled": True,
				"kwargs": {
					"minimum_interval": 10000
				}
			}
		}

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		errors = self.run_multiple_rules(view_file, rule_configs)

		# Should successfully run both rules
		self.assertIsInstance(errors, dict)

		# NamePatternRule should pass for PascalCase view
		name_pattern_errors = errors.get("NamePatternRule", [])
		self.assertEqual(name_pattern_errors, [], "NamePatternRule should pass for PascalCase view")

	def test_all_available_rules_together(self):
		"""Test running all available rules together."""
		rule_configs = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component"],
					"convention": "PascalCase"
				}
			},
			"PollingIntervalRule": {
				"enabled": True,
				"kwargs": {
					"minimum_interval": 5000
				}
			},
			"PerspectiveScriptPylintRule": {
				"enabled": True,
				"kwargs": {}
			}
		}

		test_cases = ["PascalCase", "camelCase", "ExpressionBindings"]

		for case in test_cases:
			with self.subTest(case=case):
				try:
					view_file = load_test_view(self.test_cases_dir, case)
					errors = self.run_multiple_rules(view_file, rule_configs)

					# Should complete without crashing
					self.assertIsInstance(errors, dict)

					# Verify each rule either passed or failed gracefully
					for rule_name, _ in rule_configs.items():
						if rule_name in errors:
							self.assertIsInstance(errors[rule_name], list)

				except FileNotFoundError:
					self.skipTest(f"Test case {case} not found")

	def test_rule_interactions(self):
		"""Test that rules don't interfere with each other."""
		# Run NamePatternRule alone
		single_rule_config = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component"],
					"convention": "PascalCase"
				}
			}
		}

		# Run NamePatternRule with other rules
		multi_rule_config = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component"],
					"convention": "PascalCase"
				}
			},
			"PollingIntervalRule": {
				"enabled": True,
				"kwargs": {
					"minimum_interval": 10000
				}
			}
		}

		view_file = load_test_view(self.test_cases_dir, "PascalCase")

		single_errors = self.run_multiple_rules(view_file, single_rule_config)
		multi_errors = self.run_multiple_rules(view_file, multi_rule_config)

		# NamePatternRule results should be the same in both cases
		single_name_errors = single_errors.get("NamePatternRule", [])
		multi_name_errors = multi_errors.get("NamePatternRule", [])

		self.assertEqual(
			single_name_errors, multi_name_errors,
			"NamePatternRule results should be consistent whether run alone or with other rules"
		)

	def test_error_aggregation(self):
		"""Test that errors from multiple rules are properly aggregated."""
		# Use a view that should fail NamePatternRule but pass others
		rule_configs = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component"],
					"convention": "PascalCase"
				}
			},
			"PollingIntervalRule": {
				"enabled": True,
				"kwargs": {
					"minimum_interval": 1000
				}  # Low threshold to avoid errors
			}
		}

		# Test with camelCase view which should fail PascalCase rule
		view_file = load_test_view(self.test_cases_dir, "camelCase")
		errors = self.run_multiple_rules(view_file, rule_configs)

		# Should have NamePatternRule errors
		name_pattern_errors = errors.get("NamePatternRule", [])
		self.assertGreater(len(name_pattern_errors), 0, "Should have NamePatternRule errors for camelCase view")

		# Calculate total errors
		total_errors = sum(len(rule_errors) for rule_errors in errors.values())
		self.assertGreater(total_errors, 0, "Should have some total errors")

	def test_mixed_node_type_naming_standards(self):
		"""Test standard naming conventions across multiple node types."""
		rule_configs = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component", "property"],
					"convention": "PascalCase",  # Default
					"node_type_specific_rules": {
						"component": {
							"convention": "PascalCase",
							"min_length": 1,
							"allow_numbers": True
						},
						"property": {
							"convention": "camelCase",
							"min_length": 1,
							"allow_numbers": True,
							"skip_names": ["id", "x", "y", "z"]
						}
					}
				}
			},
			"PollingIntervalRule": {
				"enabled": True,
				"kwargs": {
					"minimum_interval": 5000
				}
			}
		}

		test_cases = ["PascalCase", "camelCase"]
		for case in test_cases:
			with self.subTest(case=case):
				try:
					view_file = load_test_view(self.test_cases_dir, case)
					errors = self.run_multiple_rules(view_file, rule_configs)

					# Should complete without crashing
					self.assertIsInstance(errors, dict)

					# Verify structure of results
					for _, rule_errors in errors.items():
						self.assertIsInstance(rule_errors, list)

				except FileNotFoundError:
					self.skipTest(f"Test case {case} not found")

	def test_comprehensive_rule_coverage(self):
		"""Test comprehensive rule configuration with multiple node types."""
		rule_configs = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": [
						"component", "property", "custom_method", "event_handler"
					],
					"convention": "PascalCase",
					"node_type_specific_rules": {
						"component": {
							"convention": "PascalCase",
							"min_length": 1
						},
						"property": {
							"convention": "camelCase",
							"min_length": 1
						},
						"custom_method": {
							"convention": "camelCase",
							"min_length": 3
						},
						"event_handler": {
							"convention": "camelCase",
							"min_length": 2,
							"skip_names": ["onClick", "onLoad", "onFocus", "onBlur"]
						}
					}
				}
			},
			"PollingIntervalRule": {
				"enabled": True,
				"kwargs": {
					"minimum_interval": 10000
				}
			},
			"PerspectiveScriptPylintRule": {
				"enabled": True,
				"kwargs": {}
			}
		}

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		errors = self.run_multiple_rules(view_file, rule_configs)

		# Should successfully process all rules
		self.assertIsInstance(errors, dict)

		# Verify each configured rule either passed or failed gracefully
		for rule_name, _ in rule_configs.items():
			if rule_name in errors:
				self.assertIsInstance(
					errors[rule_name], list, f"Rule {rule_name} should return a list of errors"
				)


class TestRuleConflictPrevention(BaseIntegrationTest):
	"""Test that rules don't create conflicts or inconsistent results."""

	def test_consistent_component_naming_across_runs(self):
		"""Test that component naming results are consistent across multiple runs."""
		rule_config = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component"],
					"convention": "PascalCase",
					"min_length": 1
				}
			}
		}

		view_file = load_test_view(self.test_cases_dir, "PascalCase")

		# Run the same configuration multiple times
		results = []
		for i in range(3):
			errors = self.run_multiple_rules(view_file, rule_config)
			results.append(errors.get("NamePatternRule", []))

		# All runs should produce identical results
		for i in range(1, len(results)):
			self.assertEqual(results[0], results[i], f"Run {i+1} should produce same results as run 1")

	def test_property_naming_independence(self):
		"""Test that property naming rules work independently of component naming."""
		# Test component naming only
		component_only_config = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component"],
					"convention": "PascalCase"
				}
			}
		}

		# Test property naming only
		property_only_config = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["property"],
					"convention": "camelCase"
				}
			}
		}

		# Test both together
		combined_config = {
			"NamePatternRule": {
				"enabled": True,
				"kwargs": {
					"target_node_types": ["component", "property"],
					"convention": "PascalCase",
					"node_type_specific_rules": {
						"component": {
							"convention": "PascalCase"
						},
						"property": {
							"convention": "camelCase"
						}
					}
				}
			}
		}

		view_file = load_test_view(self.test_cases_dir, "PascalCase")

		component_errors = self.run_multiple_rules(view_file, component_only_config)
		property_errors = self.run_multiple_rules(view_file, property_only_config)
		combined_errors = self.run_multiple_rules(view_file, combined_config)

		# Combined errors should contain both types of errors
		# but each type should be consistent with individual runs
		self.assertIsInstance(component_errors.get("NamePatternRule", []), list)
		self.assertIsInstance(property_errors.get("NamePatternRule", []), list)
		self.assertIsInstance(combined_errors.get("NamePatternRule", []), list)


if __name__ == "__main__":
	unittest.main()
