"""
This module takes a JSON file and flattens it based on the defined features.
"""

import json
import logging
import sys
import re
from collections import OrderedDict
from pathlib import Path

# Characters that Ignition Perspective encodes as unicode escapes in view.json.
# These are valid ASCII but Ignition uses escapes for HTML/XSS safety.
# After json.loads decodes them, we must re-encode on write.
IGNITION_UNICODE_ESCAPES = {
	"'": "\\u0027",
	"<": "\\u003c",
	">": "\\u003e",
	"&": "\\u0026",
	"=": "\\u003d",
}

UNICODE_REPLACEMENTS = {
	r"\\u003c": "UNICODE_LT",
	r"\\u003e": "UNICODE_GT",
	r"\\u0026": "UNICODE_AMP",
	r"\\u003d": "UNICODE_EQ",
	r"\\u0027": "UNICODE_APOS",
}
UNICODE_RESTORE = {v: k for k, v in UNICODE_REPLACEMENTS.items()}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)


def preserve_unicode_escapes(text):
	"""Preserve specific Unicode escapes in JSON content."""
	for escape, placeholder in UNICODE_REPLACEMENTS.items():
		text = re.sub(escape, placeholder, text)
	return text


def restore_unicode_escapes(text):
	"""Restore Unicode escapes from placeholders."""
	for placeholder, escape in UNICODE_RESTORE.items():
		# We need to use a raw string for the replacement to handle backslashes properly
		text = text.replace(placeholder, escape.replace('\\\\', '\\'))
	return text


def format_json(obj):
	"""Format JSON with 2-space indentation, preserving Ignition unicode escapes.

	Ignition Perspective encodes certain ASCII characters as unicode escapes
	(e.g., ' as \\u0027) in view.json files. Since json.loads decodes these
	into literal characters, we re-encode them after json.dumps to maintain
	round-trip fidelity.

	Args:
		obj: JSON-serializable object.

	Returns:
		str: Formatted JSON string with Ignition-style unicode escapes.
	"""
	result = json.dumps(obj, indent=2, ensure_ascii=True).rstrip()
	for char, escape in IGNITION_UNICODE_ESCAPES.items():
		result = result.replace(char, escape)
	return result


def read_json_file(file_path):
	"""Read and parse a JSON file while preserving Unicode escapes.

	Args:
		file_path (Path): Path to the JSON file.

	Returns:
		OrderedDict: Parsed JSON data.

	Raises:
		SystemExit: If the file is not found or JSON is invalid.
	"""
	file_path = Path(file_path).resolve()
	try:
		with file_path.open("r", encoding="utf-8") as file:
			content = file.read()
			return json.loads(content, object_pairs_hook=OrderedDict)
			# preserved_content = preserve_unicode_escapes(content)
			# return json.loads(preserved_content, object_pairs_hook=OrderedDict)
	except FileNotFoundError:
		LOGGER.error("File %s not found. Confirm the file exists and is accessible.", file_path)
		sys.exit(1)
	except json.JSONDecodeError as e:
		LOGGER.error("Invalid JSON in %s: %s", file_path, e)
		sys.exit(1)


def write_json_file(file_path, data):
	"""Write formatted JSON to a file, restoring Unicode escapes.

	Args:
		file_path (Path): Path to the JSON file.
		data: JSON-serializable object.

	Raises:
		SystemExit: If the file cannot be written.
	"""
	file_path = Path(file_path).resolve()
	try:
		# Ensure the parent directory exists
		file_path.parent.mkdir(parents=True, exist_ok=True)

		formatted_json = format_json(data)
		# restored_content = restore_unicode_escapes(formatted_json)
		with file_path.open("w", encoding="utf-8", newline="\n") as file:
			# file.write(restored_content)
			file.write(formatted_json)
	except (OSError, IOError) as e:
		LOGGER.error("Failed to write %s: %s", file_path, e)
		sys.exit(1)


def _get_component_path(data, path):
	"""Extract component name and update path for better clarity."""
	component_name = data.get('meta', {}).get('name')
	if component_name:
		return f"{path}.{component_name}" if path else component_name
	return path


def _is_java_date_object(data):
	"""
	Check if a dictionary represents a Java Date object.

	Java Date objects are serialized as:
	{
		"$": ["ts", <precision>, <nanos>],
		"$ts": <millis_timestamp>
	}

	Args:
		data (dict): Dictionary to check

	Returns:
		bool: True if this looks like a Java Date object
	"""
	if not isinstance(data, dict):
		return False

	# Must have both "$" and "$ts" keys
	if "$" not in data or "$ts" not in data:
		return False

	# "$" should be a list with 3 elements: ["ts", precision, nanos]
	dollar_value = data["$"]
	if not isinstance(dollar_value, list) or len(dollar_value) != 3:
		return False

	# First element should be "ts", second and third should be numbers
	if (dollar_value[0] != "ts" or
		not isinstance(dollar_value[1], (int, float)) or
		not isinstance(dollar_value[2], (int, float))):
		return False

	# "$ts" should be a number (the millis timestamp)
	if not isinstance(data["$ts"], (int, float)):
		return False

	# Additional validation: should only have these two keys
	if len(data) != 2:
		return False

	return True


def _extract_java_date_timestamp(data):
	"""
	Extract the timestamp from a Java Date object.

	Args:
		data (dict): Java Date object dictionary

	Returns:
		int: The milliseconds timestamp from "$ts"
	"""
	return data["$ts"]


def _process_dict_item(key, value, path, results):
	"""Process a single key-value pair from a dictionary."""
	current_path = f"{path}.{key}" if path else key
	if isinstance(value, dict):
		# Check if this is a Java Date object
		if _is_java_date_object(value):
			# Store as a single encoded date value
			timestamp = _extract_java_date_timestamp(value)
			results[f"{current_path}._JavaDate"] = timestamp
		else:
			# Regular dictionary - flatten recursively
			flatten_json(value, current_path, results)
	elif isinstance(value, list):
		_process_list_items(value, current_path, results)
	else:
		results[current_path] = value


def _process_list_items(items, base_path, results):
	"""Process all items in a list."""
	for index, item in enumerate(items):
		item_path = f"{base_path}[{index}]"
		_process_single_item(item, item_path, results)


def _process_single_item(item, item_path, results):
	"""Process a single item, whether primitive or complex."""
	if isinstance(item, (dict, list)):
		flatten_json(item, item_path, results)
	else:
		results[item_path] = item


def flatten_json(data, path="", results=None):
	"""
	Recursively flattens a JSON-like dictionary into path-to-value pairs.

	Args:
		data (dict): The JSON data to flatten.
		path (str): The current path being traversed (used internally).
		results (dict): The dictionary to store the results (used internally).

	Returns:
		dict: A flattened dictionary where keys are paths and values are primitive values.
	"""
	if results is None:
		results = OrderedDict()

	if isinstance(data, dict):
		path = _get_component_path(data, path)
		for key, value in data.items():
			_process_dict_item(key, value, path, results)
	elif isinstance(data, list):
		base_path = path if path else ""
		for index, item in enumerate(data):
			item_path = f"{base_path}[{index}]" if base_path else f"[{index}]"
			_process_single_item(item, item_path, results)

	return results


def flatten_file(file_path):
	"""Flatten a JSON file and return sorted results.

	Args:
		file_path: Path to the JSON file.

	Returns:
		OrderedDict: Sorted flattened JSON data.
	"""
	json_data = read_json_file(file_path)
	flat_json = flatten_json(json_data)
	return OrderedDict(sorted(flat_json.items()))
