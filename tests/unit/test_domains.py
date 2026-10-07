# pylint: disable=import-error,wrong-import-position
"""Unit tests for the lint-domain registry and the built-in domain specs."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ignition_lint.common.domain import DomainSpec, LintDomain, LoadedFile
from ignition_lint.domains import (
	DomainRegistry, PERSPECTIVE_SPEC, SCRIPTING_SPEC, classify_file, default_globs, get_spec
)

TESTS_DIR = Path(__file__).parent.parent
VIEWS_DIR = TESTS_DIR / 'cases' / 'views'
SCRIPTING_DIR = TESTS_DIR / 'cases' / 'scripting'


class TestClassifyFile(unittest.TestCase):
	"""classify_file routes each on-disk shape to the right domain."""

	def test_view_json_is_perspective(self):
		"""Test view json is perspective."""
		spec = classify_file(VIEWS_DIR / 'PascalCase' / 'view.json')
		self.assertIs(spec, PERSPECTIVE_SPEC)
		self.assertEqual(spec.domain, LintDomain.PERSPECTIVE)

	def test_code_py_under_script_python_is_scripting(self):
		"""Test code py under script python is scripting."""
		with tempfile.TemporaryDirectory() as tmp:
			module = Path(tmp) / 'ignition' / 'script-python' / 'Pkg' / 'Mod' / 'code.py'
			module.parent.mkdir(parents=True)
			module.write_text('x = 1\n', encoding='utf-8')
			self.assertIs(classify_file(module), SCRIPTING_SPEC)

	def test_code_py_with_resource_json_is_scripting(self):
		"""Fixtures without a script-python ancestor are recognised via resource.json."""
		self.assertIs(classify_file(SCRIPTING_DIR / 'clean' / 'code.py'), SCRIPTING_SPEC)

	def test_bare_code_py_is_unknown(self):
		"""Test bare code py is unknown."""
		with tempfile.TemporaryDirectory() as tmp:
			module = Path(tmp) / 'code.py'
			module.write_text('x = 1\n', encoding='utf-8')
			self.assertIsNone(classify_file(module))

	def test_other_files_are_unknown(self):
		"""Test other files are unknown."""
		self.assertIsNone(classify_file(Path('foo/bar.json')))
		self.assertIsNone(classify_file(Path('foo/resource.json')))
		self.assertIsNone(classify_file(Path('foo/doGet.py')))


class TestRegistry(unittest.TestCase):
	"""Registry contracts used by the CLI."""

	def test_default_globs_is_union_without_duplicates(self):
		"""Test default globs is union without duplicates."""
		self.assertEqual(default_globs(), ('**/view.json',))

	def test_get_spec_round_trip(self):
		"""Test get spec round trip."""
		self.assertIs(get_spec(LintDomain.PERSPECTIVE), PERSPECTIVE_SPEC)
		self.assertIs(get_spec(LintDomain.SCRIPTING), SCRIPTING_SPEC)

	def test_domain_values_are_config_section_names(self):
		"""Domain enum values round-trip from their string form."""
		self.assertEqual(str(LintDomain.PERSPECTIVE), 'perspective')
		self.assertEqual(LintDomain('scripting'), LintDomain.SCRIPTING)

	def test_registration_order_drives_classification(self):
		"""Test registration order drives classification."""
		registry = DomainRegistry()
		first = DomainSpec(LintDomain.SCRIPTING, 'first', lambda p: True, lambda p: LoadedFile(nodes=[]))
		second = DomainSpec(LintDomain.PERSPECTIVE, 'second', lambda p: True, lambda p: LoadedFile(nodes=[]))
		registry.register_domain(first)
		registry.register_domain(second)
		self.assertIs(registry.classify_file(Path('anything')), first)
		registry.unregister_domain(LintDomain.SCRIPTING)
		self.assertIs(registry.classify_file(Path('anything')), second)
		self.assertEqual(registry.default_globs(), ())


class TestLoadedFileContracts(unittest.TestCase):
	"""What each loader promises the engine."""

	def test_perspective_loader_provides_json_features(self):
		"""Test perspective loader provides json features."""
		loaded = PERSPECTIVE_SPEC.load(VIEWS_DIR / 'PascalCase' / 'view.json')
		self.assertTrue(loaded.supports_json_features)
		self.assertTrue(loaded.flattened_json)
		self.assertGreater(len(loaded.nodes), 0)
		self.assertIn('components', loaded.model)
		self.assertIn('model_build_ms', loaded.timings)

	def test_perspective_nodes_are_deduplicated(self):
		"""Test perspective nodes are deduplicated."""
		loaded = PERSPECTIVE_SPEC.load(VIEWS_DIR / 'AllScriptTypes' / 'view.json')
		self.assertEqual(len(loaded.nodes), len({id(node) for node in loaded.nodes}))

	def test_scripting_loader_has_no_json_features(self):
		"""Test scripting loader has no json features."""
		loaded = SCRIPTING_SPEC.load(SCRIPTING_DIR / 'clean' / 'code.py')
		self.assertFalse(loaded.supports_json_features)
		self.assertEqual(loaded.flattened_json, {})
		self.assertIsNone(loaded.json_data)
		self.assertEqual(sorted(loaded.model), ['script_modules', 'script_packages'])


if __name__ == '__main__':
	unittest.main()
