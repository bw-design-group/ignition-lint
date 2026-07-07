"""
Shared parser for component references in Perspective view.json string values.

This module is the single owner of Ignition's component-reference grammar.
Both the validation rules (which navigate the component tree to check that
references resolve) and the rename fixer (which rewrites references) consume
it, so the two can never drift apart again (issues #114/#115).

Reference forms (see the official Binding Property Path Reference docs):
  - Relative:  ./Child.props.x   ../Sibling.props.x   .../Up/Two.props.x
	One leading dot is the current container (0 levels up); each extra
	dot is one more level up. Forward slashes drill down after going up.
  - Absolute:  /root/Container/Component.props.x
	A leading slash starts at the top of the view hierarchy.
  - Expressions wrap either form in braces: {../Sibling.props.x}
  - Scripts navigate via self.getSibling('Name') / .getChild('Name').

Each parsed reference records the exact source text it came from
(``full_text``) so rewrites can use maximal-context string replacement:
replacing '{../data label.props.text}' can never corrupt the neighbouring
'{../data label 2.props.text}' or the display literal 'data label: ' the
way a bare-name substring replace does (issue #115).
"""

import io
import re
import tokenize
from dataclasses import dataclass, field
from typing import List, Optional

# Property-access suffixes that terminate the component portion of a path.
PROPERTY_SUFFIXES = ('.props.', '.position.', '.meta.', '.custom.')

# Flattened-JSON key suffixes whose values hold Jython script bodies.
SCRIPT_KEY_SUFFIXES = ('.script', '.code')

# Component-navigation methods whose string argument names a component.
NAVIGATION_METHODS = ('getSibling', 'getChild')

# {./path}, {../path}, {/root/path} - single or Gson-doubled braces.
_EXPRESSION_RE = re.compile(r'\{{1,2}(\.+/|/)([^}]+?)\}{1,2}')

# Whole-value property binding path: ./path, ../path or /root/path.
_PROPERTY_PATH_RE = re.compile(r'^(\.+/|/)(.+)$', re.DOTALL)

# Regex fallback for scripts that cannot be tokenized, and free-text scan.
_SCRIPT_CALL_RE = re.compile(r'\.(getSibling|getChild)\(\s*([\'"])((?:[^\'"\\]|\\.)*?)\2\s*\)')

# Python embedded in expressions: runScript("...") may hide references.
_RUN_SCRIPT_RE = re.compile(r'\brunScript\s*\(')


@dataclass
class PathReference:
	"""A relative or absolute component path found in a string value."""
	full_text: str  # Exact source text incl. braces for expressions
	start: int  # Char offset of full_text within the value
	end: int
	form: str  # 'expression' or 'property_path'
	absolute: bool  # True for /root/... paths
	levels_up: Optional[int]  # dots-1 for relative paths, None if absolute
	segments: List[str] = field(default_factory=list)  # Component names, in path order

	def mentions(self, component_name: str) -> bool:
		"""Whether this reference's path names the given component."""
		return component_name in self.segments

	def renamed_text(self, old_name: str, new_name: str) -> str:
		"""
		Rebuild full_text with every path segment equal to old_name renamed.

		Only whole segments are replaced (delimited by '/', '{', '.', '}'),
		never arbitrary substrings, so 'data label' does not touch
		'data label 2'.
		"""
		pattern = re.compile(r'(?<=[/{])' + re.escape(old_name) + r'(?=[/.}]|$)')
		return pattern.sub(new_name, self.full_text)


@dataclass
class ScriptReference:
	"""A getSibling/getChild navigation call found in a script body."""
	full_text: str  # Exact source slice: method name through closing paren
	start: int
	end: int
	method: str  # 'getSibling' or 'getChild'
	component_name: str
	rewritable: bool = True  # False when found by fallback regex / free text

	def renamed_text(self, old_name: str, new_name: str) -> str:
		"""Rebuild full_text with the quoted argument renamed, preserving quotes."""
		if self.component_name != old_name:
			return self.full_text
		# Replace only the quoted argument, keeping the original quote style.
		return re.sub(
			r'([\'"])' + re.escape(old_name) + r'\1', lambda m: m.group(1) + new_name + m.group(1),
			self.full_text, count=1
		)


def is_script_key(flattened_key: str) -> bool:
	"""Whether a flattened-JSON key holds a Jython script body."""
	return flattened_key.endswith(SCRIPT_KEY_SUFFIXES)


def strip_property_suffix(ref_path: str) -> str:
	"""
	Return the component portion of a reference path.

	'Container/Child.props.text' -> 'Container/Child'
	'Component.position.display' -> 'Component'
	"""
	earliest = len(ref_path)
	for suffix in PROPERTY_SUFFIXES:
		idx = ref_path.find(suffix)
		if idx != -1:
			earliest = min(earliest, idx)
	return ref_path[:earliest]


def _build_path_reference(match: re.Match, form: str) -> PathReference:
	"""Construct a PathReference from a grammar match (leader, path)."""
	leader = match.group(1)  # '.../': dots+slash, or '/' for absolute
	ref_path = match.group(2)
	absolute = leader == '/'
	levels_up = None if absolute else len(leader) - 2  # dots minus one
	component_path = strip_property_suffix(ref_path)
	segments = [seg for seg in component_path.split('/') if seg]
	return PathReference(
		full_text=match.group(0), start=match.start(), end=match.end(), form=form, absolute=absolute,
		levels_up=levels_up, segments=segments
	)


def parse_expression_references(value: str) -> List[PathReference]:
	"""Find every brace-wrapped component path reference in a string."""
	return [_build_path_reference(m, 'expression') for m in _EXPRESSION_RE.finditer(value)]


def parse_property_path(value: str) -> Optional[PathReference]:
	"""Parse a whole-value property binding path, if the value is one."""
	match = _PROPERTY_PATH_RE.match(value)
	if not match:
		return None
	return _build_path_reference(match, 'property_path')


def _line_offsets(source: str) -> List[int]:
	"""Absolute char offset of the start of each 1-indexed line."""
	offsets = [0]
	for line in source.splitlines(keepends=True):
		offsets.append(offsets[-1] + len(line))
	return offsets


def _tokenize_script_references(script: str) -> List[ScriptReference]:
	"""
	Tokenize a Jython script body and extract navigation calls with exact
	source slices. Distinguishes real getSibling('X') calls from the same
	text inside comments or unrelated string literals (issue #115).

	Raises on untokenizable input; callers fall back to regex detection.
	"""
	offsets = _line_offsets(script)
	tokens = list(tokenize.generate_tokens(io.StringIO(script).readline))
	references = []

	for i, tok in enumerate(tokens):
		if tok.type != tokenize.NAME or tok.string not in NAVIGATION_METHODS:
			continue
		# Expect: NAME '(' STRING ')'
		if i + 3 >= len(tokens):
			continue
		open_paren, arg, close_paren = tokens[i + 1], tokens[i + 2], tokens[i + 3]
		if open_paren.string != '(' or arg.type != tokenize.STRING or close_paren.string != ')':
			continue

		quoted = arg.string
		if len(quoted) < 2 or quoted[0] not in '\'"' or quoted[0] != quoted[-1]:
			continue  # Prefixed/triple-quoted args are not component names

		start = offsets[tok.start[0] - 1] + tok.start[1]
		end = offsets[close_paren.end[0] - 1] + close_paren.end[1]
		references.append(
			ScriptReference(
				full_text=script[start:end], start=start, end=end, method=tok.string,
				component_name=quoted[1:-1], rewritable=True
			)
		)

	return references


def parse_script_references(script: str) -> List[ScriptReference]:
	"""
	Extract getSibling/getChild references from a script body.

	Prefers tokenization (comment/literal-aware, exact spans). Falls back to
	a regex scan for scripts that cannot be tokenized; fallback references
	are marked non-rewritable so the fixer treats them conservatively.
	"""
	try:
		return _tokenize_script_references(script)
	except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
		return [
			ScriptReference(
				full_text=m.group(0), start=m.start(), end=m.end(), method=m.group(1),
				component_name=m.group(3), rewritable=False
			) for m in _SCRIPT_CALL_RE.finditer(script)
		]


def free_text_mentions_component(value: str, component_name: str) -> bool:
	"""
	Conservative safety scan for strings that are neither scripts nor
	recognized path references: navigation-call patterns naming the
	component, or the name appearing inside a runScript(...) expression.
	Such hits make a rename unsafe but are never auto-rewritten.
	"""
	for match in _SCRIPT_CALL_RE.finditer(value):
		if match.group(3) == component_name:
			return True
	if _RUN_SCRIPT_RE.search(value) and component_name in value:
		return True
	return False
