# pylint: disable=import-error
"""
Unit tests for the auto-fix framework.

Tests: fix_operations, path_translator, fix_engine, reference_finder,
and NamePatternRule fix generation.
"""

import json
import os
import sys
import unittest
import tempfile
from collections import OrderedDict
from pathlib import Path

# Add the src directory to the PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from ignition_lint.common.fix_operations import Fix, FixOperation, FixOperationType
from ignition_lint.common.path_translator import PathTranslator
from ignition_lint.common.fix_engine import FixEngine, FixResult
from ignition_lint.common.reference_finder import ComponentReferenceFinder
from ignition_lint.common.flatten_json import flatten_json, read_json_file, write_json_file
from ignition_lint.linter import LintEngine
from ignition_lint.rules import RULES_MAP


def make_view_json(children, custom=None, params=None):
	"""Helper to build a minimal view.json OrderedDict."""
	view = OrderedDict()
	if custom:
		view['custom'] = custom
	if params:
		view['params'] = params
	view['root'] = OrderedDict([
		('children', children),
		('meta', OrderedDict([('name', 'root')])),
		('props', OrderedDict()),
		('type', 'ia.container.flex'),
	])
	return view


def make_component(name, comp_type='ia.display.label', children=None, props=None, propConfig=None):
	"""Helper to build a component OrderedDict."""
	comp = OrderedDict()
	if children is not None:
		comp['children'] = children
	comp['meta'] = OrderedDict([('name', name)])
	if props:
		comp['props'] = props
	else:
		comp['props'] = OrderedDict()
	comp['type'] = comp_type
	if propConfig:
		comp['propConfig'] = propConfig
	return comp


# =============================================================================
# Test FixOperation and Fix data model
# =============================================================================
class TestFixOperations(unittest.TestCase):
	"""Test Fix and FixOperation data structures."""

	def test_create_set_value_operation(self):
		"""FixOperation SET_VALUE should store all fields correctly."""
		op = FixOperation(
			operation=FixOperationType.SET_VALUE, json_path=['root', 'children', 0, 'meta', 'name'],
			old_value='badButton', new_value='BadButton', description='Rename component'
		)
		self.assertEqual(op.operation, FixOperationType.SET_VALUE)
		self.assertEqual(op.json_path, ['root', 'children', 0, 'meta', 'name'])
		self.assertEqual(op.old_value, 'badButton')
		self.assertEqual(op.new_value, 'BadButton')

	def test_create_string_replace_operation(self):
		"""FixOperation STRING_REPLACE should store all fields correctly."""
		op = FixOperation(
			operation=FixOperationType.STRING_REPLACE, json_path=['root', 'children', 1, 'props', 'text'],
			old_substring='badButton', new_substring='BadButton', description='Update reference'
		)
		self.assertEqual(op.operation, FixOperationType.STRING_REPLACE)
		self.assertEqual(op.old_substring, 'badButton')
		self.assertEqual(op.new_substring, 'BadButton')

	def test_format_path(self):
		"""format_path should produce human-readable path strings."""
		op = FixOperation(
			operation=FixOperationType.SET_VALUE,
			json_path=['root', 'children', 0, 'meta', 'name'],
		)
		formatted = op.format_path()
		self.assertIn('root', formatted)
		self.assertIn('[0]', formatted)
		self.assertIn('meta', formatted)
		self.assertIn('name', formatted)

	def test_create_safe_fix(self):
		"""Fix with is_safe=True should indicate a safe fix."""
		fix = Fix(
			rule_name='NamePatternRule', violation_message='test violation',
			description='Rename badButton to BadButton', operations=[
				FixOperation(
					operation=FixOperationType.SET_VALUE,
					json_path=['root', 'children', 0, 'meta',
							'name'], old_value='badButton', new_value='BadButton'
				)
			], is_safe=True
		)
		self.assertTrue(fix.is_safe)
		self.assertIsNone(fix.safety_notes)
		self.assertEqual(len(fix.operations), 1)

	def test_create_unsafe_fix(self):
		"""Fix with is_safe=False and safety_notes should indicate an unsafe fix."""
		fix = Fix(
			rule_name='NamePatternRule', violation_message='test violation',
			description='Rename myLabel to MyLabel', operations=[], is_safe=False,
			safety_notes='updates 2 references'
		)
		self.assertFalse(fix.is_safe)
		self.assertEqual(fix.safety_notes, 'updates 2 references')


# =============================================================================
# Test PathTranslator
# =============================================================================
class TestPathTranslator(unittest.TestCase):
	"""Test PathTranslator model-path to JSON-path translation."""

	def setUp(self):
		"""Create a sample view.json for testing."""
		self.json_data = make_view_json(
			children=[
				make_component('BadButton', 'ia.input.button'),
				make_component('GoodLabel', 'ia.display.label'),
			]
		)
		self.translator = PathTranslator(self.json_data)

	def test_root_component_path(self):
		"""Root component model path should map to ['root'] JSON path."""
		json_path = self.translator.model_path_to_json_path('root.root')
		self.assertEqual(json_path, ['root'])

	def test_child_component_path(self):
		"""Child component model path should map correctly."""
		json_path = self.translator.model_path_to_json_path('root.root.children[0].BadButton')
		self.assertEqual(json_path, ['root', 'children', 0])

	def test_component_name_path(self):
		"""get_component_name_path should return path to meta.name."""
		name_path = self.translator.get_component_name_path('root.root.children[0].BadButton')
		self.assertEqual(name_path, ['root', 'children', 0, 'meta', 'name'])

	def test_get_value(self):
		"""get_value should retrieve correct values from JSON data."""
		name_path = self.translator.get_component_name_path('root.root.children[0].BadButton')
		value = self.translator.get_value(name_path)
		self.assertEqual(value, 'BadButton')

	def test_set_value(self):
		"""set_value should modify the JSON data in-place."""
		name_path = self.translator.get_component_name_path('root.root.children[0].BadButton')
		self.translator.set_value(name_path, 'GoodButton')
		self.assertEqual(self.json_data['root']['children'][0]['meta']['name'], 'GoodButton')

	def test_get_all_component_paths(self):
		"""get_all_component_paths should return all component model paths."""
		paths = self.translator.get_all_component_paths()
		self.assertIn('root.root', paths)
		self.assertIn('root.root.children[0].BadButton', paths)
		self.assertIn('root.root.children[1].GoodLabel', paths)

	def test_string_replace_at(self):
		"""string_replace_at should replace substring in string values."""
		# Set a string value to test with
		self.json_data['root']['children'][0]['props']['text'] = 'Hello from BadButton'
		result = self.translator.string_replace_at(['root', 'children', 0, 'props', 'text'], 'BadButton',
								'GoodButton')
		self.assertTrue(result)
		self.assertEqual(self.json_data['root']['children'][0]['props']['text'], 'Hello from GoodButton')

	def test_string_replace_at_no_match(self):
		"""string_replace_at should return False if substring not found."""
		self.json_data['root']['children'][0]['props']['text'] = 'Hello world'
		result = self.translator.string_replace_at(['root', 'children', 0, 'props', 'text'], 'BadButton',
								'GoodButton')
		self.assertFalse(result)

	def test_nested_children_path(self):
		"""PathTranslator should handle deeply nested components."""
		json_data = make_view_json(
			children=[
				make_component(
					'Container1', 'ia.container.flex', children=[
						make_component('NestedButton', 'ia.input.button'),
					]
				),
			]
		)
		translator = PathTranslator(json_data)
		name_path = translator.get_component_name_path(
			'root.root.children[0].Container1.children[0].NestedButton'
		)
		self.assertEqual(name_path, ['root', 'children', 0, 'children', 0, 'meta', 'name'])
		self.assertEqual(translator.get_value(name_path), 'NestedButton')

	def test_property_value_path(self):
		"""PathTranslator should map property value paths correctly."""
		# Add a prop with a value so the path gets registered
		json_data = make_view_json(
			children=[
				make_component(
					'BadButton', 'ia.input.button', props=OrderedDict([('text', 'Click me')])
				),
			]
		)
		translator = PathTranslator(json_data)
		json_path = translator.model_path_to_json_path('root.root.children[0].BadButton.props.text')
		self.assertEqual(json_path, ['root', 'children', 0, 'props', 'text'])


# =============================================================================
# Test FixEngine
# =============================================================================
class TestFixEngine(unittest.TestCase):
	"""Test FixEngine apply/preview/conflict detection."""

	def setUp(self):
		"""Set up test data with a component to rename."""
		self.json_data = make_view_json(
			children=[
				make_component('badButton', 'ia.input.button'),
				make_component('GoodLabel', 'ia.display.label'),
			]
		)
		self.translator = PathTranslator(self.json_data)
		self.engine = FixEngine(self.translator)

	def _make_rename_fix(self, old_name, new_name, safe=True):
		"""Helper to create a component rename fix."""
		# Find the component's meta.name path
		for path in self.translator.get_all_component_paths():
			if path.endswith(f'.{old_name}'):
				name_path = self.translator.get_component_name_path(path)
				break
		else:
			raise ValueError(f"Component {old_name} not found")

		return Fix(
			rule_name='NamePatternRule', violation_message=f"Name '{old_name}' doesn't follow PascalCase",
			description=f"Rename '{old_name}' to '{new_name}'", operations=[
				FixOperation(
					operation=FixOperationType.SET_VALUE,
					json_path=name_path,
					old_value=old_name,
					new_value=new_name,
				)
			], is_safe=safe
		)

	def test_apply_safe_fix(self):
		"""apply_fixes should apply safe fixes and modify JSON data."""
		fix = self._make_rename_fix('badButton', 'BadButton')
		result = self.engine.apply_fixes([fix], safe_only=True)

		self.assertEqual(result.applied_count, 1)
		self.assertEqual(result.skipped_count, 0)
		self.assertEqual(self.json_data['root']['children'][0]['meta']['name'], 'BadButton')

	def test_skip_unsafe_fix_in_safe_mode(self):
		"""apply_fixes with safe_only=True should skip unsafe fixes."""
		fix = self._make_rename_fix('badButton', 'BadButton', safe=False)
		result = self.engine.apply_fixes([fix], safe_only=True)

		self.assertEqual(result.applied_count, 0)
		self.assertEqual(result.skipped_count, 1)
		# Name should NOT have changed
		self.assertEqual(self.json_data['root']['children'][0]['meta']['name'], 'badButton')

	def test_apply_unsafe_fix_when_allowed(self):
		"""apply_fixes with safe_only=False should apply unsafe fixes."""
		fix = self._make_rename_fix('badButton', 'BadButton', safe=False)
		result = self.engine.apply_fixes([fix], safe_only=False)

		self.assertEqual(result.applied_count, 1)
		self.assertEqual(self.json_data['root']['children'][0]['meta']['name'], 'BadButton')

	def test_dry_run_does_not_modify(self):
		"""dry_run should not modify JSON data."""
		fix = self._make_rename_fix('badButton', 'BadButton')
		result = self.engine.dry_run([fix], safe_only=True)

		self.assertEqual(result.applied_count, 1)  # Would be applied
		# But data should be unchanged
		self.assertEqual(self.json_data['root']['children'][0]['meta']['name'], 'badButton')

	def test_rule_filter(self):
		"""apply_fixes should filter by rule name when rule_filter is set."""
		fix = self._make_rename_fix('badButton', 'BadButton')
		result = self.engine.apply_fixes([fix], rule_filter=['OtherRule'])

		self.assertEqual(result.applied_count, 0)
		self.assertEqual(result.skipped_count, 1)
		self.assertIn('filtered', result.skipped[0].skip_reason)

	def test_conflict_detection(self):
		"""detect_conflicts should find fixes targeting the same path."""
		fix1 = self._make_rename_fix('badButton', 'BadButton')
		fix2 = Fix(
			rule_name='OtherRule',
			violation_message='other issue',
			description='Another rename',
			operations=[
			FixOperation(
			operation=FixOperationType.SET_VALUE,
			json_path=fix1.operations[0].json_path,  # Same path
			old_value='badButton',
			new_value='OtherName',
			)
			]
		)
		conflicts = self.engine.detect_conflicts([fix1, fix2])
		self.assertEqual(len(conflicts), 1)
		self.assertIs(conflicts[0].fix_a, fix1)
		self.assertIs(conflicts[0].fix_b, fix2)

	def test_no_conflicts_different_paths(self):
		"""detect_conflicts should not flag fixes on different paths."""
		fix1 = self._make_rename_fix('badButton', 'BadButton')
		fix2 = Fix(
			rule_name='NamePatternRule', violation_message='other issue', description='Another rename',
			operations=[
				FixOperation(
					operation=FixOperationType.SET_VALUE,
					json_path=['root', 'children', 1, 'meta', 'name'],
					old_value='GoodLabel',
					new_value='BetterLabel',
				)
			]
		)
		conflicts = self.engine.detect_conflicts([fix1, fix2])
		self.assertEqual(len(conflicts), 0)


# =============================================================================
# Test ComponentReferenceFinder
# =============================================================================
class TestReferenceFinder(unittest.TestCase):
	"""Test ComponentReferenceFinder searching for component name references."""

	def test_find_expression_reference(self):
		"""Should find component name in expression binding."""
		json_data = make_view_json(
			children=[
				make_component('MyButton', 'ia.input.button'),
				make_component(
					'MyLabel', 'ia.display.label',
					props=OrderedDict([('text', '{../MyButton.props.text}')])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		finder = ComponentReferenceFinder(flattened, translator)

		refs = finder.find_references('MyButton')
		self.assertGreater(len(refs), 0)
		self.assertEqual(refs[0].ref_type, 'expression')

	def test_find_property_binding_reference(self):
		"""Should find component name in property binding path value."""
		# Put the property binding path value directly in a component's props
		# so both the json_data and flattened_json contain it
		json_data = make_view_json(
			children=[
				make_component('Switch1', 'ia.input.switch'),
				make_component(
					'Label1', 'ia.display.label',
					props=OrderedDict([('bindingRef', '../Switch1.props.selected')])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		finder = ComponentReferenceFinder(flattened, translator)

		refs = finder.find_references('Switch1')
		self.assertGreater(len(refs), 0)
		self.assertEqual(refs[0].ref_type, 'property_binding')

	def test_find_script_reference(self):
		"""Should find component name in script getSibling calls."""
		json_data = make_view_json(
			children=[
				make_component('TargetButton', 'ia.input.button'),
				make_component(
					'ScriptComp', 'ia.display.label',
					props=OrderedDict([('text', "self.getSibling('TargetButton').props.text")])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		finder = ComponentReferenceFinder(flattened, translator)

		refs = finder.find_references('TargetButton')
		self.assertGreater(len(refs), 0)
		self.assertEqual(refs[0].ref_type, 'script')

	def test_no_references_for_unreferenced_component(self):
		"""Should return empty list for components not referenced anywhere."""
		json_data = make_view_json(
			children=[
				make_component('StandaloneButton', 'ia.input.button'),
				make_component('StandaloneLabel', 'ia.display.label'),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		finder = ComponentReferenceFinder(flattened, translator)

		refs = finder.find_references('StandaloneButton')
		self.assertEqual(len(refs), 0)

	def test_has_self_name_binding_expression(self):
		"""Should detect {this.meta.name} in expression bindings."""
		json_data = make_view_json(
			children=[
				make_component(
					'MyButton', 'ia.input.button', propConfig=OrderedDict([(
						'meta.tooltip.text',
						OrderedDict([(
							'binding',
							OrderedDict([
								(
									'config',
									OrderedDict([('expression',
											'{this.meta.name}')])
								),
								('type', 'expr'),
							])
						)])
					)])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		finder = ComponentReferenceFinder(flattened, translator)

		self.assertTrue(finder.has_self_name_binding('root.root.children[0].MyButton'))

	def test_has_self_name_binding_property(self):
		"""Should detect this.meta.name in property binding paths."""
		json_data = make_view_json(
			children=[
				make_component(
					'MyButton', 'ia.input.button', propConfig=OrderedDict([(
						'props.text',
						OrderedDict([(
							'binding',
							OrderedDict([
								('config', OrderedDict([('path', 'this.meta.name')])),
								('type', 'property'),
							])
						)])
					)])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		finder = ComponentReferenceFinder(flattened, translator)

		self.assertTrue(finder.has_self_name_binding('root.root.children[0].MyButton'))

	def test_no_self_name_binding(self):
		"""Should return False for components without this.meta.name bindings."""
		json_data = make_view_json(children=[
			make_component('MyButton', 'ia.input.button'),
		])
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		finder = ComponentReferenceFinder(flattened, translator)

		self.assertFalse(finder.has_self_name_binding('root.root.children[0].MyButton'))

	def test_build_rename_operations(self):
		"""build_rename_operations should create STRING_REPLACE operations."""
		json_data = make_view_json(
			children=[
				make_component('MyButton', 'ia.input.button'),
				make_component(
					'MyLabel', 'ia.display.label',
					props=OrderedDict([('text', '{../MyButton.props.text}')])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		finder = ComponentReferenceFinder(flattened, translator)

		refs = finder.find_references('MyButton')
		operations = finder.build_rename_operations('MyButton', 'NewButton', refs)

		self.assertGreater(len(operations), 0)
		self.assertEqual(operations[0].operation, FixOperationType.STRING_REPLACE)
		self.assertEqual(operations[0].old_substring, 'MyButton')
		self.assertEqual(operations[0].new_substring, 'NewButton')


# =============================================================================
# Test NamePatternRule fix generation
# =============================================================================
class TestNamePatternRuleFixes(unittest.TestCase):
	"""Test that NamePatternRule generates correct Fix objects."""

	def _create_engine_with_rule(self, convention='PascalCase'):
		"""Create a LintEngine with a NamePatternRule."""
		rule_class = RULES_MAP['NamePatternRule']
		rule = rule_class.create_from_config({
			'convention': convention,
			'target_node_types': ['component'],
			'severity': 'warning',
		})
		return LintEngine([rule])

	def test_generates_safe_fix_for_unreferenced_component(self):
		"""Should generate a safe fix when component has no references."""
		json_data = make_view_json(children=[
			make_component('badButton', 'ia.input.button'),
		])
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		engine = self._create_engine_with_rule()

		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		self.assertGreater(len(results.fixes), 0)
		fix = results.fixes[0]
		self.assertTrue(fix.is_safe)
		self.assertEqual(fix.rule_name, 'NamePatternRule')
		self.assertEqual(len(fix.operations), 1)
		self.assertEqual(fix.operations[0].operation, FixOperationType.SET_VALUE)
		self.assertEqual(fix.operations[0].old_value, 'badButton')
		self.assertEqual(fix.operations[0].new_value, 'BadButton')

	def test_generates_unsafe_fix_for_referenced_component(self):
		"""Should generate an unsafe fix when component has references."""
		json_data = make_view_json(
			children=[
				make_component('badButton', 'ia.input.button'),
				make_component(
					'MyLabel', 'ia.display.label',
					props=OrderedDict([('text', '{../badButton.props.text}')])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		engine = self._create_engine_with_rule()

		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		# Find the fix for badButton
		bad_button_fixes = [f for f in results.fixes if 'badButton' in f.description]
		self.assertGreater(len(bad_button_fixes), 0)
		fix = bad_button_fixes[0]
		self.assertFalse(fix.is_safe)
		self.assertIsNotNone(fix.safety_notes)
		# Should have the rename op + at least one reference update op
		self.assertGreater(len(fix.operations), 1)

	def test_no_fix_when_name_is_valid(self):
		"""Should not generate fixes for components with valid names."""
		json_data = make_view_json(children=[
			make_component('GoodButton', 'ia.input.button'),
		])
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		engine = self._create_engine_with_rule()

		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		self.assertEqual(len(results.fixes), 0)

	def test_no_fix_without_fix_context(self):
		"""Should not generate fixes when fix context is not provided."""
		json_data = make_view_json(children=[
			make_component('badButton', 'ia.input.button'),
		])
		flattened = flatten_json(json_data)
		engine = self._create_engine_with_rule()

		# Process without json_data/path_translator
		results = engine.process(flattened)

		# Should still detect violations but no fixes
		self.assertEqual(len(results.fixes), 0)

	def test_generates_unsafe_fix_for_self_name_binding(self):
		"""Should generate an unsafe fix when component uses this.meta.name."""
		json_data = make_view_json(
			children=[
				make_component(
					'badButton', 'ia.input.button', propConfig=OrderedDict([(
						'props.text',
						OrderedDict([(
							'binding',
							OrderedDict([
								('config', OrderedDict([('path', 'this.meta.name')])),
								('type', 'property'),
							])
						)])
					)])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		engine = self._create_engine_with_rule()

		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		self.assertGreater(len(results.fixes), 0)
		fix = results.fixes[0]
		self.assertFalse(fix.is_safe)
		self.assertIn('this.meta.name', fix.safety_notes)

	def test_generates_unsafe_fix_for_self_name_and_references(self):
		"""Should combine safety notes when both this.meta.name and references exist."""
		json_data = make_view_json(
			children=[
				make_component(
					'badButton', 'ia.input.button', propConfig=OrderedDict([(
						'props.text',
						OrderedDict([(
							'binding',
							OrderedDict([
								('config', OrderedDict([('path', 'this.meta.name')])),
								('type', 'property'),
							])
						)])
					)])
				),
				make_component(
					'MyLabel', 'ia.display.label',
					props=OrderedDict([('text', '{../badButton.props.enabled}')])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		engine = self._create_engine_with_rule()

		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		bad_button_fixes = [f for f in results.fixes if 'badButton' in f.description]
		self.assertGreater(len(bad_button_fixes), 0)
		fix = bad_button_fixes[0]
		self.assertFalse(fix.is_safe)
		self.assertIn('this.meta.name', fix.safety_notes)
		self.assertIn('reference', fix.safety_notes)

	def test_fix_skips_root_component(self):
		"""Should not generate fix for 'root' component (it's in skip_names)."""
		json_data = make_view_json(children=[])
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)
		engine = self._create_engine_with_rule()

		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		root_fixes = [f for f in results.fixes if 'root' in f.description.lower()]
		self.assertEqual(len(root_fixes), 0)


# =============================================================================
# Test end-to-end fix application
# =============================================================================
class TestEndToEndFixApplication(unittest.TestCase):
	"""Integration test: detect violation -> generate fix -> apply fix -> verify JSON."""

	def test_full_safe_rename_pipeline(self):
		"""Full pipeline: lint -> fix -> write -> verify for a safe rename."""
		json_data = make_view_json(
			children=[
				make_component('badButton', 'ia.input.button'),
				make_component('GoodLabel', 'ia.display.label'),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)

		# Create engine and process
		rule_class = RULES_MAP['NamePatternRule']
		rule = rule_class.create_from_config({
			'convention': 'PascalCase',
			'target_node_types': ['component'],
			'severity': 'warning',
		})
		engine = LintEngine([rule])
		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		# Apply fixes
		fix_engine = FixEngine(translator)
		fix_result = fix_engine.apply_fixes(results.fixes, safe_only=True)

		# Verify the JSON was modified
		self.assertEqual(fix_result.applied_count, 1)
		self.assertEqual(json_data['root']['children'][0]['meta']['name'], 'BadButton')
		# Good component should be unchanged
		self.assertEqual(json_data['root']['children'][1]['meta']['name'], 'GoodLabel')

	def test_full_unsafe_rename_with_references(self):
		"""Full pipeline: lint -> fix -> apply (unsafe) -> verify references updated."""
		json_data = make_view_json(
			children=[
				make_component('badButton', 'ia.input.button'),
				make_component(
					'MyLabel', 'ia.display.label',
					props=OrderedDict([('text', '{../badButton.props.text}')])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)

		# Create engine and process
		rule_class = RULES_MAP['NamePatternRule']
		rule = rule_class.create_from_config({
			'convention': 'PascalCase',
			'target_node_types': ['component'],
			'severity': 'warning',
		})
		engine = LintEngine([rule])
		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		# Apply fixes with unsafe allowed
		fix_engine = FixEngine(translator)
		bad_button_fixes = [f for f in results.fixes if 'badButton' in f.description]
		fix_result = fix_engine.apply_fixes(bad_button_fixes, safe_only=False)

		# Verify name was changed
		self.assertEqual(json_data['root']['children'][0]['meta']['name'], 'BadButton')
		# Verify reference was updated
		self.assertIn('BadButton', json_data['root']['children'][1]['props']['text'])
		self.assertNotIn('badButton', json_data['root']['children'][1]['props']['text'])

	def test_write_and_read_back(self):
		"""Applied fixes should survive write_json_file + read_json_file round-trip."""
		json_data = make_view_json(children=[
			make_component('badButton', 'ia.input.button'),
		])
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)

		# Create engine and process
		rule_class = RULES_MAP['NamePatternRule']
		rule = rule_class.create_from_config({
			'convention': 'PascalCase',
			'target_node_types': ['component'],
			'severity': 'warning',
		})
		engine = LintEngine([rule])
		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		# Apply fixes
		fix_engine = FixEngine(translator)
		fix_engine.apply_fixes(results.fixes, safe_only=True)

		# Write to temp file and read back
		with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
			temp_path = Path(f.name)

		try:
			write_json_file(temp_path, json_data)
			read_back = read_json_file(temp_path)
			self.assertEqual(read_back['root']['children'][0]['meta']['name'], 'BadButton')
		finally:
			temp_path.unlink(missing_ok=True)

	def test_safe_only_skips_unsafe_fixes(self):
		"""When safe_only=True, unsafe fixes should be skipped."""
		json_data = make_view_json(
			children=[
				make_component('badButton', 'ia.input.button'),
				make_component(
					'MyLabel', 'ia.display.label',
					props=OrderedDict([('text', '{../badButton.props.text}')])
				),
			]
		)
		translator = PathTranslator(json_data)
		flattened = flatten_json(json_data)

		rule_class = RULES_MAP['NamePatternRule']
		rule = rule_class.create_from_config({
			'convention': 'PascalCase',
			'target_node_types': ['component'],
			'severity': 'warning',
		})
		engine = LintEngine([rule])
		results = engine.process(flattened, json_data=json_data, path_translator=translator)

		# Apply with safe_only=True
		fix_engine = FixEngine(translator)
		bad_button_fixes = [f for f in results.fixes if 'badButton' in f.description]
		fix_result = fix_engine.apply_fixes(bad_button_fixes, safe_only=True)

		# The unsafe fix should be skipped
		self.assertEqual(fix_result.applied_count, 0)
		self.assertEqual(fix_result.skipped_count, 1)
		# Name should be unchanged
		self.assertEqual(json_data['root']['children'][0]['meta']['name'], 'badButton')


if __name__ == '__main__':
	unittest.main()
