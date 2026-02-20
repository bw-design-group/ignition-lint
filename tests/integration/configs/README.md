# Integration Test Configurations

This directory contains configuration-driven integration tests for ign-lint rules. Each rule category has its own subdirectory with JSON configuration files that define comprehensive test scenarios.

## Directory Structure

```
tests/integration/configs/
├── naming/              # Tests for naming convention rules
├── performance/         # Tests for performance-related rules
├── structure/           # Tests for component structure rules
├── properties/          # Tests for property validation rules
├── scripts/             # Tests for script analysis rules
├── examples/            # Tests for example/demo rules
└── cross-rule/          # Tests that involve multiple rules
```

## Configuration File Format

Each JSON file defines test cases with the following structure:

```json
{
  "test_suite_name": "RuleName Tests",
  "description": "Description of what these tests cover",
  "test_cases": [
    {
      "name": "test_case_name",
      "description": "What this test case validates",
      "view_file": "TestCaseName/view.json",
      "rule_config": {
        "RuleName": {
          "enabled": true,
          "kwargs": {
            "parameter": "value"
          }
        }
      },
      "expectations": [
        {
          "rule_name": "RuleName",
          "error_count": 0,
          "warning_count": 1,
          "error_patterns": ["specific error text"],
          "warning_patterns": ["specific warning text"],
          "should_pass": true
        }
      ],
      "tags": ["category", "type", "scenario"]
    }
  ]
}
```

## Adding Tests for New Rules

When creating a new rule, developers should:

1. **Create a config file** in the appropriate category directory
2. **Follow the naming convention**: `{rule_name}_tests.json`
3. **Include multiple test cases** covering positive and negative scenarios
4. **Test edge cases** and error conditions
5. **Verify configurations** work correctly

## Running Configuration Tests

```bash
# Run all configuration tests
python test_runner.py --run-config

# Run tests for specific categories
python test_runner.py --run-config --tags naming
python test_runner.py --run-config --tags performance

# Run specific test case
python test_runner.py --run-config --tags specific_test_name
```

## Best Practices

- **One file per rule** (or closely related rules)
- **Multiple test cases per file** to cover different scenarios
- **Clear, descriptive names** for test cases
- **Comprehensive error/warning patterns** for validation
- **Use appropriate tags** for filtering and organization
- **Include both positive and negative test cases**
- **Test configuration edge cases** (missing parameters, invalid values)
