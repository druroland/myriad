# Commit Changes

Create a conventional commit for staged changes.

## Steps

1. Run `git status` to see what's staged and unstaged
2. Run `git diff --cached` to review staged changes
3. If nothing is staged, ask what to stage or suggest `git add -A`
4. Determine the appropriate commit type based on changes:
   - `feat:` - New feature or capability
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `refactor:` - Code restructuring without behavior change
   - `test:` - Adding or updating tests
   - `chore:` - Maintenance, dependencies, config
5. Write a concise commit message (imperative mood, lowercase)
6. Run verification before committing:
   ```bash
   ruff check src/ && ruff format src/ --check && pytest
   ```
7. If verification passes, create the commit
8. Show the commit with `git log -1`

## Commit Message Format

```
<type>: <description>

[optional body explaining why, not what]
```

## Examples

```
feat: add host filtering by status on hosts list page
fix: handle uppercase MAC addresses in OPNsense sync
refactor: extract DHCP lease parsing into helper functions
test: add integration tests for sync_service
```
