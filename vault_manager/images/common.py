"""
Common utilities for image management.

This module now re-exports utilities from vault_manager.core for backward compatibility.
New code should import directly from vault_manager.core when possible.
"""

from pathlib import Path

# Re-export core utilities
from vault_manager.core import (
    get_vault_root,
    is_ignored_path,
)

# Module-specific constant - supported image extensions
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.ico'}


__all__ = [
    'get_vault_root',
    'is_ignored_path',
    'IMAGE_EXTENSIONS',
]
