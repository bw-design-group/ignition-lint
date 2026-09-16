# pylint: disable=import-error,wrong-import-position
"""Unit tests for --debug-output layout (one folder per file) and its cleanup."""

import contextlib
import io
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
from ignition_lint.linter import (
	DEBUG_OUTPUT_MARKER, LintEngine, debug_output_subdir, prepare_debug_output_dir, read_debug_output_manifest,
	record_debug_output_entry
)

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
	"""Cleanup removes only folders ign-lint wrote, and never adopts a directory it did not create."""

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

	@staticmethod
	def _write_leaf(root: Path, relative: str, age: float = 0.0) -> Path:
		"""Create a mirrored output folder with a model.json and list it in the manifest."""
		leaf = root / relative
		leaf.mkdir(parents=True, exist_ok=True)
		(leaf / 'model.json').write_text('{}', encoding='utf-8')
		record_debug_output_entry(str(root), Path(relative))
		if age:
			TestDebugOutputCleanup._age(leaf, age)
		return leaf

	def test_unmarked_directory_is_left_alone(self):
		"""Unmarked directory is left alone."""
		root = Path(self.tmp.name) / 'mine'
		(root / 'keep').mkdir(parents=True)
		(root / 'keep' / 'data.txt').write_text('x', encoding='utf-8')
		self._age(root / 'keep', 60)
		self.assertEqual(cleanup_debug_output_dir(str(root)), 0)
		self.assertTrue((root / 'keep' / 'data.txt').exists())

	def test_prepare_does_not_adopt_a_directory_with_other_files(self):
		"""A pre-existing non-empty directory is never marked, so two runs leave foreign files intact."""
		root = Path(self.tmp.name) / 'project'
		(root / 'important').mkdir(parents=True)
		(root / 'important' / 'notes.txt').write_text('user data', encoding='utf-8')
		(root / 'config.json').write_text('{}', encoding='utf-8')
		self._age(root / 'important', 3600)
		self._age(root / 'config.json', 3600)

		with contextlib.redirect_stdout(io.StringIO()) as out:
			prepare_debug_output_dir(str(root))
		self.assertIn('will not clean it', out.getvalue())
		self.assertFalse((root / DEBUG_OUTPUT_MARKER).exists())

		self.assertEqual(cleanup_debug_output_dir(str(root)), 0)
		prepare_debug_output_dir(str(root))
		self.assertEqual(cleanup_debug_output_dir(str(root)), 0)
		self.assertTrue((root / 'important' / 'notes.txt').exists())
		self.assertTrue((root / 'config.json').exists())

	def test_prepare_marks_new_and_empty_directories(self):
		"""Directories ign-lint creates, or finds empty, get the marker."""
		created = prepare_debug_output_dir(str(Path(self.tmp.name) / 'new' / 'nested'))
		self.assertTrue((created / DEBUG_OUTPUT_MARKER).exists())
		empty = Path(self.tmp.name) / 'empty'
		empty.mkdir()
		prepare_debug_output_dir(str(empty))
		self.assertTrue((empty / DEBUG_OUTPUT_MARKER).exists())

	def test_prepare_rejects_a_file_target(self):
		"""A file passed as --debug-output raises instead of a bare mkdir traceback."""
		target = Path(self.tmp.name) / 'file.txt'
		target.write_text('x', encoding='utf-8')
		with self.assertRaises(NotADirectoryError):
			prepare_debug_output_dir(str(target))

	def test_only_manifest_entries_are_removed(self):
		"""Stale listed folders go; unlisted files, fresh folders and the marker stay."""
		root = prepare_debug_output_dir(str(Path(self.tmp.name) / 'analysis'))
		stale = self._write_leaf(root, 'views/Old', age=60)
		fresh = self._write_leaf(root, 'views/Fresh')
		loose = root / 'loose.json'
		loose.write_text('{}', encoding='utf-8')
		self._age(loose, 60)
		unlisted = root / 'unlisted'
		unlisted.mkdir()
		self._age(unlisted, 60)

		removed = cleanup_debug_output_dir(str(root))

		self.assertEqual(removed, 1)
		self.assertFalse(stale.exists())
		self.assertTrue(fresh.exists())
		self.assertTrue(loose.exists())
		self.assertTrue(unlisted.exists())
		self.assertTrue((root / DEBUG_OUTPUT_MARKER).exists())
		self.assertEqual(read_debug_output_manifest(root / DEBUG_OUTPUT_MARKER), ['views/Fresh'])

	def test_nested_leaf_from_parallel_batch_survives_stale_sibling_cleanup(self):
		"""Age is judged per written leaf, not per top-level folder, so a fresh sibling is kept."""
		root = prepare_debug_output_dir(str(Path(self.tmp.name) / 'analysis'))
		stale = self._write_leaf(root, 'com.inductiveautomation.perspective/views/Login', age=60)
		fresh = self._write_leaf(root, 'com.inductiveautomation.perspective/views/Home')
		self._age(root / 'com.inductiveautomation.perspective', 60)

		self.assertEqual(cleanup_debug_output_dir(str(root)), 1)
		self.assertFalse(stale.exists())
		self.assertTrue((fresh / 'model.json').exists())

	def test_emptied_parents_are_pruned_but_root_is_kept(self):
		"""Removing the last leaf under a mirrored folder removes the empty ancestors too."""
		root = prepare_debug_output_dir(str(Path(self.tmp.name) / 'analysis'))
		self._write_leaf(root, 'a/b/c', age=60)
		self.assertEqual(cleanup_debug_output_dir(str(root)), 1)
		self.assertFalse((root / 'a').exists())
		self.assertTrue(root.is_dir())

	def test_manifest_entries_outside_root_are_ignored(self):
		"""Absolute or parent-escaping manifest lines never lead to deletion."""
		root = prepare_debug_output_dir(str(Path(self.tmp.name) / 'analysis'))
		victim = Path(self.tmp.name) / 'victim'
		victim.mkdir()
		(victim / 'keep.txt').write_text('x', encoding='utf-8')
		self._age(victim, 60)
		with open(root / DEBUG_OUTPUT_MARKER, 'a', encoding='utf-8') as f:
			f.write(f"{victim}\n../victim\n")

		self.assertEqual(cleanup_debug_output_dir(str(root)), 0)
		self.assertTrue((victim / 'keep.txt').exists())

	def test_engine_records_written_folders_in_manifest(self):
		"""Folders the engine writes are listed so the next run can remove exactly them."""
		old_cwd = os.getcwd()
		os.chdir(REPO_ROOT)
		try:
			out = Path(self.tmp.name) / 'analysis'
			engine = LintEngine([], debug_output_dir=str(out))
			with contextlib.redirect_stdout(io.StringIO()):
				engine.process_file(VIEW, PERSPECTIVE_SPEC)
			self.assertEqual(
				read_debug_output_manifest(out / DEBUG_OUTPUT_MARKER), ['tests/cases/views/PascalCase']
			)
		finally:
			os.chdir(old_cwd)

	def test_missing_directory_is_noop(self):
		"""Missing directory is a no-op."""
		self.assertEqual(cleanup_debug_output_dir(str(Path(self.tmp.name) / 'nope')), 0)


if __name__ == '__main__':
	unittest.main()
