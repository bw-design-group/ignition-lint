"""
This module defines the node types used in the view tree structure.
It includes base classes for nodes, specific node types, and an enum for node types.
It also provides visitor support for processing nodes in a structured way.
"""

import re
from enum import Enum
from abc import ABC
from typing import Dict, List, Any, Set


class NodeType(Enum):
	"""Enum for node types used in linting rules."""
	COMPONENT = "component"
	EXPRESSION_BINDING = "expression_binding"
	EXPRESSION_STRUCT_BINDING = "expression_struct_binding"
	PROPERTY_BINDING = "property_binding"
	TAG_BINDING = "tag_binding"
	QUERY_BINDING = "query_binding"
	MESSAGE_HANDLER = "message_handler"
	CUSTOM_METHOD = "custom_method"
	TRANSFORM = "transform"
	EVENT_HANDLER = "event_handler"
	PROPERTY = "property"


# Grouped node types - defined outside the enum to avoid enum member confusion
ALL_BINDINGS = {
	NodeType.EXPRESSION_BINDING, NodeType.EXPRESSION_STRUCT_BINDING, NodeType.PROPERTY_BINDING,
	NodeType.TAG_BINDING, NodeType.QUERY_BINDING
}
ALL_SCRIPTS = {NodeType.MESSAGE_HANDLER, NodeType.CUSTOM_METHOD, NodeType.TRANSFORM, NodeType.EVENT_HANDLER}


class ViewNode(ABC):
	"""Base class for all nodes in the view tree with centralized rule application logic."""

	def __init__(self, path: str, node_type: NodeType):
		self.path = path
		self.node_type = node_type

	def applies_to_rule(self, rule_node_types: Set[NodeType]) -> bool:
		"""Check if this node applies to a rule based on its target node types."""
		if not rule_node_types:
			return True
		return self.node_type in rule_node_types

	def accept(self, visitor):
		"""Accept a visitor that will process this node."""
		# Use the node type to determine which visit method to call
		method_name = f"visit_{self.node_type.value}"
		visit_method = getattr(visitor, method_name, None)
		if visit_method:
			return visit_method(self)
		# Fallback to generic visit method
		return visitor.visit_generic(self)

	def serialize(self):
		"""Serialize node data for debugging/inspection."""
		return {'path': self.path, 'node_type': self.node_type.value, **self._get_serializable_attrs()}

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		"""Get node-specific attributes for serialization. Override in subclasses."""
		return {}


class Component(ViewNode):
	"""Represents a component in the view."""

	def __init__(self, path: str, name: str, type_name: str = None, properties: Dict = None):
		super().__init__(path, NodeType.COMPONENT)
		self.name = name
		self.type = type_name
		self.properties = properties or {}
		self.children = []

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		return {'name': self.name, 'type': self.type, 'properties_count': len(self.properties)}


class ExpressionBinding(ViewNode):
	"""Represents an expression binding."""

	def __init__(self, path: str, expression: str, config: Dict = None):
		super().__init__(path, NodeType.EXPRESSION_BINDING)
		self.expression = expression
		self.config = config or {}

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		return {'expression': self.expression, 'config': self.config}


class ExpressionStructBinding(ViewNode):
	"""Represents an expression structure binding with multiple key-expression mappings."""

	def __init__(self, path: str, struct: Dict[str, str], config: Dict = None):
		super().__init__(path, NodeType.EXPRESSION_STRUCT_BINDING)
		self.struct = struct  # Dict mapping keys to expression strings
		self.config = config or {}

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		return {'struct': self.struct, 'config': self.config}

	def get_expressions(self) -> List[str]:
		"""Get all expression strings from the struct."""
		return list(self.struct.values())

	def get_struct_keys(self) -> List[str]:
		"""Get all keys from the struct."""
		return list(self.struct.keys())


class PropertyBinding(ViewNode):
	"""Represents a property binding."""

	def __init__(self, path: str, target_path: str, config: Dict = None):
		super().__init__(path, NodeType.PROPERTY_BINDING)
		self.target_path = target_path
		self.config = config or {}

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		return {'target_path': self.target_path, 'config': self.config}


class TagBinding(ViewNode):
	"""Represents a tag binding with support for direct, indirect, and expression modes."""

	def __init__(
		self, path: str, tag_path: str, *, mode: str = "direct", references: Dict[str, str] = None,
		config: Dict = None
	):
		super().__init__(path, NodeType.TAG_BINDING)
		self.tag_path = tag_path
		self.mode = mode  # 'direct', 'indirect', or 'expression'
		self.references = references or {}  # For indirect tags: maps placeholder keys to expressions
		self.config = config or {}

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		return {
			'tag_path': self.tag_path,
			'mode': self.mode,
			'references': self.references,
			'config': self.config
		}

	def get_expressions(self) -> List[str]:
		"""Get all expressions from this tag binding based on its mode."""
		expressions = []

		if self.mode == 'expression':
			# Expression mode: tagPath is an expression
			expressions.append(self.tag_path)
		elif self.mode == 'indirect':
			# Indirect mode: reference values are expressions
			expressions.extend(self.references.values())
		# Direct mode has no expressions

		return expressions

	def get_reference_expressions(self) -> Dict[str, str]:
		"""Get the reference expressions for indirect tag bindings."""
		return self.references.copy() if self.mode == 'indirect' else {}

	def is_expression_tag(self) -> bool:
		"""Check if this is an expression tag binding."""
		return self.mode == 'expression'

	def is_indirect_tag(self) -> bool:
		"""Check if this is an indirect tag binding."""
		return self.mode == 'indirect'

	def is_direct_tag(self) -> bool:
		"""Check if this is a direct tag binding."""
		return self.mode == 'direct'


class QueryBinding(ViewNode):
	"""Represents a query binding with a query path and parameters containing expressions."""

	def __init__(self, path: str, query_path: str, parameters: Dict[str, str], config: Dict = None):
		super().__init__(path, NodeType.QUERY_BINDING)
		self.query_path = query_path
		self.parameters = parameters  # Dict mapping parameter names to expression strings
		self.config = config or {}

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		return {'query_path': self.query_path, 'parameters': self.parameters, 'config': self.config}

	def get_parameter_expressions(self) -> List[str]:
		"""Get all parameter expression strings."""
		return list(self.parameters.values())

	def get_parameter_names(self) -> List[str]:
		"""Get all parameter names."""
		return list(self.parameters.keys())


class ScriptNode(ViewNode):
	"""Base class for all script-containing nodes."""

	def __init__(self, path: str, node_type: NodeType, script: str):
		super().__init__(path, node_type)
		self.script = script
		self.function_def = "def undefined_function(self):"

	def get_formatted_script(self) -> str:
		"""Format the script with proper function definition."""
		if not self.script.strip():
			self.script = "\tpass"
		return f"{self.function_def}\n{self.script}"

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		return {
			'script_length': len(self.script),
			'script_preview': self.script[:100] + '...' if len(self.script) > 100 else self.script
		}


class MessageHandlerScript(ScriptNode):
	"""Represents a message handler script."""

	def __init__(self, path: str, script: str, message_type: str, scope: Dict = None):
		super().__init__(path, NodeType.MESSAGE_HANDLER, script)
		self.message_type = message_type
		self.scope = scope or {}
		self.function_def = "def onMessageReceived(self, payload):"

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		base_attrs = super()._get_serializable_attrs()
		base_attrs.update({'message_type': self.message_type, 'scope': self.scope})
		return base_attrs


class CustomMethodScript(ScriptNode):
	"""Represents a custom method script."""

	def __init__(self, path: str, name: str, script: str, params=None):
		super().__init__(path, NodeType.CUSTOM_METHOD, script)
		self.name = name
		self.params = params or []
		# Strip array indices from method name for valid Python function name
		method_name = re.sub(r'\[\d+\]', '', self.name)
		self.function_def = f"def {method_name}({', '.join(['self'] + self.params)}):"

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		base_attrs = super()._get_serializable_attrs()
		base_attrs.update({'name': self.name, 'params': self.params})
		return base_attrs


class TransformScript(ScriptNode):
	"""Represents a transform script."""

	def __init__(self, path: str, script: str, binding_path: str = None):
		super().__init__(path, NodeType.TRANSFORM, script)
		self.binding_path = binding_path
		self.function_def = "def transform(self, value):"

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		base_attrs = super()._get_serializable_attrs()
		base_attrs.update({'binding_path': self.binding_path})
		return base_attrs


class EventHandlerScript(ScriptNode):
	"""Represents an event handler script."""

	def __init__(self, path: str, event_domain: str, event_type: str, script: str, *, scope: str = None):
		super().__init__(path, NodeType.EVENT_HANDLER, script)
		self.event_domain = event_domain
		self.event_type = event_type
		self.scope = scope
		# Strip array indices from event type for valid Python function name
		event_name = re.sub(r'\[\d+\]', '', self.event_type)
		self.function_def = f"def {event_name}(self, event):"

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		base_attrs = super()._get_serializable_attrs()
		base_attrs.update({
			'event_domain': self.event_domain,
			'event_type': self.event_type,
			'scope': self.scope
		})
		return base_attrs


class Property(ViewNode):
	"""Represents a component property."""

	def __init__(self, path: str, name: str, value: Any, *, persistent: bool = None, private_access: bool = None):
		super().__init__(path, NodeType.PROPERTY)
		self.name = name
		self.value = value
		self.persistent = persistent  # True if property is persistent, False if not, None if unknown
		self.private_access = private_access  # True if access mode is 'PRIVATE', False if not, None if unknown

	def _get_serializable_attrs(self) -> Dict[str, Any]:
		attrs = {'name': self.name, 'value': self.value, 'value_type': type(self.value).__name__}
		if self.persistent is not None:
			attrs['persistent'] = self.persistent
		if self.private_access is not None:
			attrs['private_access'] = self.private_access
		return attrs


class NodeUtils:
	"""Utility functions for filtering and working with nodes."""

	@staticmethod
	def filter_by_types(nodes: List[ViewNode], node_types: Set[NodeType]) -> List[ViewNode]:
		"""Filter nodes by their types."""
		return [node for node in nodes if node.applies_to_rule(node_types)]

	@staticmethod
	def get_script_nodes(nodes: List[ViewNode]) -> List[ScriptNode]:
		"""Get all script-containing nodes."""
		return [node for node in nodes if isinstance(node, ScriptNode)]

	@staticmethod
	def get_binding_nodes(nodes: List[ViewNode]) -> List[ViewNode]:
		"""Get all binding nodes."""
		return NodeUtils.filter_by_types(nodes, ALL_BINDINGS)

	@staticmethod
	def group_by_type(nodes: List[ViewNode]) -> Dict[NodeType, List[ViewNode]]:
		"""Group nodes by their type."""
		groups = {}
		for node in nodes:
			if node.node_type not in groups:
				groups[node.node_type] = []
			groups[node.node_type].append(node)
		return groups
