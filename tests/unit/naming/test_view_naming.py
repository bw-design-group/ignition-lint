# pylint: disable=import-error
"""
Unit tests for NamePatternRule applied to the view itself and its parent folders.

Test views live under tests/cases/views/Naming/. ``tests/cases/views`` is the bare ``views``
segment nearest the files, so it stands in for the Perspective views root; ``Naming``
and everything below it are view folders (plain directories).
"""

import unittest
from typing import Dict, Any

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, load_test_view
from ignition_lint.common.flatten_json import read_json_file, flatten_json
from ignition_lint.common.path_translator import PathTranslator

RULE = "NamePatternRule"
PASCAL_VIEW = "Naming/PascalFolder/PascalView"
TITLE_VIEW = "Naming/Title Case Folder/Title Case View"
DEEP_VIEW = "Naming/PascalFolder/Nested Sub Folder/DeepView"


class TestViewNamingPascalCase(BaseRuleTest):
	"""PascalCase enforced on the view name and every parent folder."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config(
			RULE, target_node_types=["view"], convention="PascalCase", severity="error"
		)

	def test_pascal_folder_and_view_pass(self):
		"""PascalCase folder and view produce no violations."""
		view_file = load_test_view(self.test_cases_dir, PASCAL_VIEW)
		self.run_lint_on_file(view_file, self.rule_config)
		self.assert_no_issues(RULE)

	def test_title_case_folder_and_view_both_fail(self):
		"""One violation for the view name and one for the folder, each with a suggestion."""
		view_file = load_test_view(self.test_cases_dir, TITLE_VIEW)
		self.assert_rule_fails(view_file, self.rule_config, RULE, expected_error_count=2)
		errors = self.get_errors_for_rule(RULE)
		self.assertIn(
			"Naming/Title Case Folder/Title Case View: Name 'Title Case View' doesn't follow PascalCase for view "
			"(suggestion: 'TitleCaseView')", errors
		)
		self.assertIn(
			"Naming/Title Case Folder/Title Case View: Folder name 'Title Case Folder' doesn't follow PascalCase "
			"for view (suggestion: 'TitleCaseFolder')", errors
		)

	def test_only_offending_folder_is_reported(self):
		"""A PascalCase view under a mixed folder chain reports just the bad folder."""
		view_file = load_test_view(self.test_cases_dir, DEEP_VIEW)
		self.assert_rule_fails(view_file, self.rule_config, RULE, expected_error_count=1)
		self.assertIn("Folder name 'Nested Sub Folder'", self.get_errors_for_rule(RULE)[0])

	def test_pattern_allows_multiple_styles_on_whole_tree(self):
		"""A pattern override on 'view' applies to folders and the view alike."""
		config = get_test_config(
			RULE, node_type_specific_rules={
				"view": {
					"pattern": r"^([A-Z][a-zA-Z0-9]*|[A-Z][a-z]*(\s[A-Z][a-z]*)*)$",
					"pattern_description": "PascalCase or Title Case",
					"suggestion_convention": "PascalCase",
					"severity": "error",
				}
			}
		)
		for case in (PASCAL_VIEW, TITLE_VIEW, DEEP_VIEW):
			self.run_lint_on_file(load_test_view(self.test_cases_dir, case), config)
			self.assert_no_issues(RULE)

	def test_title_case_convention_accepts_title_case_tree(self):
		"""The convention is honoured, not hard-coded to PascalCase."""
		config = get_test_config(RULE, target_node_types=["view"], convention="Title Case", severity="error")
		view_file = load_test_view(self.test_cases_dir, TITLE_VIEW)
		self.run_lint_on_file(view_file, config)
		self.assert_no_issues(RULE)

		view_file = load_test_view(self.test_cases_dir, PASCAL_VIEW)
		self.assert_rule_fails(view_file, config, RULE, expected_error_count=2)


class TestViewNamingTopLevelViews(BaseRuleTest):
	"""Views directly under the views root: the view name is checked and no folders are inferred."""
	rule_config: Dict[str, Dict[str, Any]]  # Override base class to make non-optional

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		self.rule_config = get_test_config(
			RULE, target_node_types=["view"], convention="PascalCase", severity="error"
		)

	def test_flat_case_directory_name_is_validated(self):
		"""tests/cases/views/Title Case/view.json is named after its directory and fails PascalCase."""
		view_file = load_test_view(self.test_cases_dir, "Title Case")
		self.assert_rule_fails(view_file, self.rule_config, RULE, expected_error_count=1)
		self.assertIn(
			"Title Case: Name 'Title Case' doesn't follow PascalCase for view",
			self.get_errors_for_rule(RULE)[0]
		)

	def test_parent_directories_are_not_treated_as_folders(self):
		"""'tests' and 'cases' must never be reported as folder names."""
		view_file = load_test_view(self.test_cases_dir, "PascalCase")
		self.run_lint_on_file(view_file, self.rule_config)
		self.assert_no_issues(RULE)


class TestViewNamingAlongsideComponents(BaseRuleTest):
	"""View targeting is opt-in and composes with per-node-type rules."""

	def test_component_only_config_ignores_view_and_folders(self):
		"""Existing configs that target components see no view violations."""
		config = get_test_config(
			RULE, target_node_types=["component"], convention="PascalCase", severity="error"
		)
		view_file = load_test_view(self.test_cases_dir, TITLE_VIEW)
		self.run_lint_on_file(view_file, config)
		self.assert_no_issues(RULE)

	def test_default_target_ignores_view(self):
		"""With no target_node_types the rule still defaults to components only."""
		config = get_test_config(RULE, convention="PascalCase", severity="error")
		view_file = load_test_view(self.test_cases_dir, TITLE_VIEW)
		self.run_lint_on_file(view_file, config)
		self.assert_no_issues(RULE)

	def test_per_node_type_conventions(self):
		"""Components may use one convention while views and folders use another."""
		config = get_test_config(
			RULE, node_type_specific_rules={
				"component": {
					"convention": "PascalCase",
					"severity": "error"
				},
				"view": {
					"convention": "Title Case",
					"severity": "warning"
				},
			}
		)
		view_file = load_test_view(self.test_cases_dir, TITLE_VIEW)
		self.run_lint_on_file(view_file, config)
		self.assert_no_issues(RULE)

		view_file = load_test_view(self.test_cases_dir, PASCAL_VIEW)
		self.run_lint_on_file(view_file, config)
		self.assertEqual(self.get_error_count(RULE), 0)
		self.assertEqual(self.get_warning_count(RULE), 2)
		self.assertTrue(all("for view" in message for message in self.get_warnings_for_rule(RULE)))

	def test_check_view_folders_false_validates_only_the_view_name(self):
		"""``check_view_folders: false`` on the view entry leaves folders alone."""
		config = get_test_config(
			RULE,
			node_type_specific_rules={"view": {
				"convention": "PascalCase",
				"check_view_folders": False
			}}, severity="error"
		)
		view_file = load_test_view(self.test_cases_dir, TITLE_VIEW)
		self.assert_rule_fails(view_file, config, RULE, expected_error_count=1)
		self.assertIn("Name 'Title Case View'", self.get_errors_for_rule(RULE)[0])

	def test_skip_names_on_view_entry_exempts_a_folder(self):
		"""A folder listed in the view entry's skip_names is not reported; the view name still is."""
		config = get_test_config(
			RULE, node_type_specific_rules={
				"view": {
					"convention": "PascalCase",
					"skip_names": ["Title Case Folder"]
				}
			}, severity="error"
		)
		view_file = load_test_view(self.test_cases_dir, TITLE_VIEW)
		self.assert_rule_fails(view_file, config, RULE, expected_error_count=1)
		self.assertIn("Name 'Title Case View'", self.get_errors_for_rule(RULE)[0])

	def test_root_is_not_exempt_for_views_and_folders(self):
		"""The implicit ``root`` skip is for the root component, not for a folder or view named root."""
		import tempfile  # pylint: disable=import-outside-toplevel
		from pathlib import Path  # pylint: disable=import-outside-toplevel
		from ignition_lint.domains import PERSPECTIVE_SPEC  # pylint: disable=import-outside-toplevel
		from ignition_lint.linter import LintEngine  # pylint: disable=import-outside-toplevel
		from ignition_lint.model.node_types import NodeType  # pylint: disable=import-outside-toplevel
		from ignition_lint.rules.naming.name_pattern import NamePatternRule  # pylint: disable=import-outside-toplevel
		with tempfile.TemporaryDirectory() as tmp:
			view_dir = Path(tmp) / 'views' / 'root' / 'RootyView'
			view_dir.mkdir(parents=True)
			(view_dir / 'view.json').write_text(
				'{"root": {"meta": {"name": "root"}, "type": "ia.container.flex", "children": []}}',
				encoding='utf-8'
			)
			rule = NamePatternRule(
				convention='PascalCase', target_node_types={NodeType.VIEW}, severity='error'
			)
			_, results = LintEngine([rule]).process_file(view_dir / 'view.json', PERSPECTIVE_SPEC)
			messages = results.errors.get(RULE, [])
			self.assertEqual(len(messages), 1, messages)
			self.assertIn("Folder name 'root'", messages[0])

	def test_no_fix_is_generated_for_views(self):
		"""Renaming a view means renaming directories; the rule never offers a fix for it, even in fix mode."""
		view_file = load_test_view(self.test_cases_dir, TITLE_VIEW)
		config = get_test_config(RULE, target_node_types=["view"], convention="PascalCase", severity="error")
		json_data = read_json_file(view_file)
		results = self.create_lint_engine(config).process(
			flatten_json(json_data), source_file_path=str(view_file), json_data=json_data,
			path_translator=PathTranslator(json_data)
		)
		self.assertEqual(len(results.errors[RULE]), 2)
		self.assertEqual(results.fixes, [])


if __name__ == '__main__':
	unittest.main()
