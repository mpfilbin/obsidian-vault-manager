"""
Core vault operations and file system utilities.

This module provides shared functionality for vault root discovery,
path validation, and directory ignore rules used across all vault_manager modules.
"""

import sys
from pathlib import Path
from typing import Optional, Set, List


# Global vault root cache (set by CLI at startup)
_VAULT_ROOT: Optional[Path] = None


def set_vault_root(path: Path) -> None:
    """
    Set the global vault root path.

    This should be called once at CLI startup after vault path resolution.

    Args:
        path: Path to vault root directory
    """
    global _VAULT_ROOT
    _VAULT_ROOT = path


def get_vault_root() -> Path:
    """
    Get the vault root directory.

    Returns:
        Path to vault root directory

    Raises:
        RuntimeError: If vault root has not been set

    Examples:
        >>> from vault_manager.core.vault import set_vault_root
        >>> set_vault_root(Path('/path/to/vault'))
        >>> vault_root = get_vault_root()
        >>> vault_root == Path('/path/to/vault')
        True
    """
    if _VAULT_ROOT is None:
        raise RuntimeError(
            "Vault root not set. This should be set by CLI during initialization."
        )
    return _VAULT_ROOT


def is_ignored_path(
    file_path: Path,
    vault_root: Path,
    additional_ignores: Optional[Set[str]] = None
) -> bool:
    """
    Check if a file path should be ignored during vault processing.

    Args:
        file_path: Path to check
        vault_root: Vault root directory
        additional_ignores: Optional set of additional directory names to ignore

    Returns:
        True if path should be ignored, False otherwise

    Default ignored directories:
        - .obsidian (Obsidian configuration)
        - .trash (deleted files)
        - .backup (backup files)

    Examples:
        >>> vault_root = Path('/vault')
        >>> is_ignored_path(Path('/vault/.obsidian/config'), vault_root)
        True
        >>> is_ignored_path(Path('/vault/Notes/file.md'), vault_root)
        False
        >>> is_ignored_path(Path('/vault/Excalidraw/drawing.md'), vault_root, {'Excalidraw'})
        True
    """
    try:
        relative_path = file_path.relative_to(vault_root)
    except ValueError:
        # Path is not relative to vault_root
        return True

    path_parts = relative_path.parts

    # Default ignore list
    ignored = {'.obsidian', '.trash', '.backup'}

    # Add module-specific ignores
    if additional_ignores:
        ignored.update(additional_ignores)

    # Check if any ignored directory is in path
    return bool(ignored & set(path_parts))


def validate_directory(
    directory_arg: str,
    vault_root: Path,
    must_exist: bool = True
) -> Path:
    """
    Validate and resolve a directory path argument.

    Args:
        directory_arg: Directory argument (can be '.' for vault root)
        vault_root: Vault root directory
        must_exist: Whether directory must exist (default True)

    Returns:
        Resolved Path object

    Raises:
        SystemExit: If validation fails

    Examples:
        >>> vault_root = Path('/vault')
        >>> target_dir = validate_directory('.', vault_root)
        >>> target_dir == vault_root
        True
    """
    # Resolve directory path
    if directory_arg == '.':
        target_dir = vault_root
    else:
        target_dir = vault_root / directory_arg

    if must_exist:
        # Validate directory exists
        if not target_dir.exists():
            print(f"Error: Directory not found: {directory_arg}")
            print(f"Looking for: {target_dir}")
            sys.exit(1)

        if not target_dir.is_dir():
            print(f"Error: Not a directory: {directory_arg}")
            sys.exit(1)

    return target_dir


def get_markdown_files(
    directory: Path,
    vault_root: Path,
    additional_ignores: Optional[Set[str]] = None,
    exclude_excalidraw: bool = True
) -> List[Path]:
    """
    Recursively find all markdown files in a directory.

    Args:
        directory: Directory to search
        vault_root: Vault root directory
        additional_ignores: Optional additional directories to ignore
        exclude_excalidraw: Exclude .excalidraw.md files (default True)

    Returns:
        List of markdown file paths

    Examples:
        >>> vault_root = Path('/vault')
        >>> directory = vault_root / 'Notes'
        >>> files = get_markdown_files(directory, vault_root)
        >>> all(f.suffix == '.md' for f in files)
        True
    """
    markdown_files = []

    for md_file in directory.rglob('*.md'):
        # Skip ignored paths
        if is_ignored_path(md_file, vault_root, additional_ignores):
            continue

        # Skip Excalidraw files if requested
        if exclude_excalidraw and md_file.name.endswith('.excalidraw.md'):
            continue

        markdown_files.append(md_file)

    return markdown_files
