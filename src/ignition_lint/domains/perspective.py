"""Perspective view domain: ``view.json`` files loaded through ``ViewModelBuilder``."""

import time
from pathlib import Path
from typing import Any, Dict, List

from ..common.domain import DomainSpec, LintDomain, LoadedFile
from ..common.flatten_json import flatten_json, read_json_file
from ..model.builder import ViewModelBuilder
from ..model.node_types import ViewNode

VIEW_FILE_NAME = "view.json"

# Collections that together hold every node exactly once. The builder also fills
# convenience collections ('bindings', 'scripts') that repeat these nodes.
SPECIFIC_COLLECTIONS = (
	'components', 'message_handlers', 'custom_methods', 'expression_bindings', 'expression_struct_bindings',
	'property_bindings', 'tag_bindings', 'query_bindings', 'script_transforms', 'event_handlers',
	'property_change_scripts', 'properties'
)


def collect_nodes(model: Dict[str, List[ViewNode]]) -> List[ViewNode]:
	"""Flatten a view model into a de-duplicated node list in stable collection order."""
	nodes: List[ViewNode] = []
	for collection_name in SPECIFIC_COLLECTIONS:
		nodes.extend(model.get(collection_name, []))
	return nodes


def load_view_json(json_data: Any, flattened_json: Dict[str, Any] = None) -> LoadedFile:
	"""Build a :class:`LoadedFile` from an already-parsed view document."""
	if flattened_json is None:
		flattened_json = flatten_json(json_data)
	model = ViewModelBuilder().build_model(flattened_json)
	return LoadedFile(nodes=collect_nodes(model), model=model, flattened_json=flattened_json, json_data=json_data)


def load_view_file(path: Path) -> LoadedFile:
	"""Read, flatten and model a ``view.json`` file, recording per-phase timings."""
	started = time.perf_counter()
	json_data = read_json_file(str(path))
	read_done = time.perf_counter()
	flattened_json = flatten_json(json_data)
	flatten_done = time.perf_counter()
	loaded = load_view_json(json_data, flattened_json)
	loaded.timings = {
		'file_read_ms': (read_done - started) * 1000.0,
		'json_flatten_ms': (flatten_done - read_done) * 1000.0,
		'model_build_ms': (time.perf_counter() - flatten_done) * 1000.0,
	}
	return loaded


def matches_view_file(path: Path) -> bool:
	"""True for Perspective view resources."""
	return Path(path).name == VIEW_FILE_NAME


PERSPECTIVE_SPEC = DomainSpec(
	domain=LintDomain.PERSPECTIVE,
	display_name="Perspective view",
	matches=matches_view_file,
	load=load_view_file,
	default_globs=(f"**/{VIEW_FILE_NAME}",),
)
