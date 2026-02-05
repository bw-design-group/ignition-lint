---
description: Automatically add recent commits to CHANGELOG.md, avoiding duplicates
---

# Auto Changelog

Automatically review recent commits, summarize changes, and add them to CHANGELOG.md if they don't already exist.

## Usage

- `/auto-changelog` - Review all commits since the latest tag
- `/auto-changelog <n>` - Review only the last n commits (e.g., `/auto-changelog 5`)

## Instructions

You are a Senior Software Developer tasked with automatically updating CHANGELOG.md by reviewing recent commits, summarizing them, and adding only new entries.

### Step 1: Determine Commit Range

**If a number was provided:**
- Use the last n commits: `git log -<n> --pretty=format:"%H|%h|%s|%an" --reverse`

**If no number was provided:**
- Find the latest tag: `git tag --sort=-version:refname | head -1`
- If no tags exist, use all commits: `git log --pretty=format:"%H|%h|%s|%an" --reverse`
- If a tag exists, get commits since that tag: `git log <tag>..HEAD --pretty=format:"%H|%h|%s|%an" --reverse`

### Step 2: Read Existing CHANGELOG.md

**If CHANGELOG.md exists:**
- Read the entire file
- Extract all commit hashes that are already referenced (look for patterns like `[abc123]` in the content)
- Store these hashes to check for duplicates

**If CHANGELOG.md doesn't exist:**
- Prepare to create it with a standard header

### Step 3: Filter Out Existing Commits

For each commit found in Step 1:
- Check if the commit hash (short or full) is already mentioned in CHANGELOG.md
- If it exists, skip it
- If it doesn't exist, add it to the list of commits to process

### Step 4: Categorize New Commits

Analyze the remaining commit messages and categorize them into sections based on conventional commit patterns:

- **Added** - New features
  - Patterns: `add`, `feat:`, `feat(`, `feature:`, `new:`

- **Changed** - Changes to existing functionality
  - Patterns: `change`, `update`, `refactor`, `improve`, `enhance`, `chore:`

- **Deprecated** - Soon-to-be removed features
  - Patterns: `deprecate`, `deprecated:`

- **Removed** - Removed features
  - Patterns: `remove`, `delete`, `drop`

- **Fixed** - Bug fixes
  - Patterns: `fix:`, `fix(`, `bug:`, `bugfix:`, `hotfix:`

- **Security** - Security-related changes
  - Patterns: `security:`, `vulnerability:`, `sec:`

**Important categorization rules:**
- Check patterns case-insensitively
- If a commit doesn't match any pattern, categorize it as **Changed**
- Remove conventional commit prefixes when displaying (e.g., `feat: add login` → `Add login`)
- Capitalize the first letter of the summary

### Step 5: Generate Changelog Entry

**If there are new commits to add:**

Create or update the `[Unreleased]` section with:

```markdown
## [Unreleased]

### Added
- Summary of change [commit-hash]

### Changed
- Summary of change [commit-hash]

### Fixed
- Summary of change [commit-hash]
```

**Important:**
- Do NOT add a date to the `[Unreleased]` section (dates are only added when the release is made)
- Only include sections that have new commits
- Clean up commit messages (remove prefixes, improve readability)
- Include the short commit hash in square brackets
- If an `[Unreleased]` section already exists, merge the new commits into the appropriate subsections

### Step 6: Update CHANGELOG.md

**If CHANGELOG.md exists:**
- If an `[Unreleased]` section exists:
  - Merge new commits into the appropriate subsections (Added, Changed, Fixed, etc.)
  - Maintain chronological order within each subsection
  - Do NOT add or update any date (the `[Unreleased]` section remains dateless)
- If no `[Unreleased]` section exists:
  - Insert the new section after the header and before any existing version entries

**If CHANGELOG.md doesn't exist:**
- Create it with a standard header:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
...
```

### Step 7: Summary

After updating CHANGELOG.md:
- Report how many new commits were added to the changelog
- Report how many commits were skipped (already in changelog)
- Show the commit range reviewed
- List the categories that were updated (Added, Changed, Fixed, etc.)
- If no new commits were found, inform the user that the changelog is already up to date

**If no new commits were added:**
- Inform the user that all recent commits are already in the changelog
- Show the range that was checked
