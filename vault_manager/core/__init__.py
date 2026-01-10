"""
Core utilities for Library vault maintenance tools.

This module provides shared functionality used across all Library
subpackages (tags, images, properties, index).

Usage:
    from vault_manager.core import get_vault_root, is_ignored_path
    from vault_manager.core.validation import require_library
    from vault_manager.core.command import Command
"""

# Vault operations
from .vault import (
    get_vault_root,
    is_ignored_path,
    validate_directory,
    get_markdown_files,
)

# Command base class
from .command import Command

# Frontmatter utilities
from .frontmatter_manager import FrontmatterManager

# Backward compatibility wrappers for frontmatter functions
def extract_frontmatter(content: str):
    """Backward compatibility wrapper for FrontmatterManager.extract_frontmatter()."""
    return FrontmatterManager.extract_frontmatter(content)

def extract_tags_from_frontmatter(content: str):
    """Backward compatibility wrapper for FrontmatterManager.extract_tags_from_frontmatter()."""
    return FrontmatterManager.extract_tags_from_frontmatter(content)

def format_tag_name(tag: str):
    """Backward compatibility wrapper for FrontmatterManager.format_tag_name()."""
    return FrontmatterManager.format_tag_name(tag)

def is_valid_obsidian_tag(tag: str):
    """Backward compatibility wrapper for FrontmatterManager.is_valid_obsidian_tag()."""
    return FrontmatterManager.is_valid_obsidian_tag(tag)

def needs_quoting(value: str):
    """Backward compatibility wrapper for FrontmatterManager.needs_quoting()."""
    return FrontmatterManager.needs_quoting(value)

# Validation utilities
from .validation import (
    require_library,
    check_api_key,
    validate_file_path,
)

# File operations
from .file_ops import (
    safe_read,
    safe_write,
    atomic_update,
    safe_move,
    FileOperationError,
)

__all__ = [
    # Vault
    'get_vault_root',
    'is_ignored_path',
    'validate_directory',
    'get_markdown_files',
    # Command
    'Command',
    # Frontmatter
    'extract_frontmatter',
    'extract_tags_from_frontmatter',
    'format_tag_name',
    'is_valid_obsidian_tag',
    'needs_quoting',
    # Validation
    'require_library',
    'check_api_key',
    'validate_file_path',
    # File Operations
    'safe_read',
    'safe_write',
    'atomic_update',
    'safe_move',
    'FileOperationError',
]
