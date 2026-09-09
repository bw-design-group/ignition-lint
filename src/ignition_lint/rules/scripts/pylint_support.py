"""
Shared pylint plumbing for the Perspective and library script rules.

Nothing here is a ``LintingRule``, so rule discovery ignores this module. Both pylint
rules use it for rcfile resolution, running pylint in-process, parsing its text output
and rendering violations grouped by pylint category with a configurable severity mapping.
"""

import os
import re
import sys
from dataclasses import dataclass
from io import StringIO
from typing import Dict, Iterable, List, Optional, Tuple

from pylint import lint
from pylint.reporters.text import TextReporter

DEFAULT_CATEGORY_MAPPING = {
	'F': 'error',  # Fatal
	'E': 'error',  # Error
	'W': 'warning',  # Warning
	'C': 'warning',  # Convention
	'R': 'warning',  # Refactor
}

CATEGORY_NAMES = {
	'F': 'Fatal',
	'E': 'Error',
	'W': 'Warning',
	'C': 'Convention',
	'R': 'Refactor',
}

CATEGORY_ORDER = ('F', 'E', 'W', 'C', 'R')

# ``path:line:col: CODE: message`` as emitted by pylint's text reporter.
MESSAGE_PATTERN = re.compile(r'.*:(\d+):\d+: ([EWCRF]\d+): (.+)')

# Directory holding the rcfiles shipped inside the package (``ignition_lint/.config``).
BUNDLED_CONFIG_DIR = os.path.join(
	os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".config"
)


@dataclass
class PylintViolation:
	"""One pylint message attributed back to a script."""
	category: str  # E, W, C, R, F
	code: str  # E0602, W0611, etc.
	message: str
	path: str  # Script path (rule-specific meaning)
	line: int  # Line number within the script
	severity: str = ''  # Set by the rule from its category mapping


def resolve_pylintrc(explicit: Optional[str], standard_filename: str) -> Optional[str]:
	"""
	Locate the rcfile to use.

	Order: the explicit path (absolute or relative to the working directory), then
	``.config/<standard_filename>`` walking up from the working directory, then the copy
	bundled with the package. Returns None when nothing is found.
	"""
	if explicit:
		candidate = explicit if os.path.isabs(explicit) else os.path.join(os.getcwd(), explicit)
		if os.path.exists(candidate):
			return candidate
		print(f"⚠️  Warning: Specified pylintrc not found: {explicit}")
		if candidate != explicit:
			print(f"   Tried: {candidate}")
			print(f"   Current directory: {os.getcwd()}")
		print("   Falling back to standard location search...")

	current_path = os.getcwd()
	while current_path != os.path.dirname(current_path):
		standard_pylintrc = os.path.join(current_path, ".config", standard_filename)
		if os.path.exists(standard_pylintrc):
			return standard_pylintrc
		current_path = os.path.dirname(current_path)

	bundled_pylintrc = os.path.join(BUNDLED_CONFIG_DIR, standard_filename)
	if os.path.exists(bundled_pylintrc):
		return bundled_pylintrc
	return None


def build_pylint_args(rcfile: Optional[str], targets: Iterable[str], extra: Iterable[str] = ()) -> List[str]:
	"""
	Assemble the pylint command line.

	Always forces ``--jobs=1``: the bundled rcfiles may set ``jobs`` higher, which makes
	pylint spawn a worker pool for every ``Run`` even when linting a single file.
	"""
	args: List[str] = []
	if rcfile:
		args.extend(['--rcfile', rcfile])
	else:
		args.extend([
			'--disable=all',
			'--enable=unused-import,undefined-variable,syntax-error,invalid-name',
		])
	args.extend(['--output-format=text', '--score=no', '--jobs=1'])
	args.extend(extra)
	args.extend(targets)
	return args


def run_pylint(args: List[str]) -> str:
	"""
	Run pylint in-process and return everything it printed.

	stdout/stderr are swapped for the duration: with ``--output-format=text`` pylint writes
	to the configured reporter, but warnings about the rcfile itself still go to the real
	streams, and those must not leak into the CLI output.
	"""
	pylint_output = StringIO()
	old_stdout, old_stderr = sys.stdout, sys.stderr
	try:
		sys.stdout = pylint_output
		sys.stderr = pylint_output
		lint.Run(args, reporter=TextReporter(pylint_output), exit=False)
	finally:
		sys.stdout, sys.stderr = old_stdout, old_stderr
	return pylint_output.getvalue()


def parse_pylint_messages(output: str) -> List[Tuple[int, str, str, str]]:
	"""Parse text-reporter output into ``(line, code, category, message)`` tuples."""
	messages: List[Tuple[int, str, str, str]] = []
	for line in output.splitlines():
		match = MESSAGE_PATTERN.match(line)
		if not match:
			continue
		try:
			line_num = int(match.group(1))
		except ValueError:
			continue
		code = match.group(2)
		messages.append((line_num, code, code[0], match.group(3)))
	return messages


class PylintCategoryMixin:
	"""
	Category-to-severity mapping and grouped rendering shared by the pylint rules.

	Host classes must provide ``self.severity`` and set ``self.pylint_violations``; they
	may override ``_format_violation_path`` to control how a violation's path is shown.
	"""

	category_mapping: Dict[str, str]
	pylint_violations: List[PylintViolation]

	def init_category_mapping(self, category_mapping: Optional[Dict[str, str]]) -> None:
		"""Install the category mapping (defaults when None) and an empty violation list."""
		self.category_mapping = dict(category_mapping) if category_mapping else dict(DEFAULT_CATEGORY_MAPPING)
		self.pylint_violations = []

	def severity_for_category(self, category: str) -> str:
		"""Severity for a pylint category, falling back to the rule's default severity."""
		return self.category_mapping.get(category, getattr(self, 'severity', 'error'))

	def _format_violation_path(self, path: str) -> str:
		"""How a violation's ``path`` is displayed. Hosts override to strip prefixes."""
		return path

	def _format_violation(self, violation: PylintViolation) -> str:
		location = self._format_violation_path(violation.path)
		prefix = f"{location}: " if location else ""
		return f"{prefix}Line {violation.line}: {violation.message} ({violation.code})"

	def get_category_grouped_violations(self) -> Dict[str, Dict[str, object]]:
		"""
		Group violations by pylint category, in F/E/W/C/R order.

		Each entry is ``{'severity': ..., 'name': ..., 'violations': [formatted, ...]}``.
		"""
		grouped: Dict[str, Dict[str, object]] = {}
		for violation in self.pylint_violations:
			entry = grouped.setdefault(
				violation.category, {
					'severity': self.severity_for_category(violation.category),
					'name': CATEGORY_NAMES.get(violation.category, violation.category),
					'violations': [],
				}
			)
			entry['violations'].append(self._format_violation(violation))
		return {cat: grouped[cat] for cat in CATEGORY_ORDER if cat in grouped}

	def format_violations_grouped(self) -> Optional[Dict[str, str]]:
		"""Render violations grouped by category, split into warning and error text."""
		grouped = self.get_category_grouped_violations()
		if not grouped:
			return None

		warnings_lines: List[str] = []
		errors_lines: List[str] = []
		for category, data in grouped.items():
			category_output = [f"\n    Pylint - {data['name']} ({category}):"]
			category_output.extend(f"      • {violation}" for violation in data['violations'])
			if data['severity'] == "error":
				errors_lines.extend(category_output)
			else:
				warnings_lines.extend(category_output)

		return {
			"warnings": '\n'.join(warnings_lines) if warnings_lines else None,
			"errors": '\n'.join(errors_lines) if errors_lines else None
		}
