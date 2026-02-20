# API Reference: Rule Registration System

> 📚 **Navigation:** [Documentation Index](README.md) | [Tutorial](tutorial-creating-your-first-rule.md) | [Developer Guide](developer-guide-rule-creation.md) | [Troubleshooting](troubleshooting-rule-development.md)

This document provides complete API documentation for the ign-lint rule registration system implemented in Story 1.4.

> 💡 **Looking for examples?** Check the [Developer Guide](developer-guide-rule-creation.md) for practical usage examples and patterns.

## Core Classes

### `RuleRegistry`

Central registry for managing linting rules with dynamic discovery and validation.

```python
from ignition_lint.rules.registry import RuleRegistry
```

#### Constructor

```python
registry = RuleRegistry()
```

Creates a new rule registry instance. The global registry is automatically created and accessible via `get_registry()`.

#### Methods

##### `register_rule(rule_class, rule_name=None) -> str`

Register a rule class with the registry.

**Parameters:**
- `rule_class` (Type[LintingRule]): The rule class to register
- `rule_name` (str, optional): Custom name for the rule (defaults to class name)

**Returns:**
- `str`: The registered rule name

**Raises:**
- `RuleValidationError`: If the rule fails validation

**Example:**
```python
from ignition_lint.rules.registry import get_registry
from ignition_lint.rules.common import LintingRule

registry = get_registry()
rule_name = registry.register_rule(MyCustomRule, "CustomName")
```

##### `get_rule(rule_name) -> Optional[Type[LintingRule]]`

Retrieve a rule class by name.

**Parameters:**
- `rule_name` (str): Name of the rule to retrieve

**Returns:**
- `Optional[Type[LintingRule]]`: Rule class if found, None otherwise

**Example:**
```python
rule_class = registry.get_rule("NamePatternRule")
if rule_class:
    instance = rule_class.create_from_config({"convention": "PascalCase"})
```

##### `get_all_rules() -> Dict[str, Type[LintingRule]]`

Get all registered rules.

**Returns:**
- `Dict[str, Type[LintingRule]]`: Mapping of rule names to rule classes

**Example:**
```python
all_rules = registry.get_all_rules()
print("Available rules:", list(all_rules.keys()))
```

##### `list_rules() -> List[str]`

List all registered rule names.

**Returns:**
- `List[str]`: List of rule names

##### `get_rule_metadata(rule_name) -> Optional[Dict[str, Any]]`

Get metadata for a specific rule.

**Parameters:**
- `rule_name` (str): Name of the rule

**Returns:**
- `Optional[Dict[str, Any]]`: Rule metadata if found, None otherwise

**Metadata Fields:**
- `class_name` (str): Class name of the rule
- `module` (str): Module where the rule is defined
- `docstring` (str): Rule class docstring
- `source_file` (str): Path to source file
- `error_message` (str): Rule's error message

**Example:**
```python
metadata = registry.get_rule_metadata("NamePatternRule")
print("Description:", metadata.get('docstring'))
print("Error message:", metadata.get('error_message'))
```

##### `is_registered(rule_name) -> bool`

Check if a rule is registered.

**Parameters:**
- `rule_name` (str): Name of the rule to check

**Returns:**
- `bool`: True if rule is registered, False otherwise

##### `discover_and_register_rules(package_path=None) -> List[str]`

Discover and register rules from a package.

**Parameters:**
- `package_path` (Path, optional): Path to search for rules (defaults to rules package)

**Returns:**
- `List[str]`: List of discovered and registered rule names

**Example:**
```python
discovered = registry.discover_and_register_rules()
print(f"Discovered {len(discovered)} rules: {discovered}")
```

## Global Functions

### `register_rule(rule_class, rule_name=None) -> str`

Decorator and function for registering rules with the global registry.

**Parameters:**
- `rule_class` (Type[LintingRule]): The rule class to register
- `rule_name` (str, optional): Custom name for the rule

**Returns:**
- `str`: The registered rule name

**Usage as Decorator:**
```python
from ignition_lint.rules.registry import register_rule

@register_rule
class MyRule(LintingRule):
    # Rule implementation
    pass
```

**Usage as Function:**
```python
# Register with default name
register_rule(MyRule)

# Register with custom name
register_rule(MyRule, "CustomRuleName")
```

### `get_registry() -> RuleRegistry`

Get the global rule registry instance.

**Returns:**
- `RuleRegistry`: The global registry instance

**Example:**
```python
from ignition_lint.rules.registry import get_registry

registry = get_registry()
all_rules = registry.get_all_rules()
```

### `get_all_rules() -> Dict[str, Type[LintingRule]]`

Get all registered rules from the global registry.

**Returns:**
- `Dict[str, Type[LintingRule]]`: Mapping of rule names to rule classes

**Example:**
```python
from ignition_lint.rules import get_all_rules

rules = get_all_rules()
for name, rule_class in rules.items():
    print(f"Rule: {name}, Class: {rule_class.__name__}")
```

### `discover_rules() -> List[str]`

Discover and register all rules in the rules package.

**Returns:**
- `List[str]`: List of discovered and registered rule names

**Example:**
```python
from ignition_lint.rules.registry import discover_rules

discovered = discover_rules()
print(f"Auto-discovered {len(discovered)} rules")
```

## Exception Classes

### `RuleValidationError`

Exception raised when a rule fails validation during registration.

**Inheritance:** `Exception`

**Common Causes:**
- Rule doesn't inherit from `LintingRule`
- Missing required `error_message` property
- Rule name conflicts with existing rule
- Rule fails basic instantiation test

**Example:**
```python
try:
    registry.register_rule(InvalidRule)
except RuleValidationError as e:
    print(f"Rule validation failed: {e}")
```

## Rule Validation Process

The registry validates rules through several checks:

1. **Class Type Check**: Must be a class
2. **Inheritance Check**: Must inherit from `LintingRule`
3. **Base Class Check**: Cannot register `LintingRule` itself
4. **Abstract Property Check**: Must implement `error_message` property
5. **Instantiation Test**: Must be instantiable with `create_from_config({})`
6. **Name Conflict Check**: Rule name must be unique

## Rule Discovery Process

The automatic discovery system:

1. **Scans Package**: Walks through all `.py` files in `src/ignition_lint/rules/`
2. **Imports Modules**: Dynamically imports each Python module
3. **Finds Classes**: Uses reflection to find all classes in each module
4. **Filters Rules**: Identifies classes that inherit from `LintingRule`
5. **Validates Rules**: Runs validation on each potential rule
6. **Registers Rules**: Adds valid rules to the registry

**Excluded Files:**
- `__init__.py`
- `registry.py`
- `common.py`

## Integration with Configuration System

The registry integrates with the configuration system through the `create_from_config` method:

```python
# Configuration preprocessing flow
config = {"convention": "PascalCase", "target_node_types": "component"}
processed_config = rule_class.preprocess_config(config)
rule_instance = rule_class.create_from_config(processed_config)
```

## Thread Safety

The rule registry is **not thread-safe**. If you need to use it in a multi-threaded environment, you must provide your own synchronization.

## Performance Considerations

- **Rule Discovery**: Performed once during package import
- **Registry Lookups**: O(1) dictionary lookups
- **Metadata Extraction**: Cached after first extraction
- **Validation**: Performed only during registration

## Backward Compatibility

The system maintains backward compatibility with the legacy `RULES_MAP`:

```python
# Legacy access (still works)
from ignition_lint.rules import RULES_MAP
rule_class = RULES_MAP.get("NamePatternRule")

# Modern access (recommended)
from ignition_lint.rules import get_all_rules
rule_class = get_all_rules().get("NamePatternRule")
```

## Error Handling Best Practices

```python
from ignition_lint.rules.registry import get_registry, RuleValidationError

registry = get_registry()

# Safe rule retrieval
rule_class = registry.get_rule("MyRule")
if rule_class is None:
    print("Rule not found")
    return

# Safe rule registration
try:
    rule_name = registry.register_rule(MyCustomRule)
    print(f"Successfully registered: {rule_name}")
except RuleValidationError as e:
    print(f"Registration failed: {e}")
```

> 🐛 **Encountering errors?** See the [Troubleshooting Guide](troubleshooting-rule-development.md) for detailed solutions to common registration and runtime issues.

## Development Workflow

1. **Create Rule**: Implement rule class inheriting from `LintingRule`
2. **Add Registration**: Use `@register_rule` decorator or call `register_rule()`
3. **Automatic Discovery**: System automatically finds and registers your rule
4. **Configuration**: Add rule to configuration JSON
5. **Testing**: Use standard testing framework to validate rule behavior

## Migration from Legacy System

**Before (Legacy):**
```python
# Manual addition to RULES_MAP required
RULES_MAP = {
    "MyRule": MyRule,
    # ... other rules
}
```

**After (Dynamic Registration):**
```python
# Automatic registration with decorator
@register_rule
class MyRule(LintingRule):
    # Rule implementation
    pass
```

The new system eliminates the need to modify core framework files when adding new rules.
