# pylint: disable=import-error
"""
Unit tests for the NamePatternRule.
Tests various naming conventions and edge cases for different node types.
"""

import unittest
from typing import Dict, Any

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, load_test_view


class TestNamePatternPascalCase(BaseRuleTest):
	"""Test PascalCase naming convention for components."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="PascalCase", allow_numbers=True,
			min_length=1, severity="error"
		)

	def test_pascal_case_passes_pascal_case_rule(self):
		"""PascalCase view should pass PascalCase rule."""
		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.assert_rule_passes(view_file, self.rule_config, "NamePatternRule")

	def test_camel_case_fails_pascal_case_rule(self):
		"""camelCase view should fail PascalCase rule."""
		view_file = load_test_view(self.test_cases_dir, "camelCase")
		self.assert_rule_fails(view_file, self.rule_config, "NamePatternRule")

	def test_snake_case_fails_pascal_case_rule(self):
		"""snake_case view should fail PascalCase rule."""
		view_file = load_test_view(self.test_cases_dir, "snake_case")
		self.assert_rule_fails(view_file, self.rule_config, "NamePatternRule")

	def test_inconsistent_case_fails_pascal_case_rule(self):
		"""inconsistentCase view should fail PascalCase rule."""
		view_file = load_test_view(self.test_cases_dir, "inconsistentCase")
		self.assert_rule_fails(view_file, self.rule_config, "NamePatternRule")


class TestNamePatternCamelCase(BaseRuleTest):
	"""Test camelCase naming convention for components."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="camelCase", allow_numbers=True,
			min_length=1, severity="error"
		)

	def test_camel_case_passes_camel_case_rule(self):
		"""camelCase view should pass camelCase rule."""
		view_file = load_test_view(self.test_cases_dir, "camelCase")
		self.assert_rule_passes(view_file, self.rule_config, "NamePatternRule")

	def test_pascal_case_fails_camel_case_rule(self):
		"""PascalCase view should fail camelCase rule."""
		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.assert_rule_fails(view_file, self.rule_config, "NamePatternRule")

	def test_snake_case_fails_camel_case_rule(self):
		"""snake_case view should fail camelCase rule."""
		view_file = load_test_view(self.test_cases_dir, "snake_case")
		self.assert_rule_fails(view_file, self.rule_config, "NamePatternRule")


class TestNamePatternSnakeCase(BaseRuleTest):
	"""Test snake_case naming convention for components."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="snake_case", allow_numbers=True,
			min_length=1, severity="error"
		)

	def test_snake_case_passes_snake_case_rule(self):
		"""snake_case view should pass snake_case rule."""
		view_file = load_test_view(self.test_cases_dir, "snake_case")
		self.assert_rule_passes(view_file, self.rule_config, "NamePatternRule")

	def test_pascal_case_fails_snake_case_rule(self):
		"""PascalCase view should fail snake_case rule."""
		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.assert_rule_fails(view_file, self.rule_config, "NamePatternRule")

	def test_camel_case_fails_snake_case_rule(self):
		"""camelCase view should fail snake_case rule."""
		view_file = load_test_view(self.test_cases_dir, "camelCase")
		self.assert_rule_fails(view_file, self.rule_config, "NamePatternRule")


class TestNamePatternKebabCase(BaseRuleTest):
	"""Test kebab-case naming convention for components."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="kebab-case", allow_numbers=True,
			min_length=1
		)

	def test_kebab_case_passes_kebab_case_rule(self):
		"""kebab-case view should pass kebab-case rule."""
		view_file = load_test_view(self.test_cases_dir, "kebab-case")
		self.assert_rule_passes(view_file, self.rule_config, "NamePatternRule")


class TestNamePatternMultipleNodeTypes(BaseRuleTest):
	"""Test naming conventions applied to multiple node types."""

	def test_components_pascal_case_properties_camel_case(self):
		"""Test PascalCase for components and camelCase for properties."""
		rule_config = get_test_config(
			"NamePatternRule",
			target_node_types=["component", "property"],
			convention="PascalCase",  # Default convention for components
			node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"min_length": 1
				},
				"property": {
					"convention": "camelCase",
					"min_length": 1
				}
			}
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_components_and_custom_methods_same_convention(self):
		"""Test applying same convention to components and custom methods."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component", "custom_method"], convention="camelCase",
			min_length=3
		)

		view_file = load_test_view(self.test_cases_dir, "camelCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_different_conventions_per_node_type(self):
		"""Test different naming conventions for different node types."""
		rule_config = get_test_config(
			"NamePatternRule",
			target_node_types=["component", "custom_method", "message_handler"],
			convention="camelCase",  # Default convention
			node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"min_length": 1
				},
				"custom_method": {
					"convention": "camelCase",
					"min_length": 3
				},
				"message_handler": {
					"convention": "snake_case",
					"min_length": 4
				}
			}
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)


class TestNamePatternMixedCase(BaseRuleTest):
	"""Test mixed PascalCase OR SCREAMING_SNAKE_CASE pattern."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], node_type_specific_rules={
				"component": {
					"pattern": "^([A-Z][a-zA-Z0-9]*|[A-Z][A-Z0-9_]*)$",
					"pattern_description": "PascalCase or SCREAMING_SNAKE_CASE",
					"suggestion_convention": "PascalCase",
					"min_length": 3,
					"severity": "error"
				}
			}
		)

	def test_pascal_case_passes(self):
		"""PascalCase component names should pass the mixed pattern."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# PascalCaseButton should pass
		pascal_case_errors = [e for e in errors if "PascalCaseButton" in e]
		self.assertEqual(len(pascal_case_errors), 0, "PascalCaseButton should pass")

	def test_screaming_snake_case_passes(self):
		"""SCREAMING_SNAKE_CASE component names should pass the mixed pattern."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# SCREAMING_SNAKE_CASE_LABEL should pass
		screaming_errors = [e for e in errors if "SCREAMING_SNAKE_CASE_LABEL" in e]
		self.assertEqual(len(screaming_errors), 0, "SCREAMING_SNAKE_CASE_LABEL should pass")

	def test_mixed_with_numbers_passes(self):
		"""Components with numbers should pass in both formats."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# DAT_02_TT_123_A should pass (SCREAMING_SNAKE_CASE with numbers)
		dat_errors = [e for e in errors if "DAT_02_TT_123_A" in e]
		self.assertEqual(len(dat_errors), 0, "DAT_02_TT_123_A should pass")

		# MyComponentWithNumbers123 should pass (PascalCase with numbers)
		pascal_num_errors = [e for e in errors if "MyComponentWithNumbers123" in e]
		self.assertEqual(len(pascal_num_errors), 0, "MyComponentWithNumbers123 should pass")

		# UPPER_WITH_NUMBERS_456 should pass (SCREAMING_SNAKE_CASE with numbers)
		upper_num_errors = [e for e in errors if "UPPER_WITH_NUMBERS_456" in e]
		self.assertEqual(len(upper_num_errors), 0, "UPPER_WITH_NUMBERS_456 should pass")

	def test_camel_case_fails(self):
		"""camelCase should fail the mixed pattern."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# camelCaseInvalid should fail
		camel_errors = [e for e in errors if "camelCaseInvalid" in e]
		self.assertGreater(len(camel_errors), 0, "camelCaseInvalid should fail")
		self.assertIn("doesn't follow PascalCase or SCREAMING_SNAKE_CASE", camel_errors[0])

	def test_snake_case_fails(self):
		"""snake_case should fail the mixed pattern."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# snake_case_invalid should fail
		snake_errors = [e for e in errors if "snake_case_invalid" in e]
		self.assertGreater(len(snake_errors), 0, "snake_case_invalid should fail")

	def test_kebab_case_fails(self):
		"""kebab-case should fail the mixed pattern."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# kebab-case-invalid should fail
		kebab_errors = [e for e in errors if "kebab-case-invalid" in e]
		self.assertGreater(len(kebab_errors), 0, "kebab-case-invalid should fail")

	def test_mixed_pascal_snake_fails(self):
		"""Mixed PascalCase and snake_case should fail."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# Mixed_PascalCase_Invalid should fail (lowercase with underscores)
		mixed_errors = [e for e in errors if "Mixed_PascalCase_Invalid" in e]
		self.assertGreater(len(mixed_errors), 0, "Mixed_PascalCase_Invalid should fail")

	def test_suggestions_provided(self):
		"""Verify that suggestions are provided for invalid names."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# Check that errors include suggestions
		camel_errors = [e for e in errors if "camelCaseInvalid" in e]
		self.assertGreater(len(camel_errors), 0)
		self.assertIn("suggestion:", camel_errors[0], "Error should include suggestion")
		self.assertIn("CamelCaseInvalid", camel_errors[0], "Suggestion should be PascalCase")

	def test_abbreviations_in_pascal_case(self):
		"""Test that abbreviations in PascalCase format pass validation."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# Test various abbreviation patterns in PascalCase
		abbreviation_tests = [
			("APIClient", "Abbreviation at start of PascalCase"),
			("HTTPSConnection", "Multiple uppercase letters in PascalCase"),
			("MyAPIHandler", "Abbreviation in middle of PascalCase"),
			("XMLHTTPRequest", "Multiple abbreviations in PascalCase"),
			("IOModuleController", "IO abbreviation in PascalCase"),
		]

		for name, description in abbreviation_tests:
			with self.subTest(name=name, description=description):
				name_errors = [e for e in errors if name in e]
				self.assertEqual(len(name_errors), 0, f"{name} should pass validation ({description})")

	def test_abbreviations_in_screaming_snake_case(self):
		"""Test that abbreviations in SCREAMING_SNAKE_CASE format pass validation."""
		view_file = load_test_view(self.test_cases_dir, "MixedCase")
		self.run_lint_on_file(view_file, self.rule_config)
		errors = self.get_errors_for_rule("NamePatternRule")

		# Test various abbreviation patterns in SCREAMING_SNAKE_CASE
		abbreviation_tests = [
			("API_CLIENT_HTTP", "Multiple abbreviations in SCREAMING_SNAKE_CASE"),
			("HTTP_API_URL", "Abbreviations with underscores"),
			("TT_DAT_API_123", "Abbreviations with numbers"),
			("CPU_GPU_MONITOR", "Hardware abbreviations"),
		]

		for name, description in abbreviation_tests:
			with self.subTest(name=name, description=description):
				name_errors = [e for e in errors if name in e]
				self.assertEqual(len(name_errors), 0, f"{name} should pass validation ({description})")


class TestNamePatternEdgeCases(BaseRuleTest):
	"""Test edge cases for naming pattern rules."""

	def test_min_length_validation(self):
		"""Test minimum length validation."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="PascalCase", min_length=5
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify the rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_max_length_validation(self):
		"""Test maximum length validation."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="PascalCase", min_length=1,
			max_length=10
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify the rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_numbers_allowed_vs_disallowed(self):
		"""Test allowing/disallowing numbers in component names."""
		rule_config_with_numbers = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="PascalCase", allow_numbers=True
		)

		rule_config_no_numbers = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="PascalCase", allow_numbers=False
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")

		# Run both configs and verify they both work (results may differ)
		self.run_lint_on_file(view_file, rule_config_with_numbers)
		errors_with_numbers = self.get_errors_for_rule("NamePatternRule")
		self.run_lint_on_file(view_file, rule_config_no_numbers)
		errors_no_numbers = self.get_errors_for_rule("NamePatternRule")

		self.assertIsInstance(errors_with_numbers, list)
		self.assertIsInstance(errors_no_numbers, list)

	def test_forbidden_names(self):
		"""Test forbidden component names."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="PascalCase",
			forbidden_names=["Button", "Label", "Panel"]
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify the rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_custom_abbreviations(self):
		"""Test custom abbreviations handling."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="PascalCase",
			allowed_abbreviations=["API", "HTTP", "XML"], auto_detect_abbreviations=False
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify the rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_skip_names(self):
		"""Test skipping certain names from validation."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"], convention="PascalCase",
			skip_names=["root", "main", "container"]
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify the rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_custom_pattern(self):
		"""Test custom regex pattern instead of predefined conventions."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component"],
			custom_pattern=r"^(btn|lbl|pnl)[A-Z][a-zA-Z0-9]*$", min_length=4, max_length=25
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		# Verify the rule runs without crashing
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)


class TestNamePatternSpecificNodeTypes(BaseRuleTest):
	"""Test naming patterns for specific node types beyond components."""

	def test_custom_method_naming(self):
		"""Test naming validation for custom methods."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["custom_method"], convention="camelCase", min_length=3,
			forbidden_names=["method", "function", "temp"]
		)

		# This test assumes your test views have custom methods
		# You might need to create specific test views with custom methods
		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_message_handler_naming(self):
		"""Test naming validation for message handlers."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["message_handler"], convention="snake_case", min_length=4,
			forbidden_names=["handler", "msg", "temp"]
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_property_naming_camel_case(self):
		"""Test naming validation for properties using camelCase."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", min_length=2,
			forbidden_names=["temp", "tmp", "test", "data"]
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)

		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	# test_event_handler_naming intentionally removed - event handler names are framework-defined
	# Event handlers like onActionPerformed, onClick, etc. are predefined by Ignition and cannot be renamed


class TestStandardNamingConventions(BaseRuleTest):
	"""Test the standard conventions: PascalCase for components, camelCase for properties."""

	def test_standard_component_property_conventions(self):
		"""Test the standard: PascalCase components, camelCase properties."""
		rule_config = get_test_config(
			"NamePatternRule",
			target_node_types=["component", "property"],
			convention="PascalCase",  # Default
			node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"min_length": 1,
					"allow_numbers": True
				},
				"property": {
					"convention": "camelCase",
					"min_length": 1,
					"allow_numbers": True,
					"skip_names": ["id", "x", "y", "z"]  # Common short property names
				}
			}
		)

		# Test with different view files
		test_cases = ["PascalCase", "camelCase"]
		for case in test_cases:
			with self.subTest(case=case):
				try:
					view_file = load_test_view(self.test_cases_dir, case)
					self.run_lint_on_file(view_file, rule_config)
					self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)
				except FileNotFoundError:
					self.skipTest(f"Test case {case} not found")

	def test_mixed_node_types_with_appropriate_conventions(self):
		"""Test multiple node types with their appropriate conventions."""
		rule_config = get_test_config(
			"NamePatternRule",
			target_node_types=["component", "property", "custom_method", "message_handler"],
			convention="PascalCase",  # Default
			node_type_specific_rules={
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
				"message_handler": {
					"convention": "camelCase",
					"min_length": 2
				}
			}
		)

		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, rule_config)
		self.assertIsInstance(self.get_errors_for_rule("NamePatternRule"), list)

	def test_pascal_case_components_camel_case_properties(self):
		"""Test that components follow PascalCase and properties follow camelCase."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component", "property"], node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"severity": "error"
				},
				"property": {
					"convention": "camelCase",
					"severity": "warning"
				}
			}
		)

		# Test with PascalCase view - components should pass, properties should fail
		view_file = load_test_view(self.test_cases_dir, "PascalCase")

		# Should have warnings for properties not following camelCase
		self.assert_rule_warnings(
			view_file,
			rule_config,
			"NamePatternRule",
			expected_warning_count=4,  # All custom properties are PascalCase
			warning_patterns=["doesn't follow camelCase", "property"]
		)

		# Should have no errors for components (they follow PascalCase)
		self.assert_rule_errors(view_file, rule_config, "NamePatternRule", expected_error_count=0)

	def test_camel_case_components_pascal_case_properties_fails(self):
		"""Test camelCase components with PascalCase properties - should produce errors and warnings."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["component", "property"], node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"severity": "error"
				},
				"property": {
					"convention": "camelCase",
					"severity": "warning"
				}
			}
		)

		# Test with camelCase view - components should fail PascalCase, properties should fail camelCase
		view_file = load_test_view(self.test_cases_dir, "camelCase")

		# Should have errors for components not following PascalCase
		self.assert_rule_errors(
			view_file,
			rule_config,
			"NamePatternRule",
			expected_error_count=1,  # The iconCamelCase component
			error_patterns=["doesn't follow PascalCase", "component"]
		)

		# Should have no warnings since properties are already camelCase
		# The camelCase view has camelCase properties, so they should pass the camelCase rule
		results = self.run_lint_on_file(view_file, rule_config)
		rule_warnings = results.warnings.get("NamePatternRule", [])
		self.assertEqual(len(rule_warnings), 0)

	def test_auto_derived_target_node_types(self):
		"""Test that target_node_types can be auto-derived from node_type_specific_rules."""
		rule_config = get_test_config(
			"NamePatternRule",
			# No explicit target_node_types provided
			node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"severity": "warning"
				},
				"property": {
					"convention": "camelCase",
					"severity": "warning"
				}
			}
		)

		# Test with PascalCase view - should validate both components and properties
		view_file = load_test_view(self.test_cases_dir, "PascalCase")

		# Should have warnings for properties (they don't follow camelCase)
		self.assert_rule_warnings(
			view_file,
			rule_config,
			"NamePatternRule",
			expected_warning_count=4,  # All properties are PascalCase instead of camelCase
			warning_patterns=["doesn't follow camelCase", "property"]
		)

		# Should have no errors since severity is set to warning
		self.assert_rule_errors(view_file, rule_config, "NamePatternRule", expected_error_count=0)


class TestNamePatternArrayProperties(BaseRuleTest):
	"""Test that array properties are treated as a single property, not multiple properties."""

	def test_array_property_validated_once(self):
		"""Array property should be validated once for the base name, not once per element."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with an array property that violates camelCase
		view_data = {
			"custom": {
				"MyArrayProperty": ["item1", "item2", "item3"]  # PascalCase - should fail
			},
			"params": {},
			"props": {},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Run the linter
			self.run_lint_on_file(view_file, rule_config)
			errors = self.get_errors_for_rule("NamePatternRule")

			# Should have exactly 1 error for MyArrayProperty, not 3 (one per element)
			self.assertEqual(
				len(errors), 1, f"Expected 1 error for array property, got {len(errors)}: {errors}"
			)

			# Error should reference the base property name, not an indexed element
			self.assertIn("MyArrayProperty", errors[0])
			self.assertNotIn("[0]", errors[0], "Error should not reference array index [0]")
			self.assertNotIn("[1]", errors[0], "Error should not reference array index [1]")
			self.assertNotIn("[2]", errors[0], "Error should not reference array index [2]")
		finally:
			view_file.unlink()

	def test_array_property_with_valid_name(self):
		"""Array property with valid name should pass validation."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with an array property that follows camelCase
		view_data = {
			"custom": {
				"myArrayProperty": ["item1", "item2", "item3"]  # camelCase - should pass
			},
			"params": {},
			"props": {},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Array property with valid name should pass
			self.assert_rule_passes(view_file, rule_config, "NamePatternRule")
		finally:
			view_file.unlink()


class TestNamePatternCSSProperties(BaseRuleTest):
	"""Test that CSS properties in style and elementStyle are not flagged as violations."""

	def test_css_properties_in_style_should_pass(self):
		"""CSS properties in style objects should not be flagged by property naming rules."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with CSS properties in style
		view_data = {
			"custom": {},
			"params": {},
			"props": {},
			"root": {
				"meta": {
					"name": "root"
				},
				"props": {
					"style": {
						"touch-action": "none",
						"background-color": "#ffffff",
						"font-size": "14px",
						"z-index": "100"
					}
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# CSS properties should NOT be flagged as violations
			self.assert_rule_passes(view_file, rule_config, "NamePatternRule")
		finally:
			view_file.unlink()

	def test_css_properties_in_element_style_should_pass(self):
		"""CSS properties in elementStyle (flex repeater) should not be flagged."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with CSS properties in elementStyle
		view_data = {
			"custom": {},
			"params": {},
			"props": {},
			"root": {
				"children": [{
					"meta": {
						"name": "FlexRepeater"
					},
					"props": {
						"elementStyle": {
							"display": "flex",
							"flex-direction": "row",
							"align-items": "center"
						}
					},
					"type": "ia.container.flex"
				}],
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# CSS properties should NOT be flagged as violations
			self.assert_rule_passes(view_file, rule_config, "NamePatternRule")
		finally:
			view_file.unlink()

	def test_regular_properties_still_validated(self):
		"""Regular properties (not in style) should still be validated."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with regular properties that violate camelCase
		view_data = {
			"custom": {
				"BadPropertyName": "value",  # PascalCase - should fail camelCase rule
				"another-bad-name": "value"  # kebab-case - should fail camelCase rule
			},
			"params": {},
			"props": {},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Regular properties SHOULD be flagged as violations
			self.assert_rule_fails(view_file, rule_config, "NamePatternRule")
		finally:
			view_file.unlink()


class TestNamePatternSVGProperties(BaseRuleTest):
	"""Test that SVG path properties (props.elements.d) are not flagged as violations."""

	def test_svg_path_properties_should_pass(self):
		"""SVG path data properties should not be flagged by property naming rules."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with SVG path data in props.elements array (real-world structure)
		view_data = {
			"custom": {},
			"params": {},
			"props": {},
			"root": {
				"children": [{
					"meta": {
						"name": "Line1"
					},
					"position": {
						"height": 0.125,
						"width": 0.0222,
						"x": 0.25,
						"y": 0.088
					},
					"props": {
						"elements": [{
							"d": "M5 15 c5 -5, 10 -5, 15 0 c5 5, 10 5, 15 0 m-15 0 v110",  # SVG path in array
							"type": "path"
						}],
						"fill": {
							"paint": "transparent"
						}
					},
					"type": "ia.shapes.svg"
				}],
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# SVG path properties should NOT be flagged as violations
			self.assert_rule_passes(view_file, rule_config, "NamePatternRule")
		finally:
			view_file.unlink()

	def test_svg_paths_skipped_but_other_props_validated(self):
		"""SVG path properties should be skipped while other properties are still validated."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with SVG paths and custom properties
		view_data = {
			"custom": {
				"BadPropertyName": "value"  # PascalCase - should fail camelCase rule
			},
			"params": {},
			"props": {
				"elements": {
					"d": "M10 10 L20 20"  # SVG path - should be skipped
				}
			},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Should fail because of BadPropertyName, but not because of SVG path
			self.run_lint_on_file(view_file, rule_config)
			errors = self.get_errors_for_rule("NamePatternRule")

			# Should have exactly 1 error for BadPropertyName
			self.assertEqual(
				len(errors), 1, f"Expected 1 error for BadPropertyName, got {len(errors)}: {errors}"
			)

			# Error should be about BadPropertyName, not SVG path
			self.assertIn("BadPropertyName", errors[0])
			self.assertNotIn("props.elements.d", errors[0])
		finally:
			view_file.unlink()


class TestNamePatternPositionProperties(BaseRuleTest):
	"""Test that position properties (.position.x, .position.y) are not flagged as violations."""

	def test_position_properties_should_pass(self):
		"""Position properties (x, y coordinates) should not be flagged by property naming rules."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with position properties
		view_data = {
			"custom": {},
			"params": {},
			"props": {},
			"root": {
				"children": [{
					"meta": {
						"name": "Button"
					},
					"position": {
						"x": 100,
						"y": 200,
						"width": 150,
						"height": 50
					},
					"type": "ia.display.button"
				}, {
					"meta": {
						"name": "Label"
					},
					"position": {
						"x": 300,
						"y": 400
					},
					"type": "ia.display.label"
				}],
				"meta": {
					"name": "root"
				},
				"position": {
					"x": 0,
					"y": 0
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Position properties should NOT be flagged as violations
			self.assert_rule_passes(view_file, rule_config, "NamePatternRule")
		finally:
			view_file.unlink()

	def test_position_properties_with_custom_properties(self):
		"""Position properties should be skipped while custom properties are still validated."""
		rule_config = get_test_config(
			"NamePatternRule", target_node_types=["property"], convention="camelCase", severity="error"
		)

		# Create a view with both position and custom properties
		view_data = {
			"custom": {
				"BadPropertyName": "value"  # PascalCase - should fail camelCase rule
			},
			"params": {},
			"props": {},
			"root": {
				"meta": {
					"name": "root"
				},
				"position": {
					"x": 0,  # Should be skipped
					"y": 0  # Should be skipped
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Should fail because of BadPropertyName, but not because of x/y
			self.run_lint_on_file(view_file, rule_config)
			errors = self.get_errors_for_rule("NamePatternRule")

			# Should have exactly 1 error for BadPropertyName
			self.assertEqual(
				len(errors), 1, f"Expected 1 error for BadPropertyName, got {len(errors)}: {errors}"
			)

			# Error should be about BadPropertyName, not x or y
			self.assertIn("BadPropertyName", errors[0])
			self.assertNotIn("position.x", errors[0])
			self.assertNotIn("position.y", errors[0])
		finally:
			view_file.unlink()


class TestNamePatternPerNodeTypeSeverity(BaseRuleTest):
	"""Test per-node-type severity configuration."""

	def test_component_error_severity(self):
		"""Test that component naming violations are reported as errors when severity='error'."""
		rule_config = get_test_config(
			"NamePatternRule",
			node_type_specific_rules={"component": {
				"convention": "PascalCase",
				"severity": "error"
			}}
		)

		# Create a view with a camelCase component (should fail PascalCase)
		view_data = {
			"custom": {},
			"params": {},
			"props": {},
			"root": {
				"children": [{
					"meta": {
						"name": "badComponent"  # camelCase - should fail
					},
					"type": "ia.display.button"
				}],
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Run the linter
			self.run_lint_on_file(view_file, rule_config)

			# Should be in errors, not warnings
			rule_errors = self.get_errors_for_rule("NamePatternRule")
			rule_warnings = self.get_warnings_for_rule("NamePatternRule")

			self.assertEqual(len(rule_errors), 1, "Should report as error when severity='error'")
			self.assertEqual(len(rule_warnings), 0, "Should not report as warning when severity='error'")
			self.assertIn("badComponent", rule_errors[0])
		finally:
			view_file.unlink()

	def test_property_warning_severity(self):
		"""Test that property naming violations are reported as warnings when severity='warning'."""
		rule_config = get_test_config(
			"NamePatternRule",
			node_type_specific_rules={"property": {
				"convention": "camelCase",
				"severity": "warning"
			}}
		)

		# Create a view with a PascalCase property (should fail camelCase)
		view_data = {
			"custom": {
				"BadPropertyName": "value"  # PascalCase - should fail camelCase
			},
			"params": {},
			"props": {},
			"root": {
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Run the linter
			self.run_lint_on_file(view_file, rule_config)

			# Should be in warnings, not errors
			rule_errors = self.get_errors_for_rule("NamePatternRule")
			rule_warnings = self.get_warnings_for_rule("NamePatternRule")

			self.assertEqual(len(rule_errors), 0, "Should not report as error when severity='warning'")
			self.assertEqual(len(rule_warnings), 1, "Should report as warning when severity='warning'")
			self.assertIn("BadPropertyName", rule_warnings[0])
		finally:
			view_file.unlink()

	def test_mixed_severity_per_node_type(self):
		"""Test that different node types can have different severity levels."""
		rule_config = get_test_config(
			"NamePatternRule", node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"severity": "error"
				},
				"property": {
					"convention": "camelCase",
					"severity": "warning"
				}
			}
		)

		# Create a view with violations in both components and properties
		view_data = {
			"custom": {
				"BadPropertyName": "value"  # PascalCase - should be warning
			},
			"params": {},
			"props": {},
			"root": {
				"children": [{
					"meta": {
						"name": "badComponent"  # camelCase - should be error
					},
					"type": "ia.display.button"
				}],
				"meta": {
					"name": "root"
				},
				"type": "ia.container.coord"
			}
		}

		# Write test view file
		import json
		import tempfile
		from pathlib import Path
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			json.dump(view_data, f)
			view_file = Path(f.name)

		try:
			# Run the linter
			self.run_lint_on_file(view_file, rule_config)

			# Should have 1 error (component) and 1 warning (property)
			rule_errors = self.get_errors_for_rule("NamePatternRule")
			rule_warnings = self.get_warnings_for_rule("NamePatternRule")

			self.assertEqual(len(rule_errors), 1, "Should have 1 error for component")
			self.assertEqual(len(rule_warnings), 1, "Should have 1 warning for property")

			self.assertIn("badComponent", rule_errors[0])
			self.assertIn("component", rule_errors[0])

			self.assertIn("BadPropertyName", rule_warnings[0])
			self.assertIn("property", rule_warnings[0])
		finally:
			view_file.unlink()

	def test_all_node_types_with_different_severities(self):
		"""Test all supported node types with different severity configurations."""
		rule_config = get_test_config(
			"NamePatternRule", node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"severity": "error"
				},
				"property": {
					"convention": "camelCase",
					"severity": "warning"
				},
				"message_handler": {
					"convention": "kebab-case",
					"severity": "warning"
				},
				"custom_method": {
					"convention": "snake_case",
					"severity": "error"
				}
			}
		)

		# Test with a view that has all node types
		view_file = load_test_view(self.test_cases_dir, "PascalCase")

		# Run the linter
		results = self.run_lint_on_file(view_file, rule_config)

		# Verify that we can get both errors and warnings
		rule_errors = results.errors.get("NamePatternRule", [])
		rule_warnings = results.warnings.get("NamePatternRule", [])

		# Should have both errors and warnings (exact counts depend on test case content)
		self.assertIsInstance(rule_errors, list)
		self.assertIsInstance(rule_warnings, list)


if __name__ == "__main__":
	unittest.main()
