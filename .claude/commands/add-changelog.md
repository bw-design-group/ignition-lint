---
description: Generate or update CHANGELOG.md with commits since a tag
---

# Changelog Generator

Generate a CHANGELOG.md entry for commits since a specified tag version.

## Usage

- `/add-changelog` - Automatically finds the latest tag
- `/add-changelog <version>` - Uses the specified tag (e.g., `v1.2.3`)
- `/add-changelog head` or `/add-changelog latest` - Uses the latest tag

## Instructions

You are tasked with generating or updating a CHANGELOG.md file following the [Keep a Changelog](https://keepachangelog.com/) format.

### Step 1: Determine the Tag Version

**If a tag version was provided:**
- If the user provided `head` or `latest`, find the latest tag using: `git tag --sort=-version:refname | head -1` and increment the patch version by 1.
- Otherwise, use the provided tag version

**If no tag version was provided:**
- Find the latest tag using: `git tag --sort=-version:refname | head -1`
- If no tags exist, this will be version `v0.0.1` (use the initial commit: `git rev-list --max-parents=0 HEAD`)

### Step 2: Get Commits Since Tag

Run the following git command to get all commits since the tag:

```bash
git log <tag>..HEAD --pretty=format:"%h - %s (%an)" --reverse
```

If no tags exist (preparing for v0.0.1), get all commits from the beginning:

```bash
git log --pretty=format:"%h - %s (%an)" --reverse
```

### Step 3: Categorize Commits

Analyze the commit messages and categorize them into sections:

- **Added** - New features (commits with "add", "feat:", "feature:")
- **Changed** - Changes to existing functionality (commits with "change", "update", "refactor")
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features (commits with "remove", "delete")
- **Fixed** - Bug fixes (commits with "fix:", "bug:", "hotfix:")
- **Security** - Security-related changes (commits with "security:", "vulnerability:")

### Step 4: Generate Changelog Entry

Create a new section in CHANGELOG.md with the format:

```markdown
## [Unreleased] - YYYY-MM-DD

### Added
- Commit message [commit-hash]

### Changed
- Commit message [commit-hash]

### Fixed
- Commit message [commit-hash]
```

**Important:**
- Use today's date for the entry
- This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
- If no tags exist, the entry should indicate this is for `v0.0.1`
- Only include sections that have commits
- If CHANGELOG.md doesn't exist, create it with a header
- Place the new entry at the top of the file (after the header)
- Include the commit hash in square brackets for reference

### Step 5: Update CHANGELOG.md

If CHANGELOG.md exists:
- Insert the new section after the header and before any existing entries
- Preserve all existing content

If CHANGELOG.md doesn't exist:
- Create it with a standard header:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - YYYY-MM-DD
...
```

### Step 6: Summary

After updating CHANGELOG.md:
- Show a summary of how many commits were categorized
- Display the tag/commit range used (or note if this is the initial v0.0.1 version)
- If no tags existed, remind the user this changelog is for the upcoming v0.0.1 release
- Remind the user to review and edit the changelog as needed
