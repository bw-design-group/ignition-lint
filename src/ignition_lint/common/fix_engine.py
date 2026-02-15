"""
Engine for applying fix operations to JSON data.

Handles conflict detection, dry-run previews, and safe vs unsafe fix filtering.
"""

from dataclasses import dataclass, field
from typing import List, Tuple
from .fix_operations import Fix, FixOperationType
from .path_translator import PathTranslator


@dataclass
class FixConflict:
	"""Describes a conflict between two fix operations."""
	fix_a: Fix
	fix_b: Fix
	conflicting_path: list
	description: str


@dataclass
class AppliedFix:
	"""Record of a fix that was applied or skipped."""
	fix: Fix
	applied: bool
	skip_reason: str = ""


@dataclass
class FixResult:
	"""Result of applying fixes."""
	applied: List[AppliedFix] = field(default_factory=list)
	skipped: List[AppliedFix] = field(default_factory=list)
	conflicts: List[FixConflict] = field(default_factory=list)

	@property
	def applied_count(self) -> int:
		return len(self.applied)

	@property
	def skipped_count(self) -> int:
		return len(self.skipped)


class FixEngine:
	"""Applies fix operations to JSON data via PathTranslator."""

	def __init__(self, path_translator: PathTranslator):
		self.path_translator = path_translator

	def apply_fixes(self, fixes: List[Fix], safe_only: bool = True, rule_filter: List[str] = None) -> FixResult:
		"""
		Apply fixes to the JSON data.

		Args:
			fixes: List of fixes to apply.
			safe_only: If True, skip fixes with is_safe=False.
			rule_filter: If provided, only apply fixes from these rule names.

		Returns:
			FixResult with details of applied and skipped fixes.
		"""
		result = FixResult()

		# Detect conflicts first
		conflicts = self.detect_conflicts(fixes)
		result.conflicts = conflicts
		conflicting_fixes = set()
		for conflict in conflicts:
			# Skip the second fix in each conflict pair
			conflicting_fixes.add(id(conflict.fix_b))

		for fix in fixes:
			# Check rule filter
			if rule_filter and fix.rule_name not in rule_filter:
				result.skipped.append(
					AppliedFix(fix=fix, applied=False, skip_reason="filtered by --fix-rules")
				)
				continue

			# Check safety
			if safe_only and not fix.is_safe:
				reason = f"unsafe: {fix.safety_notes}" if fix.safety_notes else "unsafe fix (use --fix-unsafe)"
				result.skipped.append(AppliedFix(fix=fix, applied=False, skip_reason=reason))
				continue

			# Check conflicts
			if id(fix) in conflicting_fixes:
				result.skipped.append(
					AppliedFix(fix=fix, applied=False, skip_reason="conflicts with another fix")
				)
				continue

			# Apply the fix
			try:
				self._apply_single_fix(fix)
				result.applied.append(AppliedFix(fix=fix, applied=True))
			except (KeyError, TypeError, ValueError) as e:
				result.skipped.append(AppliedFix(fix=fix, applied=False, skip_reason=f"error: {e}"))

		return result

	def dry_run(self, fixes: List[Fix], safe_only: bool = True, rule_filter: List[str] = None) -> FixResult:
		"""
		Preview what would change without modifying data.

		Returns same structure as apply_fixes but nothing is actually modified.
		"""
		result = FixResult()
		conflicts = self.detect_conflicts(fixes)
		result.conflicts = conflicts
		conflicting_fixes = set()
		for conflict in conflicts:
			conflicting_fixes.add(id(conflict.fix_b))

		for fix in fixes:
			if rule_filter and fix.rule_name not in rule_filter:
				result.skipped.append(
					AppliedFix(fix=fix, applied=False, skip_reason="filtered by --fix-rules")
				)
				continue

			if safe_only and not fix.is_safe:
				reason = f"unsafe: {fix.safety_notes}" if fix.safety_notes else "unsafe fix (use --fix-unsafe)"
				result.skipped.append(AppliedFix(fix=fix, applied=False, skip_reason=reason))
				continue

			if id(fix) in conflicting_fixes:
				result.skipped.append(
					AppliedFix(fix=fix, applied=False, skip_reason="conflicts with another fix")
				)
				continue

			# In dry run, we just mark it as would-be-applied
			result.applied.append(AppliedFix(fix=fix, applied=True))

		return result

	def detect_conflicts(self, fixes: List[Fix]) -> List[FixConflict]:
		"""
		Find conflicting fixes (e.g., two operations targeting the same path).

		First fix wins, second is flagged as conflicting.
		"""
		conflicts = []
		# Track which paths are claimed by which fix
		claimed_paths: List[Tuple[str, Fix]] = []

		for fix in fixes:
			for operation in fix.operations:
				path_key = str(operation.json_path)
				for existing_path_key, existing_fix in claimed_paths:
					if path_key == existing_path_key and existing_fix is not fix:
						conflicts.append(
							FixConflict(
								fix_a=existing_fix, fix_b=fix,
								conflicting_path=operation.json_path, description=
								f"Both fixes modify path {operation.format_path()}"
							)
						)
						break
				else:
					claimed_paths.append((path_key, fix))

		return conflicts

	def _apply_single_fix(self, fix: Fix):
		"""Apply all operations in a single fix."""
		for operation in fix.operations:
			if operation.operation == FixOperationType.SET_VALUE:
				self.path_translator.set_value(operation.json_path, operation.new_value)
			elif operation.operation == FixOperationType.STRING_REPLACE:
				self.path_translator.string_replace_at(
					operation.json_path, operation.old_substring, operation.new_substring
				)
