# pylint: disable=import-error,attribute-defined-outside-init
"""
Integration test for component references in the Pipes test case.

The Pipes view exercises component references written in every form a pipe
binding can take - property bindings, expression bindings, expression-struct
bindings and transform scripts - using both the single-dot './' (current
container) and traversal idioms. It deliberately contains broken references to
non-existent components ('Button1' in three forms, 'Button2' in one) alongside
a valid reference to the real 'Button'.

This guards the two complementary rules end-to-end:
  - ComponentReferenceValidationRule must catch every broken reference
    regardless of the form it is written in ("something is broken").
  - BadComponentReferenceRule must flag the brittle traversal in those same
    nodes, including property bindings ("you are doing a bad job").
"""

import unittest

from fixtures.base_test import BaseIntegrationTest
from fixtures.test_helpers import load_test_view

RULE_CONFIGS = {
	"ComponentReferenceValidationRule": {
		"enabled": True,
		"kwargs": {}
	},
	"BadComponentReferenceRule": {
		"enabled": True,
		"kwargs": {}
	},
}


class TestPipeReferences(BaseIntegrationTest):
	"""End-to-end checks for component references on the Pipes test case."""

	def setUp(self):  # pylint: disable=invalid-name
		super().setUp()
		view_file = load_test_view(self.test_cases_dir, "Pipes")
		self.results = self.run_multiple_rules_detailed(view_file, RULE_CONFIGS)

	def _validation_errors(self):
		return self.results.errors.get("ComponentReferenceValidationRule", [])

	def _bad_ref_errors(self):
		return self.results.errors.get("BadComponentReferenceRule", [])

	def test_all_broken_button1_references_detected(self):
		"""Every broken 'Button1' reference is caught, no matter the form."""
		button1_errors = [e for e in self._validation_errors() if "Button1" in e]

		# Three broken Button1 references exist: a property binding, an expression
		# binding and a transform script. All three must be detected.
		self.assertEqual(
			len(button1_errors), 3,
			f"Expected 3 broken Button1 references, got {len(button1_errors)}: {button1_errors}"
		)

		self.assertTrue(
			any("property binding" in e.lower() for e in button1_errors),
			f"Broken './Button1' property binding should be caught. Errors: {button1_errors}"
		)
		self.assertTrue(
			any("expression" in e.lower() for e in button1_errors),
			f"Broken '{{./Button1}}' expression should be caught. Errors: {button1_errors}"
		)
		self.assertTrue(
			any("not found as child" in e for e in button1_errors),
			f"Broken getChild('Button1') script should be caught. Errors: {button1_errors}"
		)

	def test_broken_button2_expression_reference_detected(self):
		"""The single-dot '{./Button2}' expression reference to a non-existent component is caught."""
		button2_errors = [e for e in self._validation_errors() if "Button2" in e]
		self.assertEqual(
			len(button2_errors), 1,
			f"Expected the broken Button2 expression reference to be caught, got: {button2_errors}"
		)
		self.assertIn("expression", button2_errors[0].lower())

	def test_every_broken_reference_is_reported(self):
		"""All broken references in the view (Button1 x3, Button2 x1) are reported and nothing else."""
		errors = self._validation_errors()
		self.assertEqual(
			len(errors), 4,
			f"Expected exactly 4 broken-reference errors (3x Button1, 1x Button2), got {len(errors)}: {errors}"
		)

	def test_valid_button_reference_not_flagged_as_broken(self):
		"""The valid './Button' reference resolves, so it is not a broken-reference error."""
		errors = self._validation_errors()
		# No validation error should complain about the existing 'Button' component.
		# (Matching the bare word boundary avoids matching 'Button1'.)
		spurious = [e for e in errors if "'Button'" in e]
		self.assertEqual(spurious, [], f"Valid './Button' reference must not be reported as broken: {spurious}")

	def test_property_binding_traversal_flagged_as_brittle(self):
		"""BadComponentReferenceRule now flags brittle traversal in property bindings too."""
		errors = self._bad_ref_errors()
		property_binding_flags = [e for e in errors if "Property Binding" in e]
		# Two property bindings use './' traversal (./Button and ./Button1).
		self.assertEqual(
			len(property_binding_flags), 2,
			f"Both './' property bindings should be flagged as brittle. Errors: {property_binding_flags}"
		)


if __name__ == "__main__":
	unittest.main()
