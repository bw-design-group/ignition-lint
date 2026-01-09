# Create PR Template

Description: Create a PR with proper formatting and checks

Create a pull request following these steps:

1. Run pre-commit checks: `pre-commit run --all-files`
2. Review the changes from the original dev branch creation and create a summary
3. **IMPORTANT**: Create a PR for the current branch against the `dev` branch (NOT `main`). PRs should always target `dev` branch first.
4. Use the template structure at `.github/pull_request_template.md`
5. Update the changelog by leveraging the /auto-changelog <n> command, where <n> is the number of commits made in this branch.
6. Create the PR under the current user's credentials, not claude-code's credentials.
7. Include:
    - Summary section with high-level overview
    - Change Log with Client-Facing and Internal changes
    - Use keywords: **Added**, **Changed**, **Removed**, **Fixed**
    - Target Version if known, if unknown, get the latest tags from the repo and increment the release revision by 1 (1.4.1 becomes 1.4.2)
    - Related Issues with links
    - Screenshots are not necessary, so just add the text 'N/A'
8. Exclude 'Created by Claude' in the entirety of the pull request.

Prompt the user with any additional feedback you require.
