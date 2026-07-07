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
		Find conflicting fixes: two operations targeting the same path in
		ways that cannot compose. First fix wins, second is flagged.

		STRING_REPLACE operations with disjoint contexts on the same value
		are NOT conflicts: renaming two different components referenced in
		one expression must update both references (issue #115). They only
		conflict when their contexts interact (identical old text with
		different replacements, or one context containing the other).
		"""
		conflicts = []
		# Track which (path, operation) pairs are claimed by which fix
		claimed_ops: List[Tuple[str, object, Fix]] = []

		for fix in fixes:
			conflicting_with = None
			for operation in fix.operations:
				path_key = str(operation.json_path)
				for existing_path_key, existing_op, existing_fix in claimed_ops:
					if path_key != existing_path_key or existing_fix is fix:
						continue
					if self._operations_conflict(existing_op, operation):
						conflicting_with = (existing_fix, operation)
						break
				if conflicting_with:
					break

			if conflicting_with:
				existing_fix, operation = conflicting_with
				conflicts.append(
					FixConflict(
						fix_a=existing_fix, fix_b=fix, conflicting_path=operation.json_path,
						description=f"Both fixes modify path {operation.format_path()}"
					)
				)
			else:
				for operation in fix.operations:
					claimed_ops.append((str(operation.json_path), operation, fix))

		return conflicts

	@staticmethod
	def _operations_conflict(op_a, op_b) -> bool:
		"""Whether two operations on the same JSON path cannot compose."""
		if (
			op_a.operation != FixOperationType.STRING_REPLACE or
			op_b.operation != FixOperationType.STRING_REPLACE
		):
			# SET_VALUE against anything on the same path is a conflict.
			return True

		old_a, old_b = op_a.old_substring or '', op_b.old_substring or ''
		if old_a == old_b:
			# Identical rewrites compose (second is a no-op); different
			# replacements of the same text cannot both win.
			return op_a.new_substring != op_b.new_substring
		# One context containing the other means the outer rewrite would
		# invalidate the inner one - order-dependent, treat as conflict.
		return old_a in old_b or old_b in old_a

	def _apply_single_fix(self, fix: Fix):
		"""Apply all operations in a single fix."""
		for operation in fix.operations:
			if operation.operation == FixOperationType.SET_VALUE:
				self.path_translator.set_value(operation.json_path, operation.new_value)
			elif operation.operation == FixOperationType.STRING_REPLACE:
				self.path_translator.string_replace_at(
					operation.json_path, operation.old_substring, operation.new_substring
				)
