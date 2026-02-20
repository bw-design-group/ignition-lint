# Developer Testing Guide - Test Driven Development

This guide will walk you through setting up and using the testing infrastructure for the `ign-lint` project. **Start here before writing any code** - we practice Test Driven Development (TDD), which means tests come first!

## Table of Contents
1. [Quick Start](#quick-start)
2. [Understanding the Project](#understanding-the-project)
3. [Test Environment Setup](#test-environment-setup)
4. [Running Tests](#running-tests)
5. [Test Driven Development Workflow](#test-driven-development-workflow)
6. [Writing Your First Test](#writing-your-first-test)
7. [Test Organization](#test-organization)
8. [Advanced Testing Patterns](#advanced-testing-patterns)
9. [Debugging Tests](#debugging-tests)
10. [CI/CD Integration](#cicd-integration)

## Quick Start

**New to the project? Start here:**

```bash
# 1. Clone and setup project
git clone <repository-url>
cd ignition-lint

# 2. Install dependencies
poetry install

# 3. Set up test environment
cd tests
python test_runner.py --setup

# 4. Verify everything works
python test_runner.py --run-all

# 5. List available tests to understand what exists
python test_runner.py --list
```

If all tests pass ✅, you're ready to start developing!

## Understanding the Project

### What is ign-lint?

`ign-lint` is a linting tool for Ignition Perspective views (JSON files). It validates:
- **Component naming conventions** (PascalCase, camelCase, snake_case, etc.)
- **Polling intervals** in expression bindings
- **Script quality** using pylint
- **Custom rules** you can create

### Test-First Philosophy

We follow **Test Driven Development (TDD)**:
1. 🔴 **Write a failing test** that describes what you want to build
2. 🟢 **Write minimal code** to make the test pass
3. 🔵 **Refactor** the code while keeping tests green
4. **Repeat** for the next feature

## Test Environment Setup

### Directory Structure

After running `python test_runner.py --setup`, you'll have:

```
tests/
├── __init__.py                          # Python package marker
├── test_runner.py                       # Main test runner script
├── test_config_framework.py             # Configuration-driven tests
│
├── unit/                               # Unit tests (one file per rule)
│   ├── __init__.py
│   ├── test_component_naming.py        # Component naming rule tests
│   ├── test_polling_interval.py        # Polling interval rule tests
│   ├── test_script_linting.py          # Script linting rule tests
│   └── test_discovery.py               # Framework tests
│
├── integration/                        # Integration tests (multi-component)
│   ├── __init__.py
│   ├── test_config_framework.py        # Config framework tests
│   ├── test_cli_integration.py         # CLI tool tests
│   └── test_multi_rule.py              # Multiple rules working together
│
├── fixtures/                          # Shared test utilities
│   ├── __init__.py                     # Exports common fixtures
│   ├── base_test.py                    # Base test classes
│   ├── test_helpers.py                 # Helper functions
│   └── mock_data.py                    # Mock data generators
│
├── cases/                              # Test view.json files
│   ├── PascalCase/view.json            # Example with PascalCase naming
│   ├── camelCase/view.json             # Example with camelCase naming
│   ├── snake_case/view.json            # Example with snake_case naming
│   └── ExpressionBindings/view.json    # Example with expression bindings
│
├── configs/                           # JSON test configurations
│   ├── component_naming_tests.json     # Component naming test config
│   ├── polling_interval_tests.json     # Polling interval test config
│   └── script_linting_tests.json       # Script linting test config
│
└── results/                           # Test output and debug files
    └── debug/                          # Debug files from failed tests
```

### Prerequisites

1. **Python 3.8+** (we test on 3.8-3.11)
2. **Poetry** for dependency management
3. **Git** for version control

### Initial Setup

```bash
# Install project dependencies
poetry install

# Set up test environment (creates directories, sample configs, etc.)
cd tests
python test_runner.py --setup

# Verify setup worked
python test_runner.py --list
```

**Expected output after setup:**
```
Created directory: .../tests/unit
Created directory: .../tests/integration
Created directory: .../tests/fixtures
Created directory: .../tests/configs
Created directory: .../tests/results
Created: .../tests/__init__.py
Created: .../tests/unit/__init__.py
...
Test environment setup complete!
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
python test_runner.py --run-all

# Run only unit tests (fastest)
python test_runner.py --run-unit

# Run only integration tests
python test_runner.py --run-integration

# Run configuration-driven tests
python test_runner.py --run-config
```

### Targeted Test Execution

```bash
# Run specific test file
python test_runner.py --test component_naming

# Run tests matching a pattern
python test_runner.py --unit-pattern "test_component*"

# Run config tests with specific tags
python test_runner.py --run-config --tags component_naming positive

# List all available tests
python test_runner.py --list
```

### Verbosity Control

```bash
# Quiet output
python test_runner.py --run-unit --quiet

# Normal output (default)
python test_runner.py --run-unit

# Verbose output
python test_runner.py --run-unit --verbose

# Very verbose output
python test_runner.py --run-unit -vv
```

### Expected Test Output

**Successful run:**
```
============================================================
RUNNING UNIT TESTS
============================================================
test_pascal_case_passes_pascal_case_rule ... ok
test_camel_case_fails_pascal_case_rule ... ok
test_snake_case_passes_snake_case_rule ... ok
...
----------------------------------------------------------------------
Ran 15 tests in 0.234s

OK
============================================================
ALL TESTS PASSED ✅
```

**Failed run:**
```
============================================================
RUNNING UNIT TESTS
============================================================
test_new_feature ... FAIL
...
FAIL: test_new_feature (test_my_rule.TestMyRule)
AssertionError: Rule MyRule should pass but found errors: ['Component name doesn't follow convention']
...
============================================================
SOME TESTS FAILED ❌
```

## Test Driven Development Workflow

### The TDD Cycle

For every new feature, follow this cycle:

#### 1. 🔴 **Red Phase - Write a Failing Test**

Before writing any implementation code, write a test that describes what you want:

```python
# tests/unit/test_my_new_rule.py
from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, load_test_view

class TestMyNewRule(BaseRuleTest):
    def test_my_new_rule_validates_something(self):
        """Test that MyNewRule validates the thing we want."""
        # Arrange
        rule_config = get_test_config("MyNewRule", param="value")
        view_file = load_test_view(self.test_cases_dir, "ValidCase")

        # Act & Assert
        self.assert_rule_passes(view_file, rule_config, "MyNewRule")
```

**Run the test - it should fail:**
```bash
python test_runner.py --test my_new_rule
# Expected: ImportError or "Unknown rule: MyNewRule"
```

#### 2. 🟢 **Green Phase - Make It Pass**

Now implement the minimal code to make the test pass:

```python
# src/ignition_lint/rules/my_new_rule.py
from .common import LintingRule
from ..model.node_types import NodeType

class MyNewRule(LintingRule):
    def __init__(self, param="default"):
        super().__init__({NodeType.COMPONENT})
        self.param = param

    @property
    def error_message(self):
        return "My new rule validation failed"

    def visit_component(self, node):
        # Minimal implementation to pass the test
        pass  # For now, just don't add any errors
```

**Add to rules registry:**
```python
# src/ignition_lint/rules/__init__.py
from .my_new_rule import MyNewRule

RULES_MAP = {
    # ... existing rules ...
    "MyNewRule": MyNewRule,
}
```

**Run the test - it should pass:**
```bash
python test_runner.py --test my_new_rule
# Expected: OK - test passes
```

#### 3. 🔵 **Refactor Phase - Improve the Code**

Now improve the implementation while keeping tests green:

```python
# Enhance the rule implementation
def visit_component(self, node):
    if self.param == "strict" and len(node.name) < 3:
        self.errors.append(f"{node.path}: Component name too short")
```

**Run tests frequently during refactoring:**
```bash
python test_runner.py --test my_new_rule
# Should still pass after each change
```

#### 4. **Add More Test Cases**

Add edge cases, error cases, and different scenarios:

```python
def test_my_new_rule_fails_invalid_case(self):
    """Test that MyNewRule catches invalid cases."""
    rule_config = get_test_config("MyNewRule", param="strict")
    view_file = load_test_view(self.test_cases_dir, "InvalidCase")

    self.assert_rule_fails(view_file, rule_config, "MyNewRule", expected_error_count=1)

def test_my_new_rule_with_different_parameters(self):
    """Test MyNewRule with different parameter values."""
    for param_value in ["lenient", "strict", "custom"]:
        with self.subTest(param=param_value):
            rule_config = get_test_config("MyNewRule", param=param_value)
            # ... test logic
```

### Best Practices for TDD

**✅ Do:**
- Write the smallest possible test first
- Make tests descriptive and readable
- Test one thing at a time
- Run tests frequently (after every small change)
- Write tests for both success and failure cases
- Use meaningful test names that describe behavior

**❌ Don't:**
- Write implementation code before writing tests
- Write multiple features at once
- Make tests dependent on each other
- Skip the refactor phase
- Write tests that are too complex

## Writing Your First Test

### Scenario: Adding a New Rule

Let's walk through adding a rule that validates component descriptions.

#### Step 1: Create the Test File

```python
# tests/unit/test_component_description.py
"""
Unit tests for the ComponentDescriptionRule.
Tests validation of component description properties.
"""

from fixtures.base_test import BaseRuleTest
from fixtures.test_helpers import get_test_config, create_temp_view_file, create_mock_view

class TestComponentDescriptionRule(BaseRuleTest):
    """Test component description validation."""

    def test_component_with_description_passes(self):
        """Components with descriptions should pass validation."""
        # Create a mock view with components that have descriptions
        components = [
            {
                "name": "MyButton",
                "type": "ia.input.button",
                "props": {
                    "description": "This button does something useful"
                }
            }
        ]

        view_content = create_mock_view(components)
        view_file = create_temp_view_file(view_content)

        try:
            rule_config = get_test_config(
                "ComponentDescriptionRule",
                require_description=True,
                min_length=10
            )

            self.assert_rule_passes(view_file, rule_config, "ComponentDescriptionRule")
        finally:
            view_file.unlink()  # Clean up temp file

    def test_component_without_description_fails(self):
        """Components without descriptions should fail validation."""
        components = [
            {
                "name": "MyButton",
                "type": "ia.input.button",
                "props": {
                    # No description property
                }
            }
        ]

        view_content = create_mock_view(components)
        view_file = create_temp_view_file(view_content)

        try:
            rule_config = get_test_config(
                "ComponentDescriptionRule",
                require_description=True
            )

            self.assert_rule_fails(view_file, rule_config, "ComponentDescriptionRule")

            # Also test error message content
            errors = self.run_lint_on_file(view_file, rule_config)
            error_messages = errors.get("ComponentDescriptionRule", [])
            self.assertTrue(
                any("missing description" in error.lower() for error in error_messages),
                f"Expected error about missing description, got: {error_messages}"
            )
        finally:
            view_file.unlink()

    def test_description_too_short_fails(self):
        """Components with too-short descriptions should fail."""
        components = [
            {
                "name": "MyButton",
                "type": "ia.input.button",
                "props": {
                    "description": "Short"  # Too short
                }
            }
        ]

        view_content = create_mock_view(components)
        view_file = create_temp_view_file(view_content)

        try:
            rule_config = get_test_config(
                "ComponentDescriptionRule",
                require_description=True,
                min_length=10
            )

            self.assert_rule_fails(view_file, rule_config, "ComponentDescriptionRule")
        finally:
            view_file.unlink()
```

#### Step 2: Run the Test (It Should Fail)

```bash
python test_runner.py --test component_description
```

**Expected output:**
```
ImportError: cannot import name 'ComponentDescriptionRule' from 'ignition_lint.rules'
```

Perfect! The test fails because the rule doesn't exist yet.

#### Step 3: Implement the Rule

```python
# src/ignition_lint/rules/component_description.py
"""
Rule for validating component descriptions.
"""

from .common import LintingRule
from ..model.node_types import NodeType

class ComponentDescriptionRule(LintingRule):
    """Rule to validate component descriptions."""

    def __init__(self, require_description=True, min_length=0, max_length=None):
        """
        Initialize the component description rule.

        Args:
            require_description: Whether descriptions are required
            min_length: Minimum description length
            max_length: Maximum description length (None for no limit)
        """
        super().__init__({NodeType.COMPONENT})
        self.require_description = require_description
        self.min_length = min_length
        self.max_length = max_length

    @property
    def error_message(self):
        return "Component description validation failed"

    def visit_component(self, node):
        """Check component description."""
        # Skip root component
        if node.name == "root":
            return

        # Get description from component properties
        description = node.properties.get("description", "")

        if self.require_description and not description:
            self.errors.append(f"{node.path}: Component missing description")
            return

        if description:
            if len(description) < self.min_length:
                self.errors.append(
                    f"{node.path}: Description too short "
                    f"(minimum {self.min_length} characters)"
                )

            if self.max_length and len(description) > self.max_length:
                self.errors.append(
                    f"{node.path}: Description too long "
                    f"(maximum {self.max_length} characters)"
                )
```

#### Step 4: Register the Rule

```python
# src/ignition_lint/rules/__init__.py
from .component_description import ComponentDescriptionRule

RULES_MAP = {
    # ... existing rules ...
    "ComponentDescriptionRule": ComponentDescriptionRule,
}
```

#### Step 5: Run the Test Again

```bash
python test_runner.py --test component_description
```

**Expected output:**
```
test_component_with_description_passes ... ok
test_component_without_description_fails ... ok
test_description_too_short_fails ... ok
----------------------------------------------------------------------
Ran 3 tests in 0.045s

OK
```

Great! All tests pass. Now you have a working rule with comprehensive tests.

#### Step 6: Add Configuration-Driven Tests

Create a JSON configuration for more comprehensive testing:

```json
// tests/configs/component_description_tests.json
{
  "test_suite_name": "ComponentDescriptionRule Tests",
  "description": "Test cases for component description validation",
  "test_cases": [
    {
      "name": "require_description_positive",
      "description": "Components with descriptions should pass",
      "view_file": "PascalCase/view.json",
      "rule_config": {
        "ComponentDescriptionRule": {
          "enabled": true,
          "kwargs": {
            "require_description": false
          }
        }
      },
      "expectations": [
        {
          "rule_name": "ComponentDescriptionRule",
          "error_count": 0,
          "should_pass": true
        }
      ],
      "tags": ["component_description", "positive"]
    }
  ]
}
```

## Test Organization

### Unit Tests vs Integration Tests

**Unit Tests** (`tests/unit/`) test individual rules in isolation:
- One test file per rule
- Fast execution
- Easy to debug
- Mock external dependencies

**Integration Tests** (`tests/integration/`) test multiple components working together:
- CLI tool integration
- Multiple rules running together
- Configuration framework testing
- End-to-end scenarios

### Test Categories by Tags

Use tags in configuration-driven tests to organize by:

```json
{
  "tags": ["component_naming", "positive", "pascal_case"]
}
```

**Common tag patterns:**
- **Rule type**: `component_naming`, `polling_interval`, `script_linting`
- **Test type**: `positive`, `negative`, `edge_case`
- **Feature**: `pascal_case`, `camel_case`, `abbreviations`
- **Performance**: `large_files`, `performance`

### File Naming Conventions

```
tests/unit/test_[rule_name].py           # Unit tests for specific rule
tests/integration/test_[feature].py      # Integration tests for feature area
tests/fixtures/[utility_name].py        # Shared utilities
tests/cases/[scenario]/view.json         # Test view files
tests/configs/[rule]_tests.json         # Configuration-driven tests
```

## Advanced Testing Patterns

### Testing Rule Interactions

```python
# tests/integration/test_rule_interactions.py
class TestRuleInteractions(BaseIntegrationTest):
    def test_naming_and_polling_rules_together(self):
        """Test that naming and polling rules don't interfere."""
        rule_configs = {
            "NamePatternRule": {
                "enabled": True,
                "kwargs": {"convention": "PascalCase"}
            },
            "PollingIntervalRule": {
                "enabled": True,
                "kwargs": {"minimum_interval": 5000}
            }
        }

        view_file = load_test_view(self.test_cases_dir, "PascalCase")
        errors = self.run_multiple_rules(view_file, rule_configs)

        # Both rules should run without conflicts
        self.assertIsInstance(errors, dict)
```

### Parameterized Testing

```python
class TestComponentNamingConventions(BaseRuleTest):
    def test_all_naming_conventions(self):
        """Test all supported naming conventions."""
        conventions = [
            ("PascalCase", "PascalCase"),
            ("camelCase", "camelCase"),
            ("snake_case", "snake_case"),
            ("kebab-case", "kebab-case")
        ]

        for convention, test_case in conventions:
            with self.subTest(convention=convention):
                rule_config = get_test_config("NamePatternRule", convention=convention)
                view_file = load_test_view(self.test_cases_dir, test_case)
                self.assert_rule_passes(view_file, rule_config, "NamePatternRule")
```

### Testing Error Messages

```python
def test_error_message_content(self):
    """Test that error messages are helpful and specific."""
    rule_config = get_test_config("NamePatternRule", convention="PascalCase")
    view_file = load_test_view(self.test_cases_dir, "camelCase")

    errors = self.run_lint_on_file(view_file, rule_config)
    error_messages = errors.get("NamePatternRule", [])

    # Check error message contains useful information
    self.assertTrue(any("PascalCase" in error for error in error_messages))
    self.assertTrue(any("doesn't follow" in error for error in error_messages))
```

### Performance Testing

```python
def test_rule_performance(self):
    """Test that rule processes large files efficiently."""
    import time

    # Create a large mock view
    large_components = [
        {"name": f"Component{i}", "type": "ia.display.label"}
        for i in range(1000)
    ]

    view_content = create_mock_view(large_components)
    view_file = create_temp_view_file(view_content)

    try:
        rule_config = get_test_config("NamePatternRule", convention="PascalCase")

        start_time = time.time()
        errors = self.run_lint_on_file(view_file, rule_config)
        elapsed_time = time.time() - start_time

        # Should complete within reasonable time
        self.assertLess(elapsed_time, 5.0, "Rule should process 1000 components in under 5 seconds")

        # Should handle all components
        self.assertIsInstance(errors.get("NamePatternRule", []), list)
    finally:
        view_file.unlink()
```

## Debugging Tests

### Test Debugging Strategy

1. **Run individual tests:**
```bash
python test_runner.py --test my_failing_test --verbose
```

2. **Check debug files:**
```bash
ls tests/results/debug/
cat tests/results/debug/pylint_output.txt
```

3. **Add print statements:**
```python
def test_debugging_example(self):
    print(f"Testing with config: {rule_config}")
    errors = self.run_lint_on_file(view_file, rule_config)
    print(f"Found errors: {errors}")
    self.assertEqual(errors.get("MyRule", []), [])
```

4. **Use Python debugger:**
```python
def test_with_debugger(self):
    import pdb; pdb.set_trace()  # Breakpoint
    errors = self.run_lint_on_file(view_file, rule_config)
    # Now you can inspect variables
```

### Common Test Failures

**"View file not found":**
```bash
# Check if test case exists
ls tests/cases/
python test_runner.py --list
```

**"Unknown rule":**
```python
# Check rule is registered
# In src/ignition_lint/rules/__init__.py
RULES_MAP = {
    "MyRule": MyRule,  # Make sure this line exists
}
```

**"Test passes when it should fail":**
```python
# Add debug output to see what's happening
def test_should_fail(self):
    errors = self.run_lint_on_file(view_file, rule_config)
    print(f"DEBUG: Found errors: {errors}")  # Add this line
    self.assertGreater(len(errors.get("MyRule", [])), 0)
```

### Using IDE Debugging

**VS Code:**
1. Create `.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Run Single Test",
            "type": "python",
            "request": "launch",
            "program": "test_runner.py",
            "args": ["--test", "component_naming", "--verbose"],
            "cwd": "${workspaceFolder}/tests",
            "console": "integratedTerminal"
        }
    ]
}
```

2. Set breakpoints in your test files
3. Run "Run Single Test" from debug panel

## CI/CD Integration

### GitHub Actions

The project includes GitHub Actions workflow that:

1. **Tests multiple Python versions** (3.8-3.11)
2. **Runs all test categories**
3. **Checks code quality**
4. **Reports test coverage**

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: run-tests
        name: Run ign-lint tests
        entry: python tests/test_runner.py --run-unit --quiet
        language: system
        pass_filenames: false
        always_run: true
```

### Make Targets

Add to `Makefile`:

```makefile
.PHONY: test test-unit test-integration test-config

test: test-unit test-integration test-config

test-unit:
	cd tests && python test_runner.py --run-unit

test-integration:
	cd tests && python test_runner.py --run-integration

test-config:
	cd tests && python test_runner.py --run-config

test-watch:
	# Run tests whenever files change (requires entr)
	find src/ tests/ -name "*.py" | entr -c python tests/test_runner.py --run-unit
```

## Development Workflow Summary

**For every new feature:**

1. **📋 Plan** - Understand what you're building
2. **🔴 Red** - Write failing test first
3. **🟢 Green** - Write minimal code to pass
4. **🔵 Refactor** - Improve code quality
5. **🧪 Expand** - Add edge cases and error handling
6. **🚀 Integrate** - Test with other components
7. **📚 Document** - Update README and comments

**Daily development:**

```bash
# Start of day - make sure everything works
python test_runner.py --run-unit --quiet

# While developing - run specific tests frequently
python test_runner.py --test my_feature

# Before committing - run full test suite
python test_runner.py --run-all

# Before pushing - run integration tests
python test_runner.py --run-integration
```

This testing infrastructure ensures high code quality, catches regressions early, and makes the codebase maintainable as it grows. Happy testing! 🧪✨
