"""
Naming-convention rule for the Ignition project script library.

Applies ``NamePatternRule``'s conventions to library **packages** (folders under
``script-python``) and **modules** (the folder that holds a ``code.py``). Configured the
same way, keyed by the ``script_package`` and ``script_module`` node types.
"""

from typing import Callable, Dict, Optional, Set

from .name_pattern import NamePatternRule
from ...common.domain import LintDomain
from ...model.node_types import NodeType, ViewNode


class LibraryNamePatternRule(NamePatternRule):
	"""Checks library package and module names against a naming convention."""

	domain = LintDomain.SCRIPTING
	DEFAULT_TARGET_NODE_TYPES = frozenset({NodeType.SCRIPT_PACKAGE, NodeType.SCRIPT_MODULE})
	DEFAULT_CONVENTION = "snake_case"

	def __init__(
		self, convention: Optional[str] = None, *, target_node_types: Set[NodeType] = None,
		node_type_specific_rules: Optional[Dict[NodeType, Dict]] = None, severity: str = "warning", **kwargs
	):
		if target_node_types is None and not node_type_specific_rules:
			target_node_types = set(self.DEFAULT_TARGET_NODE_TYPES)
		super().__init__(
			convention or self.DEFAULT_CONVENTION, target_node_types=target_node_types,
			node_type_specific_rules=node_type_specific_rules, severity=severity, **kwargs
		)
		# A package is surfaced by every module beneath it; report it once per run.
		self._reported_package_paths: Set[str] = set()

	@property
	def supports_fix(self) -> bool:
		"""Renaming folders on disk is out of scope; this rule only reports."""
		return False

	@property
	def error_message(self) -> str:
		target_types = ", ".join(sorted(nt.value for nt in self.target_node_types))
		return f"Library names should follow naming patterns for {target_types}"

	def _get_default_name_extractors(self) -> Dict[NodeType, Callable[[ViewNode], str]]:
		extractors = super()._get_default_name_extractors()
		extractors[NodeType.SCRIPT_PACKAGE] = lambda node: getattr(node, 'name', '')
		extractors[NodeType.SCRIPT_MODULE] = lambda node: getattr(node, 'name', '')
		return extractors

	def visit_script_module(self, node: ViewNode):
		self.visit_generic(node)

	def visit_script_package(self, node: ViewNode):
		if node.path in self._reported_package_paths:
			return
		self._reported_package_paths.add(node.path)
		self.visit_generic(node)
