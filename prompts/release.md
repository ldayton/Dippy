# Release

User provides the version number.

Create a PR with branch name `release/v<version>` containing only these changes:

1. Update version in `pyproject.toml` and `src/dippy/__init__.py`
2. Run `uv sync -U` to update dependencies

No other changes—no refactors, no fixes, no documentation updates.

## Changelog

Generate release notes from commits since the last tag:
```
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

Focus on what matters to users:
- New features and capabilities
- Breaking changes or behavior changes
- Group all bug fixes as "Various bug fixes" (don't itemize)
- If Parable was updated, just say "Bump Parable version"
- Omit internal refactors, test changes, and CI updates

Put the changelog in the PR body. The workflow extracts it for the GitHub release.

Run `just check` before pushing. PR title: `Release v<version>`

## After merge

Tag and push:
```
git tag v<version> && git push --tags
```

The tag triggers a workflow that creates the GitHub release and updates the Homebrew tap.
