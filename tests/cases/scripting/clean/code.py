"""
Clean project-library module fixture.

Exercises the Ignition scripting environment (the implicit ``system`` module, sibling
top-level packages, Jython 2.7 builtins) without triggering any pylint message under the
bundled library rcfile.
"""

TAG_PROVIDER = "[default]"


def read_setpoint(tag_path):
	"""Read a single tag value and return it, or None when the read failed."""
	results = system.tag.readBlocking([TAG_PROVIDER + tag_path])
	if results and results[0].quality.isGood():
		return results[0].value
	return None


def format_setpoint(value):
	"""Render a setpoint for display, tolerating Jython's long and unicode types."""
	if isinstance(value, (int, long)):
		return unicode(value)
	if isinstance(value, basestring):
		return unicode(value)
	return unicode(round(value, 2))


def read_setpoints(tag_paths):
	"""Read several tags in one call, indexing by position the Jython 2 way."""
	values = []
	for index in xrange(len(tag_paths)):
		values.append(read_setpoint(tag_paths[index]))
	return values
