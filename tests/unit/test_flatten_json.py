# pylint: disable=import-error,wrong-import-position
"""
Unit tests for the flatten_json module.

Tests the JSON flattening functionality that converts hierarchical JSON
structures into flat path-value pairs for linting processing.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path

# Import the module under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from ignition_lint.common.flatten_json import (
	flatten_json, flatten_file, read_json_file, write_json_file, format_json, preserve_unicode_escapes,
	restore_unicode_escapes
)


class TestFlattenJson(unittest.TestCase):
	"""Test the core flatten_json functionality."""

	def test_flatten_empty_dict(self):
		"""Test flattening an empty dictionary."""
		result = flatten_json({})
		self.assertEqual(result, OrderedDict())

	def test_flatten_simple_dict(self):
		"""Test flattening a simple dictionary with primitive values."""
		data = {"name": "TestComponent", "visible": True, "width": 100, "height": 50}

		result = flatten_json(data)
		expected = OrderedDict([("name", "TestComponent"), ("visible", True), ("width", 100), ("height", 50)])

		self.assertEqual(result, expected)

	def test_flatten_nested_dict(self):
		"""Test flattening nested dictionaries."""
		data = {
			"component": {
				"type": "Button",
				"props": {
					"text": "Click me",
					"style": {
						"color": "blue",
						"fontSize": 14
					}
				}
			}
		}

		result = flatten_json(data)
		expected = OrderedDict([("component.type", "Button"), ("component.props.text", "Click me"),
					("component.props.style.color", "blue"),
					("component.props.style.fontSize", 14)])

		self.assertEqual(result, expected)

	def test_flatten_with_lists(self):
		"""Test flattening structures with lists."""
		data = {"items": ["item1", "item2", "item3"], "nested": {"numbers": [1, 2, 3]}}

		result = flatten_json(data)
		expected = OrderedDict([("items[0]", "item1"), ("items[1]", "item2"), ("items[2]", "item3"),
					("nested.numbers[0]", 1), ("nested.numbers[1]", 2), ("nested.numbers[2]", 3)])

		self.assertEqual(result, expected)

	def test_flatten_list_with_objects(self):
		"""Test flattening lists containing objects."""
		data = {"children": [{"name": "child1", "type": "Button"}, {"name": "child2", "type": "Label"}]}

		result = flatten_json(data)
		expected = OrderedDict([("children[0].name", "child1"), ("children[0].type", "Button"),
					("children[1].name", "child2"), ("children[1].type", "Label")])

		self.assertEqual(result, expected)

	def test_flatten_with_component_name(self):
		"""Test flattening with component names that affect path structure."""
		data = {"meta": {"name": "MyButton"}, "type": "ia.input.button", "props": {"text": "Click me"}}

		result = flatten_json(data)
		expected = OrderedDict([("MyButton.meta.name", "MyButton"), ("MyButton.type", "ia.input.button"),
					("MyButton.props.text", "Click me")])

		self.assertEqual(result, expected)

	def test_flatten_root_list(self):
		"""Test flattening when the root element is a list."""
		data = ["item1", "item2", {"nested": "value"}]

		result = flatten_json(data)
		expected = OrderedDict([("[0]", "item1"), ("[1]", "item2"), ("[2].nested", "value")])

		self.assertEqual(result, expected)

	def test_flatten_complex_ignition_structure(self):
		"""Test flattening a structure similar to Ignition view components."""
		data = {
			"meta": {
				"name": "Root"
			},
			"type": "ia.container.flex",
			"props": {
				"direction": "column",
				"style": {
					"classes": ""
				}
			},
			"children": [{
				"meta": {
					"name": "Button_0"
				},
				"type": "ia.input.button",
				"props": {
					"text": "Submit",
					"events": {
						"onActionPerformed": {
							"enabled": True,
							"script": "print('clicked')"
						}
					}
				}
			}]
		}

		result = flatten_json(data)

		# Check a few key paths to ensure proper structure
		self.assertIn("Root.meta.name", result)
		self.assertIn("Root.children[0].Button_0.props.text", result)
		self.assertEqual(result["Root.children[0].Button_0.props.text"], "Submit")
		self.assertIn("Root.children[0].Button_0.props.events.onActionPerformed.script", result)

	def test_flatten_empty_list(self):
		"""Empty lists are preserved as [] leaves so they stay visible to the model."""
		data = {"items": [], "nested": {"empty": []}}

		result = flatten_json(data)
		# An empty array is still a value; dropping it would make properties like an
		# empty custom list invisible to every rule (and undeletable by --fix).
		expected = OrderedDict([("items", []), ("nested.empty", [])])

		self.assertEqual(result, expected)

	def test_flatten_empty_nested_dict(self):
		"""Empty dicts are preserved as {} leaves so they stay visible to the model."""
		data = {"custom": {"emptyMeta": {}}, "filled": {"a": 1}}

		result = flatten_json(data)
		expected = OrderedDict([("custom.emptyMeta", {}), ("filled.a", 1)])

		self.assertEqual(result, expected)

	def test_flatten_mixed_types(self):
		"""Test flattening with mixed primitive types."""
		data = {
			"string": "text",
			"number": 42,
			"float": 3.14,
			"boolean": True,
			"null": None,
			"mixed_list": [1, "two", True, None]
		}

		result = flatten_json(data)

		self.assertEqual(result["string"], "text")
		self.assertEqual(result["number"], 42)
		self.assertEqual(result["float"], 3.14)
		self.assertEqual(result["boolean"], True)
		self.assertIsNone(result["null"])
		self.assertEqual(result["mixed_list[0]"], 1)
		self.assertEqual(result["mixed_list[1]"], "two")
		self.assertEqual(result["mixed_list[2]"], True)
		self.assertIsNone(result["mixed_list[3]"])


class TestFileOperations(unittest.TestCase):
	"""Test file I/O operations for JSON processing."""

	def setUp(self):  # pylint: disable=invalid-name
		"""Set up temporary files for testing."""
		self.temp_dir = Path(tempfile.mkdtemp())

	def tearDown(self):  # pylint: disable=invalid-name
		"""Clean up temporary files."""
		if self.temp_dir.exists():
			shutil.rmtree(self.temp_dir)

	def test_read_json_file(self):
		"""Test reading a JSON file."""
		test_data = {"name": "test", "value": 123}
		test_file = self.temp_dir / "test.json"

		with test_file.open("w", encoding="utf-8") as f:
			json.dump(test_data, f)

		result = read_json_file(test_file)
		self.assertEqual(result, test_data)

	def test_write_json_file(self):
		"""Test writing a JSON file."""
		test_data = {"name": "test", "value": 123}
		test_file = self.temp_dir / "output.json"

		write_json_file(test_file, test_data)

		# Verify the file was written correctly
		with test_file.open("r", encoding="utf-8") as f:
			result = json.load(f)

		self.assertEqual(result, test_data)

	def test_flatten_file(self):
		"""Test the flatten_file convenience function."""
		test_data = {"component": {"name": "TestButton", "props": {"text": "Click"}}}
		test_file = self.temp_dir / "view.json"

		with test_file.open("w", encoding="utf-8") as f:
			json.dump(test_data, f)

		result = flatten_file(test_file)

		self.assertIsInstance(result, OrderedDict)
		self.assertIn("component.name", result)
		self.assertEqual(result["component.name"], "TestButton")

	def test_format_json(self):
		"""Test JSON formatting."""
		data = {"name": "test", "nested": {"value": 123}}
		result = format_json(data)

		# Should be properly indented
		self.assertIn("  ", result)  # 2-space indentation
		# Should not have trailing whitespace
		lines = result.split('\n')
		for line in lines:
			self.assertEqual(line, line.rstrip())


class TestUnicodeHandling(unittest.TestCase):
	"""Test Unicode escape handling functionality."""

	def test_preserve_unicode_escapes(self):
		"""Test preserving Unicode escapes in text."""
		text = "Value with \\u003c and \\u003e symbols"
		result = preserve_unicode_escapes(text)

		self.assertNotIn("\\u003c", result)
		self.assertNotIn("\\u003e", result)
		self.assertIn("UNICODE_LT", result)
		self.assertIn("UNICODE_GT", result)

	def test_restore_unicode_escapes(self):
		"""Test restoring Unicode escapes from placeholders."""
		text = "Value with UNICODE_LT and UNICODE_GT symbols"
		result = restore_unicode_escapes(text)

		self.assertNotIn("UNICODE_LT", result)
		self.assertNotIn("UNICODE_GT", result)
		self.assertIn("\\u003c", result)
		self.assertIn("\\u003e", result)

	def test_unicode_roundtrip(self):
		"""Test that preserve and restore are inverse operations."""
		original = "Text with \\u003c, \\u003e, \\u0026, \\u003d, \\u0027"
		preserved = preserve_unicode_escapes(original)
		restored = restore_unicode_escapes(preserved)

		self.assertEqual(original, restored)


if __name__ == '__main__':
	unittest.main()
