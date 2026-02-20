# Tutorial: Creating Your First Custom Linting Rule

> 📚 **Navigation:** [Documentation Index](README.md) | [Developer Guide](developer-guide-rule-creation.md) | [API Reference](api-reference-rule-registration.md) | [Troubleshooting](troubleshooting-rule-development.md)

This step-by-step tutorial will guide you through creating your first custom linting rule for ign-lint. We'll build a rule that ensures component descriptions are not empty.

> 💡 **New to ign-lint?** This tutorial is perfect for beginners. For comprehensive reference material, see the [Developer Guide](developer-guide-rule-creation.md).

## What You'll Build

By the end of this tutorial, you'll have created a `ComponentDescriptionRule` that:
- Checks if components have meaningful descriptions
- Validates description length requirements
- Integrates with the configuration system
- Includes proper error messages and suggestions

## Prerequisites

- Python 3.9+ installed
- ign-lint development environment set up
- Basic understanding of Python classes and inheritance

## Step 1: Set Up Your Development Environment

First, ensure you have the development environment ready:

```bash
# Navigate to the ignition-lint directory
cd /path/to/ignition-lint

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell

# Run tests to ensure everything works
cd tests
python test_runner.py --run-unit
```

## Step 2: Understand the Problem

Let's say you want to enforce that all components in Ignition views have meaningful descriptions for maintainability. You want to check:

1. Components have a description property
2. Descriptions are not empty or just whitespace
3. Descriptions meet minimum length requirements
4. Descriptions don't contain placeholder text like "TODO" or "Description here"

## Step 3: Create Your Rule File

Create a new file called `component_description.py` in the `src/ignition_lint/rules/` directory:

```bash
touch src/ignition_lint/rules/component_description.py
```

## Step 4: Implement the Basic Rule Structure

Open `src/ignition_lint/rules/component_description.py` and start with the basic structure:

```python
"""
Component Description Rule

Ensures components have meaningful descriptions for maintainability.
"""

from typing import Set, List
from .common import LintingRule
from .registry import register_rule
from ..model.node_types import ViewNode, NodeType


@register_rule
class ComponentDescriptionRule(LintingRule):
    """
    Ensures components have meaningful descriptions.

    This rule checks that components have non-empty descriptions
    that meet minimum length requirements and don't contain
    placeholder text.
    """

    def __init__(self,
                 min_length: int = 10,
                 max_length: int = 200,
                 forbidden_phrases: List[str] = None,
                 target_node_types: Set[NodeType] = None):
        """
        Initialize the component description rule.

        Args:
            min_length: Minimum description length (default: 10)
            max_length: Maximum description length (default: 200)
            forbidden_phrases: List of forbidden placeholder phrases
            target_node_types: Node types to check (defaults to COMPONENT)
        """
        super().__init__(target_node_types or {NodeType.COMPONENT})
        self.min_length = min_length
        self.max_length = max_length
        self.forbidden_phrases = forbidden_phrases or [
            "todo", "description here", "add description",
            "placeholder", "tbd", "fixme"
        ]

    @property
    def error_message(self) -> str:
        """Required property describing what this rule checks."""
        return f"Components must have meaningful descriptions ({self.min_length}-{self.max_length} characters)"

    def visit_component(self, component: ViewNode):
        """Called for each component node."""
        # This is where we'll implement our logic
        pass
```

## Step 5: Implement the Core Logic

Now let's implement the actual checking logic in the `visit_component` method:

```python
def visit_component(self, component: ViewNode):
    """Called for each component node."""
    component_name = component.path.split('.')[-1]

    # Check if component has a description property
    description = self._get_component_description(component)

    if description is None:
        self.errors.append(
            f"{component.path}: Component '{component_name}' is missing a description property"
        )
        return

    # Check if description is empty or whitespace
    if not description or description.strip() == "":
        self.errors.append(
            f"{component.path}: Component '{component_name}' has an empty description"
        )
        return

    # Clean description for analysis
    clean_description = description.strip()

    # Check minimum length
    if len(clean_description) < self.min_length:
        self.errors.append(
            f"{component.path}: Component '{component_name}' description is too short "
            f"({len(clean_description)} < {self.min_length} characters)"
        )

    # Check maximum length
    if len(clean_description) > self.max_length:
        self.errors.append(
            f"{component.path}: Component '{component_name}' description is too long "
            f"({len(clean_description)} > {self.max_length} characters)"
        )

    # Check for forbidden phrases
    description_lower = clean_description.lower()
    for phrase in self.forbidden_phrases:
        if phrase.lower() in description_lower:
            self.errors.append(
                f"{component.path}: Component '{component_name}' description contains "
                f"placeholder text: '{phrase}'"
            )

def _get_component_description(self, component: ViewNode) -> str:
    """
    Extract the description from a component.

    In Ignition views, descriptions might be stored in different places:
    - component.props.meta.description
    - component.meta.description
    - component.description
    """
    # Try different possible locations for description
    if hasattr(component, 'props') and hasattr(component.props, 'meta'):
        if hasattr(component.props.meta, 'description'):
            return getattr(component.props.meta, 'description', None)

    if hasattr(component, 'meta') and hasattr(component.meta, 'description'):
        return getattr(component.meta, 'description', None)

    if hasattr(component, 'description'):
        return getattr(component, 'description', None)

    # Check in the raw flattened data
    description_paths = [
        f"{component.path}.props.meta.description",
        f"{component.path}.meta.description",
        f"{component.path}.description"
    ]

    for path in description_paths:
        if hasattr(component, 'flattened_data') and path in component.flattened_data:
            return component.flattened_data[path]

    return None
```

## Step 6: Add Configuration Preprocessing (Optional)

Let's add configuration preprocessing to handle string inputs more gracefully:

```python
@classmethod
def preprocess_config(cls, config):
    """Preprocess configuration before rule instantiation."""
    processed = config.copy()

    # Convert string numbers to integers
    if 'min_length' in processed and isinstance(processed['min_length'], str):
        processed['min_length'] = int(processed['min_length'])

    if 'max_length' in processed and isinstance(processed['max_length'], str):
        processed['max_length'] = int(processed['max_length'])

    # Handle forbidden_phrases as string or list
    if 'forbidden_phrases' in processed:
        phrases = processed['forbidden_phrases']
        if isinstance(phrases, str):
            # Split comma-separated string into list
            processed['forbidden_phrases'] = [p.strip() for p in phrases.split(',')]

    return processed
```

## Step 7: Create Configuration

Create a configuration file to test your rule. Create `test_description_rule.json`:

```json
{
  "ComponentDescriptionRule": {
    "enabled": true,
    "kwargs": {
      "min_length": 15,
      "max_length": 100,
      "forbidden_phrases": ["TODO", "fix this", "placeholder"]
    }
  }
}
```

## Step 8: Test Your Rule

Let's create a simple test to verify our rule works. Create `test_component_description.py` in the `tests/unit/` directory:

```python
import unittest
from pathlib import Path
from tests.fixtures.base_test import BaseRuleTest
from tests.fixtures.test_helpers import get_test_config, create_mock_view


class TestComponentDescriptionRule(BaseRuleTest):
    def setUp(self):
        super().setUp()
        self.rule_config = get_test_config("ComponentDescriptionRule",
                                         min_length=10,
                                         max_length=50)

    def test_missing_description(self):
        """Test that components without descriptions are flagged."""
        view_content = create_mock_view({
            "root": {
                "type": "@root",
                "children": [
                    {
                        "type": "ia.display.button",
                        "name": "TestButton"
                        # No description property
                    }
                ]
            }
        })

        errors = self.run_rule_on_view(view_content, self.rule_config, "ComponentDescriptionRule")
        self.assertEqual(len(errors), 1)
        self.assertIn("missing a description", errors[0])

    def test_empty_description(self):
        """Test that empty descriptions are flagged."""
        view_content = create_mock_view({
            "root": {
                "type": "@root",
                "children": [
                    {
                        "type": "ia.display.button",
                        "name": "TestButton",
                        "meta": {
                            "description": ""
                        }
                    }
                ]
            }
        })

        errors = self.run_rule_on_view(view_content, self.rule_config, "ComponentDescriptionRule")
        self.assertEqual(len(errors), 1)
        self.assertIn("empty description", errors[0])

    def test_short_description(self):
        """Test that short descriptions are flagged."""
        view_content = create_mock_view({
            "root": {
                "type": "@root",
                "children": [
                    {
                        "type": "ia.display.button",
                        "name": "TestButton",
                        "meta": {
                            "description": "Short"  # Only 5 characters
                        }
                    }
                ]
            }
        })

        errors = self.run_rule_on_view(view_content, self.rule_config, "ComponentDescriptionRule")
        self.assertEqual(len(errors), 1)
        self.assertIn("too short", errors[0])

    def test_valid_description(self):
        """Test that valid descriptions pass."""
        view_content = create_mock_view({
            "root": {
                "type": "@root",
                "children": [
                    {
                        "type": "ia.display.button",
                        "name": "TestButton",
                        "meta": {
                            "description": "This button triggers the main workflow process"
                        }
                    }
                ]
            }
        })

        errors = self.run_rule_on_view(view_content, self.rule_config, "ComponentDescriptionRule")
        self.assertEqual(len(errors), 0)

    def test_forbidden_phrases(self):
        """Test that forbidden phrases are detected."""
        rule_config = get_test_config("ComponentDescriptionRule",
                                    forbidden_phrases=["TODO", "placeholder"])

        view_content = create_mock_view({
            "root": {
                "type": "@root",
                "children": [
                    {
                        "type": "ia.display.button",
                        "name": "TestButton",
                        "meta": {
                            "description": "TODO: Add proper description here"
                        }
                    }
                ]
            }
        })

        errors = self.run_rule_on_view(view_content, rule_config, "ComponentDescriptionRule")
        self.assertEqual(len(errors), 1)
        self.assertIn("placeholder text", errors[0])


if __name__ == '__main__':
    unittest.main()
```

## Step 9: Run Your Tests

Run your tests to make sure everything works:

```bash
cd tests
python test_runner.py --test component_description
```

## Step 10: Test with Real View Files

Test your rule against actual view files:

```bash
poetry run python -m ignition_lint --config test_description_rule.json tests/cases/PascalCase/view.json
```

## Step 11: Register Your Rule (Automatic)

Your rule is automatically registered because of the `@register_rule` decorator! You can verify it's working by checking the available rules:

```python
from ignition_lint.rules import get_all_rules

rules = get_all_rules()
print("Available rules:", list(rules.keys()))
# Should include 'ComponentDescriptionRule'
```

## Step 12: Advanced Features (Optional)

### Add Rule Metadata

You can add additional metadata to help users understand your rule:

```python
@register_rule
class ComponentDescriptionRule(LintingRule):
    """
    Ensures components have meaningful descriptions.

    This rule helps maintain code quality by ensuring all components
    have descriptive documentation that helps with maintenance.

    Configuration Options:
    - min_length: Minimum description length (default: 10)
    - max_length: Maximum description length (default: 200)
    - forbidden_phrases: List of placeholder phrases to avoid
    """
    # ... rest of implementation
```

### Add Post-Processing Summary

```python
def post_process(self):
    """Called after processing all nodes."""
    if hasattr(self, '_components_checked'):
        print(f"ComponentDescriptionRule: Checked {self._components_checked} components")

def visit_component(self, component: ViewNode):
    # Add counter
    if not hasattr(self, '_components_checked'):
        self._components_checked = 0
    self._components_checked += 1

    # ... rest of visit logic
```

## Step 13: Documentation

Document your rule by adding it to the main documentation. Add an entry to `docs/developer-guide-rule-creation.md` in the examples section.

## Troubleshooting

> 🐛 **Having issues?** Check the comprehensive [Troubleshooting Guide](troubleshooting-rule-development.md) for detailed solutions.

### Rule Not Found
If your rule isn't being discovered:
1. Ensure the file is in `src/ignition_lint/rules/`
2. Verify the `@register_rule` decorator is used
3. Check that your class inherits from `LintingRule`
4. Verify all imports are correct

For more detailed troubleshooting, see [Troubleshooting Guide: Rule Registration Issues](troubleshooting-rule-development.md#rule-registration-issues).

### Import Errors
Use relative imports within the rules package:
```python
from .common import LintingRule  # ✓ Correct
from ignition_lint.rules.common import LintingRule  # ✗ Incorrect
```

### Configuration Issues
Test your configuration preprocessing:
```python
config = {"min_length": "15", "forbidden_phrases": "TODO,FIXME"}
processed = ComponentDescriptionRule.preprocess_config(config)
print(processed)  # Should convert strings to proper types
```

### Testing Issues
Make sure your test view structure matches what the framework expects:
- Use `create_mock_view()` helper for consistent structure
- Include proper component types and names
- Test edge cases (empty, missing, invalid values)

## Next Steps

Now that you've created your first rule, you can:

1. **Learn Advanced Patterns**: Check the [Developer Guide](developer-guide-rule-creation.md) for advanced features like cross-node analysis and batch processing
2. **Understand the API**: Review the [API Reference](api-reference-rule-registration.md) for programmatic access to the registry
3. **Create More Rules**: Apply this pattern to other linting needs using the concepts from this tutorial
4. **Contribute Back**: Share useful rules with the community
5. **Integration Testing**: Test with real Ignition project files

### Recommended Next Reading
- [Developer Guide: Advanced Topics](developer-guide-rule-creation.md#advanced-topics) - Learn about complex rule patterns
- [API Reference: RuleRegistry](api-reference-rule-registration.md#ruleregistry) - Programmatic rule management

## Complete Example

Here's the complete rule implementation:

```python
"""
Component Description Rule

Ensures components have meaningful descriptions for maintainability.
"""

from typing import Set, List
from .common import LintingRule
from .registry import register_rule
from ..model.node_types import ViewNode, NodeType


@register_rule
class ComponentDescriptionRule(LintingRule):
    """
    Ensures components have meaningful descriptions.

    This rule checks that components have non-empty descriptions
    that meet minimum length requirements and don't contain
    placeholder text.
    """

    @classmethod
    def preprocess_config(cls, config):
        """Preprocess configuration before rule instantiation."""
        processed = config.copy()

        if 'min_length' in processed and isinstance(processed['min_length'], str):
            processed['min_length'] = int(processed['min_length'])

        if 'max_length' in processed and isinstance(processed['max_length'], str):
            processed['max_length'] = int(processed['max_length'])

        if 'forbidden_phrases' in processed:
            phrases = processed['forbidden_phrases']
            if isinstance(phrases, str):
                processed['forbidden_phrases'] = [p.strip() for p in phrases.split(',')]

        return processed

    def __init__(self,
                 min_length: int = 10,
                 max_length: int = 200,
                 forbidden_phrases: List[str] = None,
                 target_node_types: Set[NodeType] = None):
        """Initialize the component description rule."""
        super().__init__(target_node_types or {NodeType.COMPONENT})
        self.min_length = min_length
        self.max_length = max_length
        self.forbidden_phrases = forbidden_phrases or [
            "todo", "description here", "add description",
            "placeholder", "tbd", "fixme"
        ]

    @property
    def error_message(self) -> str:
        """Required property describing what this rule checks."""
        return f"Components must have meaningful descriptions ({self.min_length}-{self.max_length} characters)"

    def visit_component(self, component: ViewNode):
        """Called for each component node."""
        component_name = component.path.split('.')[-1]
        description = self._get_component_description(component)

        if description is None:
            self.errors.append(
                f"{component.path}: Component '{component_name}' is missing a description property"
            )
            return

        if not description or description.strip() == "":
            self.errors.append(
                f"{component.path}: Component '{component_name}' has an empty description"
            )
            return

        clean_description = description.strip()

        if len(clean_description) < self.min_length:
            self.errors.append(
                f"{component.path}: Component '{component_name}' description is too short "
                f"({len(clean_description)} < {self.min_length} characters)"
            )

        if len(clean_description) > self.max_length:
            self.errors.append(
                f"{component.path}: Component '{component_name}' description is too long "
                f"({len(clean_description)} > {self.max_length} characters)"
            )

        description_lower = clean_description.lower()
        for phrase in self.forbidden_phrases:
            if phrase.lower() in description_lower:
                self.errors.append(
                    f"{component.path}: Component '{component_name}' description contains "
                    f"placeholder text: '{phrase}'"
                )

    def _get_component_description(self, component: ViewNode) -> str:
        """Extract the description from a component."""
        # Try different possible locations for description
        if hasattr(component, 'props') and hasattr(component.props, 'meta'):
            if hasattr(component.props.meta, 'description'):
                return getattr(component.props.meta, 'description', None)

        if hasattr(component, 'meta') and hasattr(component.meta, 'description'):
            return getattr(component.meta, 'description', None)

        if hasattr(component, 'description'):
            return getattr(component, 'description', None)

        return None
```

Congratulations! You've successfully created your first custom linting rule for ign-lint!
