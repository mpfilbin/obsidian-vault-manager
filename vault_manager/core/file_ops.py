"""
Safe file operations with error handling and dry-run support.

This module provides centralized file I/O operations with consistent error
handling, dry-run support, and atomic update patterns. All commands should
use these utilities instead of implementing their own file I/O.
"""

import sys
from pathlib import Path
from typing import Optional, Callable


class FileOperationError(Exception):
    """Raised when file operations fail."""
    pass


def safe_read(
    path: Path,
    encoding: str = 'utf-8',
    on_error: Optional[Callable[[Path, Exception], None]] = None,
    silent: bool = False
) -> Optional[str]:
    """
    Safely read a file with error handling.

    Args:
        path: File to read
        encoding: File encoding (default: utf-8)
        on_error: Optional callback for custom error handling
        silent: If True, suppress error messages

    Returns:
        File content as string, or None if reading failed

    Examples:
        >> from pathlib import Path
        >> content = safe_read(Path('note.md'))
        >> if content:
        ...     print(f"Read {len(content)} characters")

        >> # With custom error handling
        >> def handle_error(path, error):
        ...     print(f"Failed to read {path}: {error}")
        >> content = safe_read(Path('note.md'), on_error=handle_error)
    """
    try:
        return path.read_text(encoding=encoding)
    except FileNotFoundError:
        if on_error:
            on_error(path, FileNotFoundError(f"File not found: {path}"))
        elif not silent:
            print(f"Error: File not found: {path}", file=sys.stderr)
        return None
    except PermissionError as e:
        if on_error:
            on_error(path, e)
        elif not silent:
            print(f"Error: Permission denied: {path}", file=sys.stderr)
        return None
    except UnicodeDecodeError as e:
        if on_error:
            on_error(path, e)
        elif not silent:
            print(f"Error: Could not decode file (wrong encoding?): {path}", file=sys.stderr)
        return None
    except Exception as e:
        if on_error:
            on_error(path, e)
        elif not silent:
            print(f"Error reading {path}: {e}", file=sys.stderr)
        return None


def safe_write(
    path: Path,
    content: str,
    encoding: str = 'utf-8',
    dry_run: bool = False,
    on_error: Optional[Callable[[Path, Exception], None]] = None,
    silent: bool = False,
    create_parents: bool = True
) -> bool:
    """
    Safely write content to a file with dry-run support.

    Args:
        path: File to write
        content: Content to write
        encoding: File encoding (default: utf-8)
        dry_run: If True, don't actually write (just pretend)
        on_error: Optional callback for custom error handling
        silent: If True, suppress error messages
        create_parents: Create parent directories if needed (default: True)

    Returns:
        True if successful (or dry-run), False on error

    Examples:
        >> from pathlib import Path
        >> # Normal write
        >> success = safe_write(Path('note.md'), '# My Note\\n')
        >> print(f"Write {'succeeded' if success else 'failed'}")

        >> # Dry-run (doesn't actually write)
        >> success = safe_write(Path('note.md'), '# Test', dry_run=True)

        >> # With parent directory creation
        >> success = safe_write(Path('subdir/note.md'), '# Test', create_parents=True)
    """
    if dry_run:
        return True

    try:
        # Create parent directories if needed
        if create_parents and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding=encoding)
        return True
    except PermissionError as e:
        if on_error:
            on_error(path, e)
        elif not silent:
            print(f"Error: Permission denied: {path}", file=sys.stderr)
        return False
    except OSError as e:
        if on_error:
            on_error(path, e)
        elif not silent:
            print(f"Error writing to {path}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        if on_error:
            on_error(path, e)
        elif not silent:
            print(f"Error writing {path}: {e}", file=sys.stderr)
        return False


def atomic_update(
    path: Path,
    updater: Callable[[str], Optional[str]],
    dry_run: bool = False,
    encoding: str = 'utf-8',
    on_error: Optional[Callable[[Path, Exception], None]] = None,
    silent: bool = False
) -> bool:
    """
    Atomically read, update, and write a file.

    This is the recommended pattern for modifying files. It ensures:
    1. File is read successfully before attempting modifications
    2. Updater function is called to transform content
    3. File is only written if updater succeeds
    4. All errors are handled consistently

    Args:
        path: File to update
        updater: Function that transforms content (str -> Optional[str])
                Returns None to signal error/skip
        dry_run: If True, read but don't write
        encoding: File encoding (default: utf-8)
        on_error: Optional callback for custom error handling
        silent: If True, suppress error messages

    Returns:
        True if successful, False on error

    Examples:
        >> from pathlib import Path
        >>
        >> # Simple update function
        >> def add_line(content):
        ...     return content + "\\n# New Section\\n"
        >>
        >> success = atomic_update(Path('note.md'), add_line)
        >>
        >> # Update with validation
        >> def update_if_valid(content):
        ...     if '# Title' not in content:
        ...         return None  # Skip this file
        ...     return content.replace('old', 'new')

        >> success = atomic_update(Path('note.md'), update_if_valid)

        >> # Dry-run mode
        >> success = atomic_update(Path('note.md'), add_line, dry_run=True)
    """
    # Read current content
    content = safe_read(path, encoding=encoding, on_error=on_error, silent=silent)
    if content is None:
        return False

    # Transform content
    try:
        updated_content = updater(content)
    except Exception as e:
        if on_error:
            on_error(path, e)
        elif not silent:
            print(f"Error in updater function for {path}: {e}", file=sys.stderr)
        return False

    # If updater returned None, skip this file
    if updated_content is None:
        return False

    # Only write if content actually changed (unless in dry-run)
    if updated_content == content and not dry_run:
        return True  # No changes needed

    # Write updated content
    return safe_write(
        path,
        updated_content,
        encoding=encoding,
        dry_run=dry_run,
        on_error=on_error,
        silent=silent,
        create_parents=False  # File already exists
    )


def safe_move(
    source: Path,
    destination: Path,
    dry_run: bool = False,
    overwrite: bool = False,
    on_error: Optional[Callable[[Path, Exception], None]] = None,
    silent: bool = False
) -> bool:
    """
    Safely move/rename a file with dry-run support.

    Args:
        source: Source file path
        destination: Destination file path
        dry_run: If True, don't actually move
        overwrite: If True, overwrite existing destination
        on_error: Optional callback for custom error handling
        silent: If True, suppress error messages

    Returns:
        True if successful (or dry-run), False on error

    Examples:
        >> from pathlib import Path
        >> # Move file
        >> success = safe_move(Path('old.md'), Path('.trash/old.md'))

        >> # Dry-run
        >> success = safe_move(Path('old.md'), Path('new.md'), dry_run=True)
    """
    if dry_run:
        return True

    try:
        # Check source exists
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        # Check destination
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {destination}")

        # Create parent directory if needed
        if not destination.parent.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)

        # Move/rename file
        source.rename(destination)
        return True

    except (FileNotFoundError, FileExistsError, PermissionError, OSError) as e:
        if on_error:
            on_error(source, e)
        elif not silent:
            print(f"Error moving {source} to {destination}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        if on_error:
            on_error(source, e)
        elif not silent:
            print(f"Unexpected error moving {source} to {destination}: {e}", file=sys.stderr)
        return False
