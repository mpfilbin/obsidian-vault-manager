"""
Core vault operations and file system utilities.

This module provides shared functionality for vault root discovery,
path validation, and directory ignore rules used across all vault_manager modules.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Set, List, Iterator, Callable


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

    Note:
        For memory-efficient iteration over large vaults, use iter_markdown_files()
        instead, which returns an iterator.
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


def iter_markdown_files(
    directory: Path,
    vault_root: Path,
    additional_ignores: Optional[Set[str]] = None,
    exclude_excalidraw: bool = True,
    progress_callback: Optional[Callable[[Path], None]] = None,
    follow_symlinks: bool = True
) -> Iterator[Path]:
    """
    Iterate over markdown files in a directory (memory-efficient).

    This function yields markdown files one at a time, making it memory-efficient
    for large vaults. It's the recommended way to process markdown files when
    you don't need the full list upfront.

    Args:
        directory: Directory to search
        vault_root: Vault root directory
        additional_ignores: Optional additional directories to ignore
        exclude_excalidraw: Exclude .excalidraw.md files (default True)
        progress_callback: Optional callback function called for each file found
        follow_symlinks: Follow symbolic links (default True)

    Yields:
        Path objects for each markdown file found

    Examples:
        >>> vault_root = Path('/vault')
        >>> for md_file in iter_markdown_files(vault_root, vault_root):
        ...     # Process file
        ...     pass

        >>> # With progress callback
        >>> def on_progress(file_path):
        ...     print(f"Processing: {file_path.name}")
        >>> for md_file in iter_markdown_files(vault_root, vault_root, progress_callback=on_progress):
        ...     # Process file
        ...     pass

        >>> # Without following symlinks
        >>> for md_file in iter_markdown_files(vault_root, vault_root, follow_symlinks=False):
        ...     # Process file
        ...     pass
    """
    # Use os.walk() with followlinks parameter for explicit symlink control
    for root, dirs, files in os.walk(directory, followlinks=follow_symlinks):
        root_path = Path(root)

        # Skip ignored directories (and prune the walk tree)
        if is_ignored_path(root_path, vault_root, additional_ignores):
            dirs[:] = []  # Don't recurse into this directory
            continue

        # Process markdown files in this directory
        for filename in files:
            if not filename.endswith('.md'):
                continue

            # Skip Excalidraw files if requested
            if exclude_excalidraw and filename.endswith('.excalidraw.md'):
                continue

            md_file = root_path / filename

            # Call progress callback if provided
            if progress_callback:
                progress_callback(md_file)

            yield md_file


def count_markdown_files(
    directory: Path,
    vault_root: Path,
    additional_ignores: Optional[Set[str]] = None,
    exclude_excalidraw: bool = True,
    follow_symlinks: bool = True
) -> int:
    """
    Count markdown files in a directory without loading them into memory.

    Useful for progress tracking when you need to know the total count
    before processing files.

    Args:
        directory: Directory to search
        vault_root: Vault root directory
        additional_ignores: Optional additional directories to ignore
        exclude_excalidraw: Exclude .excalidraw.md files (default True)
        follow_symlinks: Follow symbolic links (default True)

    Returns:
        Number of markdown files found

    Examples:
        >>> vault_root = Path('/vault')
        >>> total = count_markdown_files(vault_root, vault_root)
        >>> print(f"Found {total} markdown files")
    """
    count = 0
    for _ in iter_markdown_files(
        directory, vault_root, additional_ignores, exclude_excalidraw,
        follow_symlinks=follow_symlinks
    ):
        count += 1
    return count
