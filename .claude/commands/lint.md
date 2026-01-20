# Lint and Format

Run Ruff linter and formatter to check and fix code quality issues.

## Steps

1. Run linter check:
   ```bash
   ruff check src/
   ```

2. If there are fixable issues, fix them:
   ```bash
   ruff check src/ --fix
   ```

3. Check formatting:
   ```bash
   ruff format src/ --check
   ```

4. If formatting needed, apply it:
   ```bash
   ruff format src/
   ```

5. Report what was fixed and any remaining issues that need manual attention

## Ruff Rules Enabled

From `pyproject.toml`:

- **E** - pycodestyle errors
- **F** - Pyflakes (undefined names, unused imports)
- **I** - isort (import sorting)
- **UP** - pyupgrade (Python version upgrades)
- **B** - flake8-bugbear (common bugs)

## Common Issues

### Import Sorting (I001)
Imports should be grouped: stdlib, third-party, local

```python
# Correct
import logging
from datetime import datetime

import httpx
from fastapi import Depends

from myriad.core.database import get_db
```

### Unused Imports (F401)
Remove unused imports or mark intentional re-exports:

```python
from .models import Host  # Re-exported
from .models import Host as Host  # Explicit re-export
```

### Line Length
Max 100 characters. Break long lines appropriately.
