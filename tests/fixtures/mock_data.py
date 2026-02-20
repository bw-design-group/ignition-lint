"""
Mock data generators for testing ign-lint rules.
"""

from typing import Dict, Any


def create_pascal_case_component(name: str, component_type: str = "ia.display.label") -> Dict[str, Any]:
	"""Create a component with PascalCase naming."""
	return {"name": name, "type": component_type, "props": {"text": f"Text for {name}"}}


def create_camel_case_component(name: str, component_type: str = "ia.display.label") -> Dict[str, Any]:
	"""Create a component with camelCase naming."""
	return {"name": name, "type": component_type, "props": {"text": f"Text for {name}"}}


def create_snake_case_component(name: str, component_type: str = "ia.display.label") -> Dict[str, Any]:
	"""Create a component with snake_case naming."""
	return {"name": name, "type": component_type, "props": {"text": f"Text for {name}"}}


def create_expression_binding(expression: str, polling_rate: int = None) -> Dict[str, Any]:
	"""Create an expression binding for testing."""
	binding = {"type": "expr", "config": {"expression": expression}}

	if polling_rate:
		binding["config"]["pollingRate"] = polling_rate

	return binding


def create_component_with_script(name: str, script_content: str, event_type: str = "onClick") -> Dict[str, Any]:
	"""Create a component with an event script for testing."""
	return {
		"name": name,
		"type": "ia.input.button",
		"props": {
			"text": name
		},
		"events": {
			"dom": {
				event_type: {
					"config": {
						"script": script_content
					}
				}
			}
		}
	}
