"""
Helper functions and utilities for ignition-lint tests.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List


def create_mock_view(components: List[Dict[str, Any]], custom_properties: Dict[str, Any] = None) -> str:
	"""
	Create a mock view.json content for testing.

	Args:
		components: List of component definitions
		custom_properties: Additional properties to add to the view

	Returns:
		JSON string representing the view
	"""
	view_data = {"meta": {"name": "root"}, "type": "ia.container.coord", "version": 0, "props": {}}

	if custom_properties:
		view_data["props"].update(custom_properties)

	# Add components as children
	if components:
		children = {}
		for i, component in enumerate(components):
			child_name = component.get("name", f"Component_{i}")
			children[child_name] = {
				"meta": {
					"name": child_name
				},
				"type": component.get("type", "ia.display.label"),
				"props": component.get("props", {})
			}

			# Add any additional component properties
			for key, value in component.items():
				if key not in ["name", "type", "props"]:
					children[child_name][key] = value

		view_data["props"]["children"] = children

	return json.dumps(view_data, indent=2)


def create_temp_view_file(view_content: str) -> Path:
	"""
	Create a temporary view.json file with the given content.

	Args:
		view_content: JSON content for the view file

	Returns:
		Path to the temporary file
	"""
	with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
		f.write(view_content)
		return Path(f.name)


def assert_rule_errors(
	errors: Dict[str, List[str]], rule_name: str, expected_count: int = None, error_patterns: List[str] = None
):
	"""
	Assert that a rule has the expected errors.

	Args:
		errors: Dictionary of errors by rule name
		rule_name: Name of the rule to check
		expected_count: Expected number of errors (optional)
		error_patterns: List of patterns that should be found in errors (optional)
	"""
	rule_errors = errors.get(rule_name, [])

	if expected_count is not None:
		error_msg = f"Rule {rule_name} should have {expected_count} errors but found {len(rule_errors)}: {rule_errors}"
		assert len(rule_errors) == expected_count, error_msg

	if error_patterns:
		for pattern in error_patterns:
			matching_errors = [error for error in rule_errors if pattern in error]
			error_msg = f"Rule {rule_name} should have error containing '{pattern}'. Found errors: {rule_errors}"
			assert len(matching_errors) > 0, error_msg


def assert_no_errors(errors: Dict[str, List[str]], rule_name: str = None):
	"""
	Assert that there are no errors for a specific rule or overall.

	Args:
		errors: Dictionary of errors by rule name
		rule_name: Specific rule to check, or None for all rules
	"""
	if rule_name:
		rule_errors = errors.get(rule_name, [])
		assert rule_errors == [], f"Rule {rule_name} should have no errors but found: {rule_errors}"
	else:
		total_errors = sum(len(rule_errors) for rule_errors in errors.values())
		assert total_errors == 0, f"Should have no errors but found: {errors}"


def get_test_config(rule_name: str, **kwargs) -> Dict[str, Dict[str, Any]]:
	"""
	Create a test configuration for a specific rule.

	Args:
		rule_name: Name of the rule
		**kwargs: Keyword arguments for the rule

	Returns:
		Configuration dictionary
	"""
	return {rule_name: {"enabled": True, "kwargs": kwargs}}


def load_test_view(test_cases_dir: Path, case_name: str) -> Path:
	"""
	Load a test view file by case name.

	Args:
		test_cases_dir: Path to test cases directory
		case_name: Name of the test case subdirectory

	Returns:
		Path to the view.json file
	"""
	view_file = test_cases_dir / case_name / "view.json"
	if not view_file.exists():
		# Debug: show what we're looking for and what exists
		print(f"Looking for: {view_file}")
		print(f"test_cases_dir exists: {test_cases_dir.exists()}")
		if test_cases_dir.exists():
			print(f"Contents of test_cases_dir: {list(test_cases_dir.iterdir())}")
		raise FileNotFoundError(f"Test view file not found: {view_file}")
	return view_file


def create_mock_script(script_type: str, source_code: str, component_name: str = "TestComponent") -> str:
	"""
	Create a mock view.json with a script for testing script-based rules.

	Args:
		script_type: Type of script ("message_handler", "custom_method", "transform", "event_handler")
		source_code: Python source code for the script
		component_name: Name of the component containing the script

	Returns:
		JSON string representing the view with the script
	"""

	if script_type == "message_handler":
		# Message handlers are at root level scripts.messageHandlers
		view_data = {
			"custom": {},
			"params": {},
			"propConfig": {},
			"props": {},
			"root": {
				"children": [
					{
						"meta": {"name": component_name},
						"type": "ia.input.button",
						"props": {"text": "Test Button"}
					}
				],
				"meta": {"name": "root"},
				"type": "ia.container.coord",
				"scripts": {
					"messageHandlers": [
						{
							"messageType": "test_message",
							"script": source_code,
							"pageScope": False,
							"sessionScope": False,
							"viewScope": True
						}
					]
				}
			}
		}

	elif script_type == "custom_method":
		# Custom methods are at component level scripts.customMethods
		view_data = {
			"custom": {},
			"params": {},
			"propConfig": {},
			"props": {},
			"root": {
				"children": [
					{
						"meta": {"name": component_name},
						"type": "ia.input.button",
						"props": {"text": "Test Button"},
						"scripts": {
							"customMethods": [
								{
									"name": "testMethod",
									"params": [],
									"script": source_code
								}
							]
						}
					}
				],
				"meta": {"name": "root"},
				"type": "ia.container.coord"
			}
		}

	elif script_type == "transform":
		# Transform scripts are in binding transforms
		view_data = {
			"custom": {},
			"params": {},
			"propConfig": {
				"root.children[0].props.text": {
					"binding": {
						"type": "property",
						"config": {"path": "view.params.inputValue"},
						"transforms": [
							{
								"type": "script",
								"code": source_code
							}
						]
					}
				}
			},
			"props": {},
			"root": {
				"children": [
					{
						"meta": {"name": component_name},
						"type": "ia.display.label",
						"props": {"text": "Initial Text"}
					}
				],
				"meta": {"name": "root"},
				"type": "ia.container.coord"
			}
		}

	elif script_type == "event_handler":
		# Event handlers are at component level events with domain
		# Format: events.{domain}.{eventType}
		view_data = {
			"custom": {},
			"params": {},
			"propConfig": {},
			"props": {},
			"root": {
				"children": [
					{
						"meta": {"name": component_name},
						"type": "ia.input.button",
						"props": {"text": "Test Button"},
						"events": {
							"component": {
								"onActionPerformed": {
									"config": {
										"script": source_code
									},
									"scope": "G",
									"type": "script"
								}
							}
						}
					}
				],
				"meta": {"name": "root"},
				"type": "ia.container.coord"
			}
		}
	else:
		raise ValueError(f"Unknown script type: {script_type}. Available: message_handler, custom_method, transform, event_handler")

	return json.dumps(view_data, indent=2)
