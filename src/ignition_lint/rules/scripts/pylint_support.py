"""
Shared pylint plumbing for the Perspective and library script rules.

Nothing here is a ``LintingRule``, so rule discovery ignores this module. Both pylint
rules use it for rcfile resolution, running pylint in-process, parsing its text output
and rendering violations grouped by pylint category with a configurable severity mapping.
"""

import os
import re
import sys
import tempfile
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
MESSAGE_PATTERN = re.compile(r'(.*?):(\d+):\d+: ([EWCRF]\d+): (.+)')

# Synthetic code for "pylint itself could not run" (bad rcfile option, argparse error).
PYLINT_RUN_ERROR_CODE = 'F0001'

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


class PylintRunError(RuntimeError):
	"""pylint refused to run (typically an invalid option value in the rcfile); ``output`` holds what it printed."""

	def __init__(self, output: str):
		super().__init__(output.strip().splitlines()[-1] if output.strip() else "pylint exited before linting")
		self.output = output


def _run_capturing(args: List[str]) -> Tuple[Optional[lint.Run], str]:
	"""Run pylint in-process with both streams captured; ``(None, output)`` when it bailed out."""
	pylint_output = StringIO()
	old_stdout, old_stderr = sys.stdout, sys.stderr
	try:
		sys.stdout = pylint_output
		sys.stderr = pylint_output
		run = lint.Run(args, reporter=TextReporter(pylint_output), exit=False)
	except SystemExit:
		return None, pylint_output.getvalue()
	finally:
		sys.stdout, sys.stderr = old_stdout, old_stderr
	return run, pylint_output.getvalue()


def run_pylint(args: List[str]) -> str:
	"""
	Run pylint in-process and return everything it printed.

	stdout/stderr are swapped for the duration: with ``--output-format=text`` pylint writes
	to the configured reporter, but warnings about the rcfile itself still go to the real
	streams, and those must not leak into the CLI output. ``exit=False`` only covers the
	post-lint exit; an argparse error still raises ``SystemExit``, which is turned into a
	``PylintRunError`` carrying the captured text so the caller can report it.
	"""
	run, output = _run_capturing(args)
	if run is None:
		raise PylintRunError(output)
	return output


def read_rcfile_list_option(rcfile: Optional[str], option: str) -> List[str]:
	"""
	Effective value of a list-valued option exactly as pylint parses ``rcfile``.

	Goes through pylint's own configuration loader (against an empty probe module with every
	checker disabled), so INI and TOML rcfiles, inline comments and multi-line values all come
	out as pylint sees them. Needed because a value passed on the command line *replaces* the
	rcfile's, so extending e.g. ``additional-builtins`` requires merging with the rcfile's
	list. ``[]`` when the rcfile is missing, rejected by pylint, or does not set the option.
	"""
	if not rcfile or not os.path.exists(rcfile):
		return []
	with tempfile.NamedTemporaryFile(prefix="ign_rc_probe_", suffix=".py", delete=False) as handle:
		probe = handle.name
	try:
		# ``--disable=all`` alone makes pylint exit with "No files to lint"; one cheap check keeps it running.
		run, _ = _run_capturing([
			'--rcfile', rcfile, '--disable=all', '--enable=syntax-error', '--jobs=1', '--score=no', probe
		])
	finally:
		try:
			os.remove(probe)
		except OSError:
			pass
	if run is None:
		return []
	value = getattr(run.linter.config, option.replace('-', '_'), None)
	if value is None:
		return []
	if isinstance(value, str):
		value = [value]
	return [str(item).strip() for item in value if str(item).strip()]


def _same_file(first: str, second: str) -> bool:
	try:
		return os.path.realpath(first) == os.path.realpath(second)
	except (OSError, ValueError):
		return False


def parse_pylint_messages(output: str, target: Optional[str] = None) -> List[Tuple[int, str, str, str]]:
	"""
	Parse text-reporter output into ``(line, code, category, message)`` tuples.

	When ``target`` (the linted file) is given, messages pylint attributes to another path,
	its own configuration diagnostics such as ``E0015 unrecognized-option`` reported against
	the rcfile, come back with line ``0`` and the offending path folded into the message,
	so they are never pinned to a line of the user's code.
	"""
	messages: List[Tuple[int, str, str, str]] = []
	for line in output.splitlines():
		match = MESSAGE_PATTERN.match(line)
		if not match:
			continue
		path, line_text, code, message = match.groups()
		try:
			line_num = int(line_text)
		except ValueError:
			continue
		if target is not None and not _same_file(path, target
							) and os.path.basename(path) != os.path.basename(target):
			messages.append((0, code, code[0], f"{message} [in {path}]"))
			continue
		messages.append((line_num, code, code[0], message))
	return messages


def run_error_violation(error: PylintRunError, rcfile: Optional[str], path: str) -> PylintViolation:
	"""One fatal violation describing why pylint could not run, so the run continues and the user sees the cause."""
	source = f" with {rcfile}" if rcfile else ""
	return PylintViolation(
		category='F', code=PYLINT_RUN_ERROR_CODE, message=f"pylint could not run{source}: {error}", path=path,
		line=0
	)


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
		where = f"Line {violation.line}: " if violation.line > 0 else ""
		return f"{prefix}{where}{violation.message} ({violation.code})"

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
