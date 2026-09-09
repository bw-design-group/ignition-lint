# pylint: disable=import-error,wrong-import-position
"""Unit tests for --debug-output layout (one folder per file) and its cleanup."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ignition_lint.cli import cleanup_debug_output_dir
from ignition_lint.domains import PERSPECTIVE_SPEC, SCRIPTING_SPEC
from ignition_lint.linter import DEBUG_OUTPUT_MARKER, LintEngine, debug_output_subdir, prepare_debug_output_dir

REPO_ROOT = Path(__file__).parent.parent.parent
VIEW = REPO_ROOT / 'tests' / 'cases' / 'views' / 'PascalCase' / 'view.json'
SCRIPT = REPO_ROOT / 'tests' / 'cases' / 'scripting' / 'clean' / 'code.py'


class TestDebugOutputLayout(unittest.TestCase):
	"""Each linted file gets its own mirrored folder with plainly named artifacts."""

	def __init__(self, method_name='runTest'):
		super().__init__(method_name)
		self.tmp = None
		self.old_cwd = None

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
		self.old_cwd = os.getcwd()
		os.chdir(REPO_ROOT)

	def tearDown(self):
		"""Restore cwd and remove temp output."""
		os.chdir(self.old_cwd)
		self.tmp.cleanup()

	def test_subdir_mirrors_source_folder_relative_to_cwd(self):
		"""Subdir mirrors source folder relative to cwd."""
		self.assertEqual(debug_output_subdir(str(VIEW)), Path('tests/cases/views/PascalCase'))
		self.assertEqual(debug_output_subdir(str(SCRIPT)), Path('tests/cases/scripting/clean'))

	def test_subdir_for_file_outside_cwd_uses_sanitized_absolute_parts(self):
		"""Subdir for file outside cwd uses sanitized absolute parts."""
		outside = Path(self.tmp.name) / 'proj' / 'my view!' / 'view.json'
		sub = debug_output_subdir(str(outside))
		self.assertFalse(sub.is_absolute())
		self.assertIn('my_view_', sub.parts)
		self.assertNotIn('..', sub.parts)

	def test_view_and_script_write_separate_folders(self):
		"""View and script write separate folders."""
		out = Path(self.tmp.name) / 'analysis'
		engine = LintEngine([], debug_output_dir=str(out))
		self.assertTrue((out / DEBUG_OUTPUT_MARKER).exists())

		engine.process_file(VIEW, PERSPECTIVE_SPEC)
		engine.process_file(SCRIPT, SCRIPTING_SPEC)

		view_dir = out / 'tests' / 'cases' / 'views' / 'PascalCase'
		script_dir = out / 'tests' / 'cases' / 'scripting' / 'clean'
		self.assertEqual(
			sorted(p.name for p in view_dir.iterdir()), ['flattened.json', 'model.json', 'stats.json']
		)
		self.assertEqual(sorted(p.name for p in script_dir.iterdir()), ['model.json', 'stats.json'])
		with open(script_dir / 'stats.json', encoding='utf-8') as f:
			self.assertEqual(json.load(f)['node_type_counts'], {'script_module': 1})

	def test_two_views_do_not_collide(self):
		"""Two views do not collide."""
		out = Path(self.tmp.name) / 'analysis'
		engine = LintEngine([], debug_output_dir=str(out))
		engine.process_file(VIEW, PERSPECTIVE_SPEC)
		engine.process_file(
			REPO_ROOT / 'tests' / 'cases' / 'views' / 'camelCase' / 'view.json', PERSPECTIVE_SPEC
		)
		self.assertTrue((out / 'tests/cases/views/PascalCase/model.json').exists())
		self.assertTrue((out / 'tests/cases/views/camelCase/model.json').exists())


class TestDebugOutputCleanup(unittest.TestCase):
	"""Cleanup only touches marked directories and keeps fresh entries."""

	def __init__(self, method_name='runTest'):
		super().__init__(method_name)
		self.tmp = None

	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with

	def tearDown(self):
		"""Remove temp output."""
		self.tmp.cleanup()

	@staticmethod
	def _age(path: Path, seconds: float):
		"""Back-date a path's mtime."""
		stamp = time.time() - seconds
		os.utime(path, (stamp, stamp))

	def test_unmarked_directory_is_left_alone(self):
		"""Unmarked directory is left alone."""
		root = Path(self.tmp.name) / 'mine'
		(root / 'keep').mkdir(parents=True)
		(root / 'keep' / 'data.txt').write_text('x', encoding='utf-8')
		self._age(root / 'keep', 60)
		self.assertEqual(cleanup_debug_output_dir(str(root)), 0)
		self.assertTrue((root / 'keep' / 'data.txt').exists())

	def test_stale_entries_removed_fresh_entries_and_marker_kept(self):
		"""Stale entries removed; fresh entries and marker kept."""
		root = prepare_debug_output_dir(str(Path(self.tmp.name) / 'analysis'))
		stale = root / 'views' / 'Old'
		stale.mkdir(parents=True)
		(stale / 'model.json').write_text('{}', encoding='utf-8')
		self._age(root / 'views', 60)
		fresh = root / 'fresh'
		fresh.mkdir()
		loose = root / 'loose.json'
		loose.write_text('{}', encoding='utf-8')
		self._age(loose, 60)

		removed = cleanup_debug_output_dir(str(root))

		self.assertEqual(removed, 2)
		self.assertFalse(stale.exists())
		self.assertFalse(loose.exists())
		self.assertTrue(fresh.exists())
		self.assertTrue((root / DEBUG_OUTPUT_MARKER).exists())

	def test_missing_directory_is_noop(self):
		"""Missing directory is a no-op."""
		self.assertEqual(cleanup_debug_output_dir(str(Path(self.tmp.name) / 'nope')), 0)


if __name__ == '__main__':
	unittest.main()
