# pylint: disable=import-error,wrong-import-position
"""
Unit tests for deriving a view's name and folder path from its view.json location.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from ignition_lint.common.view_path import resolve_view_location, ViewLocation


class TestResolveViewLocation(unittest.TestCase):
	"""Anchor detection and name/folder extraction."""

	def test_perspective_project_layout(self):
		"""Standard export layout: folders are everything between views/ and the view directory."""
		location = resolve_view_location(
			'MyProject/com.inductiveautomation.perspective/views/Screens/Line1/Overview/view.json'
		)
		self.assertEqual(location.name, 'Overview')
		self.assertEqual(location.folders, ('Screens', 'Line1'))
		self.assertEqual(location.view_path, 'Screens/Line1/Overview')
		self.assertTrue(location.views_root_found)

	def test_view_at_views_root_has_no_folders(self):
		"""A view directly under views/ has an empty folder path."""
		location = resolve_view_location('com.inductiveautomation.perspective/views/Home/view.json')
		self.assertEqual(location.name, 'Home')
		self.assertEqual(location.folders, ())
		self.assertEqual(location.view_path, 'Home')
		self.assertTrue(location.views_root_found)

	def test_bare_views_directory_is_an_anchor(self):
		"""Without the module directory, a plain views/ segment still marks the root."""
		location = resolve_view_location(
			'tests/cases/ViewNaming/views/Title Case Folder/Title Case View/view.json'
		)
		self.assertEqual(location.name, 'Title Case View')
		self.assertEqual(location.folders, ('Title Case Folder',))
		self.assertTrue(location.views_root_found)

	def test_perspective_anchor_preferred_over_earlier_views_segment(self):
		"""A views/ directory above the project must not be mistaken for the views root."""
		location = resolve_view_location(
			'/home/dev/views/Proj/com.inductiveautomation.perspective/views/Folder/View/view.json'
		)
		self.assertEqual(location.folders, ('Folder',))
		self.assertEqual(location.name, 'View')

	def test_nearest_bare_views_segment_wins(self):
		"""With only bare views/ segments, the one nearest the file is the root."""
		location = resolve_view_location('views/Screens/views/Detail/view.json')
		self.assertEqual(location.folders, ())
		self.assertEqual(location.name, 'Detail')
		self.assertTrue(location.views_root_found)

	def test_parent_directory_named_views_is_not_the_root(self):
		"""A checkout or workspace called views/ above the project never becomes the views root."""
		location = resolve_view_location('/home/x/views/proj/ignition/perspective/views/Foo/view.json')
		self.assertEqual(location.name, 'Foo')
		self.assertEqual(location.folders, ())
		location = resolve_view_location('data/projects/views/ignition/views/Folder/MyView/view.json')
		self.assertEqual(location.folders, ('Folder',))

	def test_parent_references_are_normalised(self):
		"""``..`` segments never show up as folder names."""
		location = resolve_view_location(
			'proj/com.inductiveautomation.perspective/views/Folder/../Other/MyView/view.json'
		)
		self.assertEqual(location.folders, ('Other',))
		self.assertEqual(location.name, 'MyView')

	def test_no_anchor_falls_back_to_parent_directory(self):
		"""Unanchored paths still name the view after its directory but report no folders."""
		location = resolve_view_location('tests/cases/PascalCase/view.json')
		self.assertEqual(location, ViewLocation(name='PascalCase', folders=(), views_root_found=False))
		self.assertEqual(location.view_path, 'PascalCase')

	def test_absolute_unanchored_path(self):
		"""Leading root separator is not treated as a folder."""
		location = resolve_view_location('/tmp/Some View/view.json')
		self.assertEqual(location.name, 'Some View')
		self.assertEqual(location.folders, ())
		self.assertFalse(location.views_root_found)

	def test_file_directly_inside_views_root_has_no_view(self):
		"""view.json sitting directly in the views root is not a view Ignition would write; no node."""
		self.assertIsNone(resolve_view_location('project/views/view.json'))
		self.assertIsNone(resolve_view_location('com.inductiveautomation.perspective/views/view.json'))

	def test_accepts_path_objects(self):
		"""Path instances work the same as strings."""
		location = resolve_view_location(Path('views') / 'Folder' / 'View' / 'view.json')
		self.assertEqual(location.view_path, 'Folder/View')

	def test_empty_and_none_inputs(self):
		"""No path means no location."""
		self.assertIsNone(resolve_view_location(None))
		self.assertIsNone(resolve_view_location(''))

	def test_bare_filename_has_no_location(self):
		"""A bare filename has no parent directory to name the view after."""
		self.assertIsNone(resolve_view_location('view.json'))


if __name__ == '__main__':
	unittest.main()
