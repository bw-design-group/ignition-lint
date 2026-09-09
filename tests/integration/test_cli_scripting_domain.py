# pylint: disable=import-error,wrong-import-position
"""
Integration tests for the scripting domain end to end, plus the n-domain extensibility proof.

The extensibility test registers a throwaway DomainSpec and rule at runtime and drives the
generic CLI helpers (collect_files, setup_linter, process_single_file). It must pass without
any change to cli.py or linter.py; if adding a domain ever requires touching them, this test
is what breaks.
"""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from ignition_lint import cli
from ignition_lint.common.domain import DomainSpec, LintDomain, LoadedFile
from ignition_lint.domains import get_domain_registry
from ignition_lint.model.node_types import NodeType, ViewNode
from ignition_lint.rules.common import LintingRule
from ignition_lint.rules.registry import get_registry

MAIN_PY = REPO_ROOT / 'src' / 'ignition_lint' / '__main__.py'
SCRIPTING_DIR = REPO_ROOT / 'tests' / 'cases' / 'scripting'
VIEWS_DIR = REPO_ROOT / 'tests' / 'cases' / 'views'


def _run_cli(args, timeout=120):
	"""Run the CLI from the repo root and return the CompletedProcess."""
	return subprocess.run([sys.executable, str(MAIN_PY)] + args, capture_output=True, text=True, timeout=timeout,
				check=False, cwd=REPO_ROOT)


class TestScriptingDomainCli(unittest.TestCase):
	"""ign-lint dispatches code.py files to the scripting domain."""

	def test_violations_fixture_reports_library_rule(self):
		"""Test violations fixture reports library rule."""
		result = _run_cli(['--config', 'rule_config.json', str(SCRIPTING_DIR / 'violations' / 'code.py')])
		self.assertEqual(result.returncode, 1, result.stdout)
		self.assertIn('LibraryScriptPylintRule', result.stdout)
		self.assertIn("Undefined variable 'undefined_helper'", result.stdout)
		self.assertNotIn('NamePatternRule:', result.stdout.replace('LibraryNamePatternRule:', ''))
		self.assertNotIn('deprecated', result.stdout)

	def test_mixed_run_covers_both_domains_in_results_file(self):
		"""Test mixed run covers both domains in results file."""
		with tempfile.TemporaryDirectory() as tmp:
			out = Path(tmp) / 'results.txt'
			result = _run_cli([
				'--config', 'rule_config.json', '--results-output',
				str(out),
				str(VIEWS_DIR / 'PascalCase' / 'view.json'),
				str(SCRIPTING_DIR / 'violations' / 'code.py')
			])
			self.assertIn('Files processed: 2', result.stdout)
			text = out.read_text(encoding='utf-8')
			self.assertIn('PascalCase/view.json', text)
			self.assertIn('violations/code.py', text)
			self.assertIn('LibraryScriptPylintRule', text)
			self.assertIn('UnusedCustomPropertiesRule', text)

	def test_glob_mode_filters_to_recognised_files(self):
		"""Test glob mode filters to recognised files."""
		result = _run_cli([
			'--config', 'rule_config.json', '--verbose', '--files',
			'tests/cases/scripting/**/code.py,tests/cases/scripting/**/resource.json'
		])
		self.assertIn('Processing 3 files', result.stdout)
		self.assertIn('script library module: 3', result.stdout)

	def test_unrecognised_explicit_file_is_skipped(self):
		"""Test unrecognised explicit file is skipped."""
		result = _run_cli(['--config', 'rule_config.json', str(SCRIPTING_DIR / 'clean' / 'resource.json')])
		self.assertIn('not a recognised Ignition resource', result.stdout)
		self.assertIn('No files specified or found', result.stdout)

	def test_fix_on_scripting_file_prints_unavailable_note(self):
		"""Test fix on scripting file prints unavailable note."""
		result = _run_cli([
			'--config', 'rule_config.json', '--fix',
			str(SCRIPTING_DIR / 'violations' / 'code.py')
		])
		self.assertIn('LibraryScriptPylintRule', result.stdout)
		self.assertIn('Auto-fix is not available for script library module files', result.stdout)
		self.assertNotIn('Applying fixes', result.stdout)

	def test_legacy_flat_config_still_works_with_one_deprecation(self):
		"""Test legacy flat config still works with one deprecation."""
		with tempfile.TemporaryDirectory() as tmp:
			cfg = Path(tmp) / 'legacy.json'
			cfg.write_text(
				json.dumps({"PylintScriptRule": {
					"enabled": True,
					"kwargs": {
						"severity": "warning"
					}
				}}), encoding='utf-8'
			)
			result = _run_cli(['--config', str(cfg), str(VIEWS_DIR / 'PylintViolations' / 'view.json')])
			self.assertEqual(result.stdout.count('deprecated'), 1)
			self.assertIn('PerspectiveScriptPylintRule', result.stdout)
			self.assertNotIn('Unknown rule', result.stdout)

	def test_fix_rules_accepts_new_perspective_rule_name(self):
		"""Test fix rules accepts new perspective rule name."""
		with tempfile.TemporaryDirectory() as tmp:
			view = Path(tmp) / 'view.json'
			view.write_text(
				json.dumps({
					"custom": {},
					"params": {},
					"propConfig": {},
					"root": {
						"children": [{
							"events": {
								"component": {
									"onActionPerformed": {
										"config": {
											"script":
												"\tx = 1   \n\tprint(x)"
										},
										"scope": "G",
										"type": "script"
									}
								}
							},
							"meta": {
								"name": "Button"
							},
							"type": "ia.input.button"
						}],
						"meta": {
							"name": "root"
						},
						"type": "ia.container.flex"
					}
				}), encoding='utf-8'
			)
			rc = Path(tmp) / 'rc'
			rc.write_text("[MESSAGES CONTROL]\ndisable=all\nenable=trailing-whitespace\n", encoding='utf-8')
			cfg = Path(tmp) / 'cfg.json'
			cfg.write_text(
				json.dumps({
					"PerspectiveScriptPylintRule": {
						"enabled": True,
						"kwargs": {
							"pylintrc": str(rc)
						}
					}
				}), encoding='utf-8'
			)
			result = _run_cli([
				'--config',
				str(cfg), '--fix', '--fix-rules', 'PerspectiveScriptPylintRule',
				str(view)
			])
			self.assertIn('Applied: 1 fix(es)', result.stdout, result.stdout)
			self.assertIn('x = 1\\n', json.dumps(json.loads(view.read_text(encoding='utf-8'))))


class _TextNode(ViewNode):
	"""Throwaway node for the extensibility proof."""

	def __init__(self, path, text):
		"""A node carrying raw text under the PROPERTY type (re-used to avoid touching NodeType)."""
		super().__init__(path, NodeType.PROPERTY)
		self.text = text


class TestExtensibilityProof(unittest.TestCase):
	"""A new domain is a pure addition: spec + rule, no CLI/engine edits."""

	def __init__(self, method_name='runTest'):
		"""Init  ."""
		super().__init__(method_name)
		self.registry = get_domain_registry()
		self.rule_registry = get_registry()
		self._saved_spec = None

	def setUp(self):
		"""Remember the real scripting spec so the throwaway one can be swapped back out."""
		self._saved_spec = self.registry.get_spec(LintDomain.SCRIPTING)
		self.addCleanup(self.registry.register_domain, self._saved_spec)

	def test_throwaway_domain_runs_through_generic_cli_path(self):
		"""Test throwaway domain runs through generic cli path."""

		# Borrow the SCRIPTING enum member for the throwaway spec: the registry keys on the
		# enum, and adding a new member is part of "adding a domain" by design.
		def load_sql(path: Path) -> LoadedFile:
			return LoadedFile(nodes=[_TextNode(path.stem, path.read_text(encoding='utf-8'))])

		spec = DomainSpec(LintDomain.SCRIPTING, 'SQL query', lambda p: p.suffix == '.sql', load_sql)
		self.registry.register_domain(spec)

		class NoSelectStarRule(LintingRule):
			"""Flags SELECT * in throwaway SQL nodes."""
			domain = LintDomain.SCRIPTING
			error_message = "SELECT * is forbidden"

			def __init__(self, **_kwargs):
				"""Init  ."""
				super().__init__({NodeType.PROPERTY})

			def visit_property(self, node):
				if 'SELECT *' in node.text:
					self.add_violation(f"{node.path}: uses SELECT *")

		self.rule_registry.register_rule(NoSelectStarRule)
		try:
			with tempfile.TemporaryDirectory() as tmp:
				query = Path(tmp) / 'AllRows.sql'
				query.write_text('SELECT * FROM t', encoding='utf-8')
				cfg = Path(tmp) / 'cfg.json'
				cfg.write_text(json.dumps({"NoSelectStarRule": {"enabled": True}}), encoding='utf-8')
				args = Namespace(
					filenames=[str(query)], files=None, verbose=False, stats_only=False,
					config=str(cfg), debug_output=None, fix_rules=None, analyze_rules=False,
					debug_nodes=None, fix=False, fix_unsafe=False, fix_dry_run=False
				)
				buf = io.StringIO()
				with contextlib.redirect_stdout(buf):
					files_by_domain, _ = cli.collect_files(args, set())
					self.assertEqual(list(files_by_domain), [LintDomain.SCRIPTING])
					engines = cli.setup_linter(args, list(files_by_domain))
					warnings, errors, _, results = cli.process_single_file(
						query, spec, engines[LintDomain.SCRIPTING], args
					)
			self.assertEqual((warnings, errors), (0, 1))
			self.assertEqual(results.errors['NoSelectStarRule'], ['AllRows: uses SELECT *'])
			self.assertIn('AllRows: uses SELECT *', buf.getvalue())
		finally:
			# The rule registry has no public unregister; drop the throwaway entry directly.
			self.rule_registry._rules.pop('NoSelectStarRule', None)  # pylint: disable=protected-access
			self.rule_registry._validated_rules.discard('NoSelectStarRule')  # pylint: disable=protected-access


if __name__ == '__main__':
	unittest.main()
