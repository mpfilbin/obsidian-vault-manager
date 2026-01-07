"""
Common utilities for tag management.

This module now re-exports utilities from vault_manager.core for backward compatibility.
New code should import directly from vault_manager.core.frontmatter.FrontmatterManager when possible.
"""

from pathlib import Path
from typing import List

# Re-export core utilities
from vault_manager.core import (
    get_vault_root,
    is_ignored_path,
)
from vault_manager.core.frontmatter_manager import FrontmatterManager


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


# Backward compatibility wrappers
def extract_tags_from_frontmatter(content: str) -> List[str]:
    """Backward compatibility wrapper for FrontmatterManager.extract_tags_from_frontmatter()."""
    return FrontmatterManager.extract_tags_from_frontmatter(content)


def format_tag_name(tag: str) -> str:
    """Backward compatibility wrapper for FrontmatterManager.format_tag_name()."""
    return FrontmatterManager.format_tag_name(tag)


def is_valid_obsidian_tag(tag: str) -> bool:
    """Backward compatibility wrapper for FrontmatterManager.is_valid_obsidian_tag()."""
    return FrontmatterManager.is_valid_obsidian_tag(tag)


def needs_quoting(value: str) -> bool:
    """Backward compatibility wrapper for FrontmatterManager.needs_quoting()."""
    return FrontmatterManager.needs_quoting(value)


__all__ = [
    'get_vault_root',
    'is_ignored_path',
    'is_ignored_path_for_add',
    'extract_tags_from_frontmatter',
    'format_tag_name',
    'is_valid_obsidian_tag',
    'needs_quoting',
]
