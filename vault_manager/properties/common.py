"""
Common utilities for property management.

This module now re-exports utilities from vault_manager.core for backward compatibility.
New code should import directly from vault_manager.core.frontmatter.FrontmatterManager when possible.
"""

from pathlib import Path

# Re-export core utilities
from vault_manager.core import (
    get_vault_root,
    is_ignored_path as core_is_ignored_path,
)
from vault_manager.core.frontmatter_manager import FrontmatterManager


def is_ignored_path(file_path: Path, vault_root: Path) -> bool:
    """
    Check if a file path should be ignored for property management.

    This is a module-specific wrapper around core's is_ignored_path
    with additional ignore rules for the properties module.

    Args:
        file_path: Path to check
        vault_root: Vault root directory

    Returns:
        True if path should be ignored, False otherwise

    Ignores:
        - .obsidian directory
        - .trash directory
        - .backup directory
        - Excalidraw directory
        - Calendar directory
    """
    # Use core function with additional Excalidraw and Calendar ignores
    additional_ignores = {'Excalidraw', 'Calendar'}
    return core_is_ignored_path(file_path, vault_root, additional_ignores)


# Backward compatibility wrapper
def extract_frontmatter(content: str):
    """Backward compatibility wrapper for FrontmatterManager.extract_frontmatter()."""
    return FrontmatterManager.extract_frontmatter(content)


__all__ = [
    'get_vault_root',
    'is_ignored_path',
    'extract_frontmatter',
]
