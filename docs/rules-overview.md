# Ignition Lint Rules Overview

This document provides a high-level overview of all available linting rules in the ignition-lint framework.

## Quick Reference

| Rule | Purpose | Impact |
|------|---------|---------|
| **NamePatternRule** | Enforces consistent naming conventions for components | Code consistency and readability |
| **BadComponentReferenceRule** | Prevents brittle component traversal patterns (`.getSibling()`, `.getParent()`) | Architecture stability and maintainability |
| **PollingIntervalRule** | Validates polling intervals to prevent performance issues | Gateway performance and resource usage |
| **UnusedCustomPropertiesRule** | Identifies unused custom properties and view parameters | Code cleanup and complexity reduction |
| **PylintScriptRule** | Runs Python linting on all scripts within views | Code quality and error prevention |

## Rule Categories

### 🏷️ Naming Rules

#### NamePatternRule
**Purpose**: Validates component, binding, and script naming conventions
**Category**: Naming / Code Style
**Severity**: Configurable (warning/error)

**What it checks:**
- Component names follow specified conventions (PascalCase, camelCase, snake_case, etc.)
- Name length constraints (min/max length)
- Forbidden name patterns
- Abbreviation handling and validation
- Node-specific naming patterns
- **Note**: CSS properties in `style` and `elementStyle` objects are automatically exempted from validation (they remain in kebab-case per CSS spec)

**Configuration options:**
- `convention`: Predefined patterns (PascalCase, camelCase, snake_case, kebab-case, UPPER_CASE)
- `custom_pattern`: Custom regex patterns
- `allow_numbers`: Allow numbers in names
- `min_length`/`max_length`: Length constraints
- `forbidden_names`: Blacklisted names
- `allowed_abbreviations`: Permitted abbreviations
- `node_types`: Apply different rules to different node types

---

### 🏗️ Structure Rules

#### BadComponentReferenceRule
**Purpose**: Detects brittle component traversal patterns
**Category**: Structure / Architecture
**Severity**: Error (default)

**What it checks:**
- Usage of `.getSibling()`, `.getParent()`, `.getChild()`
- Direct `.parent` and `.children` property access
- Object traversal patterns that create tight coupling

**Why it matters:**
These patterns create brittle dependencies on view structure. Changes to component hierarchy break functionality. Better alternatives:
- Use `view.custom` properties for component communication
- Implement message handling patterns
- Use session/page scope variables

**Configuration options:**
- `forbidden_patterns`: Custom patterns to detect
- `case_sensitive`: Pattern matching sensitivity
- `severity`: Configure as warning or error

---

### ⚡ Performance Rules

#### PollingIntervalRule
**Purpose**: Validates polling intervals in bindings to prevent performance issues
**Category**: Performance
**Severity**: Error (default)

**What it checks:**
- Tag bindings with polling intervals below minimum threshold
- Expression bindings using `now()` without proper rate limiting
- Property bindings with excessive update rates

**Performance impact:**
- Low polling intervals can cause high CPU usage
- Frequent updates can overwhelm the gateway
- UI lag and poor user experience

**Configuration options:**
- `minimum_interval`: Minimum allowed polling interval (default: 10000ms)
- `severity`: Configure warning level

---

### 🧹 Properties Rules

#### UnusedCustomPropertiesRule
**Purpose**: Identifies unused custom properties and view parameters
**Category**: Code Quality / Cleanup
**Severity**: Error (default)

**What it checks:**
- View-level custom properties (`custom.*`) that are never referenced
- View parameters (`params.*`) that are never used
- Component-level custom properties (`{component}.custom.*`) without references
- Distinguishes between persistent and non-persistent properties

**Detection scope:**
- ✅ Expression bindings (`{view.custom.prop}`, `{this.custom.prop}`)
- ✅ Property bindings and tag paths
- ✅ Script content (event handlers, transforms, custom methods)
- ✅ Message handler scripts
- ✅ Any string context in view definition

**Benefits:**
- Reduces view complexity
- Identifies dead code
- Improves maintainability
- Reduces memory footprint

---

### 📝 Script Quality Rules

#### PylintScriptRule
**Purpose**: Runs Python linting on all scripts in the view
**Category**: Code Quality / Python Standards
**Severity**: Error (default)

**What it checks:**
- Python syntax errors
- Undefined variables
- Unused imports
- Code style violations (configurable)
- Python best practices

**Script types analyzed:**
- Event handlers (onStartup, onShutdown, onClick, etc.)
- Message handlers
- Transform scripts in bindings
- Custom methods
- Expression binding scripts

**How it works:**
1. Collects all scripts from the view
2. Combines them into a temporary file with proper context
3. Runs pylint with Ignition-specific configurations
4. Maps results back to original script locations

**Configuration:**
- Uses project-specific pylint configuration
- Includes Ignition API stubs for proper validation
- Configurable enabled/disabled checks

---

## Example Rules (for Development/Testing)

### ExampleNameLengthRule
**Purpose**: Demonstrates rule development patterns
**Category**: Example
**Use**: Development reference only

### ExampleBindingCountRule
**Purpose**: Shows binding analysis techniques
**Category**: Example
**Use**: Development reference only

### ExampleMixedSeverityRule
**Purpose**: Demonstrates warning vs error severity handling
**Category**: Example
**Use**: Development reference only

---

## Rule Configuration

### Global Configuration
All rules support these common configuration options:

```json
{
  "RuleName": {
    "enabled": true,
    "kwargs": {
      "severity": "error"  // or "warning"
    }
  }
}
```

### Severity Levels
- **Error**: Fails CI/CD pipeline, blocks commits
- **Warning**: Reports issues but allows builds to proceed

### Node Type Targeting
Rules can target specific node types:
- `COMPONENT`: UI components
- `EXPRESSION_BINDING`: Expression-based bindings
- `PROPERTY_BINDING`: Property-to-property bindings
- `TAG_BINDING`: Tag-based bindings
- `MESSAGE_HANDLER_SCRIPT`: Message handler scripts
- `CUSTOM_METHOD_SCRIPT`: Custom component methods
- `TRANSFORM_SCRIPT`: Script transforms in bindings
- `EVENT_HANDLER_SCRIPT`: Event handler scripts

---

## Best Practices

### Rule Selection
1. **Start with structure rules**: BadComponentReferenceRule prevents architectural issues
2. **Add performance rules**: PollingIntervalRule prevents gateway overload
3. **Include naming conventions**: NamePatternRule improves code consistency
4. **Add code quality**: PylintScriptRule catches Python errors
5. **Clean up unused code**: UnusedCustomPropertiesRule reduces complexity

### Configuration Strategy
1. **Begin with warnings**: Start rules as warnings to assess impact
2. **Gradually promote to errors**: Once teams adapt, make critical rules errors
3. **Customize for your team**: Adjust naming conventions and thresholds
4. **Use in CI/CD**: Integrate with pre-commit hooks and build pipelines

### Development Workflow
1. **Test locally**: Run rules during development
2. **Pre-commit validation**: Catch issues before code review
3. **CI/CD integration**: Ensure quality gates in deployment pipeline
4. **Regular rule updates**: Review and adjust rules as standards evolve
