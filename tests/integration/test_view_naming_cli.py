# pylint: disable=import-error,wrong-import-position
"""
The view node must reach the rules on the real CLI path (domain loader → process_file), not only
via LintEngine.process as the unit tests use. This is the regression guard for the loader dropping
the source path, which every unit test would miss.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from ignition_lint.domains import PERSPECTIVE_SPEC
from ignition_lint.linter import LintEngine
from ignition_lint.model.node_types import NodeType
from ignition_lint.rules.naming.name_pattern import NamePatternRule

MAIN_PY = REPO_ROOT / 'src' / 'ignition_lint' / '__main__.py'
TITLE_VIEW = REPO_ROOT / 'tests' / 'cases' / 'views' / 'Naming' / 'Title Case Folder' / 'Title Case View' / 'view.json'


def _run_cli(args, timeout=120):
	"""Run the CLI from the repo root and return the CompletedProcess."""
	return subprocess.run([sys.executable, str(MAIN_PY)] + args, capture_output=True, text=True, timeout=timeout,
				check=False, cwd=REPO_ROOT)


class TestViewNodeOnCliPath(unittest.TestCase):
	"""View and folder names are validated when files go through the Perspective domain loader."""

	def test_process_file_builds_and_visits_the_view_node(self):
		"""Test process file builds and visits the view node."""
		rule = NamePatternRule(convention='PascalCase', target_node_types={NodeType.VIEW}, severity='error')
		engine = LintEngine([rule])
		_, results = engine.process_file(TITLE_VIEW, PERSPECTIVE_SPEC)
		messages = results.errors.get('NamePatternRule', [])
		self.assertEqual(len(messages), 2, messages)
		self.assertTrue(any("Name 'Title Case View'" in m for m in messages))
		self.assertTrue(any("Folder name 'Title Case Folder'" in m for m in messages))

	def test_cli_reports_view_and_folder_violations(self):
		"""Test cli reports view and folder violations."""
		result = _run_cli(['--config', 'rule_config.json', '--files', 'tests/cases/views/Naming/**/view.json'])
		self.assertEqual(result.returncode, 1, result.stdout)
		self.assertIn("Name 'Title Case View' doesn't follow PascalCase for view", result.stdout)
		self.assertIn("Folder name 'Title Case Folder' doesn't follow PascalCase for view", result.stdout)
		self.assertIn("Folder name 'Nested Sub Folder' doesn't follow PascalCase for view", result.stdout)
		self.assertEqual(result.stdout.count('for view ('), 3, result.stdout)

	def test_stats_and_debug_nodes_show_the_view(self):
		"""Test stats and debug nodes show the view."""
		result = _run_cli(['--stats-only', '--debug-nodes', 'view', str(TITLE_VIEW)])
		self.assertIn('view: 1', result.stdout)
		self.assertIn('Naming/Title Case Folder/Title Case View (view)', result.stdout)


if __name__ == '__main__':
	unittest.main()
