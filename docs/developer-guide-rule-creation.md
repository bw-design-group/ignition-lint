# Developer Guide: Creating Custom Linting Rules

> 📚 **Navigation:** [Documentation Index](README.md) | [Tutorial](tutorial-creating-your-first-rule.md) | [API Reference](api-reference-rule-registration.md) | [Troubleshooting](troubleshooting-rule-development.md)

This guide shows developers how to create and register custom linting rules for ign-lint using the extensible rule registration system.

> 💡 **First time creating rules?** Start with the [hands-on tutorial](tutorial-creating-your-first-rule.md) for step-by-step guidance.

## Quick Start

### 1. Create a Rule File

Create a new Python file in `src/ignition_lint/rules/` (e.g., `my_custom_rule.py`):

```python
from typing import Set
from .common import LintingRule
from .registry import register_rule
from ..model.node_types import ViewNode, NodeType

@register_rule
class MyCustomRule(LintingRule):
    """My custom linting rule description."""

    def __init__(self, target_node_types: Set[NodeType] = None):
        super().__init__(target_node_types or {NodeType.COMPONENT})

    @property
    def error_message(self) -> str:
        return "Description of what this rule checks"

    def visit_component(self, component: ViewNode):
        # Your rule logic here
        if some_condition:
            self.errors.append(f"{component.path}: Error message")
```

### 2. Use Your Rule

Add to your `rule_config.json`:

```json
{
  "MyCustomRule": {
    "enabled": true,
    "kwargs": {
      "your_parameter": "value"
    }
  }
}
```

### 3. Test Your Rule

```bash
poetry run python -m ignition_lint --config rule_config.json path/to/view.json
```

That's it! Your rule is automatically discovered and registered.

## Rule Development Concepts

### Node Types and Visitor Pattern

ign-lint uses the **visitor pattern** to process different types of nodes in Ignition view files:

- **`NodeType.COMPONENT`** - UI components (buttons, labels, containers, etc.)
- **`NodeType.EXPRESSION_BINDING`** - Expression-based bindings
- **`NodeType.PROPERTY_BINDING`** - Property-to-property bindings
- **`NodeType.TAG_BINDING`** - Tag-based bindings
- **`NodeType.MESSAGE_HANDLER`** - Message handler scripts
- **`NodeType.CUSTOM_METHOD`** - Custom component methods
- **`NodeType.TRANSFORM`** - Script transforms in bindings
- **`NodeType.EVENT_HANDLER`** - Event handler scripts
- **`NodeType.PROPERTY`** - Component properties

### Required Implementation

Every rule must:

1. **Inherit from `LintingRule`**
2. **Implement `error_message` property** - describes what the rule checks
3. **Call `super().__init__(target_node_types)`** - specify which node types to process

### Optional Implementation

Rules can optionally implement:

- **Visitor methods** - `visit_component()`, `visit_expression_binding()`, etc.
- **`post_process()`** - called after all nodes are processed for batch analysis
- **`preprocess_config()`** - customize configuration before instantiation

## Rule Registration Methods

### Method 1: Decorator Registration (Recommended)

```python
@register_rule
class MyRule(LintingRule):
    # Rule implementation
    pass
```

### Method 2: Manual Registration

```python
class MyRule(LintingRule):
    # Rule implementation
    pass

# Register manually
register_rule(MyRule, "CustomRuleName")
```

### Method 3: Automatic Discovery

Just place your rule file in `src/ignition_lint/rules/` and inherit from `LintingRule`. The system automatically discovers and registers all valid rules.

## Complete Examples

### Example 1: Simple Component Rule

```python
from typing import Set
from .common import LintingRule
from .registry import register_rule
from ..model.node_types import ViewNode, NodeType

@register_rule
class ComponentNameLengthRule(LintingRule):
    """Ensures component names meet minimum length requirements."""

    def __init__(self, min_length: int = 3, max_length: int = 50, target_node_types: Set[NodeType] = None):
        super().__init__(target_node_types or {NodeType.COMPONENT})
        self.min_length = min_length
        self.max_length = max_length

    @property
    def error_message(self) -> str:
        return f"Component names must be between {self.min_length} and {self.max_length} characters"

    def visit_component(self, component: ViewNode):
        name = component.path.split('.')[-1]

        if len(name) < self.min_length:
            self.errors.append(f"{component.path}: Name too short ({len(name)} < {self.min_length})")
        elif len(name) > self.max_length:
            self.errors.append(f"{component.path}: Name too long ({len(name)} > {self.max_length})")
```

### Example 2: Multi-Node Type Rule

```python
from .common import LintingRule
from .registry import register_rule
from ..model.node_types import ViewNode, NodeType, ALL_SCRIPTS

@register_rule
class ScriptComplexityRule(LintingRule):
    """Checks script complexity across all script types."""

    def __init__(self, max_lines: int = 50):
        super().__init__(ALL_SCRIPTS)  # Target all script types
        self.max_lines = max_lines
        self.script_count = 0

    @property
    def error_message(self) -> str:
        return f"Scripts should not exceed {self.max_lines} lines"

    def visit_message_handler(self, script: ViewNode):
        self._check_script_complexity(script)

    def visit_custom_method(self, script: ViewNode):
        self._check_script_complexity(script)

    def visit_transform(self, script: ViewNode):
        self._check_script_complexity(script)

    def visit_event_handler(self, script: ViewNode):
        self._check_script_complexity(script)

    def _check_script_complexity(self, script: ViewNode):
        self.script_count += 1
        if hasattr(script, 'script_content'):
            lines = script.script_content.count('\n') + 1
            if lines > self.max_lines:
                self.errors.append(
                    f"{script.path}: Script too long ({lines} lines > {self.max_lines})"
                )

    def post_process(self):
        """Called after processing all nodes."""
        print(f"Analyzed {self.script_count} scripts")
```

### Example 3: Configuration Preprocessing

```python
@register_rule
class AdvancedNamingRule(LintingRule):
    """Advanced naming rule with configuration preprocessing."""

    @classmethod
    def preprocess_config(cls, config):
        """Convert string configurations to proper types."""
        processed = config.copy()

        # Convert string node types to NodeType enums
        if 'target_node_types' in processed:
            node_types = processed['target_node_types']
            if isinstance(node_types, str):
                processed['target_node_types'] = [node_types]

        # Convert string patterns to compiled regex
        if 'forbidden_patterns' in processed:
            import re
            patterns = processed['forbidden_patterns']
            processed['compiled_patterns'] = [re.compile(p) for p in patterns]

        return processed

    def __init__(self, forbidden_patterns=None, **kwargs):
        super().__init__()
        self.compiled_patterns = kwargs.get('compiled_patterns', [])

    @property
    def error_message(self) -> str:
        return "Component names must not match forbidden patterns"

    def visit_component(self, component: ViewNode):
        name = component.path.split('.')[-1]
        for pattern in self.compiled_patterns:
            if pattern.search(name):
                self.errors.append(f"{component.path}: Name matches forbidden pattern")
```

## Configuration Examples

### Basic Configuration

```json
{
  "ExampleNameLengthRule": {
    "enabled": true,
    "kwargs": {
      "min_length": 5
    }
  }
}
```

### Advanced Configuration

```json
{
  "AdvancedNamingRule": {
    "enabled": true,
    "kwargs": {
      "target_node_types": ["component", "property"],
      "forbidden_patterns": ["^temp", "test$", "debug"],
      "case_sensitive": false
    }
  }
}
```

## Testing Your Rules

### Unit Testing

Create test files in `tests/unit/test_your_rule.py`:

```python
import unittest
from pathlib import Path
from tests.fixtures.base_test import BaseRuleTest
from tests.fixtures.test_helpers import get_test_config

class TestYourRule(BaseRuleTest):
    def setUp(self):
        super().setUp()
        self.rule_config = get_test_config("YourRule", param1="value1")

    def test_rule_passes_valid_case(self):
        view_file = self.test_cases_dir / "ValidCase" / "view.json"
        self.assert_rule_passes(view_file, self.rule_config, "YourRule")

    def test_rule_fails_invalid_case(self):
        view_file = self.test_cases_dir / "InvalidCase" / "view.json"
        self.assert_rule_fails(view_file, self.rule_config, "YourRule")
```

### Integration Testing

Test your rule with real view files:

```bash
# Create test view files in tests/cases/
mkdir tests/cases/MyTestCase

# Test your rule
poetry run python -m ignition_lint --config your_config.json tests/cases/MyTestCase/view.json
```

## Best Practices

### 1. Rule Design

- **Single Responsibility**: Each rule should check one specific thing
- **Clear Error Messages**: Include the problem, location, and suggestion for fix
- **Configurable**: Allow users to customize rule behavior through parameters
- **Performance**: Minimize expensive operations in visitor methods

### 2. Error Messages

Good error messages include:
- **Location**: Full path to the problematic node
- **Problem**: What's wrong
- **Context**: Current value vs expected
- **Suggestion**: How to fix it

```python
# Good
self.errors.append(f"{component.path}: Name 'myButton' should use PascalCase (suggestion: 'MyButton')")

# Bad
self.errors.append("Invalid name")
```

### 3. Configuration

- Use `preprocess_config()` to validate and transform configuration
- Provide sensible defaults
- Support both simple and advanced configuration styles

### 4. Node Type Selection

Choose the right node types for your rule:

```python
# Only components
super().__init__({NodeType.COMPONENT})

# All bindings
from ..model.node_types import ALL_BINDINGS
super().__init__(ALL_BINDINGS)

# All scripts
from ..model.node_types import ALL_SCRIPTS
super().__init__(ALL_SCRIPTS)

# Multiple specific types
super().__init__({NodeType.COMPONENT, NodeType.PROPERTY})
```

## Advanced Topics

### Working with Node Hierarchy

```python
def visit_component(self, component: ViewNode):
    # Get component name
    name = component.path.split('.')[-1]

    # Get parent path
    parent_path = '.'.join(component.path.split('.')[:-1])

    # Check if it's a root component
    is_root = component.path.count('.') == 1
```

### Batch Processing

```python
def __init__(self):
    super().__init__({NodeType.COMPONENT})
    self.collected_data = []

def visit_component(self, component: ViewNode):
    # Collect data during traversal
    self.collected_data.append(component)

def post_process(self):
    # Analyze collected data after all nodes processed
    for component in self.collected_data:
        # Perform analysis that requires all components
        pass
```

### Cross-Node Analysis

```python
def __init__(self):
    super().__init__({NodeType.COMPONENT, NodeType.TAG_BINDING})
    self.components = {}
    self.bindings = {}

def visit_component(self, component: ViewNode):
    self.components[component.path] = component

def visit_tag_binding(self, binding: ViewNode):
    self.bindings[binding.path] = binding

def post_process(self):
    # Analyze relationships between components and their bindings
    for component_path, component in self.components.items():
        related_bindings = [b for b_path, b in self.bindings.items()
                          if b_path.startswith(component_path)]
        # Analysis here
```

## Rule Registry API

> 📖 **Complete API Reference:** See [API Reference: Rule Registration System](api-reference-rule-registration.md) for full documentation of all classes and methods.

### Programmatic Access

```python
from ignition_lint.rules import get_registry, get_all_rules

# Get registry instance
registry = get_registry()

# List all rules
all_rules = get_all_rules()
print("Available rules:", list(all_rules.keys()))

# Get rule metadata
metadata = registry.get_rule_metadata("MyRule")
print("Rule description:", metadata.get('docstring'))

# Check if rule exists
if registry.is_registered("MyRule"):
    rule_class = registry.get_rule("MyRule")
```

For complete API documentation including all parameters, return types, and advanced usage, see the [API Reference](api-reference-rule-registration.md).

### Dynamic Rule Loading

The system automatically discovers rules in the `rules` package, but you can also trigger discovery manually:

```python
from ignition_lint.rules.registry import discover_rules

# Discover rules in current package
discovered = discover_rules()
print(f"Discovered {len(discovered)} rules")
```

## Troubleshooting

> 🐛 **Need detailed help?** See the comprehensive [Troubleshooting Guide](troubleshooting-rule-development.md) for solutions to common issues.

### Rule Not Found

If your rule isn't being discovered:

1. **Check file location**: Must be in `src/ignition_lint/rules/`
2. **Check inheritance**: Must inherit from `LintingRule`
3. **Check abstract methods**: Must implement `error_message` property
4. **Check imports**: Verify all imports are correct

**→ More solutions:** [Troubleshooting Guide: Rule Registration Issues](troubleshooting-rule-development.md#rule-registration-issues)

### Validation Errors

Common validation errors:

- **Missing error_message**: Implement the required property
- **Invalid inheritance**: Must inherit from `LintingRule`
- **Instantiation failure**: Check `__init__` method and parameters
- **Name conflict**: Rule name already registered

### Import Errors

If you get import errors:

```python
# Use relative imports within the rules package
from .common import LintingRule  # ✓
from ignition_lint.rules.common import LintingRule  # ✗

# Use absolute imports for model types
from ..model.node_types import NodeType  # ✓
```

This rule registration system provides a powerful, extensible foundation for developers to contribute custom linting rules without modifying core framework code.
