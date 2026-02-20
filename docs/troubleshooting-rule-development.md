# Troubleshooting Guide: Rule Development

> 📚 **Navigation:** [Documentation Index](README.md) | [Tutorial](tutorial-creating-your-first-rule.md) | [Developer Guide](developer-guide-rule-creation.md) | [API Reference](api-reference-rule-registration.md)

This comprehensive troubleshooting guide covers common issues developers encounter when creating custom linting rules for ign-lint.

> 💡 **Quick solutions:** Use the table of contents to jump directly to your specific issue. For learning, see the [Tutorial](tutorial-creating-your-first-rule.md) or [Developer Guide](developer-guide-rule-creation.md).

## Table of Contents

- [Rule Registration Issues](#rule-registration-issues)
- [Import and Module Problems](#import-and-module-problems)
- [Configuration Issues](#configuration-issues)
- [Testing Problems](#testing-problems)
- [Runtime Errors](#runtime-errors)
- [Performance Issues](#performance-issues)
- [Integration Problems](#integration-problems)
- [Development Environment Issues](#development-environment-issues)

## Rule Registration Issues

### Problem: Rule Not Found or Not Registered

**Symptoms:**
- Rule doesn't appear when running `get_all_rules()`
- Configuration references to rule result in "unknown rule" errors
- Rule class exists but isn't being discovered

**Causes and Solutions:**

#### 1. File Location
**Cause:** Rule file not in correct directory
```
❌ Wrong: src/my_rules/custom_rule.py
✅ Correct: src/ignition_lint/rules/custom_rule.py
```

**Solution:**
```bash
# Move your rule file to the correct location
mv src/my_rules/custom_rule.py src/ignition_lint/rules/
```

#### 2. Missing Registration Decorator
**Cause:** Forgot `@register_rule` decorator
```python
❌ Wrong:
class MyRule(LintingRule):
    pass

✅ Correct:
@register_rule
class MyRule(LintingRule):
    pass
```

#### 3. Inheritance Issues
**Cause:** Rule doesn't inherit from `LintingRule`
```python
❌ Wrong:
class MyRule:
    pass

✅ Correct:
from .common import LintingRule

class MyRule(LintingRule):
    pass
```

#### 4. Import Errors in Rule File
**Cause:** Rule file has import errors preventing module loading
```python
❌ Wrong:
from ignition_lint.rules.common import LintingRule  # Absolute import

✅ Correct:
from .common import LintingRule  # Relative import
```

**Diagnostic Commands:**
```bash
# Check if rule is registered
python -c "from ignition_lint.rules import get_all_rules; print(list(get_all_rules().keys()))"

# Test rule discovery manually
python -c "from ignition_lint.rules.registry import discover_rules; print(discover_rules())"
```

### Problem: RuleValidationError During Registration

**Symptoms:**
```
RuleValidationError: Rule MyRule must implement error_message property
```

**Solutions:**

#### 1. Missing error_message Property
```python
❌ Wrong:
class MyRule(LintingRule):
    def __init__(self):
        super().__init__({NodeType.COMPONENT})

✅ Correct:
class MyRule(LintingRule):
    def __init__(self):
        super().__init__({NodeType.COMPONENT})

    @property
    def error_message(self) -> str:
        return "Description of what this rule checks"
```

#### 2. Instantiation Failure
**Cause:** Rule constructor fails with default parameters
```python
❌ Wrong:
def __init__(self, required_param):  # No default value
    super().__init__({NodeType.COMPONENT})

✅ Correct:
def __init__(self, required_param="default"):  # Provide default
    super().__init__({NodeType.COMPONENT})
```

#### 3. Name Conflicts
**Cause:** Two rules with the same name
```
RuleValidationError: Rule name MyRule is already registered
```

**Solution:**
```python
# Use custom name for registration
@register_rule
class MyCustomRule(LintingRule):
    pass

# Or register with explicit name
register_rule(MyRule, "UniqueRuleName")
```

## Import and Module Problems

### Problem: Import Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'ignition_lint.rules.common'
ImportError: attempted relative import with no known parent package
```

**Solutions:**

#### 1. Incorrect Import Style
```python
❌ Wrong - Absolute imports within rules package:
from ignition_lint.rules.common import LintingRule
from ignition_lint.model.node_types import NodeType

✅ Correct - Use relative imports:
from .common import LintingRule
from ..model.node_types import NodeType
```

#### 2. Missing __init__.py Files
**Cause:** Package structure incomplete
```bash
# Verify package structure
find src/ignition_lint -name "__init__.py"
# Should include:
# src/ignition_lint/__init__.py
# src/ignition_lint/rules/__init__.py
# src/ignition_lint/model/__init__.py
```

#### 3. Virtual Environment Issues
**Cause:** Not using correct Python environment
```bash
# Activate Poetry environment
poetry shell

# Or run commands via Poetry
poetry run python -m ignition_lint
```

### Problem: Circular Import Errors

**Symptoms:**
```
ImportError: cannot import name 'X' from partially initialized module
```

**Cause:** Rules importing each other or importing from registry during module load

**Solution:**
```python
❌ Wrong - Import at module level:
from .my_other_rule import MyOtherRule

class MyRule(LintingRule):
    def __init__(self):
        self.other_rule = MyOtherRule()

✅ Correct - Import within methods:
class MyRule(LintingRule):
    def __init__(self):
        super().__init__({NodeType.COMPONENT})

    def some_method(self):
        from .my_other_rule import MyOtherRule  # Import when needed
        other_rule = MyOtherRule()
```

## Configuration Issues

### Problem: Configuration Not Applied

**Symptoms:**
- Rule uses default values instead of configuration
- `preprocess_config` not being called
- Type conversion errors

**Solutions:**

#### 1. Configuration File Format
**Cause:** Incorrect JSON structure
```json
❌ Wrong:
{
  "MyRule": {
    "param1": "value1"  // Missing "enabled" and "kwargs"
  }
}

✅ Correct:
{
  "MyRule": {
    "enabled": true,
    "kwargs": {
      "param1": "value1"
    }
  }
}
```

#### 2. Parameter Type Mismatches
**Cause:** String values not converted to expected types
```python
# Add preprocessing to handle string inputs
@classmethod
def preprocess_config(cls, config):
    processed = config.copy()

    # Convert string numbers to integers
    if 'max_count' in processed and isinstance(processed['max_count'], str):
        try:
            processed['max_count'] = int(processed['max_count'])
        except ValueError:
            raise ValueError(f"max_count must be a number, got: {processed['max_count']}")

    return processed
```

#### 3. NodeType Conversion Issues
```python
# Handle string node types in preprocessing
@classmethod
def preprocess_config(cls, config):
    from ..model.node_types import NodeType

    processed = config.copy()

    if 'target_node_types' in processed:
        node_types = processed['target_node_types']
        if isinstance(node_types, str):
            # Single string to enum
            processed['target_node_types'] = {getattr(NodeType, node_types.upper())}
        elif isinstance(node_types, list):
            # List of strings to set of enums
            processed['target_node_types'] = {
                getattr(NodeType, nt.upper()) for nt in node_types
            }

    return processed
```

**Testing Configuration:**
```python
# Test your preprocessing
config = {"max_count": "10", "target_node_types": "component"}
processed = MyRule.preprocess_config(config)
print(processed)  # Should show converted types
```

## Testing Problems

### Problem: Tests Not Running

**Symptoms:**
- Test files not discovered by test runner
- Import errors in test files
- Tests pass but rule doesn't work in practice

**Solutions:**

#### 1. Test File Location and Naming
```bash
❌ Wrong: tests/my_rule_tests.py
✅ Correct: tests/unit/test_my_rule.py
```

#### 2. Test Base Class Usage
```python
❌ Wrong:
import unittest

class TestMyRule(unittest.TestCase):
    def test_something(self):
        # Manual setup required
        pass

✅ Correct:
from tests.fixtures.base_test import BaseRuleTest

class TestMyRule(BaseRuleTest):
    def setUp(self):
        super().setUp()  # Important!
        # Your setup here
```

#### 3. Mock View Creation
```python
from tests.fixtures.test_helpers import create_mock_view

# Create realistic test data
view_content = create_mock_view({
    "root": {
        "type": "@root",
        "children": [
            {
                "type": "ia.display.button",
                "name": "TestButton",
                "props": {
                    "text": "Click Me"
                }
            }
        ]
    }
})
```

### Problem: Test Data Issues

**Symptoms:**
- Tests pass but don't reflect real view structure
- Rule works in tests but fails on real files

**Solution - Use Real Test Cases:**
```bash
# Create test case directory
mkdir tests/cases/MyTestCase

# Copy real view.json file
cp /path/to/real/view.json tests/cases/MyTestCase/

# Test against real data
view_file = self.test_cases_dir / "MyTestCase" / "view.json"
errors = self.run_rule_on_file(view_file, config, "MyRule")
```

## Runtime Errors

### Problem: AttributeError in Rule Logic

**Symptoms:**
```
AttributeError: 'ViewNode' object has no attribute 'props'
```

**Causes and Solutions:**

#### 1. Node Structure Assumptions
```python
❌ Wrong - Assuming structure exists:
def visit_component(self, component: ViewNode):
    text = component.props.text  # May not exist

✅ Correct - Safe attribute access:
def visit_component(self, component: ViewNode):
    text = getattr(component, 'props', {}).get('text')
    # Or use hasattr check
    if hasattr(component, 'props') and hasattr(component.props, 'text'):
        text = component.props.text
```

#### 2. Accessing Flattened Data
```python
# Access the original flattened JSON data
def visit_component(self, component: ViewNode):
    # Check if property exists in flattened data
    prop_path = f"{component.path}.props.text"
    if hasattr(component, 'flattened_data') and prop_path in component.flattened_data:
        text = component.flattened_data[prop_path]
```

### Problem: Infinite Recursion or Performance Issues

**Symptoms:**
- Rule takes very long to run
- Stack overflow errors
- High memory usage

**Solutions:**

#### 1. Avoid Recursive Property Access
```python
❌ Wrong - May cause recursion:
def visit_component(self, component: ViewNode):
    for child in component.children:  # May trigger infinite loops
        self.visit_component(child)

✅ Correct - Let framework handle traversal:
def visit_component(self, component: ViewNode):
    # Only process current node
    # Framework handles child traversal automatically
    pass
```

#### 2. Limit Expensive Operations
```python
❌ Wrong - Expensive operation in visitor:
def visit_component(self, component: ViewNode):
    # Complex regex matching on every node
    import re
    pattern = re.compile(r"complex.*pattern.*here")
    if pattern.search(component.path):
        pass

✅ Correct - Compile once, use efficiently:
def __init__(self):
    super().__init__({NodeType.COMPONENT})
    self.pattern = re.compile(r"complex.*pattern.*here")

def visit_component(self, component: ViewNode):
    if self.pattern.search(component.path):
        pass
```

## Performance Issues

### Problem: Slow Rule Execution

**Symptoms:**
- Linting takes much longer with your rule enabled
- Memory usage increases significantly

**Solutions:**

#### 1. Optimize Data Structures
```python
❌ Wrong - Linear search in visitor:
def __init__(self):
    self.forbidden_names = ["name1", "name2", "name3"]  # List

def visit_component(self, component: ViewNode):
    name = component.path.split('.')[-1]
    if name in self.forbidden_names:  # O(n) search
        pass

✅ Correct - Use set for O(1) lookup:
def __init__(self):
    self.forbidden_names = {"name1", "name2", "name3"}  # Set

def visit_component(self, component: ViewNode):
    name = component.path.split('.')[-1]
    if name in self.forbidden_names:  # O(1) search
        pass
```

#### 2. Batch Processing
```python
# Use post_process for batch analysis
def __init__(self):
    super().__init__({NodeType.COMPONENT})
    self.components = []

def visit_component(self, component: ViewNode):
    # Just collect data during traversal
    self.components.append(component)

def post_process(self):
    # Perform expensive analysis after collection
    for component in self.components:
        # Complex analysis here
        pass
```

## Integration Problems

### Problem: Rule Works in Isolation But Not with Others

**Symptoms:**
- Rule passes individual tests but fails in integration
- Conflicts with other rules
- Unexpected interactions

**Solutions:**

#### 1. Namespace Your Rule's State
```python
❌ Wrong - Global state conflicts:
class MyRule(LintingRule):
    counter = 0  # Class variable shared across instances

✅ Correct - Instance state:
class MyRule(LintingRule):
    def __init__(self):
        super().__init__({NodeType.COMPONENT})
        self.counter = 0  # Instance variable
```

#### 2. Avoid Side Effects
```python
❌ Wrong - Modifying input data:
def visit_component(self, component: ViewNode):
    component.processed = True  # Don't modify the node

✅ Correct - Track state separately:
def __init__(self):
    super().__init__({NodeType.COMPONENT})
    self.processed_components = set()

def visit_component(self, component: ViewNode):
    self.processed_components.add(component.path)
```

## Development Environment Issues

### Problem: Poetry/Dependency Issues

**Symptoms:**
- Module import failures
- Version conflicts
- Missing dependencies

**Solutions:**

#### 1. Refresh Environment
```bash
# Clear poetry cache and reinstall
poetry env remove python
poetry install --with dev

# Verify installation
poetry run python -c "import ignition_lint; print('OK')"
```

#### 2. Check Python Version
```bash
# Ensure compatible Python version
poetry env info
python --version  # Should be 3.9+
```

### Problem: IDE/Editor Issues

**Symptoms:**
- Syntax highlighting not working
- Import suggestions incorrect
- Debugging not working

**Solutions:**

#### 1. Configure IDE Python Interpreter
```bash
# Get Poetry environment path
poetry env info --path

# Configure your IDE to use this Python interpreter
```

#### 2. Verify Project Structure
```bash
# Project should look like:
src/ignition_lint/
├── __init__.py
├── rules/
│   ├── __init__.py
│   ├── common.py
│   ├── registry.py
│   └── your_rule.py
tests/
├── unit/
│   └── test_your_rule.py
└── fixtures/
```

## Debugging Techniques

### Enable Debug Logging

```python
import logging

# Add to your rule for debugging
class MyRule(LintingRule):
    def __init__(self):
        super().__init__({NodeType.COMPONENT})
        self.logger = logging.getLogger(__name__)

    def visit_component(self, component: ViewNode):
        self.logger.debug(f"Processing component: {component.path}")
        # Your logic here
```

### Interactive Testing

```python
# Test rule interactively
from ignition_lint.rules import get_all_rules
from ignition_lint.linter import Linter
from pathlib import Path

# Get your rule
rule_class = get_all_rules()["MyRule"]

# Create test instance
config = {"MyRule": {"enabled": True, "kwargs": {}}}
linter = Linter(config)

# Test on file
results = linter.lint_file(Path("tests/cases/PascalCase/view.json"))
print(results)
```

### Validation Commands

```bash
# Test rule registration
poetry run python -c "from ignition_lint.rules.registry import discover_rules; print(discover_rules())"

# Test configuration loading
poetry run python -c "from ignition_lint.cli import load_config; print(load_config('your_config.json'))"

# Test rule instantiation
poetry run python -c "from ignition_lint.rules import get_all_rules; rule = get_all_rules()['MyRule']; instance = rule.create_from_config({}); print('OK')"
```

## Getting Help

If you're still experiencing issues:

1. **Check documentation**:
   - [Tutorial](tutorial-creating-your-first-rule.md) - Step-by-step guidance
   - [Developer Guide](developer-guide-rule-creation.md) - Comprehensive patterns and examples
   - [API Reference](api-reference-rule-registration.md) - Complete API specifications

2. **Check existing issues**: Look at the project's issue tracker

3. **Create minimal reproduction**: Simplify your rule to the minimum that reproduces the problem

4. **Include diagnostics**: Run the validation commands above and include output

5. **Provide context**: Include your Python version, operating system, and environment details

## Common Anti-Patterns

### Don't Do This

```python
# ❌ Modifying global state
GLOBAL_COUNTER = 0

class BadRule(LintingRule):
    def visit_component(self, component):
        global GLOBAL_COUNTER
        GLOBAL_COUNTER += 1

# ❌ Importing inside class definition
class BadRule(LintingRule):
    from ..model.node_types import NodeType  # Wrong place

# ❌ Complex logic in __init__
class BadRule(LintingRule):
    def __init__(self):
        super().__init__({NodeType.COMPONENT})
        # Don't do heavy processing here
        self.complex_data = self._load_huge_dataset()

# ❌ Raising exceptions for rule violations
def visit_component(self, component):
    if some_condition:
        raise ValueError("Component is invalid")  # Use self.errors instead
```

### Do This Instead

```python
# ✅ Instance state, proper imports, lightweight init, proper error handling
from typing import Set
from .common import LintingRule
from ..model.node_types import NodeType

class GoodRule(LintingRule):
    def __init__(self):
        super().__init__({NodeType.COMPONENT})
        self.component_count = 0  # Instance state

    def visit_component(self, component):
        self.component_count += 1
        if some_condition:
            self.errors.append(f"{component.path}: Error message")  # Proper error reporting
```

This troubleshooting guide should help you resolve most issues you'll encounter while developing custom linting rules for ign-lint.
