"""
Builds scripting-domain nodes from an Ignition project-library module on disk.

Ignition stores the project script library as ``<project>/ignition/script-python/<Pkg>/.../<Name>/code.py``
with a sibling ``resource.json`` carrying scope and modification metadata. The dotted module path
Ignition scripts import (``Pkg.Name``) is the directory chain after ``script-python``; every folder in
between is a package.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from ..common.domain import LoadedFile
from .node_types import ScriptModule, ScriptPackage, ViewNode


class ScriptModelBuilder:
	"""Builds ``ScriptModule``/``ScriptPackage`` nodes for one ``code.py`` file."""

	LIBRARY_DIR = "script-python"
	MODULE_FILE = "code.py"
	RESOURCE_FILE = "resource.json"

	def __init__(self):
		self.model: Dict[str, List[ViewNode]] = self._empty_model()
		self.library_root: Optional[Path] = None

	@staticmethod
	def _empty_model() -> Dict[str, List[ViewNode]]:
		return {'script_modules': [], 'script_packages': []}

	@classmethod
	def find_library_root(cls, path: Path) -> Optional[Path]:
		"""Return the innermost ``script-python`` ancestor of ``path``, or None."""
		resolved = Path(path).resolve()
		parts = resolved.parts
		for index in range(len(parts) - 1, -1, -1):
			if parts[index] == cls.LIBRARY_DIR:
				return Path(*parts[:index + 1])
		return None

	@classmethod
	def module_parts(cls, path: Path) -> List[str]:
		"""
		Directory names that make up the dotted module path.

		With a ``script-python`` ancestor these are the folders between it and ``code.py``
		(empty when the file sits directly in ``script-python``, which Ignition never writes).
		Without one (e.g. fixtures checked out on their own) only the parent folder name is
		used, so the working directory never leaks into module or package names.
		"""
		resolved = Path(path).resolve()
		root = cls.find_library_root(resolved)
		if root is None:
			return [resolved.parent.name]
		return list(resolved.parent.relative_to(root).parts)

	@classmethod
	def read_resource(cls, module_dir: Path) -> Dict:
		"""Parse the sibling ``resource.json``; ``{}`` when missing or invalid."""
		resource_file = Path(module_dir) / cls.RESOURCE_FILE
		try:
			with open(resource_file, 'r', encoding='utf-8') as handle:
				data = json.load(handle)
		except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError):
			return {}
		return data if isinstance(data, dict) else {}

	def build_from_file(self, path: Path) -> LoadedFile:
		"""Load ``path`` (a ``code.py``) and return its nodes as a :class:`LoadedFile`."""
		file_path = Path(path)
		resolved = file_path.resolve()
		self.model = self._empty_model()
		self.library_root = self.find_library_root(resolved)

		parts = self.module_parts(resolved)
		if not parts:
			raise ValueError(
				f"{file_path} sits directly inside '{self.LIBRARY_DIR}'; Ignition library modules live in a "
				f"named folder ({self.LIBRARY_DIR}/<Package>/{self.MODULE_FILE})"
			)

		if self.library_root is not None:
			for depth in range(1, len(parts)):
				package_parts = parts[:depth]
				self.model['script_packages'].append(
					ScriptPackage(
						".".join(package_parts), package_parts[-1],
						dir_path=str(self.library_root.joinpath(*package_parts))
					)
				)

		with open(resolved, 'r', encoding='utf-8', errors='replace') as handle:
			source = handle.read()

		module = ScriptModule(
			".".join(parts), parts[-1], source, file_path=str(file_path),
			resource=self.read_resource(resolved.parent)
		)
		self.model['script_modules'].append(module)

		nodes: List[ViewNode] = list(self.model['script_packages']) + [module]
		return LoadedFile(nodes=nodes, model=dict(self.model))
