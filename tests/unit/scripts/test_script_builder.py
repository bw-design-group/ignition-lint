# pylint: disable=import-error,wrong-import-position
"""Unit tests for ScriptModelBuilder (scripting-domain node construction)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'src'))

from ignition_lint.model.node_types import NodeType, ScriptModule, ScriptPackage
from ignition_lint.model.script_builder import ScriptModelBuilder

SCRIPTING_DIR = Path(__file__).parent.parent.parent / 'cases' / 'scripting'


def _make_module(root: Path, *parts: str, source: str = "X = 1\n", resource=None) -> Path:
	module_dir = root.joinpath(*parts)
	module_dir.mkdir(parents=True, exist_ok=True)
	(module_dir / 'code.py').write_text(source, encoding='utf-8')
	if resource is not None:
		(module_dir / 'resource.json').write_text(resource, encoding='utf-8')
	return module_dir / 'code.py'


class TestScriptModelBuilder(unittest.TestCase):
	"""Dotted paths, packages, resource metadata and the no-ancestor fallback."""

	def __init__(self, method_name='runTest'):
		"""Init  ."""
		super().__init__(method_name)
		self.tmp = None
		self.library = None

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
		self.library = Path(self.tmp.name) / 'proj' / 'ignition' / 'script-python'

	def tearDown(self):
		"""Remove the temporary library tree."""
		self.tmp.cleanup()

	def test_dotted_paths_and_packages(self):
		"""Test dotted paths and packages."""
		module = _make_module(self.library, 'General', 'Util', 'Config')
		loaded = ScriptModelBuilder().build_from_file(module)

		modules = loaded.model['script_modules']
		packages = loaded.model['script_packages']
		self.assertEqual(len(modules), 1)
		self.assertEqual(modules[0].path, 'General.Util.Config')
		self.assertEqual(modules[0].name, 'Config')
		self.assertEqual(modules[0].node_type, NodeType.SCRIPT_MODULE)
		self.assertEqual([p.path for p in packages], ['General', 'General.Util'])
		self.assertEqual([p.name for p in packages], ['General', 'Util'])
		self.assertTrue(all(isinstance(p, ScriptPackage) for p in packages))
		self.assertEqual(loaded.nodes, packages + modules)

	def test_last_script_python_occurrence_wins(self):
		"""Test last script python occurrence wins."""
		nested = Path(self.tmp.name) / 'script-python' / 'outer' / 'ignition' / 'script-python'
		module = _make_module(nested, 'Pkg', 'Mod')
		loaded = ScriptModelBuilder().build_from_file(module)
		self.assertEqual(loaded.model['script_modules'][0].path, 'Pkg.Mod')
		self.assertEqual([p.path for p in loaded.model['script_packages']], ['Pkg'])

	def test_top_level_module_has_no_packages(self):
		"""Test top level module has no packages."""
		module = _make_module(self.library, 'Solo')
		loaded = ScriptModelBuilder().build_from_file(module)
		self.assertEqual(loaded.model['script_packages'], [])
		self.assertEqual(loaded.model['script_modules'][0].path, 'Solo')

	def test_resource_json_is_parsed(self):
		"""Test resource json is parsed."""
		resource = json.dumps({"scope": "G", "restricted": True, "overridable": False, "files": ["code.py"]})
		module = _make_module(self.library, 'Pkg', 'Mod', resource=resource)
		node = ScriptModelBuilder().build_from_file(module).model['script_modules'][0]
		self.assertEqual(node.resource['scope'], 'G')
		serialized = node.serialize()
		self.assertEqual(serialized['scope'], 'G')
		self.assertIs(serialized['restricted'], True)
		self.assertEqual(serialized['node_type'], 'script_module')

	def test_missing_or_invalid_resource_is_empty_dict(self):
		"""Test missing or invalid resource is empty dict."""
		module = _make_module(self.library, 'Pkg', 'NoRes')
		self.assertEqual(ScriptModelBuilder().build_from_file(module).model['script_modules'][0].resource, {})
		module = _make_module(self.library, 'Pkg', 'BadRes', resource='{not json')
		self.assertEqual(ScriptModelBuilder().build_from_file(module).model['script_modules'][0].resource, {})

	def test_source_is_verbatim(self):
		"""Test source is verbatim."""
		source = "import system\n\ndef go():\n\treturn 1\n"
		module = _make_module(self.library, 'Pkg', 'Mod', source=source)
		node = ScriptModelBuilder().build_from_file(module).model['script_modules'][0]
		self.assertIsInstance(node, ScriptModule)
		self.assertEqual(node.script, source)
		self.assertEqual(node.get_formatted_script(), source)
		self.assertEqual(node.file_path, str(module))

	def test_fallback_without_script_python_ancestor(self):
		"""Fixtures on disk: module name is the parent folder only, no package nodes."""
		builder = ScriptModelBuilder()
		loaded = builder.build_from_file(SCRIPTING_DIR / 'clean' / 'code.py')
		self.assertIsNone(builder.library_root)
		self.assertEqual(loaded.model['script_packages'], [])
		module = loaded.model['script_modules'][0]
		self.assertEqual(module.path, 'clean')
		self.assertEqual(module.name, 'clean')
		self.assertEqual(module.resource.get('scope'), 'A')

	def test_library_root_exposed(self):
		"""Test library root exposed."""
		module = _make_module(self.library, 'Pkg', 'Mod')
		builder = ScriptModelBuilder()
		builder.build_from_file(module)
		self.assertEqual(builder.library_root, self.library.resolve())

	def test_scripting_types_not_in_all_scripts(self):
		"""Scripting nodes must never leak into Perspective script rules."""
		from ignition_lint.model.node_types import ALL_SCRIPTS, COMPONENT_REFERENCE_NODES  # pylint: disable=import-outside-toplevel
		self.assertNotIn(NodeType.SCRIPT_MODULE, ALL_SCRIPTS)
		self.assertNotIn(NodeType.SCRIPT_PACKAGE, ALL_SCRIPTS)
		self.assertNotIn(NodeType.SCRIPT_MODULE, COMPONENT_REFERENCE_NODES)


if __name__ == '__main__':
	unittest.main()
