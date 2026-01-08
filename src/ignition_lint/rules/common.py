"""
This module contains common and base node types for rule implementation
"""

from abc import ABC, abstractmethod
from typing import Set, List, Dict, Any, Literal
from ..model.node_types import Property, ViewNode, NodeType, ScriptNode, ALL_BINDINGS, ALL_SCRIPTS

# Type definition for severity levels
Severity = Literal["warning", "error"]
RESERVED_KEY_NAMES = {"_JavaDate"}

class NodeVisitor(ABC):
	"""Simplified base visitor class that rules can extend."""

	def visit_generic(self, node: ViewNode):
		"""Generic visit method for nodes that don't have specific handlers."""

	# Specific visit methods - rules only need to implement what they care about
	def visit_component(self, node: ViewNode):
		"""Visit a component node."""

	def visit_expression_binding(self, node: ViewNode):
		"""Visit an expression binding node."""

	def visit_property_binding(self, node: ViewNode):
		"""Visit a property binding node."""

	def visit_tag_binding(self, node: ViewNode):
		"""Visit a tag binding node."""

	def visit_message_handler(self, node: ViewNode):
		"""Visit a message handler node."""

	def visit_custom_method(self, node: ViewNode):
		"""Visit a component custom method node."""

	def visit_transform(self, node: ViewNode):
		"""Visit a transform node."""

	def visit_event_handler(self, node: ViewNode):
		"""Visit an event handler node."""

	def visit_property(self, node: ViewNode):
		"""Visit a property node."""


class LintingRule(NodeVisitor):
	"""Base class for linting rules with simplified interface and self-processing capability."""

	def __init__(self, target_node_types: Set[NodeType] = None, severity: str = "error", include_private_properties: bool = False):
		"""
		Initialize the rule.

		Args:
			target_node_types: Set of node types this rule applies to.
							  If None, applies to all nodes.
			severity: Default severity level for violations ("warning" or "error")
			include_private_properties: Whether to include properties starting with '_' (default: False)
		"""
		self.target_node_types = target_node_types or set()
		self.severity = severity if severity in ["warning", "error"] else "error"
		self.include_private_properties = include_private_properties
		self.errors = []
		self.warnings = []

	@classmethod
	def preprocess_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Preprocess configuration before rule instantiation.
		Override this method in subclasses that need special config handling.

		Args:
			config: Raw configuration dictionary from JSON

		Returns:
			Processed configuration dictionary ready for __init__
		"""
		# Filter out keys starting with '_' (used for comments and metadata)
		return {k: v for k, v in config.items() if not k.startswith('_')}

	@classmethod
	def create_from_config(cls, config: Dict[str, Any]):
		"""
		Create a rule instance from configuration, applying any necessary preprocessing.

		Args:
			config: Raw configuration dictionary from JSON

		Returns:
			Rule instance
		"""
		processed_config = cls.preprocess_config(config)
		return cls(**processed_config)

	def _is_private_property(self, node: ViewNode) -> bool:
		"""Check if a node represents a private property (name starts with '_')."""
		if node.node_type == NodeType.PROPERTY and isinstance(node, Property):
			return node.name.startswith('_') or node.name in RESERVED_KEY_NAMES
		return False

	def applies_to(self, node: ViewNode) -> bool:
		"""Check if this rule applies to the given node."""
		# First check if the node type matches the rule's target types
		if not node.applies_to_rule(self.target_node_types):
			return False

		# Filter out private properties unless explicitly included
		if self._is_private_property(node) and not self.include_private_properties:
			return False

		return True

	def process_nodes(self, nodes: List[ViewNode]):
		"""Process a list of nodes, applying the rule to applicable ones."""
		self.errors = []  # Reset errors
		self.warnings = []  # Reset warnings

		# Filter nodes that this rule applies to
		applicable_nodes = [node for node in nodes if self.applies_to(node)]

		# Visit each applicable node
		for node in applicable_nodes:
			node.accept(self)

		# Allow for batch processing if needed
		self.post_process()

	def post_process(self):
		"""Override this method if you need to do batch processing after visiting all nodes."""

	def add_violation(self, message: str, severity: str = None):
		"""
		Add a violation with the specified severity.

		Args:
			message: The violation message
			severity: Override the default severity ("warning" or "error")
		"""
		actual_severity = severity if severity in ["warning", "error"] else self.severity
		if actual_severity == "error":
			self.errors.append(message)
		else:
			self.warnings.append(message)

	@property
	@abstractmethod
	def error_message(self) -> str:
		"""Return a description of what this rule checks for."""

	@property
	def error_key(self) -> str:
		"""Key to use in the errors dict for this rule."""
		return self.__class__.__name__


class BindingRule(LintingRule):
	"""Base class for binding-specific rules."""

	def __init__(self, target_node_types: Set[NodeType] = None, severity: str = "error", include_private_properties: bool = False):
		if target_node_types is None:
			target_node_types = ALL_BINDINGS
		super().__init__(target_node_types, severity, include_private_properties)


class ScriptRule(LintingRule):
	"""Base class for script-specific rules with built-in script collection."""

	def __init__(self, target_node_types: Set[NodeType] = None, severity: str = "error", include_private_properties: bool = False):
		if target_node_types is None:
			target_node_types = ALL_SCRIPTS
		super().__init__(target_node_types, severity, include_private_properties)
		self.collected_scripts = {}

	def process_nodes(self, nodes: List[ViewNode]):
		"""Process a list of nodes, applying the rule to applicable ones."""
		self.errors = []  # Reset errors
		self.warnings = []  # Reset warnings
		self.collected_scripts = {}  # Reset collected scripts

		# Filter nodes that this rule applies to
		applicable_nodes = [node for node in nodes if self.applies_to(node)]

		# Visit each applicable node
		for node in applicable_nodes:
			node.accept(self)

		# Allow for batch processing if needed
		self.post_process()

	def visit_message_handler(self, node: ViewNode):
		self._collect_script(node)

	def visit_custom_method(self, node: ViewNode):
		self._collect_script(node)

	def visit_transform(self, node: ViewNode):
		self._collect_script(node)

	def visit_event_handler(self, node: ViewNode):
		self._collect_script(node)

	def _collect_script(self, node: ViewNode):
		"""Collect script for batch processing."""
		if isinstance(node, ScriptNode):
			self.collected_scripts[node.path] = node

	def post_process(self):
		"""Process all collected scripts in batch."""
		if self.collected_scripts:
			self.process_scripts(self.collected_scripts)
			self.collected_scripts = {}

	@abstractmethod
	def process_scripts(self, scripts: Dict[str, ScriptNode]):
		"""Process the collected scripts. Override in subclasses."""
