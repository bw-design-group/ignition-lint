# Whitelist Guide

**Version:** 1.0
**Last Updated:** 2026-02-13

## Overview

The whitelist feature allows you to exclude specific files from linting, even when those files are passed via pre-commit hooks or glob patterns. This is essential for managing technical debt at scale and preventing known issues in legacy code from blocking development workflows.

## Table of Contents

- [Quick Start](#quick-start)
- [Whitelist File Format](#whitelist-file-format)
- [Generating Whitelists](#generating-whitelists)
- [Using Whitelists](#using-whitelists)
- [Pre-commit Integration](#pre-commit-integration)
- [CLI Reference](#cli-reference)
- [Workflow Examples](#workflow-examples)
- [Performance](#performance)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Generate Whitelist from Legacy Files

```bash
# Navigate to repository root
cd /path/to/ignition-project

# Generate whitelist from legacy views
ignition-lint --generate-whitelist \
    "views/legacy/**/*.json" \
    "views/deprecated/**/*.json"

# Output: ✓ Whitelist generated: .whitelist.txt
#   Total files: 612
```

### 2. Use Whitelist During Linting

```bash
# Lint with whitelist (whitelisted files are skipped)
ignition-lint \
    --config rule_config.json \
    --whitelist .whitelist.txt \
    --files "**/view.json"
```

### 3. Integrate with Pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/your-org/ignition-lint
    rev: v1.0.0
    hooks:
      - id: ignition-lint
        args: ['--config=.ignition-lint-precommit.json', '--whitelist=.whitelist.txt', '--files']
```

## Whitelist File Format

### Specification

- **Filename:** `.whitelist.txt` (recommended default)
- **Location:** Repository root (or any location specified via `--whitelist`)
- **Format:** Plain text, one file path per line

### Format Rules

```text
# Comments start with # and are ignored
# Blank lines are also ignored

# One file path per line (relative to repository root)
views/legacy/Dashboard/view.json
views/deprecated/Widget/view.json

# Leading/trailing whitespace is trimmed
  views/prototype/Experimental/view.json

# No glob patterns in whitelist file (explicit paths only)
```

### Example Whitelist

```text
# Ignition-lint Whitelist
# Generated: 2026-02-13

# Legacy views - scheduled for refactor Q2 2026 (JIRA-1234)
views/legacy/OldDashboard/view.json
views/legacy/MainScreen/view.json
views/legacy/ControlPanel/view.json

# Deprecated views - being replaced
views/deprecated/TempView/view.json
views/deprecated/OldWidget/view.json

# Known issues - technical debt tracked in backlog
views/components/ComponentWithKnownIssues/view.json
```

## Generating Whitelists

### Basic Generation

```bash
# Generate from single pattern
ignition-lint --generate-whitelist "views/legacy/**/*.json"

# Generate from multiple patterns
ignition-lint --generate-whitelist \
    "views/legacy/**/*.json" \
    "views/deprecated/**/*.json" \
    "views/prototype/**/*.json"
```

### Custom Output File

```bash
# Specify custom output file
ignition-lint --generate-whitelist "views/legacy/**/*.json" \
    --whitelist-output custom-whitelist.txt
```

### Append Mode

```bash
# Append to existing whitelist (preserves existing entries)
ignition-lint --generate-whitelist "views/temp/**/*.json" \
    --append

# Append automatically deduplicates entries
```

### Dry Run

```bash
# Preview what would be added without writing file
ignition-lint --generate-whitelist "views/legacy/**/*.json" \
    --dry-run

# Output shows first 20 matches:
# 🔍 Would add 612 files to whitelist:
#   views/legacy/Dashboard/view.json
#   views/legacy/MainScreen/view.json
#   ...
```

## Using Whitelists

### CLI Usage

```bash
# Use default whitelist (.whitelist.txt)
ignition-lint --config rule_config.json \
    --whitelist .whitelist.txt \
    --files "**/view.json"

# Use custom whitelist
ignition-lint --config rule_config.json \
    --whitelist path/to/custom-whitelist.txt \
    --files "**/view.json"

# Disable whitelist (overrides --whitelist)
ignition-lint --config rule_config.json \
    --whitelist .whitelist.txt \
    --no-whitelist \
    --files "**/view.json"
```

### Default Behavior

**Important:** By default, ignition-lint does NOT use a whitelist unless you explicitly specify `--whitelist <path>`.

```bash
# No whitelist used (processes all files)
ignition-lint --config rule_config.json --files "**/view.json"

# Whitelist explicitly enabled
ignition-lint --config rule_config.json --whitelist .whitelist.txt --files "**/view.json"
```

### Verbose Mode

```bash
# Show detailed information about whitelisted files
ignition-lint --config rule_config.json \
    --whitelist .whitelist.txt \
    --files "**/view.json" \
    --verbose

# Output:
# 🔒 Loaded whitelist with 612 files
# 🔒 Ignored 8 whitelisted files
#   • views/legacy/Dashboard/view.json
#   • views/legacy/MainScreen/view.json
#   ... and 6 more files
```

## Pre-commit Integration

### Setup

**Step 1: Add to .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/your-org/ignition-lint
    rev: v1.0.0  # Use specific tag
    hooks:
      - id: ignition-lint
        # Add whitelist argument (opt-in)
        args: ['--config=.ignition-lint-precommit.json', '--whitelist=.whitelist.txt', '--files']
        # Exclude test files that intentionally contain violations
        exclude: '^tests/.*|.*test.*\.json$'
```

**Step 2: Create .whitelist.txt**

```bash
# Generate whitelist from legacy files
ignition-lint --generate-whitelist "views/legacy/**/*.json"

# Commit whitelist to repository
git add .whitelist.txt
git commit -m "Add whitelist for legacy views (technical debt)"
```

### Workflow

When you commit changes:

```bash
# Developer makes changes
vim views/components/NewDashboard/view.json
vim views/legacy/OldDashboard/view.json  # This file is whitelisted

# Stage changes
git add views/

# Commit (pre-commit runs automatically)
git commit -m "Update dashboards"

# Pre-commit behavior:
# 1. Passes NewDashboard/view.json to ignition-lint
# 2. Passes OldDashboard/view.json to ignition-lint
# 3. ignition-lint filters out OldDashboard (whitelisted)
# 4. Only NewDashboard is linted
# 5. Commit succeeds if NewDashboard passes linting
```

## CLI Reference

### Whitelist Arguments

```bash
--whitelist PATH              # Path to whitelist file (no default)
--no-whitelist                # Disable whitelist (overrides --whitelist)
--generate-whitelist PATTERN  # Generate whitelist from glob patterns
--whitelist-output PATH       # Output file for generated whitelist (default: .whitelist.txt)
--append                      # Append to existing whitelist (use with --generate-whitelist)
--dry-run                     # Preview without writing (use with --generate-whitelist)
```

### Examples

```bash
# Generate whitelist
ignition-lint --generate-whitelist "views/legacy/**/*.json"

# Use whitelist
ignition-lint --config rule_config.json --whitelist .whitelist.txt --files "**/view.json"

# Generate and append
ignition-lint --generate-whitelist "views/temp/**/*.json" --append

# Dry run
ignition-lint --generate-whitelist "views/legacy/**/*.json" --dry-run

# Override whitelist
ignition-lint --config rule_config.json --whitelist .whitelist.txt --no-whitelist --files "**/view.json"
```

## Workflow Examples

### Initial Setup for Large Project

```bash
# Step 1: Identify legacy files
find views/legacy -name "view.json" | wc -l
# Output: 612 files

# Step 2: Generate whitelist
ignition-lint --generate-whitelist "views/legacy/**/*.json"

# Step 3: Review generated whitelist
cat .whitelist.txt

# Step 4: Add comments to document why files are whitelisted
vim .whitelist.txt

# Step 5: Commit whitelist
git add .whitelist.txt
git commit -m "Add whitelist for legacy views (technical debt)"

# Step 6: Update pre-commit config
vim .pre-commit-config.yaml  # Add --whitelist=.whitelist.txt to args

# Step 7: Test linting with whitelist
ignition-lint --config rule_config.json --whitelist .whitelist.txt --files "**/view.json"
```

### Adding New Files to Whitelist

```bash
# Option 1: Add manually
echo "views/problematic/NewFile/view.json" >> .whitelist.txt

# Option 2: Generate and append
ignition-lint --generate-whitelist "views/problematic/**/*.json" --append

# Commit changes
git add .whitelist.txt
git commit -m "Add problematic views to whitelist (JIRA-5678)"
```

### Removing Files from Whitelist

```bash
# Edit whitelist file and delete lines
vim .whitelist.txt

# Or use sed/grep
grep -v "OldDashboard" .whitelist.txt > .whitelist.txt.tmp
mv .whitelist.txt.tmp .whitelist.txt

# Commit changes
git add .whitelist.txt
git commit -m "Remove OldDashboard from whitelist (fixed)"
```

### Regenerating Whitelist After Files Move

```bash
# Files have moved from views/legacy to views/archive
# Regenerate whitelist
ignition-lint --generate-whitelist "views/archive/**/*.json"

# Review changes
git diff .whitelist.txt

# Commit updated whitelist
git add .whitelist.txt
git commit -m "Update whitelist after moving legacy views"
```

## Performance

The whitelist feature is designed for performance at scale:

### Benchmarks

- **Load 600-file whitelist:** < 0.5ms
- **Filter 900 files:** < 1ms
- **Total overhead:** < 2ms (negligible)

### Scaling

- **Current:** 600 whitelisted files, 900 total files
- **Future:** Scales linearly with file count
- **Bottleneck:** Disk I/O for reading view.json files (not whitelist processing)

### Implementation Details

- **Set-based lookup:** O(1) per file
- **Path normalization:** Done once during load, not during filtering
- **Memory usage:** < 100KB for 600 files

## Best Practices

### Documentation

```text
# Always document WHY files are whitelisted
# Include JIRA tickets or dates for tracking

# ❌ Bad (no context)
views/legacy/Dashboard/view.json

# ✅ Good (clear context)
# Legacy views - scheduled for refactor Q2 2026 (JIRA-1234)
views/legacy/Dashboard/view.json
views/legacy/MainScreen/view.json
```

### Organization

```text
# Group related files with comments
# Use blank lines for readability

# Legacy views (pre-2024)
views/legacy/Dashboard/view.json
views/legacy/MainScreen/view.json

# Deprecated views (replaced in v2.0)
views/deprecated/OldWidget/view.json

# Third-party vendor code (cannot modify)
views/vendor/VendorDashboard/view.json
```

### Maintenance

```bash
# Regular review: Remove fixed files from whitelist
# Schedule quarterly review: grep for old JIRA tickets

# Check if whitelisted files still exist
while IFS= read -r file; do
  [[ "$file" =~ ^# ]] && continue  # Skip comments
  [[ -z "$file" ]] && continue     # Skip blank lines
  [[ ! -f "$file" ]] && echo "Missing: $file"
done < .whitelist.txt
```

### Version Control

```bash
# Commit whitelist to repository (don't ignore it)
# Track changes with clear commit messages

# ✅ Good commit messages
git commit -m "Add legacy views to whitelist (technical debt - JIRA-1234)"
git commit -m "Remove fixed views from whitelist"
git commit -m "Update whitelist after refactoring legacy code"

# ❌ Bad commit messages
git commit -m "Update whitelist"
git commit -m "WIP"
```

## Troubleshooting

### Whitelist Not Working

**Problem:** Files are still being linted despite being in whitelist

**Solution:**

```bash
# 1. Verify whitelist is being loaded
ignition-lint --config rule_config.json --whitelist .whitelist.txt --files "**/view.json" --verbose

# Should show: "🔒 Loaded whitelist with N files"

# 2. Check path format (should be relative to repo root)
cat .whitelist.txt
# Correct: views/legacy/Dashboard/view.json
# Wrong: /absolute/path/to/views/legacy/Dashboard/view.json

# 3. Test with single file
echo "views/legacy/Dashboard/view.json" > test_whitelist.txt
ignition-lint --config rule_config.json --whitelist test_whitelist.txt --files "views/legacy/Dashboard/view.json"
```

### Performance Issues

**Problem:** Linting is slow with large whitelist

**Solution:**

```bash
# 1. Check whitelist size
wc -l .whitelist.txt

# 2. Profile with timing output
ignition-lint --config rule_config.json --whitelist .whitelist.txt --files "**/view.json" --timing-output timing.txt

# Whitelist overhead should be < 2ms even for 1000+ files
```

### Pre-commit Not Using Whitelist

**Problem:** Pre-commit hook processes whitelisted files

**Solution:**

```yaml
# Verify .pre-commit-config.yaml includes --whitelist argument
repos:
  - repo: https://github.com/your-org/ignition-lint
    rev: v1.0.0
    hooks:
      - id: ignition-lint
        # IMPORTANT: Add whitelist argument explicitly
        args: ['--config=.ignition-lint-precommit.json', '--whitelist=.whitelist.txt', '--files']
```

### Whitelist File Not Found

**Problem:** Warning about missing whitelist file

**Solution:**

```bash
# 1. Create whitelist if it doesn't exist
ignition-lint --generate-whitelist "views/legacy/**/*.json"

# 2. Or specify correct path
ignition-lint --config rule_config.json --whitelist path/to/whitelist.txt --files "**/view.json"

# 3. Or disable whitelist if not needed
ignition-lint --config rule_config.json --no-whitelist --files "**/view.json"
```

## FAQ

**Q: Is whitelist mandatory?**
A: No, whitelist is completely optional. By default, ignition-lint processes all files unless you specify `--whitelist <path>`.

**Q: Can I use glob patterns in the whitelist file?**
A: No, the whitelist file only supports explicit file paths (one per line). Use `--generate-whitelist` with glob patterns to populate the whitelist.

**Q: Does whitelist work with pre-commit hooks?**
A: Yes, but you must explicitly add `--whitelist=.whitelist.txt` to the `args` list in your `.pre-commit-config.yaml`.

**Q: What's the performance impact of a large whitelist?**
A: Minimal. Loading and using a 600-file whitelist adds < 2ms overhead.

**Q: How do I temporarily disable the whitelist?**
A: Use the `--no-whitelist` flag, which overrides any `--whitelist` argument.

**Q: Should I commit the whitelist to git?**
A: Yes! The whitelist is project-specific configuration that should be version-controlled.

**Q: Can I have multiple whitelist files?**
A: Currently, only one whitelist file can be specified per invocation. You can combine multiple files manually or use `--append` to merge them.

## See Also

- [CLAUDE.md](../CLAUDE.md) - Development guide and commands
- [README.md](../README.md) - Project overview and quick start
- [.whitelist.txt.example](../.whitelist.txt.example) - Example whitelist file
