"""
Common utilities for tag management.

This module now re-exports utilities from vault_manager.core for backward compatibility.
New code should import directly from vault_manager.core when possible.
"""

from pathlib import Path
from typing import List

# Re-export core utilities
from vault_manager.core import (
    get_vault_root,
    is_ignored_path,
    extract_tags_from_frontmatter,
    format_tag_name,
    is_valid_obsidian_tag,
    needs_quoting,
)


def is_ignored_path_for_add(file_path: Path, vault_root: Path) -> bool:
    """
    Check if a file path should be ignored for AI tag generation.

    This is a module-specific wrapper around core's is_ignored_path
    with additional ignore rules for the add command.

    Args:
        file_path: Path to check
        vault_root: Vault root directory

    Returns:
        True if path should be ignored, False otherwise

    Ignores:
        - .obsidian directory
        - .trash directory
        - Entire Excalidraw directory
    """
    # Use core function with additional Excalidraw ignore
    additional_ignores = {'Excalidraw'}
    return is_ignored_path(file_path, vault_root, additional_ignores)


__all__ = [
    'get_vault_root',
    'is_ignored_path',
    'is_ignored_path_for_add',
    'extract_tags_from_frontmatter',
    'format_tag_name',
    'is_valid_obsidian_tag',
    'needs_quoting',
]
