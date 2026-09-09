"""
Derive a Perspective view's name and folder path from the location of its view.json.

Ignition stores each view as a directory named after the view, with the view's
definition in ``view.json`` inside it. Folders that group views are plain
directories with no resource files of their own:

    <project>/com.inductiveautomation.perspective/views/<Folder>/<SubFolder>/<ViewName>/view.json

The view name is therefore the directory containing view.json, and the folder
path is every directory between the ``views`` root and the view directory.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

PERSPECTIVE_MODULE_DIR = "com.inductiveautomation.perspective"
VIEWS_DIR = "views"


@dataclass(frozen=True)
class ViewLocation:
	"""Name and folder placement of a view, derived from its file path."""
	name: str
	folders: Tuple[str, ...] = ()
	views_root_found: bool = False

	@property
	def view_path(self) -> str:
		"""Slash-separated path of the view relative to the views root (e.g. ``Folder/Sub/ViewName``)."""
		return "/".join(self.folders + (self.name,))


def _find_views_root(parts: Sequence[str]) -> Optional[int]:
	"""
	Return the index of the ``views`` directory that acts as the views root, or None.

	Prefers the ``views`` directory directly under the Perspective module directory,
	the layout of an exported Ignition project. Falls back to the first bare ``views``
	segment, since paths are usually given relative to the project root and any
	leading segments belong to the project rather than the view tree.
	"""
	for index in range(len(parts) - 1):
		if parts[index] == PERSPECTIVE_MODULE_DIR and parts[index + 1] == VIEWS_DIR:
			return index + 1
	for index, part in enumerate(parts):
		if part == VIEWS_DIR:
			return index
	return None


def resolve_view_location(source_file_path: Union[str, Path, None]) -> Optional[ViewLocation]:
	"""
	Derive the view name and parent folders from the path of a view.json file.

	Returns None when the path has no parent directory to name the view after.
	When no views root can be found, the immediate parent directory is taken as the
	view name and no folders are reported (``views_root_found`` is False).
	"""
	if not source_file_path:
		return None

	directories = Path(source_file_path).parent.parts
	directories = tuple(part for part in directories if part not in ("", "/", "\\"))
	if not directories:
		return None

	root_index = _find_views_root(directories)
	if root_index is None or root_index == len(directories) - 1:
		# No anchor, or view.json sits directly inside the views root.
		return ViewLocation(name=directories[-1], folders=(), views_root_found=False)

	below_root = directories[root_index + 1:]
	return ViewLocation(name=below_root[-1], folders=tuple(below_root[:-1]), views_root_found=True)
