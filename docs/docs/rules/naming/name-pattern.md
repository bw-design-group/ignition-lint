---
title: NamePatternRule
sidebar_label: NamePatternRule
description: Enforces consistent naming conventions on components, properties, scripts, and the view and folder names themselves.
---

# NamePatternRule

Enforces consistent naming conventions across your views. By default it checks that components match **PascalCase**, but you can pick a different convention, mix conventions per node type, or supply a custom regex. It can also check the **view name and its parent folders** — the directories in the project's view tree — by targeting the `view` node type.

**Severity:** `warning` by default — naming violations are stylistic and rarely block runtime behavior. Promote to `"error"` once your team is aligned.

**Auto-fix:** Yes, for component names. The rule emits a rename operation that updates `meta.name` and (when references exist) every binding/script that mentions the old name.

## Basic config

The simplest setup — enforce PascalCase on component names, leave everything else alone:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "convention": "PascalCase"
    }
  }
}
```

That's it. Run the linter and any component named `myButton`, `data_table`, or `my-thing` is flagged with a suggested PascalCase replacement.

## Common configurations

### Enforce different conventions per node type

The most common real-world setup — components are PascalCase, custom methods are camelCase, properties are snake_case:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "component":     { "convention": "PascalCase" },
        "custom_method": { "convention": "snake_case" },
        "property":      { "convention": "camelCase" }
      }
    }
  }
}
```

When `node_type_specific_rules` is set and `target_node_types` is omitted, the rule auto-targets every node type listed in the dict.

### Enforce PascalCase view and folder names

Ignition stores each view as a directory named after the view, grouped into plain folders. The `view` node type exposes that location: the view name is the directory containing `view.json`, and the folders are every directory between the `views` root and the view. Target it to keep the view tree itself consistent — for example PascalCase everywhere, no Title Case:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "convention": "PascalCase",
      "target_node_types": ["component", "view"]
    }
  }
}
```

A view at `com.inductiveautomation.perspective/views/Title Case Folder/Title Case View/view.json` then reports:

```
NamePatternRule (warning):
  • Title Case Folder/Title Case View: Name 'Title Case View' doesn't follow PascalCase for view (suggestion: 'TitleCaseView')
  • Title Case Folder/Title Case View: Folder name 'Title Case Folder' doesn't follow PascalCase for view (suggestion: 'TitleCaseFolder')
```

Views and folders share one configuration. To give them a different convention from components, use a `"view"` entry in `node_type_specific_rules`. To allow more than one style on the view tree, use a `pattern` instead of a `convention`, for example PascalCase or Title Case:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "component": { "convention": "PascalCase" },
        "view": {
          "pattern": "^([A-Z][a-zA-Z0-9]*|[A-Z][a-z]*(\\s[A-Z][a-z]*)*)$",
          "pattern_description": "PascalCase or Title Case",
          "suggestion_convention": "PascalCase"
        }
      }
    }
  }
}
```

Not ready to enforce view names yet? Leave `view` out of `target_node_types` (or out of `node_type_specific_rules`) and only components are checked.

The views root is located automatically from the file path (`com.inductiveautomation.perspective/views`, or the first `views` directory). If no root is found the view is still named after its directory, but no folders are checked — so linting a lone `view.json` in a scratch directory never reports your working-directory names as folders.

### Allow PascalCase OR SCREAMING_SNAKE_CASE on components

For codebases that use SCREAMING_SNAKE_CASE for "constants" (config singletons, etc.) alongside PascalCase components:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "node_type_specific_rules": {
        "component": {
          "pattern": "^([A-Z][a-zA-Z0-9]*|[A-Z][A-Z0-9_]*)$",
          "pattern_description": "PascalCase or SCREAMING_SNAKE_CASE",
          "suggestion_convention": "PascalCase",
          "min_length": 3,
          "severity": "error"
        }
      }
    }
  }
}
```

`pattern_description` controls the error message; `suggestion_convention` controls how name suggestions are generated.

### Block specific names

Reject `temp`, `test`, `placeholder` regardless of casing:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "convention": "PascalCase",
      "forbidden_names": ["temp", "test", "placeholder"]
    }
  }
}
```

### Enforce a length range

Reject names shorter than 3 characters or longer than 40:

```json
{
  "NamePatternRule": {
    "enabled": true,
    "kwargs": {
      "convention": "PascalCase",
      "min_length": 3,
      "max_length": 40
    }
  }
}
```

## Examples

### Correct code

A view with PascalCase component names passes the basic config above:

```json
{
  "root": {
    "children": [
      { "meta": { "name": "DashboardHeader" }, "type": "ia.display.label" },
      { "meta": { "name": "RefreshButton" },   "type": "ia.input.button" },
      { "meta": { "name": "APIClient" },       "type": "ia.display.icon" }
    ],
    "meta": { "name": "root" }
  }
}
```

`APIClient` passes because the rule auto-detects `API` as a known abbreviation.

### Problematic code

A view with mixed casing fails:

```json
{
  "children": [
    { "meta": { "name": "GoodLabelName" } },
    { "meta": { "name": "badEmbeddedPotato_0" } },
    { "meta": { "name": "bad potato" } },
    { "meta": { "name": "anotherBadPotato" } }
  ]
}
```

Output:

```
NamePatternRule (warning):
  • root.children[1].meta.name: Name 'badEmbeddedPotato_0' doesn't follow PascalCase for component (suggestion: 'BadEmbeddedPotato0')
  • root.children[2].meta.name: Name 'bad potato' doesn't follow PascalCase for component (suggestion: 'BadPotato')
  • root.children[3].meta.name: Name 'anotherBadPotato' doesn't follow PascalCase for component (suggestion: 'AnotherBadPotato')
```

`GoodLabelName` is silently accepted.

## What `--fix` does

When run in fix mode, NamePatternRule rewrites component names to match the configured convention.

- **Safe fixes** (applied with `--fix`): when nothing references the component by name, the rule changes only `meta.name`. Single, isolated edit.
- **Unsafe fixes** (applied with `--fix-unsafe`): when other expressions, property bindings, or scripts reference the component name (e.g. `{Button1.props.text}`, `self.getSibling('Button1')`), the rule bundles the rename together with rewrites of every reference. The fix is marked unsafe because the references may have meaning the rule can't infer (e.g. they could be intentionally bound to a name that's about to be deleted). `--fix-unsafe` applies both safe and unsafe fixes, so use it on its own — you don't also pass `--fix`.

The rule fixes only **component** violations. Property, custom-method, and message-handler renames are reported but not auto-fixed — those renames are riskier and the rule defers to a human. View and folder names are never auto-fixed either: renaming them means moving directories and updating every reference to the view across the project.

## What gets skipped

A few things are deliberately exempt from validation, because the names are framework-defined or aren't really "names":

- The `root` component name (always)
- Event handler names like `onActionPerformed` (Ignition defines them)
- CSS properties: anything under `style`, `elementStyle`, `textStyle`, `instanceStyle` (kebab-case is part of the CSS spec)
- Position properties: `x`, `y`, `width`, `height`, etc. under `.position.`
- SVG path data: properties named `d` inside `props.elements`
- Properties whose name starts with `_` (treated as private)
- View folders when no views root can be found in the file path (the view name is still checked)

If your view has names that look like they should be flagged but aren't, check the [reference page's edge cases section](../../reference/naming/name-pattern.md#edge-cases--exemptions).

## Available conventions

| Key | Pattern | Example |
| --- | --- | --- |
| `PascalCase` | upper start, alphanumeric | `DashboardHeader` |
| `camelCase` | lower start, alphanumeric | `dashboardHeader` |
| `snake_case` | lower with underscores | `dashboard_header` |
| `kebab-case` | lower with hyphens | `dashboard-header` |
| `SCREAMING_SNAKE_CASE` | upper with underscores | `DASHBOARD_HEADER` |
| `Title Case` | space-separated words | `Dashboard Header` |
| `lower case` | lower with spaces | `dashboard header` |

For pattern regexes, the abbreviation set, and exact behavior of every option, see the [full reference](../../reference/naming/name-pattern.md#predefined-naming-conventions).

## See also

- [Full NamePatternRule reference](../../reference/naming/name-pattern.md) — every option, edge case, and violation message format
- [Configuration overview](../../getting-started/configuration.md) — the `rule_config.json` schema
