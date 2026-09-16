# pylint: disable=import-error,wrong-import-position
"""
Unit tests for the View node: how the model builder and LintEngine expose the
view's name and folder path derived from the source file location.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from ignition_lint.common.flatten_json import flatten_file
from ignition_lint.linter import LintEngine
from ignition_lint.model.builder import ViewModelBuilder
from ignition_lint.model.node_types import NodeType, View
from ignition_lint.rules.common import LintingRule

CASES_DIR = Path(__file__).parent.parent / 'cases' / 'views'
# tests/cases/views is the first bare 'views' segment, so it is the views root and 'Naming' is a view folder.
NESTED_VIEW = CASES_DIR / 'Naming' / 'Title Case Folder' / 'Title Case View' / 'view.json'


class _RecordingRule(LintingRule):
	"""Test rule that records every view node it is handed."""

	def __init__(self):
		super().__init__({NodeType.VIEW})
		self.visited = []

	@property
	def error_message(self) -> str:
		return "Records visited view nodes"

	def visit_view(self, node):
		self.visited.append(node)


class TestViewNode(unittest.TestCase):
	"""Behaviour of the View node class itself."""

	def test_path_is_the_view_path(self):
		"""The node path reads as Folder/Sub/Name so violations are self-describing."""
		node = View('Overview', ['Screens', 'Line1'], source_file='x/view.json', views_root_found=True)
		self.assertEqual(node.path, 'Screens/Line1/Overview')
		self.assertEqual(node.view_path, 'Screens/Line1/Overview')
		self.assertEqual(node.node_type, NodeType.VIEW)

	def test_serialize_omits_machine_specific_source_file(self):
		"""Serialized form is stable across machines (used in golden files)."""
		node = View('Home', source_file='/abs/path/Home/view.json')
		serialized = node.serialize()
		self.assertEqual(
			serialized, {
				'path': 'Home',
				'node_type': 'view',
				'name': 'Home',
				'folder_path': [],
				'view_path': 'Home',
				'views_root_found': False,
				'root_container_type': None,
				'default_size': {
					'width': None,
					'height': None
				},
				'node_counts': {},
				'total_nodes': 0,
			}
		)
		self.assertEqual(node.source_file, '/abs/path/Home/view.json')


class TestBuilderViewCollection(unittest.TestCase):
	"""ViewModelBuilder emits the 'view' collection."""

	def test_view_collection_always_present(self):
		"""The collection exists even when no source path is known, but is empty."""
		model = ViewModelBuilder().build_model(flatten_file(NESTED_VIEW))
		self.assertIn('view', model)
		self.assertEqual(model['view'], [])

	def test_view_node_built_from_source_path(self):
		"""Given a source path, exactly one View node describes the file location."""
		model = ViewModelBuilder().build_model(flatten_file(NESTED_VIEW), source_file_path=str(NESTED_VIEW))
		self.assertEqual(len(model['view']), 1)
		view = model['view'][0]
		self.assertIsInstance(view, View)
		self.assertEqual(view.name, 'Title Case View')
		self.assertEqual(view.folder_path, ['Naming', 'Title Case Folder'])
		self.assertTrue(view.views_root_found)
		self.assertEqual(view.source_file, str(NESTED_VIEW))

	def test_view_node_summarizes_root_type_and_node_counts(self):
		"""The view node carries the root container type and a per-type count of the other nodes."""
		model = ViewModelBuilder().build_model(flatten_file(NESTED_VIEW), source_file_path=str(NESTED_VIEW))
		view = model['view'][0]
		self.assertEqual(view.root_container_type, 'ia.container.flex')
		self.assertEqual(view.node_counts['component'], len(model['components']))
		self.assertEqual(view.node_counts['property'], len(model['properties']))
		self.assertNotIn('view', view.node_counts)
		self.assertEqual(
			view.total_nodes,
			sum(
				len(model[name])
				for name in ('components', 'properties', 'expression_bindings', 'event_handlers')
			)
		)

	def test_view_node_without_root(self):
		"""A view with no root container still builds, with root_container_type None."""
		model = ViewModelBuilder().build_model({'custom.thing': 1}, source_file_path='views/Bare/view.json')
		view = model['view'][0]
		self.assertIsNone(view.root_container_type)
		self.assertEqual(view.node_counts, {'property': 1})

	def test_root_type_found_for_real_fixture_with_nested_containers(self):
		"""Nested containers of the same type must not be mistaken for the root."""
		view_file = CASES_DIR / 'LineDashboard' / 'view.json'
		model = ViewModelBuilder().build_model(flatten_file(view_file), source_file_path=str(view_file))
		self.assertEqual(model['view'][0].root_container_type, 'ia.container.flex')

	def test_default_size_from_view_props(self):
		"""props.defaultSize is surfaced as a width/height dict; both None when the view does not declare it."""
		view_file = CASES_DIR / 'LineDashboard' / 'view.json'
		model = ViewModelBuilder().build_model(flatten_file(view_file), source_file_path=str(view_file))
		self.assertEqual(model['view'][0].default_size, {'width': 1200, 'height': 1145})

		model = ViewModelBuilder().build_model(flatten_file(NESTED_VIEW), source_file_path=str(NESTED_VIEW))
		self.assertEqual(model['view'][0].default_size, {'width': None, 'height': None})

	def test_partially_declared_default_size(self):
		"""A view declaring only one dimension keeps both keys, with the missing one None."""
		model = ViewModelBuilder().build_model({'props.defaultSize.width': 640},
							source_file_path='views/V/view.json')
		self.assertEqual(model['view'][0].default_size, {'width': 640, 'height': None})

	def test_view_node_does_not_accumulate_across_builds(self):
		"""Rebuilding the model resets the view collection."""
		builder = ViewModelBuilder()
		builder.build_model(flatten_file(NESTED_VIEW), source_file_path=str(NESTED_VIEW))
		model = builder.build_model(flatten_file(NESTED_VIEW), source_file_path=str(NESTED_VIEW))
		self.assertEqual(len(model['view']), 1)


class TestEngineViewPlumbing(unittest.TestCase):
	"""LintEngine hands the View node to rules and analysis helpers."""

	def test_rule_receives_view_node(self):
		"""Rules targeting NodeType.VIEW are visited once per file."""
		rule = _RecordingRule()
		engine = LintEngine([rule])
		engine.process(flatten_file(NESTED_VIEW), source_file_path=str(NESTED_VIEW))
		self.assertEqual(len(rule.visited), 1)
		self.assertEqual(rule.visited[0].view_path, 'Naming/Title Case Folder/Title Case View')

	def test_no_view_node_without_source_path(self):
		"""Callers that do not supply a path get no View node rather than a bogus one."""
		rule = _RecordingRule()
		LintEngine([rule]).process(flatten_file(NESTED_VIEW))
		self.assertEqual(rule.visited, [])

	def test_model_rebuilt_when_only_source_path_changes(self):
		"""Same flattened JSON object under a new path must not reuse the stale View node."""
		rule = _RecordingRule()
		engine = LintEngine([rule])
		flattened = flatten_file(NESTED_VIEW)
		engine.process(flattened, source_file_path='views/A/view.json')
		engine.process(flattened, source_file_path='views/B/view.json')
		self.assertEqual([node.name for node in rule.visited], ['A', 'B'])

	def test_statistics_and_debug_include_view(self):
		"""Stats count the view node and --debug-nodes can filter on 'view'."""
		engine = LintEngine([])
		flattened = flatten_file(NESTED_VIEW)
		stats = engine.get_model_statistics(flattened, str(NESTED_VIEW))
		self.assertEqual(stats['node_type_counts'].get('view'), 1)
		self.assertIn('view', stats['model_keys'])

		debug = engine.debug_nodes(flattened, ['view'], str(NESTED_VIEW))
		self.assertEqual(len(debug), 1)
		self.assertEqual(debug[0]['view_path'], 'Naming/Title Case Folder/Title Case View')

	def test_rule_impact_summary_for_view(self):
		"""analyze_rule_impact describes the view node in plain words."""
		engine = LintEngine([_RecordingRule()])
		analysis = engine.analyze_rule_impact(flatten_file(NESTED_VIEW), str(NESTED_VIEW))
		details = analysis['_RecordingRule']['node_details']
		self.assertEqual(len(details), 1)
		self.assertEqual(details[0]['summary'], "View 'Title Case View' in folder 'Naming/Title Case Folder'")


if __name__ == '__main__':
	unittest.main()
