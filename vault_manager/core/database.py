#!/usr/bin/env python3
"""
Database utilities for vault maintenance.

This module provides shared utilities for database operations,
particularly for rebuilding the vault index database.
"""

import sys
from argparse import Namespace
from functools import wraps
from typing import Optional


def rebuild_vault_database(silent: bool = False, verbose: bool = False) -> bool:
    """
    Rebuild the vault index database.

    This is a shared utility used by multiple commands that need to rebuild
    the database after making changes to vault files (e.g., purge, rename, normalize).

    Args:
        silent: If True, suppress all output
        verbose: If True, show detailed build output (only used if not silent)

    Returns:
        True if successful, False if failed

    Example:
        >> from vault_manager.core.database import rebuild_vault_database
        >> if rebuild_vault_database():
        ...     print("Database updated successfully")
    """
    try:
        from vault_manager.index.commands.build import BuildCommand

        if not silent:
            print(f"\n{'='*60}")
            print("Rebuilding vault index database...")
            print(f"{'='*60}\n")

        # Create build command with all required arguments
        build_cmd = BuildCommand()
        build_args = Namespace(
            force=True,           # Force full rebuild
            incremental=False,    # Not incremental
            no_hash=False,        # Include hashing for duplicate detection
            max_hash_size=100     # Default max hash size in MB
        )

        # Execute the build
        build_cmd.execute(build_args)

        if not silent:
            print("\nDatabase updated successfully.")

        return True

    except Exception as e:
        if not silent:
            print(f"\nWarning: Failed to rebuild database: {e}")
            print("You may need to run 'vault index build' manually.")
        return False


def get_database_stats(db_path) -> dict:
    """
    Get statistics about the vault database.

    Args:
        db_path: Path to vault.db file

    Returns:
        Dictionary with database statistics

    Example:
        >> from pathlib import Path
        >> from vault_manager.core.database import get_database_stats
        >> stats = get_database_stats(Path('vault.db'))
        >> print(f"Total files: {stats['total_files']}")
    """
    import sqlite3

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            stats = {}

            # Get total files
            cursor.execute("SELECT COUNT(*) FROM files")
            stats['total_files'] = cursor.fetchone()[0]

            # Get total tags
            cursor.execute("SELECT COUNT(DISTINCT tag) FROM file_tags")
            stats['total_tags'] = cursor.fetchone()[0]

            # Get total links
            cursor.execute("SELECT COUNT(*) FROM links")
            stats['total_links'] = cursor.fetchone()[0]

            # Get files with frontmatter
            cursor.execute("SELECT COUNT(*) FROM files WHERE has_frontmatter = 1")
            stats['files_with_frontmatter'] = cursor.fetchone()[0]

            # Get metadata
            cursor.execute("SELECT key, value FROM metadata")
            for key, value in cursor.fetchall():
                stats[key] = value

            return stats

    except Exception as e:
        return {'error': str(e)}


def database_exists(vault_root) -> bool:
    """
    Check if vault.db exists.

    Args:
        vault_root: Path to vault root directory

    Returns:
        True if database exists, False otherwise
    """
    from pathlib import Path

    db_path = Path(vault_root) / 'vault.db'
    return db_path.exists()


def require_database(vault_root, command_name: str = "this command") -> None:
    """
    Check if database exists and exit with helpful message if not.

    Args:
        vault_root: Path to vault root directory
        command_name: Name of the command requiring the database (for error message)

    Example:
        >> from vault_manager.core.database import require_database
        >> from vault_manager.core.vault import get_vault_root
        >> require_database(get_vault_root(), "query")
    """
    if not database_exists(vault_root):
        print("\nError: vault.db not found.")
        print(f"Run 'vault tags update' or 'vault index build' before using {command_name}.")
        sys.exit(1)


def rebuild_if_needed(
    skip: bool = False,
    message: Optional[str] = None,
    silent: bool = False
) -> bool:
    """
    Rebuild database with optional skip.

    This function provides a standardized way for commands to handle
    database rebuilding after making changes to files. It supports
    skipping the rebuild (e.g., when using --no-rebuild flag) with
    a helpful message to the user.

    Args:
        skip: If True, skip rebuild and show message
        message: Custom message to show when skipping (default: standard message)
        silent: Suppress all output

    Returns:
        True if rebuilt or skipped, False if rebuild failed

    Examples:
        >> # Normal rebuild
        >> rebuild_if_needed()

        >> # Skip rebuild (with --no-rebuild flag)
        >> rebuild_if_needed(skip=args.no_rebuild)

        >> # Custom skip message
        >> rebuild_if_needed(
        ...     skip=args.no_rebuild,
        ...     message="Database not updated. Run 'vault tags update' to sync."
        ... )
    """
    if skip:
        if not silent:
            print("\n" + "=" * 60)
            print("⚠ Database Rebuild Skipped")
            print("=" * 60)

            if message:
                print(f"\n{message}")
            else:
                print("\nThe vault.db database was NOT updated.")
                print("To update the database, run: vault index build")

        return True

    return rebuild_vault_database(silent=silent)


def auto_rebuild_after(operation_name: str):
    """
    Decorator to auto-rebuild database after command execution.

    This decorator wraps command execute methods to automatically
    rebuild the database after the command completes, unless the
    --no-rebuild flag is set.

    Args:
        operation_name: Name of the operation (for logging/debugging)

    Returns:
        Decorated function that rebuilds database after execution

    Examples:
        >> from vault_manager.core.database import auto_rebuild_after
        >> from vault_manager.core.command import Command
        >>
        >> class PurgeCommand(Command):
        ...     @auto_rebuild_after("tag purge")
        ...     def execute(self, args):
        ...         # Remove tags from files
        ...         ...
        ...         # Database will be auto-rebuilt after this returns

        >> class RenameCommand(Command):
        ...     @auto_rebuild_after("tag rename")
        ...     def execute(self, args):
        ...         # Rename tags in files
        ...         ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, args):
            # Execute the command
            result = func(self, args)

            # Rebuild database after command completes
            skip_rebuild = getattr(args, 'no_rebuild', False)
            rebuild_if_needed(skip=skip_rebuild)

            return result
        return wrapper
    return decorator
