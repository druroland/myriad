"""Shared Jinja2 templates utility."""

from functools import lru_cache

from fastapi.templating import Jinja2Templates


@lru_cache(maxsize=1)
def get_templates(templates_dir: str) -> Jinja2Templates:
    """Get cached Jinja2 templates instance.

    Uses LRU cache to avoid creating multiple instances for the same directory.
    """
    return Jinja2Templates(directory=templates_dir)
