# BadComponentReferenceRule Severity Configuration

## Overview

The `BadComponentReferenceRule` now supports configurable severity levels, allowing users to choose whether violations should be treated as errors or warnings.

## Configuration

### Default (Error)

By default, the rule treats violations as errors, which is recommended for most projects to strictly enforce best practices:

```json
{
  "BadComponentReferenceRule": {
    "enabled": true,
    "kwargs": {
      "severity": "error"
    }
  }
}
```

### Warning Mode

For legacy views or gradual adoption, you can configure the rule to issue warnings instead:

```json
{
  "BadComponentReferenceRule": {
    "enabled": true,
    "kwargs": {
      "severity": "warning"
    }
  }
}
```

## Use Cases

### Error Mode (Recommended)
- **New projects**: Start with strict enforcement from the beginning
- **Refactored views**: Ensure no brittle dependencies are introduced
- **CI/CD pipelines**: Block commits/PRs that introduce bad patterns
- **Team standards**: Enforce architectural best practices

### Warning Mode
- **Legacy migration**: Gradually identify issues in existing views without blocking builds
- **Education**: Help developers learn about bad patterns without enforcement
- **Transition period**: During migration from legacy patterns to best practices
- **Technical debt tracking**: Identify issues to fix later without blocking current work

## Examples

### Detected Patterns

The rule detects these brittle component reference patterns:

```python
# ❌ Bad - Object traversal methods
sibling = self.getSibling("Button1")
parent = self.getParent()
child = self.view.getChild("Container")

# ❌ Bad - Property access
parent_component = self.parent
child_components = self.children

# ❌ Bad - Path traversal in expressions
{../Component.props.value}
{./Sibling.props.enabled}
```

### Recommended Alternatives

```python
# ✅ Good - Use view.custom properties
target_value = self.view.custom.targetValue
self.view.custom.currentState = "active"

# ✅ Good - Use message handling
system.perspective.sendMessage("update-component", {
    "componentId": "Button1",
    "value": 42
})

# ✅ Good - Direct property access
self.props.text = "Updated"

# ✅ Good - Session/page scope for coordination
self.session.custom.sharedValue = 100
```

## Additional Configuration Options

### Custom Forbidden Patterns

You can customize the list of forbidden patterns:

```json
{
  "BadComponentReferenceRule": {
    "enabled": true,
    "kwargs": {
      "severity": "error",
      "forbidden_patterns": [
        ".getSibling(",
        ".getParent(",
        ".getChild(",
        ".customBadMethod("
      ]
    }
  }
}
```

### Case Sensitivity

Control case-sensitive pattern matching:

```json
{
  "BadComponentReferenceRule": {
    "enabled": true,
    "kwargs": {
      "severity": "warning",
      "case_sensitive": false
    }
  }
}
```

## Testing

The rule includes comprehensive tests for severity configuration:

```bash
# Run all BadComponentReferenceRule tests
cd tests
python -m unittest unit.test_bad_component_reference -v

# Run specific severity tests
python -m unittest unit.test_bad_component_reference.TestBadComponentReferenceRule.test_severity_configuration_error -v
python -m unittest unit.test_bad_component_reference.TestBadComponentReferenceRule.test_severity_configuration_warning -v
```

## Pre-commit Integration

Example pre-commit configuration using warning mode:

```yaml
repos:
  - repo: https://github.com/your-org/ignition-lint
    rev: v1.0.0
    hooks:
      - id: ign-lint
        args: ['--config=.ign-lint.json', '--files']
```

With `.ign-lint.json`:
```json
{
  "BadComponentReferenceRule": {
    "enabled": true,
    "kwargs": {
      "severity": "warning"
    }
  }
}
```

## Migration Strategy

### Phase 1: Discovery (Warnings)
```json
{"severity": "warning"}
```
- Identify all existing violations
- Create remediation plan
- Track technical debt

### Phase 2: Remediation
- Fix violations in new/modified views
- Document approved patterns
- Train team on best practices

### Phase 3: Enforcement (Errors)
```json
{"severity": "error"}
```
- Enable strict mode for new views
- Block new violations in CI/CD
- Continue fixing legacy views

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [Rule Configuration](../rule_config.json) - Complete configuration reference
- [Developer Guide](developer-guide-rule-creation.md) - Creating custom rules
