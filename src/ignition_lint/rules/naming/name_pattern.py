"""
Fixed NamePatternRule that properly handles node-specific pattern configurations.
"""
import re
from typing import Dict, Optional, Set, Callable, Any
from dataclasses import dataclass
from ..common import LintingRule
from ...model.node_types import ViewNode, NodeType


@dataclass
class NamePatternConfig:
	"""Configuration for name pattern validation."""
	# Validation constraints
	allow_numbers: bool = True
	min_length: int = 1
	max_length: Optional[int] = None
	forbidden_names: Optional[Set[str]] = None
	skip_names: Optional[Set[str]] = None
	# Abbreviation handling
	allowed_abbreviations: Optional[Set[str]] = None
	auto_detect_abbreviations: bool = True
	# Severity configuration
	severity: str = "warning"  # "warning" or "error"

	def __post_init__(self):
		"""Convert lists to sets if needed and validate severity."""
		if self.forbidden_names is not None and not isinstance(self.forbidden_names, set):
			self.forbidden_names = set(self.forbidden_names)
		if self.skip_names is not None and not isinstance(self.skip_names, set):
			self.skip_names = set(self.skip_names)
		if self.allowed_abbreviations is not None and not isinstance(self.allowed_abbreviations, set):
			self.allowed_abbreviations = set(self.allowed_abbreviations)

		# Validate severity
		if self.severity not in ("warning", "error"):
			raise ValueError(f"severity must be 'warning' or 'error', got '{self.severity}'")


class NamePatternRule(LintingRule):
	"""
	A flexible naming rule that can validate names for different types of nodes.
	Supports predefined naming conventions, custom regex patterns, and node-specific configurations.
	"""

	@classmethod
	def preprocess_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Preprocess configuration to convert string node types to NodeType enums.
		"""
		processed_config = super().preprocess_config(config)

		# Convert target_node_types from strings to NodeType enums
		if 'target_node_types' in processed_config:
			target_types = processed_config['target_node_types']
			converted_types = set()

			if isinstance(target_types, str):
				# Handle single string
				try:
					converted_types.add(NodeType(target_types))
				except ValueError:
					print(
						f"Warning: Unknown node type '{target_types}'. Available types: {[nt.value for nt in NodeType]}"
					)
			elif isinstance(target_types, (list, set)):
				# Handle list/set of strings
				for nt_str in target_types:
					try:
						converted_types.add(NodeType(nt_str))
					except ValueError:
						print(
							f"Warning: Unknown node type '{nt_str}'. Available types: {[nt.value for nt in NodeType]}"
						)

			if converted_types:  # Only set if we successfully converted something
				processed_config['target_node_types'] = converted_types

		# Convert node_type_specific_rules keys from strings to NodeType enums
		if 'node_type_specific_rules' in processed_config:
			old_rules = processed_config['node_type_specific_rules']
			new_rules = {}

			for node_type_str, rule_config in old_rules.items():
				try:
					node_type = NodeType(node_type_str)
					new_rules[node_type] = rule_config
				except ValueError:
					print(
						f"Warning: Unknown node type '{node_type_str}' in node_type_specific_rules"
					)

			processed_config['node_type_specific_rules'] = new_rules

		return processed_config

	NAMING_CONVENTIONS = {
		'PascalCase': {
			'pattern': r'^[A-Z][a-zA-Z0-9]*$',
			'description': 'PascalCase',
			'examples': ['Button1', 'DataTable', 'MyCustomComponent'],
			'invalid_examples': ['button1', 'data_table', 'my-component']
		},
		'camelCase': {
			'pattern': r'^[a-z][a-zA-Z0-9]*$',
			'description': 'camelCase',
			'examples': ['button1', 'dataTable', 'myCustomComponent'],
			'invalid_examples': ['Button1', 'data_table', 'my-component']
		},
		'snake_case': {
			'pattern': r'^[a-z][a-z0-9_]*$',
			'description': 'snake_case',
			'examples': ['button_1', 'data_table', 'my_custom_component'],
			'invalid_examples': ['Button1', 'dataTable', 'my-component']
		},
		'kebab-case': {
			'pattern': r'^[a-z][a-z0-9-]*$',
			'description': 'kebab-case',
			'examples': ['button-1', 'data-table', 'my-custom-component'],
			'invalid_examples': ['Button1', 'dataTable', 'my_component']
		},
		'SCREAMING_SNAKE_CASE': {
			'pattern': r'^[A-Z][A-Z0-9_]*$',
			'description': 'SCREAMING_SNAKE_CASE',
			'examples': ['BUTTON_1', 'DATA_TABLE', 'MY_CUSTOM_COMPONENT'],
			'invalid_examples': ['Button1', 'dataTable', 'my-component']
		},
		'Title Case': {
			'pattern': r'^[A-Z][a-z]*(\s[A-Z][a-z]*)*$',
			'description': 'Title Case',
			'examples': ['Button One', 'Data Table', 'My Custom Component'],
			'invalid_examples': ['button one', 'dataTable', 'my-component']
		},
		'lower case': {
			'pattern': r'^[a-z][a-z\s]*$',
			'description': 'lower case with spaces (e.g., my button, data table)',
			'examples': ['button one', 'data table', 'my custom component'],
			'invalid_examples': ['Button One', 'dataTable', 'my-component']
		}
	}

	def __init__(
		self,
		convention: Optional[str] = None,
		*,
		target_node_types: Set[NodeType] = None,
		custom_pattern: Optional[str] = None,
		config: Optional[NamePatternConfig] = None,
		name_extractors: Optional[Dict[NodeType, Callable[[ViewNode], str]]] = None,
		node_type_specific_rules: Optional[Dict[NodeType, Dict]] = None,
		severity: str = "warning",  # New parameter for configurable severity
		**kwargs  # Backward compatibility for old parameter names
	):
		"""
		Initialize the naming rule.

		Args:
			target_node_types: Node types this rule should apply to. If not provided and
			                  node_type_specific_rules is provided, will be auto-derived from the keys
			convention: Naming convention (PascalCase, camelCase, etc.)
			custom_pattern: Custom regex pattern (overrides convention)
			config: Configuration for validation and abbreviation handling
			name_extractors: Custom name extraction functions for node types
			node_type_specific_rules: Per-node-type rule overrides. Keys automatically become target_node_types
			severity: Severity level for violations ('warning' or 'error')
		"""
		# Auto-derive target_node_types from node_type_specific_rules if not provided
		if target_node_types is None and node_type_specific_rules:
			target_node_types = set(node_type_specific_rules.keys())

		# Use the config severity if available, otherwise use the parameter
		effective_severity = config.severity if config else severity
		super().__init__(target_node_types or {NodeType.COMPONENT}, severity=effective_severity)

		self.convention = convention
		self.custom_pattern = custom_pattern
		# Handle configuration - use provided config or create from kwargs/defaults
		if config is not None:
			self.config = config
		else:
			# Create config from individual parameters (backward compatibility)
			self.config = NamePatternConfig(
				allow_numbers=kwargs.get('allow_numbers', True), min_length=kwargs.get('min_length', 1),
				max_length=kwargs.get('max_length',
							None), forbidden_names=kwargs.get('forbidden_names', None),
				skip_names=kwargs.get('skip_names', None),
				allowed_abbreviations=kwargs.get('allowed_abbreviations', None),
				auto_detect_abbreviations=kwargs.get('auto_detect_abbreviations', True),
				severity=kwargs.get('severity', severity)  # Use provided severity or default
			)
		# Store configurations - use properties for backward compatibility access

		# Advanced configurations
		self.node_type_specific_rules = node_type_specific_rules or {}
		self.name_extractors = name_extractors or self._get_default_name_extractors()

		# Common abbreviations
		self.common_abbreviations = {
			'API', 'HTTP', 'HTTPS', 'XML', 'JSON', 'SQL', 'URL', 'URI', 'UUID', 'CPU', 'GPU', 'RAM', 'SSD',
			'HDD', 'PDF', 'CSV', 'ZIP', 'GIF', 'PNG', 'JPG', 'JPEG', 'SVG', 'CSS', 'HTML', 'JS', 'TS',
			'PHP', 'ASP', 'JSP', 'CGI', 'FTP', 'SSH', 'TCP', 'UDP', 'IP', 'DNS', 'DHCP', 'VPN', 'SSL',
			'TLS', 'JWT', 'CRUD', 'REST', 'SOAP', 'AJAX', 'DOM', 'UI', 'UX', 'GUI', 'CLI', 'OS', 'iOS',
			'macOS', 'AWS', 'GCP', 'IBM', 'AI', 'ML', 'NLP', 'OCR', 'QR', 'RFID', 'NFC', 'GPS', 'LED',
			'LCD', 'OLED', 'CRT', 'ID'
		}

		# Combine user-provided and common abbreviations
		if self.auto_detect_abbreviations:
			self.all_abbreviations = self.allowed_abbreviations | self.common_abbreviations
		else:
			self.all_abbreviations = self.allowed_abbreviations

		# Set up the default pattern and description
		self._setup_pattern()

		# Process node-specific rules to ensure they have patterns
		self._process_node_specific_rules()

	# Properties for backward compatibility
	@property
	def allow_numbers(self) -> bool:
		return self.config.allow_numbers

	@property
	def min_length(self) -> int:
		return self.config.min_length

	@property
	def max_length(self) -> Optional[int]:
		return self.config.max_length

	@property
	def forbidden_names(self) -> Set[str]:
		return self.config.forbidden_names or set()

	@property
	def skip_names(self) -> Set[str]:
		return self.config.skip_names or {'root'}

	@property
	def allowed_abbreviations(self) -> Set[str]:
		return self.config.allowed_abbreviations or set()

	@property
	def auto_detect_abbreviations(self) -> bool:
		return self.config.auto_detect_abbreviations


	def _get_default_name_extractors(self) -> Dict[NodeType, Callable[[ViewNode], str]]:
		"""Get default name extractors for different node types."""
		return {
			NodeType.COMPONENT: lambda node: getattr(node, 'name', ''),
			NodeType.MESSAGE_HANDLER: lambda node: getattr(node, 'message_type', ''),
			NodeType.CUSTOM_METHOD: lambda node: getattr(node, 'name', ''),
			NodeType.PROPERTY: lambda node: getattr(node, 'name', ''),
			NodeType.EVENT_HANDLER: lambda node: getattr(node, 'event_type', ''),
		}

	def _setup_pattern(self):
		"""Set up the default regex pattern and description based on configuration."""
		if self.custom_pattern:
			self.pattern = self.custom_pattern
			self.pattern_description = f"custom pattern: {self.custom_pattern}"
		elif self.convention and self.convention in self.NAMING_CONVENTIONS:
			conv_info = self.NAMING_CONVENTIONS[self.convention]
			base_pattern = conv_info['pattern']

			# Modify pattern based on allow_numbers setting
			if not self.allow_numbers:
				base_pattern = base_pattern.replace('0-9', '')

			self.pattern = base_pattern
			self.pattern_description = conv_info['description']
		else:
			# Default to PascalCase
			self.pattern = self.NAMING_CONVENTIONS['PascalCase']['pattern']
			self.pattern_description = self.NAMING_CONVENTIONS['PascalCase']['description']
			if self.convention:
				print(f"Warning: Unknown convention '{self.convention}', using PascalCase as default")

	def _process_node_specific_rules(self):
		"""Process node-specific rules to ensure they have proper patterns."""
		for _, rules in self.node_type_specific_rules.items():
			# If the rule has a convention but no pattern, generate the pattern
			if 'convention' in rules and 'pattern' not in rules:
				convention = rules['convention']
				if convention in self.NAMING_CONVENTIONS:
					conv_info = self.NAMING_CONVENTIONS[convention]
					pattern = conv_info['pattern']

					# Apply allow_numbers setting
					allow_numbers = rules.get('allow_numbers', self.allow_numbers)
					if not allow_numbers:
						pattern = pattern.replace('0-9', '')

					rules['pattern'] = pattern
					if 'pattern_description' not in rules:
						rules['pattern_description'] = conv_info['description']

	def _get_node_specific_config(self, node_type: NodeType, key: str, default_value):
		"""Get a configuration value that might be overridden for a specific node type."""
		if node_type in self.node_type_specific_rules:
			return self.node_type_specific_rules[node_type].get(key, default_value)
		return default_value

	def _extract_name_from_node(self, node: ViewNode) -> Optional[str]:
		"""Extract the name from a node based on its type."""
		node_type = node.node_type
		if node_type in self.name_extractors:
			try:
				return self.name_extractors[node_type](node)
			except (AttributeError, KeyError):
				return None
		return None

	def _is_css_property(self, node: ViewNode) -> bool:
		"""
		Check if a property is a CSS property (in style or elementStyle).
		CSS properties should always be in kebab-case and should not be validated.

		Args:
			node: The property node to check

		Returns:
			True if the property is a CSS property, False otherwise
		"""
		if node.node_type != NodeType.PROPERTY:
			return False

		# Check if the path contains .style. or .elementStyle.
		# Examples:
		#   root.root.props.style.touch-action -> CSS property
		#   root.FlexRepeater.props.elementStyle.flex-direction -> CSS property
		#   custom.myProperty -> NOT a CSS property
		path = node.path
		return '.style.' in path or '.elementStyle.' in path

	def _validate_name(self, node: ViewNode, name: str) -> list:
		"""
		Validate a name according to the rules and return a list of error messages.
		Returns empty list if validation passes.
		"""
		errors = []
		node_type = node.node_type

		# Skip validation for certain names
		skip_names = self._get_node_specific_config(node_type, 'skip_names', self.skip_names)
		if name in skip_names:
			return errors

		# Check forbidden names
		forbidden_names = self._get_node_specific_config(node_type, 'forbidden_names', self.forbidden_names)
		if name in forbidden_names:
			errors.append(f"Name '{name}' is forbidden for {node_type.value}")
			return errors

		# Check length constraints
		min_length = self._get_node_specific_config(node_type, 'min_length', self.min_length)
		max_length = self._get_node_specific_config(node_type, 'max_length', self.max_length)

		if len(name) < min_length:
			errors.append(
				f"Name '{name}' is too short (minimum {min_length} characters) for {node_type.value}"
			)
			return errors

		if max_length and len(name) > max_length:
			errors.append(
				f"Name '{name}' is too long (maximum {max_length} characters) for {node_type.value}"
			)
			return errors

		# Check pattern
		pattern = self._get_node_specific_config(node_type, 'pattern', self.pattern)
		pattern_description = self._get_node_specific_config(
			node_type, 'pattern_description', self.pattern_description
		)

		processed_name = self._process_abbreviations(name, node_type)
		if not re.match(pattern, processed_name):
			error_msg = f"Name '{name}' doesn't follow {pattern_description} for {node_type.value}"

			# Add helpful suggestions if using a predefined convention
			node_convention = self._get_node_specific_config(node_type, 'convention', self.convention)
			if node_convention and node_convention in self.NAMING_CONVENTIONS:
				suggestion = self._suggest_name(name, node_type)
				if suggestion:
					error_msg += f" (suggestion: '{suggestion}')"

			errors.append(error_msg)

		return errors

	@property
	def error_message(self) -> str:
		target_types = ", ".join([nt.value for nt in self.target_node_types])
		return f"Names should follow naming patterns for {target_types}"

	def visit_generic(self, node: ViewNode):
		"""Generic visit method that handles all node types."""
		name = self._extract_name_from_node(node)
		if name:
			validation_errors = self._validate_name(node, name)
			for error in validation_errors:
				# Use node-specific severity if available, otherwise fall back to global severity
				node_severity = self._get_node_specific_config(node.node_type, 'severity', self.severity)
				self.add_violation(f"{node.path}: {error}", node_severity)

	# Specific visit methods that delegate to the generic method
	def visit_component(self, node: ViewNode):
		self.visit_generic(node)

	def visit_message_handler(self, node: ViewNode):
		self.visit_generic(node)

	def visit_custom_method(self, node: ViewNode):
		self.visit_generic(node)

	def visit_property(self, node: ViewNode):
		# Skip validation for CSS properties (in style or elementStyle)
		if self._is_css_property(node):
			return
		self.visit_generic(node)

	def visit_event_handler(self, node: ViewNode):
		self.visit_generic(node)

	def _process_abbreviations(self, name: str, node_type: NodeType) -> str:
		"""Process a name to handle abbreviations according to the naming convention."""
		if not self.all_abbreviations:
			return name

		# Get node-specific custom pattern
		custom_pattern = self._get_node_specific_config(node_type, 'custom_pattern', self.custom_pattern)
		if custom_pattern:
			return name

		processed_name = name

		# Get node-specific convention
		convention = self._get_node_specific_config(node_type, 'convention', self.convention)

		for abbrev in sorted(self.all_abbreviations, key=len, reverse=True):
			if abbrev in name.upper():
				if convention in ['PascalCase', 'camelCase']:
					processed_name = self._adjust_abbreviation_for_camel_case(
						processed_name, abbrev
					)
				elif convention in ['snake_case', 'kebab-case']:
					processed_name = processed_name.replace(abbrev.upper(), abbrev.lower())
					processed_name = processed_name.replace(abbrev.lower(), abbrev.lower())
				elif convention == 'SCREAMING_SNAKE_CASE':
					processed_name = processed_name.upper()
				elif convention in ['Title Case', 'lower case']:
					if convention == 'Title Case':
						processed_name = self._adjust_abbreviation_for_title_case(
							processed_name, abbrev
						)
					else:
						processed_name = processed_name.lower()

		return processed_name

	def _suggest_name(self, name: str, node_type: NodeType) -> Optional[str]:
		"""Suggest a corrected name based on the node-specific or default convention."""
		convention = self._get_node_specific_config(node_type, 'convention', self.convention)

		if not convention or convention not in self.NAMING_CONVENTIONS:
			return None

		if convention == 'PascalCase':
			suggested_name = self._to_pascal_case(name)
		elif convention == 'camelCase':
			suggested_name = self._to_camel_case(name)
		elif convention == 'snake_case':
			suggested_name = self._to_snake_case(name)
		elif convention == 'kebab-case':
			suggested_name = self._to_kebab_case(name)
		elif convention == 'SCREAMING_SNAKE_CASE':
			suggested_name = self._to_snake_case(name).upper()
		elif convention == 'Title Case':
			suggested_name = self._to_title_case(name)
		elif convention == 'lower case':
			suggested_name = self._to_lower_case(name)
		else:
			suggested_name = 'No suggestion available'
		return suggested_name

	def _adjust_abbreviation_for_camel_case(self, name: str, abbrev: str) -> str:
		"""Adjust abbreviations in camelCase/PascalCase names."""
		variations = [abbrev.upper(), abbrev.lower(), abbrev.capitalize()]
		for variation in variations:
			if variation in name:
				name = name.replace(variation, abbrev.upper())
		return name

	def _adjust_abbreviation_for_title_case(self, name: str, abbrev: str) -> str:
		"""Adjust abbreviations in Title Case names."""
		words = name.split()
		adjusted_words = []
		for word in words:
			if word.upper() == abbrev.upper():
				adjusted_words.append(abbrev.upper())
			else:
				adjusted_words.append(word)
		return ' '.join(adjusted_words)

	def _split_name_into_parts(self, name: str) -> list:
		"""Split a name into parts, handling various formats consistently."""
		# First try splitting on delimiters (spaces, hyphens, underscores)
		parts = re.split(r'[-_\s]+', name.strip())

		# If we only got one part, try splitting camelCase/PascalCase
		if len(parts) == 1 and parts[0]:
			# Split on capital letters: VeryVeryBadProperty -> ['Very', 'Very', 'Bad', 'Property']
			camel_parts = re.findall(r'[A-Z][a-z]*|[a-z]+|[A-Z]+(?=[A-Z][a-z]|$)', name)
			if len(camel_parts) > 1:
				parts = camel_parts

		# Filter out empty parts
		return [part for part in parts if part]

	def _to_pascal_case(self, name: str) -> str:
		"""Convert name to PascalCase, preserving abbreviations."""
		parts = self._split_name_into_parts(name)
		result_parts = []

		for part in parts:
			if part.upper() in self.all_abbreviations:
				result_parts.append(part.upper())
			else:
				result_parts.append(part.capitalize())

		return ''.join(result_parts)

	def _to_camel_case(self, name: str) -> str:
		"""Convert name to camelCase, preserving abbreviations."""
		parts = self._split_name_into_parts(name)
		if not parts:
			return ""

		result_parts = []

		# Handle first part (should be lowercase unless it's an abbreviation)
		first_part = parts[0]
		if first_part.upper() in self.all_abbreviations:
			result_parts.append(first_part.upper())
		else:
			result_parts.append(first_part.lower())

		# Handle remaining parts (should be capitalized, abbreviations stay uppercase)
		for part in parts[1:]:
			if part.upper() in self.all_abbreviations:
				result_parts.append(part.upper())
			else:
				result_parts.append(part.capitalize())

		return ''.join(result_parts)

	def _to_snake_case(self, name: str) -> str:
		"""Convert name to snake_case, handling abbreviations."""
		parts = self._split_name_into_parts(name)
		result_parts = []

		for part in parts:
			if part.upper() in self.all_abbreviations:
				result_parts.append(part.lower())  # Abbreviations become lowercase in snake_case
			else:
				result_parts.append(part.lower())

		return '_'.join(result_parts)

	def _to_kebab_case(self, name: str) -> str:
		"""Convert name to kebab-case, handling abbreviations."""
		parts = self._split_name_into_parts(name)
		result_parts = []

		for part in parts:
			if part.upper() in self.all_abbreviations:
				result_parts.append(part.lower())  # Abbreviations become lowercase in kebab-case
			else:
				result_parts.append(part.lower())

		return '-'.join(result_parts)

	def _to_title_case(self, name: str) -> str:
		"""Convert name to Title Case, preserving abbreviations."""
		parts = self._split_name_into_parts(name)
		result_parts = []

		for part in parts:
			if part.upper() in self.all_abbreviations:
				result_parts.append(part.upper())  # Abbreviations stay uppercase
			else:
				result_parts.append(part.capitalize())

		return ' '.join(result_parts)

	def _to_lower_case(self, name: str) -> str:
		"""Convert name to lower case with spaces."""
		parts = self._split_name_into_parts(name)
		result_parts = []

		for part in parts:
			# In lower case, even abbreviations become lowercase
			result_parts.append(part.lower())

		return ' '.join(result_parts)
