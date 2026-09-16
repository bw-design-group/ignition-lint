# pylint: disable=import-error,wrong-import-position
"""Unit tests for LibraryNamePatternRule (package/module naming in the script library)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'src'))

from ignition_lint.common.domain import LintDomain
from ignition_lint.domains import SCRIPTING_SPEC
from ignition_lint.linter import LintEngine
from ignition_lint.model.node_types import NodeType
from ignition_lint.rules import RULES_MAP
from ignition_lint.rules.naming.library_name_pattern import LibraryNamePatternRule

SCRIPTING_DIR = Path(__file__).parent.parent.parent / 'cases' / 'scripting'
RULE = 'LibraryNamePatternRule'


def _module(lib: Path, *parts: str) -> Path:
	folder = lib.joinpath(*parts)
	folder.mkdir(parents=True, exist_ok=True)
	path = folder / 'code.py'
	path.write_text('"""Doc."""\n', encoding='utf-8')
	return path


class TestLibraryNamePatternRule(unittest.TestCase):
	"""Default targets, per-type conventions, dedup and fixtures."""

	def __init__(self, method_name='runTest'):
		"""Init  ."""
		super().__init__(method_name)
		self.tmp = None
		self.lib = None

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
		self.lib = Path(self.tmp.name) / 'ignition' / 'script-python'

	def tearDown(self):
		"""Remove the temporary library tree."""
		self.tmp.cleanup()

	@staticmethod
	def _run(rule, *paths):
		"""Run ``rule`` over ``paths`` with one engine; return one LintResults per path."""
		engine = LintEngine([rule])
		return [engine.process_file(path, SCRIPTING_SPEC)[1] for path in paths]

	def test_registered_in_scripting_domain_with_defaults(self):
		"""Test registered in scripting domain with defaults."""
		self.assertEqual(RULES_MAP[RULE].domain, LintDomain.SCRIPTING)
		rule = RULES_MAP[RULE].create_from_config({})
		self.assertEqual(rule.target_node_types, {NodeType.SCRIPT_PACKAGE, NodeType.SCRIPT_MODULE})
		self.assertEqual(rule.convention, 'snake_case')
		self.assertFalse(rule.supports_fix)
		self.assertIn('script_module', rule.error_message)

	def test_package_and_module_judged_by_own_config(self):
		"""Test package and module judged by own config."""
		rule = LibraryNamePatternRule.create_from_config({
			"node_type_specific_rules": {
				"script_package": {
					"convention": "snake_case",
					"severity": "warning"
				},
				"script_module": {
					"convention": "PascalCase",
					"severity": "error"
				},
			}
		})
		results = self._run(rule, _module(self.lib, 'good_pkg', 'badName'))[0]
		self.assertNotIn(RULE, results.warnings)  # good_pkg satisfies snake_case
		self.assertEqual(len(results.errors[RULE]), 1)
		self.assertIn(
			"badName: Name 'badName' doesn't follow PascalCase for script_module", results.errors[RULE][0]
		)
		self.assertIn("(suggestion: 'BadName')", results.errors[RULE][0])

	def test_package_violation_reported_once_across_modules(self):
		"""Test package violation reported once across modules."""
		rule = LibraryNamePatternRule()
		runs = self._run(rule, _module(self.lib, 'BadPkg', 'one'), _module(self.lib, 'BadPkg', 'two'))
		first, second = runs[0], runs[1]
		self.assertEqual(len(first.warnings[RULE]), 1)
		self.assertIn(
			"BadPkg: Name 'BadPkg' doesn't follow snake_case for script_package", first.warnings[RULE][0]
		)
		self.assertNotIn(RULE, second.warnings)

	def test_nested_package_paths_are_dotted(self):
		"""Test nested package paths are dotted."""
		rule = LibraryNamePatternRule()
		results = self._run(rule, _module(self.lib, 'good', 'BadSub', 'mod'))[0]
		self.assertEqual(len(results.warnings[RULE]), 1)
		self.assertTrue(results.warnings[RULE][0].startswith('good.BadSub: '))

	def test_fixture_bad_module_is_flagged_and_clean_passes(self):
		"""Test fixture bad module name is flagged and clean passes."""
		rule = LibraryNamePatternRule()
		runs = self._run(
			rule, SCRIPTING_DIR / 'badModule_name' / 'code.py', SCRIPTING_DIR / 'clean' / 'code.py'
		)
		bad, clean = runs[0], runs[1]
		self.assertEqual(len(bad.warnings[RULE]), 1)
		self.assertIn(
			"badModule_name: Name 'badModule_name' doesn't follow snake_case for script_module",
			bad.warnings[RULE][0]
		)
		self.assertNotIn(RULE, clean.warnings)
		self.assertNotIn(RULE, clean.errors)

	def test_never_emits_fixes(self):
		"""Test never emits fixes."""
		rule = LibraryNamePatternRule()
		results = self._run(rule, _module(self.lib, 'BadPkg', 'BadMod'))[0]
		self.assertEqual(results.fixes, [])
		self.assertEqual(len(results.warnings[RULE]), 2)

	def test_ignores_perspective_nodes(self):
		"""Test ignores perspective nodes."""
		from ignition_lint.model.node_types import Component  # pylint: disable=import-outside-toplevel
		rule = LibraryNamePatternRule()
		rule.process_nodes([Component('root.bad_name', 'bad_name')])
		self.assertEqual(rule.warnings, [])


if __name__ == '__main__':
	unittest.main()
