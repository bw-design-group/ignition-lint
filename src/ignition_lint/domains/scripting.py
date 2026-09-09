"""Scripting domain: Ignition project-library modules (``script-python/**/code.py``)."""

from pathlib import Path

from ..common.domain import DomainSpec, LintDomain, LoadedFile
from ..model.script_builder import ScriptModelBuilder


def matches_library_module(path: Path) -> bool:
	"""
	True for project-library modules.

	A ``code.py`` counts when it sits under a ``script-python`` folder, or when a sibling
	``resource.json`` marks it as an Ignition resource (fixtures checked out on their own).
	"""
	path = Path(path)
	if path.name != ScriptModelBuilder.MODULE_FILE:
		return False
	if ScriptModelBuilder.find_library_root(path) is not None:
		return True
	return (path.parent / ScriptModelBuilder.RESOURCE_FILE).exists()


def load_library_module(path: Path) -> LoadedFile:
	"""Load one library module and its enclosing packages as nodes."""
	return ScriptModelBuilder().build_from_file(Path(path))


SCRIPTING_SPEC = DomainSpec(
	domain=LintDomain.SCRIPTING,
	display_name="script library module",
	matches=matches_library_module,
	load=load_library_module,
	default_globs=(),
)
