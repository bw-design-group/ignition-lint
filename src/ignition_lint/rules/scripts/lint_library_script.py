"""
Pylint rule for Ignition project-library modules (``ignition/script-python/**/code.py``).

Each module is a complete Python file, so pylint runs on it directly and line numbers map
1:1. Configuration is independent from ``PerspectiveScriptPylintRule``: its own ``pylintrc``
(default ``.config/.ignition-library-pylintrc``), its own ``category_mapping`` and an
``additional_builtins`` list. Top-level library packages are implicit globals in Ignition
scripts, so when the module lives under a ``script-python`` folder its sibling top-level
packages are discovered and declared as builtins automatically.
"""

import configparser
import os
import tempfile
from typing import List, Optional

from ..common import LintingRule
from ...common.domain import LintDomain
from ...model.node_types import NodeType, ScriptModule
from ...model.script_builder import ScriptModelBuilder
from .pylint_support import (
	PylintCategoryMixin,
	PylintViolation,
	build_pylint_args,
	parse_pylint_messages,
	resolve_pylintrc,
	run_pylint,
)

LIBRARY_PYLINTRC_NAME = ".ignition-library-pylintrc"


def read_rcfile_list_option(rcfile: Optional[str], option: str) -> List[str]:
	"""
	Read a comma-separated list option from an INI-style pylintrc, ``[]`` when absent.

	Needed because a value passed on the command line *replaces* the rcfile's value, so
	extending ``additional-builtins`` requires merging with what the rcfile declares.
	"""
	if not rcfile:
		return []
	parser = configparser.RawConfigParser(strict=False)
	try:
		parser.read(rcfile, encoding='utf-8')
	except (configparser.Error, OSError, UnicodeDecodeError):
		return []
	for section in parser.sections():
		if parser.has_option(section, option):
			raw = parser.get(section, option)
			return [item.strip() for item in raw.replace('\n', ',').split(',') if item.strip()]
	return []


class LibraryScriptPylintRule(PylintCategoryMixin, LintingRule):
	"""Runs pylint on project-library script modules."""

	domain = LintDomain.SCRIPTING

	def __init__(
		self, severity="error", pylintrc=None, debug=False, *, category_mapping=None, additional_builtins=None
	):
		super().__init__({NodeType.SCRIPT_MODULE}, severity=severity)
		self.debug = debug
		self.pylintrc = resolve_pylintrc(pylintrc, LIBRARY_PYLINTRC_NAME)
		self.init_category_mapping(category_mapping)
		self.additional_builtins: List[str] = list(additional_builtins or [])
		self.current_source_file: Optional[str] = None
		self.collected_modules: List[ScriptModule] = []
		self._rc_builtins: Optional[List[str]] = None

		if self.debug:
			name = self.__class__.__name__
			if self.pylintrc:
				print(f"🔍 {name}: Using pylintrc: {self.pylintrc}")
			else:
				print(f"🔍 {name}: No pylintrc found, using inline configuration")
			print(f"🔍 {name}: Category mapping: {self.category_mapping}")

	@property
	def error_message(self) -> str:
		return "Pylint detected issues in library script module"

	def set_source_file(self, source_file_path: Optional[str]) -> None:
		"""Record the file being processed (called by LintEngine)."""
		self.current_source_file = source_file_path

	def process_nodes(self, nodes):
		"""Reset per-file state, then collect and lint the module nodes."""
		self.pylint_violations = []
		self.collected_modules = []
		super().process_nodes(nodes)

	def visit_script_module(self, node):
		if isinstance(node, ScriptModule):
			self.collected_modules.append(node)

	def post_process(self):
		"""Lint every collected module and register one placeholder violation per message."""
		for module in self.collected_modules:
			self._lint_module(module)

		# Placeholders keep the counts right; format_violations_grouped() renders the text.
		for violation in self.pylint_violations:
			self.add_violation("", severity=self.severity_for_category(violation.category))

	def _format_violation_path(self, path: str) -> str:
		# One file = one module, and the file header already names it.
		return "" if len(self.collected_modules) <= 1 else path

	def _lint_module(self, module: ScriptModule) -> None:
		target = module.file_path if module.file_path and os.path.exists(module.file_path) else None
		temp_path = None
		if target is None:
			# Node built in memory (tests, future loaders): lint a temporary copy.
			with tempfile.NamedTemporaryFile(prefix="ign_lib_", suffix=".py", delete=False) as handle:
				handle.write(module.script.encode('utf-8'))
				temp_path = handle.name
			target = temp_path

		try:
			extra = self._builtins_args(target)
			output = run_pylint(build_pylint_args(self.pylintrc, [target], extra=extra))
		finally:
			if temp_path:
				try:
					os.remove(temp_path)
				except OSError:
					pass

		for line_num, code, category, message in parse_pylint_messages(output):
			self.pylint_violations.append(
				PylintViolation(
					category=category, code=code, message=message, path=module.path, line=line_num
				)
			)

	def _builtins_args(self, target: str) -> List[str]:
		"""``--additional-builtins`` merging rcfile names, discovered packages and user names."""
		names: List[str] = []
		for name in self._rcfile_builtins(
		) + self._discover_top_level_packages(target) + self.additional_builtins:
			if name and name not in names:
				names.append(name)
		if not names:
			return []
		if self.debug:
			print(f"🔍 {self.__class__.__name__}: additional builtins: {', '.join(names)}")
		return [f"--additional-builtins={','.join(names)}"]

	def _rcfile_builtins(self) -> List[str]:
		if self._rc_builtins is None:
			self._rc_builtins = read_rcfile_list_option(self.pylintrc, 'additional-builtins')
		return self._rc_builtins

	@staticmethod
	def _discover_top_level_packages(target: str) -> List[str]:
		"""Names of the top-level package folders beside this module's package, if any."""
		root = ScriptModelBuilder.find_library_root(target)
		if root is None:
			return []
		try:
			entries = sorted(os.listdir(root))
		except OSError:
			return []
		return [
			name for name in entries
			if not name.startswith('.') and os.path.isdir(os.path.join(root, name)) and name.isidentifier()
		]
