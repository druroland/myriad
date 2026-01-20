# Create Pull Request

Full workflow: lint, test, commit, push, and create a PR.

## Steps

1. **Check branch status**:
   ```bash
   git status
   git branch --show-current
   ```

2. **Run verification**:
   ```bash
   ruff check src/ && ruff format src/ --check && pytest
   ```
   If issues found, fix them before proceeding.

3. **Review changes**:
   ```bash
   git diff
   git diff --cached
   ```

4. **Stage and commit** (if not already committed):
   - Use conventional commit format
   - Ensure commit message describes the change

5. **Push to remote**:
   ```bash
   git push -u origin $(git branch --show-current)
   ```

6. **Create PR**:
   If using GitHub CLI:
   ```bash
   gh pr create --title "<type>: <description>" --body "## Summary

   <brief description of changes>

   ## Testing

   - [ ] All tests pass
   - [ ] Manual testing completed

   ## Checklist

   - [ ] Code follows project patterns
   - [ ] Tests added/updated
   - [ ] Documentation updated (if needed)"
   ```

## PR Title Format

Use conventional commit format for PR titles:

```
feat: add host status filtering
fix: correct MAC normalization for Cisco format
refactor: extract sync logic to dedicated service
```

## Branch Naming

Suggested format: `<type>/<short-description>`

```
feat/host-filtering
fix/mac-normalization
refactor/sync-service
```
