"""
Project-library module fixture with predictable pylint violations.

Expected under the bundled library rcfile:
  * W0611 unused-import       (line 11)
  * C0103 invalid-name        (line 13, module constant not UPPER_CASE)
  * E0602 undefined-variable  (line 19)
  * R1711 useless-return      (line 22)
  * W0612 unused-variable     (line 24)
"""
import json

badConstant = 42


def read_status(tag_path):
	"""Read a status tag; references a name that is never defined."""
	result = system.tag.readBlocking([tag_path])[0]
	return undefined_helper(result.value)


def unused_local():
	"""Assign a local that is never used."""
	scratch = badConstant * 2
	return None
