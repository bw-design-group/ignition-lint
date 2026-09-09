# pylint: disable=import-error,wrong-import-position
"""Unit tests for LibraryScriptPylintRule."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'src'))

from ignition_lint.common.domain import LintDomain
from ignition_lint.domains import SCRIPTING_SPEC
from ignition_lint.linter import LintEngine
from ignition_lint.rules import RULES_MAP
from ignition_lint.rules.scripts.lint_library_script import LibraryScriptPylintRule, read_rcfile_list_option

SCRIPTING_DIR = Path(__file__).parent.parent.parent / 'cases' / 'scripting'
RULE = 'LibraryScriptPylintRule'


def _lint(path: Path, **kwargs):
	"""Lint one file with a fresh rule; return (rule, LintResults)."""
	rule = LibraryScriptPylintRule(**kwargs)
	engine = LintEngine([rule])
	_, results = engine.process_file(path, SCRIPTING_SPEC)
	return rule, results


class TestLibraryScriptPylintRule(unittest.TestCase):
	"""Runs pylint directly on library modules with independent configuration."""

	def test_registered_in_scripting_domain_and_zero_arg_constructible(self):
		"""Test registered in scripting domain and zero arg constructible."""
		self.assertIn(RULE, RULES_MAP)
		self.assertEqual(RULES_MAP[RULE].domain, LintDomain.SCRIPTING)
		rule = RULES_MAP[RULE].create_from_config({})
		self.assertTrue(rule.error_message)
		self.assertIsNotNone(rule.pylintrc, "bundled .ignition-library-pylintrc should be found")
		self.assertTrue(rule.pylintrc.endswith('.ignition-library-pylintrc'))

	def test_violations_fixture_reports_expected_codes_with_real_lines(self):
		"""Test violations fixture reports expected codes with real lines."""
		rule, results = _lint(SCRIPTING_DIR / 'violations' / 'code.py')
		by_code = {(v.code, v.line) for v in rule.pylint_violations}
		self.assertIn(('W0611', 11), by_code)
		self.assertIn(('C0103', 13), by_code)
		self.assertIn(('E0602', 19), by_code)
		self.assertIn(('W0612', 24), by_code)
		# E → error stream, W/C → warning stream under the default mapping
		self.assertIn(RULE, results.errors)
		self.assertIn(RULE, results.warnings)
		self.assertIn('Pylint - Error (E):', results.custom_formatted_errors[RULE])
		self.assertIn("Line 19: Undefined variable 'undefined_helper'", results.custom_formatted_errors[RULE])
		self.assertIn('Pylint - Warning (W):', results.custom_formatted_warnings[RULE])
		# One module per file: no path prefix before "Line N"
		self.assertIn('• Line 19:', results.custom_formatted_errors[RULE])

	def test_clean_fixture_has_no_violations(self):
		"""Test clean fixture has no violations."""
		rule, results = _lint(SCRIPTING_DIR / 'clean' / 'code.py')
		self.assertEqual(rule.pylint_violations, [])
		self.assertNotIn(RULE, results.errors)
		self.assertNotIn(RULE, results.warnings)

	def test_strict_category_mapping_moves_warnings_to_errors(self):
		"""Test strict category mapping moves warnings to errors."""
		mapping = {'F': 'error', 'E': 'error', 'W': 'error', 'C': 'error', 'R': 'error'}
		_, results = _lint(SCRIPTING_DIR / 'violations' / 'code.py', category_mapping=mapping)
		self.assertNotIn(RULE, results.warnings)
		self.assertIn('Pylint - Warning (W):', results.custom_formatted_errors[RULE])

	def test_explicit_pylintrc_is_honoured(self):
		"""Test explicit pylintrc is honoured."""
		with tempfile.TemporaryDirectory() as tmp:
			rc = Path(tmp) / 'lib.pylintrc'
			rc.write_text(
				"[MAIN]\n[MESSAGES CONTROL]\ndisable=all\nenable=unused-import\n"
				"[VARIABLES]\nadditional-builtins=system\n", encoding='utf-8'
			)
			rule, _ = _lint(SCRIPTING_DIR / 'violations' / 'code.py', pylintrc=str(rc))
			self.assertEqual(rule.pylintrc, str(rc))
			self.assertEqual({v.code for v in rule.pylint_violations}, {'W0611'})

	def test_additional_builtins_suppress_undefined_variable(self):
		"""Test additional builtins suppress undefined variable."""
		rule, _ = _lint(SCRIPTING_DIR / 'violations' / 'code.py', additional_builtins=['undefined_helper'])
		self.assertNotIn('E0602', {v.code for v in rule.pylint_violations})
		# rcfile builtins (system) must survive the merge, so no new E0602 for `system`
		self.assertFalse(any("'system'" in v.message for v in rule.pylint_violations))

	def test_sibling_top_level_packages_become_builtins(self):
		"""Test sibling top level packages become builtins."""
		with tempfile.TemporaryDirectory() as tmp:
			lib = Path(tmp) / 'ignition' / 'script-python'
			(lib / 'General' / 'Config').mkdir(parents=True)
			(lib / 'General' / 'Config' / 'code.py').write_text('"""Cfg."""\nVALUE = 1\n', encoding='utf-8')
			(lib / 'Other' / 'Mod').mkdir(parents=True)
			target = lib / 'Other' / 'Mod' / 'code.py'
			target.write_text(
				'"""Uses a sibling package."""\n\n\ndef read():\n\t"""Read."""\n\treturn General.Config.VALUE\n',
				encoding='utf-8'
			)
			rule, _ = _lint(target)
			self.assertNotIn('E0602', {v.code for v in rule.pylint_violations}, rule.pylint_violations)

	def test_in_memory_module_is_linted_via_temp_file(self):
		"""Test in memory module is linted via temp file."""
		from ignition_lint.model.node_types import ScriptModule  # pylint: disable=import-outside-toplevel
		rule = LibraryScriptPylintRule()
		rule.process_nodes([ScriptModule('Pkg.Mod', 'Mod', '"""Doc."""\nimport json\n')])
		self.assertEqual({v.code for v in rule.pylint_violations}, {'W0611'})
		self.assertEqual(rule.warnings, [""])

	def test_read_rcfile_list_option(self):
		"""Test read rcfile list option."""
		with tempfile.TemporaryDirectory() as tmp:
			rc = Path(tmp) / 'rc'
			rc.write_text("[VARIABLES]\nadditional-builtins=a, b,\n\tc\n", encoding='utf-8')
			self.assertEqual(read_rcfile_list_option(str(rc), 'additional-builtins'), ['a', 'b', 'c'])
			self.assertEqual(read_rcfile_list_option(str(rc), 'missing'), [])
			self.assertEqual(read_rcfile_list_option(None, 'additional-builtins'), [])


if __name__ == '__main__':
	unittest.main()
