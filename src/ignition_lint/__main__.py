"""
Entry point for running ign-lint as a module: python -m ignition_lint
"""
# pylint: disable=wrong-import-position
import sys
from pathlib import Path

# Add the src directory to Python path
src_dir = Path(__file__).parent.parent
if str(src_dir) not in sys.path:
	sys.path.insert(0, str(src_dir))

# Now import from the package
from ignition_lint.cli import main

if __name__ == "__main__":
	main()
