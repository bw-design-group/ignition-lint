"""
This module implements a linting engine for processing ViewModel data from Ignition Perspective views.
It provides functionality to apply linting rules, collect errors, and analyze the structure of the view model.
It also includes methods for debugging nodes and analyzing rule impact on the view model.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, NamedTuple, Optional
from .rules.common import LintingRule
from .model.builder import ViewModelBuilder
from .model.node_types import NodeType, NodeUtils


class LintResults(NamedTuple):
	"""Results from linting process."""
	warnings: Dict[str, List[str]]
	errors: Dict[str, List[str]]
	has_errors: bool


class LintEngine:
	"""Simplified linter engine that processes nodes more efficiently."""

	def __init__(self, rules: List[LintingRule], debug_output_dir: Optional[str] = None):
		self.rules = rules
		self.model_builder = ViewModelBuilder()
		self.flattened_json = {}
		self.view_model = {}
		self.debug_output_dir = debug_output_dir

		# Create debug output directory if specified
		if self.debug_output_dir:
			Path(self.debug_output_dir).mkdir(parents=True, exist_ok=True)

	def get_view_model(self) -> Dict[str, List[Any]]:
		"""Return the structured view model."""
		return self.model_builder.build_model(self.flattened_json)

	def process(self, flattened_json: Dict[str, Any], source_file_path: Optional[str] = None) -> LintResults:
		"""Lint the given flattened JSON and return warnings and errors."""
		# Build the object model
		self.flattened_json = flattened_json
		self.view_model = self.get_view_model()

		# Save debug information if debug output directory is configured
		if self.debug_output_dir and source_file_path:
			self._save_debug_files(source_file_path)

		# Collect all nodes in a flat list, excluding generic collections to avoid duplicates
		# Generic collections ('bindings', 'scripts', 'event_handlers') are convenience collections
		# that contain the same nodes as specific collections, causing duplicates
		specific_collections = [
			'components', 'message_handlers', 'custom_methods', 'expression_bindings',
			'expression_struct_bindings', 'property_bindings', 'tag_bindings', 'query_bindings', 'script_transforms', 'event_handlers', 'properties'
		]
		all_nodes = []
		for collection_name in specific_collections:
			if collection_name in self.view_model:
				all_nodes.extend(self.view_model[collection_name])

		warnings = {}
		errors = {}

		# Apply each rule to the nodes
		for rule in self.rules:
			# Give rules access to flattened JSON if they need it
			if hasattr(rule, 'set_flattened_json'):
				rule.set_flattened_json(self.flattened_json)

			# Let the rule process all nodes it's interested in
			rule.process_nodes(all_nodes)

			# Collect warnings from this rule
			if rule.warnings:
				warnings[rule.error_key] = rule.warnings

			# Collect errors from this rule
			if rule.errors:
				errors[rule.error_key] = rule.errors

		return LintResults(warnings=warnings, errors=errors, has_errors=bool(errors))

	def get_model_statistics(self, flattened_json: Dict[str, Any]) -> Dict[str, Any]:
		"""Get statistics about the parsed model for debugging/analysis."""
		self.flattened_json = flattened_json
		self.view_model = self.get_view_model()

		# Get all nodes for analysis, excluding generic collections to avoid duplicates
		specific_collections = [
			'components', 'message_handlers', 'custom_methods', 'expression_bindings',
			'expression_struct_bindings', 'property_bindings', 'tag_bindings', 'query_bindings', 'script_transforms', 'event_handlers', 'properties'
		]
		all_nodes = []
		for collection_name in specific_collections:
			if collection_name in self.view_model:
				all_nodes.extend(self.view_model[collection_name])

		# Count by individual node types
		node_type_counts = {}
		for node_type in NodeType:
			count = len(NodeUtils.filter_by_types(all_nodes, {node_type}))
			if count > 0:  # Only include types that have nodes
				node_type_counts[node_type.value] = count

		# Count components by their actual type (Button, Label, etc.)
		components_by_type = {}
		component_nodes = NodeUtils.filter_by_types(all_nodes, {NodeType.COMPONENT})
		for comp in component_nodes:
			comp_type = getattr(comp, 'type', 'unknown')
			components_by_type[comp_type] = components_by_type.get(comp_type, 0) + 1

		# Get rule coverage statistics
		rule_coverage = self._get_rule_coverage_stats(all_nodes)

		stats = {
			'total_nodes': len(all_nodes),
			'node_type_counts': node_type_counts,
			'components_by_type': components_by_type,
			'rule_coverage': rule_coverage,
			'model_keys': list(self.view_model.keys()),
		}

		return stats

	def _get_rule_coverage_stats(self, all_nodes: List) -> Dict[str, Any]:
		"""Get statistics about which nodes each rule would process."""
		coverage = {}
		for rule in self.rules:
			rule_name = rule.__class__.__name__

			# Count how many nodes this rule would apply to
			if rule.target_node_types:
				applicable_nodes = NodeUtils.filter_by_types(all_nodes, rule.target_node_types)
				coverage[rule_name] = {
					'target_types': sorted([nt.value for nt in rule.target_node_types]),
					'applicable_node_count': len(applicable_nodes)
				}
			else:
				# Rule applies to all nodes
				coverage[rule_name] = {'target_types': ['all'], 'applicable_node_count': len(all_nodes)}

		return coverage

	def debug_nodes(self, flattened_json: Dict[str, Any], node_types: List[str] = None) -> List[Dict]:
		"""Get detailed information about nodes for debugging."""
		self.flattened_json = flattened_json
		self.view_model = self.get_view_model()

		all_nodes = []
		for node_list in self.view_model.values():
			all_nodes.extend(node_list)

		# Filter by node types if specified
		if node_types:
			target_types = set()

			for nt_str in node_types:
				try:
					target_types.add(NodeType(nt_str))
				except ValueError:
					print(
						f"Warning: Unknown node type '{nt_str}'. Available types: {[nt.value for nt in NodeType]}"
					)

			if target_types:
				all_nodes = NodeUtils.filter_by_types(all_nodes, target_types)

		# Return serialized node information
		return [node.serialize() for node in all_nodes]

	def analyze_rule_impact(self, flattened_json: Dict[str, Any]) -> Dict[str, Dict]:
		"""Analyze which nodes each rule would target."""
		self.flattened_json = flattened_json
		self.view_model = self.get_view_model()

		all_nodes = []
		for node_list in self.view_model.values():
			all_nodes.extend(node_list)

		analysis = {}
		for rule in self.rules:
			rule_name = rule.__class__.__name__

			if rule.target_node_types:
				applicable_nodes = NodeUtils.filter_by_types(all_nodes, rule.target_node_types)

				analysis[rule_name] = {
					'target_types': sorted([nt.value for nt in rule.target_node_types]),
					'applicable_nodes': len(applicable_nodes),
					'sample_paths': [node.path for node in applicable_nodes[:5]
							],  # First 5 as examples
					'node_details': [
						{
							'path': node.path,
							'type': node.node_type.value,
							'summary': self._get_node_summary(node)
						} for node in applicable_nodes[:3]  # First 3 with details
					]
				}
			else:
				analysis[rule_name] = {
					'target_types': ['all'],
					'applicable_nodes': len(all_nodes),
					'sample_paths': [node.path for node in all_nodes[:5]],
					'node_details': []  # Don't show details for rules that target everything
				}

		return analysis

	def _get_node_summary(self, node) -> str:
		"""Get a brief summary of what a node represents."""
		if node.node_type == NodeType.COMPONENT:
			return f"Component '{node.name}' of type '{getattr(node, 'type', 'unknown')}'"
		if node.node_type == NodeType.EXPRESSION_BINDING:
			expr_preview = node.expression[:50] + '...' if len(node.expression) > 50 else node.expression
			return f"Expression: {expr_preview}"
		if node.node_type == NodeType.TAG_BINDING:
			return f"Tag path: {getattr(node, 'tag_path', 'unknown')}"
		if node.node_type == NodeType.PROPERTY_BINDING:
			return f"Property path: {getattr(node, 'target_path', 'unknown')}"
		if hasattr(node, 'script'):
			script_preview = node.script[:30] + '...' if len(node.script) > 30 else node.script
			return f"Script: {script_preview}"
		return f"{node.node_type.value} node"

	def _save_debug_files(self, source_file_path: str):
		"""Save debug information (flattened JSON and model state) to files."""
		try:
			# Get a safe filename from the source path
			source_name = Path(source_file_path).stem

			# Save flattened JSON
			flattened_file = Path(self.debug_output_dir) / f"{source_name}_flattened.json"
			with open(flattened_file, 'w', encoding='utf-8') as f:
				json.dump(self.flattened_json, f, indent=2, sort_keys=True)

			# Serialize the view model
			serialized_model = self.serialize_view_model()

			# Save serialized model
			model_file = Path(self.debug_output_dir) / f"{source_name}_model.json"
			with open(model_file, 'w', encoding='utf-8') as f:
				json.dump(serialized_model, f, indent=2, sort_keys=True)

			# Save model statistics
			stats = self.get_model_statistics(self.flattened_json)
			stats_file = Path(self.debug_output_dir) / f"{source_name}_stats.json"
			with open(stats_file, 'w', encoding='utf-8') as f:
				json.dump(stats, f, indent=2, sort_keys=True)

			print("✅ Debug files saved:")
			print(f"   - Flattened JSON: {flattened_file}")
			print(f"   - Model state: {model_file}")
			print(f"   - Statistics: {stats_file}")

		except (OSError, PermissionError, TypeError, ValueError) as e:
			print(f"⚠️  Warning: Could not save debug files: {e}")

	def serialize_view_model(self) -> Dict[str, Any]:
		"""Serialize the view model to a JSON-compatible format."""
		serialized = {}

		for model_key, nodes in self.view_model.items():
			if nodes:  # Only include non-empty node lists
				serialized[model_key] = {
					'count': len(nodes),
					'nodes': [node.serialize() for node in nodes]
				}
			else:
				serialized[model_key] = {'count': 0, 'nodes': []}

		return serialized

	def enable_debug_output(self, debug_output_dir: str):
		"""Enable debug output to the specified directory."""
		self.debug_output_dir = debug_output_dir
		Path(self.debug_output_dir).mkdir(parents=True, exist_ok=True)
