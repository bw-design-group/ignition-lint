"""
Linting engine: loads a resource file through its domain spec, runs the configured rules
over the resulting nodes and collects the results.

The engine is domain-agnostic. Everything that differs between Perspective views, library
scripts and future resource kinds is declared on a ``DomainSpec`` (see ``common/domain.py``);
the engine only ever sees a ``LoadedFile``. ``process()`` remains as the Perspective-only
entry point used by tests and the debug-file generator.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Any, NamedTuple, Optional, Tuple

from .common.domain import DomainSpec, LoadedFile
from .common.path_translator import PathTranslator
from .domains.perspective import collect_nodes
from .rules.common import LintingRule
from .model.builder import ViewModelBuilder
from .model.node_types import NodeType, NodeUtils


class LintResults(NamedTuple):
	"""Results from linting process."""
	warnings: Dict[str, List[str]]
	errors: Dict[str, List[str]]
	has_errors: bool
	rule_timings: Dict[str, float] = {}
	custom_formatted_warnings: Dict[str, str] = {}  # rule_name -> custom formatted warnings
	custom_formatted_errors: Dict[str, str] = {}  # rule_name -> custom formatted errors
	fixes: List[Any] = []  # List of Fix objects from fixable rules


def merge_lint_results(results: List[LintResults]) -> LintResults:
	"""Combine several LintResults (e.g. one per domain engine) into one."""
	warnings: Dict[str, List[str]] = {}
	errors: Dict[str, List[str]] = {}
	rule_timings: Dict[str, float] = {}
	custom_warnings: Dict[str, str] = {}
	custom_errors: Dict[str, str] = {}
	fixes: List[Any] = []
	for result in results:
		for key, values in result.warnings.items():
			warnings.setdefault(key, []).extend(values)
		for key, values in result.errors.items():
			errors.setdefault(key, []).extend(values)
		rule_timings.update(result.rule_timings)
		custom_warnings.update(result.custom_formatted_warnings)
		custom_errors.update(result.custom_formatted_errors)
		fixes.extend(result.fixes)
	return LintResults(
		warnings=warnings,
		errors=errors,
		has_errors=bool(errors),
		rule_timings=rule_timings,
		custom_formatted_warnings=custom_warnings,
		custom_formatted_errors=custom_errors,
		fixes=fixes,
	)


# Marker written into a --debug-output directory ign-lint created (or found empty). Lines after
# the header list the folders the last run wrote; cleanup removes exactly those and nothing else.
DEBUG_OUTPUT_MARKER = ".ignition-lint-debug"
_DEBUG_OUTPUT_MARKER_HEADER = (
	"# Created by ign-lint --debug-output. The lines below list folders written by the last run;\n"
	"# they are removed at the start of the next run. Do not store anything else in this directory.\n"
)
_UNOWNED_DEBUG_DIRS_WARNED: set = set()


def prepare_debug_output_dir(debug_output_dir: str) -> Path:
	"""
	Create a --debug-output directory and mark it as owned by ign-lint.

	Only a directory ign-lint creates, or one that is already empty, receives the marker.
	A pre-existing directory holding other files is written into but never marked, so
	cleanup never touches it; a warning says so once per process.
	"""
	path = Path(debug_output_dir)
	if path.exists() and not path.is_dir():
		raise NotADirectoryError(f"--debug-output target is not a directory: {debug_output_dir}")
	marker = path / DEBUG_OUTPUT_MARKER
	if marker.exists():
		return path
	if path.is_dir() and any(path.iterdir()):
		key = str(path.resolve())
		if key not in _UNOWNED_DEBUG_DIRS_WARNED:
			_UNOWNED_DEBUG_DIRS_WARNED.add(key)
			print(
				f"⚠️  --debug-output directory '{debug_output_dir}' already contains other files; "
				"ign-lint will write into it but will not clean it between runs"
			)
		return path
	path.mkdir(parents=True, exist_ok=True)
	marker.write_text(_DEBUG_OUTPUT_MARKER_HEADER, encoding='utf-8')
	return path


def read_debug_output_manifest(marker: Path) -> List[str]:
	"""Return the relative folders listed in a marker file, de-duplicated and confined to the directory."""
	entries: List[str] = []
	try:
		lines = marker.read_text(encoding='utf-8').splitlines()
	except OSError:
		return entries
	for line in lines:
		entry = line.strip()
		if not entry or entry.startswith('#'):
			continue
		parts = Path(entry).parts
		if Path(entry).is_absolute() or '..' in parts or entry in entries:
			continue
		entries.append(entry)
	return entries


def write_debug_output_manifest(marker: Path, entries: List[str]) -> None:
	"""Rewrite a marker file with its header and the given relative folders."""
	marker.write_text(_DEBUG_OUTPUT_MARKER_HEADER + "".join(f"{entry}\n" for entry in entries), encoding='utf-8')


def record_debug_output_entry(debug_output_dir: str, relative_dir: Path) -> None:
	"""Append one written folder to the marker manifest when the directory is ign-lint owned."""
	marker = Path(debug_output_dir) / DEBUG_OUTPUT_MARKER
	if not marker.exists():
		return
	with open(marker, 'a', encoding='utf-8') as f:
		f.write(f"{relative_dir.as_posix()}\n")


def debug_output_subdir(source_file_path: str) -> Path:
	"""
	Relative folder under the debug dir for one source file.

	Mirrors the source file's parent folder relative to the working directory
	(``views/Dashboard/view.json`` -> ``views/Dashboard``) so a thousand ``view.json``
	files never collide. Files outside the working directory use their absolute path
	without the drive/root; every part is filesystem-safe.
	"""
	resolved = Path(source_file_path).resolve()
	try:
		relative = resolved.relative_to(Path.cwd())
	except ValueError:
		relative = Path(*resolved.parts[1:]) if resolved.is_absolute() else resolved
	parts = list(relative.parent.parts) or [resolved.stem]
	safe = [re.sub(r'[^A-Za-z0-9_.-]+', '_', part) for part in parts if part not in ('', '.')]
	return Path(*safe) if safe else Path(re.sub(r'[^A-Za-z0-9_.-]+', '_', resolved.stem))


class LintEngine:
	"""Runs rules over the nodes of one loaded file at a time."""

	def __init__(self, rules: List[LintingRule], debug_output_dir: Optional[str] = None):
		self.rules = rules
		self.model_builder = ViewModelBuilder()
		self.flattened_json: Dict[str, Any] = {}
		self.source_file_path: Optional[str] = None
		self.view_model: Dict[str, List[Any]] = {}
		self.last_loaded: Optional[LoadedFile] = None
		self.debug_output_dir = debug_output_dir

		if self.debug_output_dir:
			prepare_debug_output_dir(self.debug_output_dir)

	# ------------------------------------------------------------------ loading

	def get_view_model(self, source_file_path: Optional[str] = None) -> Dict[str, List[Any]]:
		"""
		Build the Perspective view model from ``self.flattened_json``.

		Args:
			source_file_path: Path of the view.json being modeled. When given, the model
				includes a 'view' node carrying the view name and folder path derived
				from the file location.
		"""
		return self.model_builder.build_model(self.flattened_json, source_file_path=source_file_path)

	def _load_view(
		self, flattened_json: Dict[str, Any], json_data=None, *, source_file_path: Optional[str] = None
	) -> LoadedFile:
		"""
		Perspective-only loader used by ``process()`` and the dict form of the analysis helpers.

		Reuses the current model when both the flattened JSON (by identity) and the source
		path are unchanged; the path matters because it is what the 'view' node is built from.
		"""
		if (
			self.flattened_json is not flattened_json or self.source_file_path != source_file_path or
			not self.view_model
		):
			self.flattened_json = flattened_json
			self.source_file_path = source_file_path
			self.view_model = self.get_view_model(source_file_path)
		loaded = LoadedFile(
			nodes=collect_nodes(self.view_model), model=self.view_model, flattened_json=flattened_json,
			json_data=json_data
		)
		self.last_loaded = loaded
		return loaded

	def _set_loaded(self, loaded: LoadedFile, source_file_path: Optional[str] = None) -> None:
		self.last_loaded = loaded
		self.flattened_json = loaded.flattened_json
		self.source_file_path = source_file_path
		self.view_model = loaded.model

	# ------------------------------------------------------------------ linting

	def process_file(self, path: Path, spec: DomainSpec, *, enable_timing: bool = False,
				fix_mode: bool = False) -> Tuple[LoadedFile, LintResults]:
		"""
		Load ``path`` through ``spec`` and lint it.

		Fix context (original JSON plus a PathTranslator) is only established when the
		loader returned a JSON document, so non-JSON domains simply never see fixes.
		"""
		loaded = spec.load(Path(path))
		self._set_loaded(loaded, str(path))

		if self.debug_output_dir:
			self._save_debug_files(str(path))

		json_data = loaded.json_data if (fix_mode and loaded.json_data is not None) else None
		path_translator = PathTranslator(json_data) if json_data is not None else None
		results = self._run_rules(
			loaded.nodes, loaded.flattened_json, str(path), enable_timing=enable_timing,
			json_data=json_data, path_translator=path_translator
		)
		return loaded, results

	def process(
		self, flattened_json: Dict[str, Any], source_file_path: Optional[str] = None,
		enable_timing: bool = False, *, json_data=None, path_translator=None
	) -> LintResults:
		"""
		Lint an already-flattened Perspective view and return warnings and errors.

		Args:
			flattened_json: The flattened JSON data to lint.
			source_file_path: Optional path to the source file being linted. Also the
				source of the 'view' node (view name and folder path).
			enable_timing: Whether to time rule execution.
			json_data: Optional original JSON data (needed for fix mode).
			path_translator: Optional PathTranslator instance (needed for fix mode).
		"""
		loaded = self._load_view(flattened_json, json_data, source_file_path=source_file_path)

		if self.debug_output_dir and source_file_path:
			self._save_debug_files(source_file_path)

		return self._run_rules(
			loaded.nodes, flattened_json, source_file_path, enable_timing=enable_timing,
			json_data=json_data, path_translator=path_translator
		)

	def _run_rules(
		self, all_nodes: List[Any], flattened_json: Dict[str, Any], source_file_path: Optional[str], *,
		enable_timing: bool = False, json_data=None, path_translator=None
	) -> LintResults:
		"""Apply every rule to ``all_nodes`` and collect the results."""
		warnings = {}
		errors = {}
		rule_timings = {}
		custom_formatted_warnings = {}
		custom_formatted_errors = {}

		for rule in self.rules:
			if enable_timing:
				start_time = time.perf_counter()

			self._prepare_rule(
				rule, flattened_json, source_file_path, json_data=json_data,
				path_translator=path_translator
			)

			# Let the rule process all nodes it's interested in
			rule.process_nodes(all_nodes)

			if enable_timing:
				duration_ms = (time.perf_counter() - start_time) * 1000.0
				rule_timings[rule.__class__.__name__] = duration_ms

			# Capture custom formatted output BEFORE collecting violations
			# (this must happen before process_nodes resets structured violations)
			self._collect_custom_formatted(rule, custom_formatted_warnings, custom_formatted_errors)

			if rule.warnings:
				warnings[rule.error_key] = rule.warnings
			if rule.errors:
				errors[rule.error_key] = rule.errors

		all_fixes = self._collect_fixes()

		return LintResults(
			warnings=warnings,
			errors=errors,
			has_errors=bool(errors),
			rule_timings=rule_timings,
			custom_formatted_warnings=custom_formatted_warnings,
			custom_formatted_errors=custom_formatted_errors,
			fixes=all_fixes,
		)

	def _prepare_rule(self, rule, flattened_json, source_file_path, *, json_data=None, path_translator=None):
		"""Set up a rule with context before processing nodes."""
		if hasattr(rule, 'set_flattened_json'):
			rule.set_flattened_json(flattened_json)
		if hasattr(rule, 'set_source_file'):
			rule.set_source_file(source_file_path)
		if json_data is not None and path_translator is not None:
			if hasattr(rule, 'set_fix_context'):
				rule.set_fix_context(json_data, path_translator)

	def _collect_custom_formatted(self, rule, custom_formatted_warnings, custom_formatted_errors):
		"""Capture custom formatted output from a rule."""
		if hasattr(rule, 'format_violations_grouped'):
			formatted_output = rule.format_violations_grouped()
			if formatted_output:
				if formatted_output.get('warnings'):
					custom_formatted_warnings[rule.error_key] = formatted_output['warnings']
				if formatted_output.get('errors'):
					custom_formatted_errors[rule.error_key] = formatted_output['errors']

	def _collect_fixes(self) -> List[Any]:
		"""Collect fixes from all fixable rules."""
		all_fixes = []
		for rule in self.rules:
			if hasattr(rule, 'supports_fix') and rule.supports_fix:
				all_fixes.extend(rule.get_fixes())
		return all_fixes

	def finalize_batch_rules(self, enable_timing: bool = False) -> LintResults:
		"""
		Finalize batch rules after all files have been processed.

		This method should be called after processing all files to allow batch rules
		(like PerspectiveScriptPylintRule in batch mode) to process accumulated data.

		Args:
			enable_timing: Whether to time rule finalization

		Returns:
			LintResults containing any warnings/errors from finalization
		"""
		warnings = {}
		errors = {}
		rule_timings = {}
		custom_formatted_warnings = {}
		custom_formatted_errors = {}

		for rule in self.rules:
			if not hasattr(rule, 'finalize'):
				continue

			if enable_timing:
				start_time = time.perf_counter()

			rule.finalize()

			if enable_timing:
				duration_ms = (time.perf_counter() - start_time) * 1000.0
				rule_timings[f"{rule.__class__.__name__}_finalize"] = duration_ms

			self._collect_custom_formatted(rule, custom_formatted_warnings, custom_formatted_errors)

			if rule.warnings:
				warnings[rule.error_key] = rule.warnings
			if rule.errors:
				errors[rule.error_key] = rule.errors

		return LintResults(
			warnings=warnings,
			errors=errors,
			has_errors=bool(errors),
			rule_timings=rule_timings,
			custom_formatted_warnings=custom_formatted_warnings,
			custom_formatted_errors=custom_formatted_errors,
		)

	# --------------------------------------------------------------- analysis

	def _nodes_for_analysis(self, source=None,
				source_file_path: Optional[str] = None) -> Tuple[List[Any], Dict[str, List[Any]]]:
		"""
		Resolve ``source`` to ``(nodes, model)``.

		``source`` may be a LoadedFile, a flattened Perspective view (dict) or None for the
		most recently loaded file. ``source_file_path`` only applies to the dict form and
		is what gives the model its 'view' node.
		"""
		if isinstance(source, LoadedFile):
			self._set_loaded(source)
			return source.nodes, source.model
		if isinstance(source, dict):
			loaded = self._load_view(source, source_file_path=source_file_path)
			return loaded.nodes, loaded.model
		if self.last_loaded is not None:
			return self.last_loaded.nodes, self.last_loaded.model
		return [], {}

	def get_model_statistics(self, source=None, source_file_path: Optional[str] = None) -> Dict[str, Any]:
		"""Get statistics about the parsed model for debugging/analysis."""
		all_nodes, model = self._nodes_for_analysis(source, source_file_path)

		node_type_counts = {}
		for node_type in NodeType:
			count = len(NodeUtils.filter_by_types(all_nodes, {node_type}))
			if count > 0:  # Only include types that have nodes
				node_type_counts[node_type.value] = count

		# Count components by their actual type (Button, Label, etc.)
		components_by_type = {}
		for comp in NodeUtils.filter_by_types(all_nodes, {NodeType.COMPONENT}):
			comp_type = getattr(comp, 'type', 'unknown')
			components_by_type[comp_type] = components_by_type.get(comp_type, 0) + 1

		return {
			'total_nodes': len(all_nodes),
			'node_type_counts': node_type_counts,
			'components_by_type': components_by_type,
			'rule_coverage': self._get_rule_coverage_stats(all_nodes),
			'model_keys': list(model.keys()),
		}

	def _get_rule_coverage_stats(self, all_nodes: List) -> Dict[str, Any]:
		"""Get statistics about which nodes each rule would process."""
		coverage = {}
		for rule in self.rules:
			rule_name = rule.__class__.__name__
			if rule.target_node_types:
				applicable_nodes = NodeUtils.filter_by_types(all_nodes, rule.target_node_types)
				coverage[rule_name] = {
					'target_types': sorted([nt.value for nt in rule.target_node_types]),
					'applicable_node_count': len(applicable_nodes)
				}
			else:
				coverage[rule_name] = {'target_types': ['all'], 'applicable_node_count': len(all_nodes)}
		return coverage

	def debug_nodes(self, source=None, node_types: List[str] = None,
			source_file_path: Optional[str] = None) -> List[Dict]:
		"""Get detailed information about nodes for debugging."""
		_, model = self._nodes_for_analysis(source, source_file_path)
		all_nodes = [node for node_list in model.values() for node in node_list]

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

		return [node.serialize() for node in all_nodes]

	def analyze_rule_impact(self, source=None, source_file_path: Optional[str] = None) -> Dict[str, Dict]:
		"""Analyze which nodes each rule would target."""
		_, model = self._nodes_for_analysis(source, source_file_path)
		all_nodes = [node for node_list in model.values() for node in node_list]

		analysis = {}
		for rule in self.rules:
			rule_name = rule.__class__.__name__

			if rule.target_node_types:
				applicable_nodes = NodeUtils.filter_by_types(all_nodes, rule.target_node_types)
				analysis[rule_name] = {
					'target_types': sorted([nt.value for nt in rule.target_node_types]),
					'applicable_nodes': len(applicable_nodes),
					'sample_paths': [node.path for node in applicable_nodes[:5]],
					'node_details': [{
						'path': node.path,
						'type': node.node_type.value,
						'summary': self._get_node_summary(node)
					} for node in applicable_nodes[:3]]
				}
			else:
				analysis[rule_name] = {
					'target_types': ['all'],
					'applicable_nodes': len(all_nodes),
					'sample_paths': [node.path for node in all_nodes[:5]],
					'node_details': []
				}

		return analysis

	def _get_node_summary(self, node) -> str:
		"""Get a brief summary of what a node represents."""
		if node.node_type == NodeType.COMPONENT:
			return f"Component '{node.name}' of type '{getattr(node, 'type', 'unknown')}'"
		if node.node_type == NodeType.VIEW:
			return f"View '{node.name}' in folder '{'/'.join(node.folder_path) or '(views root)'}'"
		if node.node_type == NodeType.EXPRESSION_BINDING:
			expr_preview = node.expression[:50] + '...' if len(node.expression) > 50 else node.expression
			return f"Expression: {expr_preview}"
		if node.node_type == NodeType.TAG_BINDING:
			return f"Tag path: {getattr(node, 'tag_path', 'unknown')}"
		if node.node_type == NodeType.PROPERTY_BINDING:
			return f"Property path: {getattr(node, 'target_path', 'unknown')}"
		if node.node_type in (NodeType.SCRIPT_MODULE, NodeType.SCRIPT_PACKAGE):
			return f"{node.node_type.value} '{getattr(node, 'name', '')}' ({node.path})"
		if hasattr(node, 'script'):
			script_preview = node.script[:30] + '...' if len(node.script) > 30 else node.script
			return f"Script: {script_preview}"
		return f"{node.node_type.value} node"

	# ------------------------------------------------------------ debug output

	def _save_debug_files(self, source_file_path: str):
		"""
		Save debug information for one file under ``<debug_output_dir>/<mirrored source folder>/``.

		Writes ``flattened.json`` (JSON domains only), ``model.json`` and ``stats.json`` with
		plain names, so the layout matches the golden files in ``tests/debug/cases/``.
		"""
		try:
			subdir = debug_output_subdir(source_file_path)
			target_dir = Path(self.debug_output_dir) / subdir
			target_dir.mkdir(parents=True, exist_ok=True)

			if self.flattened_json:
				with open(target_dir / 'flattened.json', 'w', encoding='utf-8') as f:
					json.dump(self.flattened_json, f, indent=2, sort_keys=True)

			with open(target_dir / 'model.json', 'w', encoding='utf-8') as f:
				json.dump(self.serialize_view_model(), f, indent=2, sort_keys=True)

			with open(target_dir / 'stats.json', 'w', encoding='utf-8') as f:
				json.dump(self.get_model_statistics(), f, indent=2, sort_keys=True)
			record_debug_output_entry(self.debug_output_dir, subdir)

			shown = os.path.relpath(target_dir)
			if shown.startswith('..'):
				shown = str(target_dir)
			print(f"🔍 Debug files saved to: {shown}")

		except (OSError, PermissionError, TypeError, ValueError) as e:
			print(f"⚠️  Warning: Could not save debug files: {e}")

	def serialize_view_model(self) -> Dict[str, Any]:
		"""Serialize the current model (``self.view_model``) to a JSON-compatible format."""
		serialized = {}
		for model_key, nodes in self.view_model.items():
			serialized[model_key] = {'count': len(nodes), 'nodes': [node.serialize() for node in nodes]}
		return serialized

	def enable_debug_output(self, debug_output_dir: str):
		"""Enable debug output to the specified directory."""
		self.debug_output_dir = debug_output_dir
		prepare_debug_output_dir(self.debug_output_dir)
