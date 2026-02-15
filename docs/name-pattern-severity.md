# NamePatternRule Per-Node-Type Severity Configuration

## Overview

The `NamePatternRule` supports **per-node-type severity configuration**, allowing you to set different severity levels (error or warning) for each type of node (components, properties, message handlers, custom methods). This provides fine-grained control over naming enforcement.

## Why Per-Node-Type Severity?

Different elements in Ignition Perspective views have different criticality levels:

- **Components** (error): Highly visible in the view hierarchy and designer, should follow strict standards
- **Custom Methods** (error): Part of the code API, should follow consistent Python naming conventions
- **Properties** (warning): Internal data storage, more lenient enforcement allows flexibility
- **Message Handlers** (warning): Team-specific patterns, allow variation while providing guidance

## Configuration

### Recommended Configuration (Default)

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "component": {
          "convention": "PascalCase",
          "min_length": 3,
          "severity": "error"
        },
        "property": {
          "convention": "camelCase",
          "min_length": 2,
          "severity": "warning"
        },
        "message_handler": {
          "convention": "kebab-case",
          "min_length": 2,
          "severity": "warning"
        },
        "custom_method": {
          "convention": "snake_case",
          "min_length": 2,
          "severity": "error"
        }
      }
    }
  }
}
```

### Strict Mode (All Errors)

For maximum consistency enforcement:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "component": {
          "convention": "PascalCase",
          "severity": "error"
        },
        "property": {
          "convention": "camelCase",
          "severity": "error"
        },
        "message_handler": {
          "convention": "kebab-case",
          "severity": "error"
        },
        "custom_method": {
          "convention": "snake_case",
          "severity": "error"
        }
      }
    }
  }
}
```

### Lenient Mode (All Warnings)

For gradual adoption or legacy projects:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "component": {
          "convention": "PascalCase",
          "severity": "warning"
        },
        "property": {
          "convention": "camelCase",
          "severity": "warning"
        },
        "message_handler": {
          "convention": "kebab-case",
          "severity": "warning"
        },
        "custom_method": {
          "convention": "snake_case",
          "severity": "warning"
        }
      }
    }
  }
}
```

## Use Cases by Node Type

### Component Severity

**Recommended: Error**

- Components are highly visible in the designer and view hierarchy
- Component names are referenced in scripts, bindings, and other components
- Consistent naming makes views easier to navigate and understand
- Breaking component naming standards causes confusion across the team

**When to use Warning:**
- Legacy projects with established (but non-standard) naming conventions
- Transition period while team learns new standards
- Views with generated component names that cannot be easily changed

### Property Severity

**Recommended: Warning**

- Custom properties are internal data storage mechanisms
- Property naming has less visual impact than component naming
- Teams may have project-specific property naming conventions
- Flexibility allows for domain-specific naming patterns

**When to use Error:**
- Strict coding standards required by organization
- Properties are exposed via APIs or message handlers
- Team has fully adopted standard property naming conventions
- New projects starting with strict standards

### Message Handler Severity

**Recommended: Warning**

- Message handler names are team/project-specific
- Often follow business domain terminology rather than technical conventions
- Different teams may have different message naming patterns
- Flexibility allows for descriptive, domain-appropriate names

**When to use Error:**
- Organization has established enterprise-wide message naming standards
- Message handlers are part of a documented API
- Team wants strict enforcement for consistency
- Project is part of a larger ecosystem with naming requirements

### Custom Method Severity

**Recommended: Error**

- Custom methods are Python code and should follow Python naming conventions
- Method names are used in scripts throughout the project
- Consistent Python-style naming (snake_case) improves code readability
- Methods may be called from other views or shared across project

**When to use Warning:**
- Legacy views with existing method naming patterns
- Transition period for teams moving to standard Python conventions
- Methods are rarely used or called only locally

## Configuration Examples

### Example 1: Strict Components, Lenient Properties

Enforce component naming strictly while allowing flexibility in property names:

```json
{
  "node_type_specific_rules": {
    "component": {
      "convention": "PascalCase",
      "min_length": 3,
      "severity": "error"
    },
    "property": {
      "convention": "camelCase",
      "min_length": 2,
      "severity": "warning"
    }
  }
}
```

**Result:**
- ✅ Component `myButton` → ❌ **Error**: "Name 'myButton' doesn't follow PascalCase for component"
- ✅ Property `MyProperty` → ⚠️ **Warning**: "Name 'MyProperty' doesn't follow camelCase for property"

### Example 2: Domain-Specific Message Patterns

Allow domain-specific message naming while enforcing other standards:

```json
{
  "node_type_specific_rules": {
    "component": {
      "convention": "PascalCase",
      "severity": "error"
    },
    "message_handler": {
      "convention": "kebab-case",
      "severity": "warning"
    },
    "custom_method": {
      "convention": "snake_case",
      "severity": "error"
    }
  }
}
```

**Result:**
- Message handler `update_Status` → ⚠️ **Warning** (guidance provided, not blocking)
- Component `statusPanel` → ❌ **Error** (strict enforcement)
- Custom method `UpdateStatus` → ❌ **Error** (strict enforcement)

### Example 3: Legacy Migration

Start with all warnings, gradually move to errors:

**Phase 1 - Discovery:**
```json
{
  "node_type_specific_rules": {
    "component": {"convention": "PascalCase", "severity": "warning"},
    "property": {"convention": "camelCase", "severity": "warning"},
    "custom_method": {"convention": "snake_case", "severity": "warning"}
  }
}
```

**Phase 2 - Partial Enforcement:**
```json
{
  "node_type_specific_rules": {
    "component": {"convention": "PascalCase", "severity": "error"},  // Now enforced
    "property": {"convention": "camelCase", "severity": "warning"},
    "custom_method": {"convention": "snake_case", "severity": "warning"}
  }
}
```

**Phase 3 - Full Enforcement:**
```json
{
  "node_type_specific_rules": {
    "component": {"convention": "PascalCase", "severity": "error"},
    "property": {"convention": "camelCase", "severity": "error"},  // Now enforced
    "custom_method": {"convention": "snake_case", "severity": "error"}  // Now enforced
  }
}
```

## Testing

The rule includes comprehensive tests for per-node-type severity:

```bash
# Run all NamePatternRule tests
cd tests
python -m unittest unit.test_component_naming -v

# Run specific per-node-type severity tests
python -m unittest unit.test_component_naming.TestNamePatternPerNodeTypeSeverity -v

# Run individual test cases
python -m unittest unit.test_component_naming.TestNamePatternPerNodeTypeSeverity.test_component_error_severity -v
python -m unittest unit.test_component_naming.TestNamePatternPerNodeTypeSeverity.test_property_warning_severity -v
python -m unittest unit.test_component_naming.TestNamePatternPerNodeTypeSeverity.test_mixed_severity_per_node_type -v
```

## Output Examples

### Mixed Severity Output

When using mixed severity levels, violations are grouped appropriately:

```
❌ ERRORS (1 total):

  NamePatternRule:
    • root.myButton: Name 'myButton' doesn't follow PascalCase for component (suggestion: 'MyButton')

⚠️  WARNINGS (2 total):

  NamePatternRule:
    • custom.MyProperty: Name 'MyProperty' doesn't follow camelCase for property (suggestion: 'myProperty')
    • custom.update_handler: Name 'update_handler' doesn't follow kebab-case for message_handler (suggestion: 'update-handler')
```

## Pre-commit Integration

Example pre-commit configuration with per-node-type severity:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/your-org/ignition-lint
    rev: v1.0.0
    hooks:
      - id: ignition-lint
        args: ['--config=.ignition-lint.json', '--files']
```

With `.ignition-lint.json`:
```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "component": {
          "convention": "PascalCase",
          "severity": "error"
        },
        "property": {
          "convention": "camelCase",
          "severity": "warning"
        },
        "custom_method": {
          "convention": "snake_case",
          "severity": "error"
        }
      }
    }
  }
}
```

## Migration Strategy

### Step 1: Assess Current State

Run with all warnings to understand violations:

```bash
ignition-lint --config lenient-config.json --files "**/view.json" --verbose
```

### Step 2: Categorize Violations

Group violations by node type and prioritize:
1. **Critical**: Components and custom methods (high visibility, code impact)
2. **Medium**: Message handlers (team communication)
3. **Low**: Properties (internal data)

### Step 3: Incremental Enforcement

**Week 1-2**: Components to error
**Week 3-4**: Custom methods to error
**Week 5-6**: Message handlers to error (if needed)
**Week 7+**: Properties to error (if desired)

### Step 4: Monitor and Adjust

- Track violation trends over time
- Adjust severity based on team feedback
- Document exceptions in whitelist if needed

## Best Practices

1. **Start Conservative**: Begin with warnings to understand impact
2. **Enforce Incrementally**: Move one node type at a time from warning to error
3. **Communicate Changes**: Notify team before changing severity levels
4. **Document Rationale**: Explain why different node types have different severity
5. **Review Regularly**: Reassess severity configuration as team matures
6. **Use Whitelists**: For legacy views that cannot be fixed immediately
7. **CI/CD Integration**: Use error severity in CI pipelines, warnings in pre-commit

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [Rule Configuration](../rule_config.json) - Complete configuration reference
- [BadComponentReferenceRule Severity](bad-component-reference-severity.md) - Similar severity feature
- [Developer Guide](developer-guide-rule-creation.md) - Creating custom rules

## Advanced: Custom Patterns with Per-Type Severity

You can combine custom patterns with per-node-type severity:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "component": {
          "pattern": "^(btn|lbl|pnl)[A-Z][a-zA-Z0-9]*$",
          "pattern_description": "Prefixed PascalCase (btn, lbl, pnl)",
          "suggestion_convention": "PascalCase",
          "severity": "error"
        },
        "property": {
          "pattern": "^[a-z][a-zA-Z0-9]*$",
          "pattern_description": "camelCase without special characters",
          "suggestion_convention": "camelCase",
          "severity": "warning"
        }
      }
    }
  }
}
```

This allows maximum flexibility: different patterns AND different severity levels per node type!
