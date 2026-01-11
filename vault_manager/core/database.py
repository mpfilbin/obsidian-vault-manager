#!/usr/bin/env python3
"""
Database utilities for vault maintenance.

This module provides database operations through the VaultDatabase class.
The class uses a context manager pattern for proper resource management.
"""

import sqlite3
import sys
from argparse import Namespace
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from sqlite3 import Connection
from typing import Any, Generator, List, Optional, Tuple

# ============================================================================
# VaultDatabase Class (OOP Interface)
# ============================================================================


class VaultDatabase:
    """
    Manages database operations for the vault.

    Provides connection management, query execution, and transaction support.
    Designed to be used as a context manager for proper resource cleanup.

    Usage:
        # Query operations
        with VaultDatabase() as db:
            results = db.query("SELECT * FROM tags")
            single = db.query_single("SELECT COUNT(*) FROM files")

        # Transaction operations
        with VaultDatabase() as db:
            with db.transaction() as conn:
                conn.execute("INSERT INTO files ...")
                conn.execute("INSERT INTO tags ...")
                # Auto-commit on exit

        # Utility operations
        with VaultDatabase() as db:
            db.require_exists("query")
            stats = db.get_stats()
    """

    def __init__(self, vault_root: Optional[Path] = None):
        """
        Initialize database manager.

        Args:
            vault_root: Path to vault root directory. If None, uses get_vault_root()
        """
        self.vault_root = vault_root
        self.db_path = self._resolve_db_path()
        self._connection: Optional[sqlite3.Connection] = None

    def _resolve_db_path(self) -> Path:
        """
        Resolve database path from vault root.

        Returns:
            Path to vault.db file
        """
        if self.vault_root is None:
            from vault_manager.core.vault import get_vault_root

            self.vault_root = get_vault_root()
        return Path(self.vault_root) / "vault.db"

    def __enter__(self) -> "VaultDatabase":
        """
        Enter context and open database connection.

        Returns:
            self for use in with statement
        """
        self._connection = self._create_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def _create_connection(self, read_only: bool = False) -> sqlite3.Connection:
        """
        Create and configure database connection.

        Args:
            read_only: If True, open database in read-only mode

        Returns:
            Configured SQLite connection

        Raises:
            FileNotFoundError: If database doesn't exist (read-only mode)
        """
        db_path_str = str(self.db_path)

        # Add read-only URI parameter if requested
        if read_only:
            if not self.db_path.exists():
                raise FileNotFoundError(f"Database not found: {self.db_path}")
            db_path_str = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(db_path_str, uri=True)
        else:
            conn = sqlite3.connect(db_path_str)

        # Apply standard configuration
        self._configure_connection(conn)
        return conn

    @staticmethod
    def _configure_connection(conn: sqlite3.Connection) -> None:
        """
        Apply standard configuration to a database connection.

        Args:
            conn: SQLite connection to configure
        """
        conn.execute("PRAGMA foreign_keys = ON")

    # Query Methods

    def query(self, sql: str, params: Tuple = ()) -> List[Tuple]:
        """
        Execute SELECT query and return all results.

        Args:
            sql: SQL SELECT query
            params: Query parameters (use ? placeholders)

        Returns:
            List of result tuples

        Raises:
            sqlite3.Error: On database or SQL errors
            RuntimeError: If called outside context manager

        Examples:
            >> with VaultDatabase() as db:
            ...     results = db.query("SELECT * FROM tags")
            ...     for row in results:
            ...         print(row)
        """
        if self._connection is None:
            raise RuntimeError(
                "Database connection not established. Use 'with VaultDatabase() as db:'"
            )

        cursor = self._connection.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()

    def query_single(self, sql: str, params: Tuple = ()) -> Tuple:
        """
        Execute SELECT query and return single result or empty tuple.

        Args:
            sql: SQL SELECT query
            params: Query parameters (use ? placeholders)

        Returns:
            Single result tuple, or empty tuple if no results

        Raises:
            sqlite3.Error: On database or SQL errors
            RuntimeError: If called outside context manager

        Examples:
            >> with VaultDatabase() as db:
            ...     row = db.query_single("SELECT COUNT(*) FROM files")
            ...     count = row[0] if row else 0
        """
        if self._connection is None:
            raise RuntimeError(
                "Database connection not established. Use 'with VaultDatabase() as db:'"
            )

        cursor = self._connection.cursor()
        cursor.execute(sql, params)
        result = cursor.fetchone()
        return result if result is not None else ()

    def query_with_columns(self, sql: str, params: Tuple = ()) -> Tuple[List[str], List[Tuple]]:
        """
        Execute SELECT query and return column names and results.

        Args:
            sql: SQL SELECT query
            params: Query parameters (use ? placeholders)

        Returns:
            Tuple of (column_names, results) where:
            - column_names is a list of column name strings
            - results is a list of result tuples

        Raises:
            sqlite3.Error: On database or SQL errors
            RuntimeError: If called outside context manager

        Examples:
            >> with VaultDatabase() as db:
            ...     columns, rows = db.query_with_columns("SELECT * FROM tags")
            ...     print(" | ".join(columns))
        """
        if self._connection is None:
            raise RuntimeError(
                "Database connection not established. Use 'with VaultDatabase() as db:'"
            )

        cursor = self._connection.cursor()
        cursor.execute(sql, params)
        results = cursor.fetchall()
        column_names = (
            [description[0] for description in cursor.description] if cursor.description else []
        )
        return column_names, results

    # Write Methods

    def write(self, sql: str, params: Tuple = ()) -> int:
        """
        Execute INSERT/UPDATE/DELETE and return affected row count.

        Automatically commits the transaction.

        Args:
            sql: SQL INSERT/UPDATE/DELETE query
            params: Query parameters (use ? placeholders)

        Returns:
            Number of affected rows

        Raises:
            sqlite3.Error: On database or SQL errors
            RuntimeError: If called outside context manager

        Examples:
            >> with VaultDatabase() as db:
            ...     rows = db.write("INSERT INTO tags (tag) VALUES (?)", ("newtag",))
            ...     print(f"Inserted {rows} row(s)")
        """
        if self._connection is None:
            raise RuntimeError(
                "Database connection not established. Use 'with VaultDatabase() as db:'"
            )

        cursor = self._connection.cursor()
        cursor.execute(sql, params)
        self._connection.commit()
        return cursor.rowcount

    def write_many(self, sql: str, param_list: List[Tuple]) -> int:
        """
        Execute batch INSERT/UPDATE/DELETE operations.

        More efficient than multiple write() calls as it uses a single transaction.

        Args:
            sql: SQL INSERT/UPDATE/DELETE query
            param_list: List of parameter tuples

        Returns:
            Total number of affected rows

        Raises:
            sqlite3.Error: On database or SQL errors
            RuntimeError: If called outside context manager

        Examples:
            >> with VaultDatabase() as db:
            ...     tags = [("tag1",), ("tag2",), ("tag3",)]
            ...     rows = db.write_many("INSERT INTO tags (tag) VALUES (?)", tags)
        """
        if self._connection is None:
            raise RuntimeError(
                "Database connection not established. Use 'with VaultDatabase() as db:'"
            )

        cursor = self._connection.cursor()
        cursor.executemany(sql, param_list)
        self._connection.commit()
        return cursor.rowcount

    # Transaction Support

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.

        Changes are automatically committed on successful exit or rolled back
        if an exception occurs.

        Yields:
            sqlite3.Connection in transaction context

        Raises:
            RuntimeError: If called outside VaultDatabase context manager

        Examples:
            >> with VaultDatabase() as db:
            ...     with db.transaction() as conn:
            ...         conn.execute("INSERT INTO tags (tag) VALUES (?)", ("newtag",))
            ...         conn.execute("INSERT INTO file_tags (file_path, tag) VALUES (?, ?)",
            ...                      ("note.md", "newtag"))
            ...         # Auto-commit on success, rollback on exception
        """
        if self._connection is None:
            raise RuntimeError(
                "Database connection not established. Use 'with VaultDatabase() as db:'"
            )

        try:
            yield self._connection
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    # Utility Methods

    def exists(self) -> bool:
        """
        Check if vault.db exists.

        Returns:
            True if database exists, False otherwise
        """
        return self.db_path.exists()

    def ensure_path(self) -> Path:
        """
        Ensure database parent directory exists.

        Returns:
            Path to vault.db file

        Examples:
            >> db = VaultDatabase()
            >> db.ensure_path()  # Creates parent directory if needed
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return self.db_path

    def get_stats(self) -> dict:
        """
        Get statistics about the vault database.

        Returns:
            Dictionary with database statistics

        Raises:
            RuntimeError: If called outside context manager

        Examples:
            >> with VaultDatabase() as db:
            ...     stats = db.get_stats()
            ...     print(f"Total files: {stats['total_files']}")
        """
        if self._connection is None:
            raise RuntimeError(
                "Database connection not established. Use 'with VaultDatabase() as db:'"
            )

        try:
            cursor = self._connection.cursor()
            stats = {}

            # Get total files
            cursor.execute("SELECT COUNT(*) FROM files")
            stats["total_files"] = cursor.fetchone()[0]

            # Get total tags
            cursor.execute("SELECT COUNT(DISTINCT tag) FROM file_tags")
            stats["total_tags"] = cursor.fetchone()[0]

            # Get total links
            cursor.execute("SELECT COUNT(*) FROM links")
            stats["total_links"] = cursor.fetchone()[0]

            # Get files with frontmatter
            cursor.execute("SELECT COUNT(*) FROM files WHERE has_frontmatter = 1")
            stats["files_with_frontmatter"] = cursor.fetchone()[0]

            # Get metadata
            cursor.execute("SELECT key, value FROM metadata")
            for key, value in cursor.fetchall():
                stats[key] = value

            return stats

        except Exception as e:
            return {"error": str(e)}

    def rebuild(self, silent: bool = False) -> bool:
        """
        Rebuild the vault index database.

        Args:
            silent: If True, suppress all output

        Returns:
            True if successful, False if failed

        Examples:
            >> db = VaultDatabase()
            >> if db.rebuild():
            ...     print("Database updated successfully")
        """
        try:
            from vault_manager.index.commands.build import BuildCommand

            if not silent:
                print(f"\n{'=' * 60}")
                print("Rebuilding vault index database...")
                print(f"{'=' * 60}\n")

            # Create build command with all required arguments
            build_cmd = BuildCommand()
            build_args = Namespace(
                force=True,  # Force full rebuild
                incremental=False,  # Not incremental
                no_hash=False,  # Include hashing for duplicate detection
                max_hash_size=100,  # Default max hash size in MB
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

    def require_exists(self, command_name: str = "this command") -> None:
        """
        Check if database exists and exit with helpful message if not.

        Args:
            command_name: Name of the command requiring the database (for error message)

        Examples:
            >> with VaultDatabase() as db:
            ...     db.require_exists("query")
            ...     # Proceeds if database exists, exits if not
        """
        if not self.exists():
            print("\nError: vault.db not found.")
            print(f"Run 'vault tags update' or 'vault index build' before using {command_name}.")
            sys.exit(1)


# ============================================================================
# Database Path Utilities
# ============================================================================


def get_database_path(vault_root: Optional[Path] = None) -> Path:
    """
    Get path to vault.db database file.

    Args:
        vault_root: Path to vault root directory. If None, uses get_vault_root()

    Returns:
        Path to vault.db file

    Example:
        >> from vault_manager.core.database import get_database_path
        >> db_path = get_database_path()
        >> print(db_path)
        Path('/path/to/vault/vault.db')
    """
    if vault_root is None:
        from vault_manager.core.vault import get_vault_root

        vault_root = get_vault_root()

    return Path(vault_root) / "vault.db"


def ensure_database_path(vault_root: Optional[Path] = None) -> Path:
    """
    Get database path and ensure parent directory exists.

    Useful for database creation operations where the vault directory
    might not exist yet.

    Args:
        vault_root: Path to vault root directory. If None, uses get_vault_root()

    Returns:
        Path to vault.db file

    Example:
        >> from vault_manager.core.database import ensure_database_path
        >> db_path = ensure_database_path()
        >> # Parent directory is guaranteed to exist
    """
    db_path = get_database_path(vault_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


# ============================================================================
# Database Connection Management
# ============================================================================


def configure_connection(conn: sqlite3.Connection) -> None:
    """
    Apply standard configuration to a database connection.

    Enables foreign keys and sets optimal pragmas for performance.

    Args:
        conn: SQLite connection to configure

    Example:
        >> import sqlite3
        >> conn = sqlite3.connect('vault.db')
        >> configure_connection(conn)
    """
    conn.execute("PRAGMA foreign_keys = ON")


@contextmanager
def get_database_connection(
    db_path: Optional[Path] = None, read_only: bool = False
) -> Generator[Connection, Any, None]:
    """
    Get a database connection with automatic cleanup.

    This context manager ensures connections are always properly closed,
    even when exceptions occur. Foreign keys are automatically enabled.

    Args:
        db_path: Path to database file. If None, uses vault.db in vault root
        read_only: If True, open database in read-only mode

    Yields:
        sqlite3.Connection with foreign keys enabled

    Raises:
        sqlite3.Error: On database errors
        FileNotFoundError: If database doesn't exist (read-only mode)

    Examples:
        >> # Simple query
        >> with get_database_connection() as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM tags")
        ...     results = cursor.fetchall()

        >> # Read-only access
        >> with get_database_connection(read_only=True) as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT COUNT(*) FROM files")

        >> # Custom database path
        >> from pathlib import Path
        >> with get_database_connection(Path('/tmp/test.db')) as conn:
        ...     conn.execute("CREATE TABLE test (id INTEGER)")
    """
    if db_path is None:
        db_path = get_database_path()

    # Convert to string for sqlite3.connect
    db_path_str = str(db_path)

    # Add read-only URI parameter if requested
    if read_only:
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        db_path_str = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(db_path_str, uri=True)
    else:
        conn = sqlite3.connect(db_path_str)

    try:
        configure_connection(conn)
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(db_path: Optional[Path] = None):
    """
    Execute operations in a transaction with automatic commit/rollback.

    This context manager provides clear transaction boundaries. Changes
    are automatically committed on successful exit or rolled back if an
    exception occurs.

    Args:
        db_path: Path to database file. If None, uses vault.db in vault root

    Yields:
        sqlite3.Connection in transaction context

    Examples:
        >> # Atomic multi-table update
        >> with transaction() as conn:
        ...     conn.execute("INSERT INTO tags (tag) VALUES (?)", ("newtag",))
        ...     conn.execute("INSERT INTO file_tags (file_path, tag) VALUES (?, ?)",
        ...                  ("note.md", "newtag"))
        ...     # Both inserts commit together

        >> # Automatic rollback on error
        >> try:
        ...     with transaction() as conn:
        ...         conn.execute("INSERT INTO tags (tag) VALUES (?)", ("tag1",))
        ...         conn.execute("INVALID SQL")  # This fails
        ... except sqlite3.Error:
        ...     pass
        ... # First insert is rolled back automatically
    """
    with get_database_connection(db_path) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# ============================================================================
# Query Helper Functions
# ============================================================================


def execute_query(sql: str, params: Tuple = (), db_path: Optional[Path] = None) -> List[Tuple]:
    """
    Execute SELECT query and return all results.

    Convenience function for simple queries that don't need manual
    connection management.

    Args:
        sql: SQL SELECT query
        params: Query parameters (use ? placeholders)
        db_path: Path to database file. If None, uses vault.db in vault root

    Returns:
        List of result tuples

    Raises:
        sqlite3.Error: On database or SQL errors

    Examples:
        >> # Simple query
        >> results = execute_query("SELECT * FROM tags")
        >> for row in results:
        ...     print(row)

        >> # Parameterized query
        >> results = execute_query(
        ...     "SELECT * FROM tags WHERE tag LIKE ?",
        ...     ("project/%",)
        ... )

        >> # Count query
        >> results = execute_query("SELECT COUNT(*) FROM files")
        >> count = results[0][0]
    """
    with get_database_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()


def execute_query_with_columns(
    sql: str, params: Tuple = (), db_path: Optional[Path] = None
) -> Tuple[List[str], List[Tuple]]:
    """
    Execute SELECT query and return column names and results.

    Useful for displaying query results in table format where you
    need the column headers.

    Args:
        sql: SQL SELECT query
        params: Query parameters (use ? placeholders)
        db_path: Path to database file. If None, uses vault.db in vault root

    Returns:
        Tuple of (column_names, results) where:
        - column_names is a list of column name strings
        - results is a list of result tuples

    Raises:
        sqlite3.Error: On database or SQL errors

    Examples:
        >> # Get results with column names
        >> columns, rows = execute_query_with_columns("SELECT * FROM tags")
        >> print(" | ".join(columns))  # Print header
        >> for row in rows:
        ...     print(" | ".join(str(val) for val in row))

        >> # Empty results still return column names
        >> columns, rows = execute_query_with_columns(
        ...     "SELECT tag, COUNT(*) as count FROM tags WHERE 1=0"
        ... )
        >> print(columns)  # ['tag', 'count']
        >> print(rows)     # []
    """
    with get_database_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        results = cursor.fetchall()
        column_names = (
            [description[0] for description in cursor.description] if cursor.description else []
        )
        return column_names, results


def execute_single(sql: str, params: Tuple = (), db_path: Optional[Path] = None) -> Tuple:
    """
    Execute SELECT query and return single result or empty tuple.

    Convenience function for queries expected to return zero or one row.

    Args:
        sql: SQL SELECT query
        params: Query parameters (use ? placeholders)
        db_path: Path to database file. If None, uses vault.db in vault root

    Returns:
        Single result tuple, or empty tuple if no results

    Raises:
        sqlite3.Error: On database or SQL errors

    Examples:
        >> # Get single row
        >> row = execute_single("SELECT * FROM tags WHERE tag = ?", ("mytag",))
        >> if row:
        ...     print(f"Found tag: {row[0]}")

        >> # Get count
        >> row = execute_single("SELECT COUNT(*) FROM files")
        >> count = row[0] if row else 0

        >> # Check existence
        >> exists = bool(execute_single(
        ...     "SELECT 1 FROM files WHERE path = ?",
        ...     ("note.md",)
        ... ))
    """
    with get_database_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        result = cursor.fetchone()
        return result if result is not None else ()


def execute_write(sql: str, params: Tuple = (), db_path: Optional[Path] = None) -> int:
    """
    Execute INSERT/UPDATE/DELETE and return affected row count.

    Automatically commits the transaction.

    Args:
        sql: SQL INSERT/UPDATE/DELETE query
        params: Query parameters (use ? placeholders)
        db_path: Path to database file. If None, uses vault.db in vault root

    Returns:
        Number of affected rows

    Raises:
        sqlite3.Error: On database or SQL errors

    Examples:
        >> # Insert row
        >> rows = execute_write(
        ...     "INSERT INTO tags (tag) VALUES (?)",
        ...     ("newtag",)
        ... )
        >> print(f"Inserted {rows} row(s)")

        >> # Update rows
        >> rows = execute_write(
        ...     "UPDATE file_tags SET tag = ? WHERE tag = ?",
        ...     ("project/new", "project/old")
        ... )
        >> print(f"Updated {rows} row(s)")

        >> # Delete rows
        >> rows = execute_write(
        ...     "DELETE FROM file_tags WHERE tag = ?",
        ...     ("oldtag",)
        ... )
    """
    with get_database_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount


def execute_many(sql: str, param_list: List[Tuple], db_path: Optional[Path] = None) -> int:
    """
    Execute batch INSERT/UPDATE/DELETE operations.

    More efficient than multiple execute_write() calls as it uses
    a single transaction.

    Args:
        sql: SQL INSERT/UPDATE/DELETE query
        param_list: List of parameter tuples
        db_path: Path to database file. If None, uses vault.db in vault root

    Returns:
        Total number of affected rows

    Raises:
        sqlite3.Error: On database or SQL errors

    Examples:
        >> # Batch insert
        >> tags = [("tag1",), ("tag2",), ("tag3",)]
        >> rows = execute_many(
        ...     "INSERT INTO tags (tag) VALUES (?)",
        ...     tags
        ... )
        >> print(f"Inserted {rows} rows")

        >> # Batch update
        >> updates = [("new1", "old1"), ("new2", "old2")]
        >> rows = execute_many(
        ...     "UPDATE file_tags SET tag = ? WHERE tag = ?",
        ...     updates
        ... )
    """
    with get_database_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(sql, param_list)
        conn.commit()
        return cursor.rowcount


# ============================================================================
# Database Rebuild and Validation
# ============================================================================


def rebuild_vault_database(silent: bool = False) -> bool:
    """
    Rebuild the vault index database.

    This is a shared utility used by multiple commands that need to rebuild
    the database after making changes to vault files (e.g., purge, rename, normalize).

    Args:
        silent: If True, suppress all output

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
            print(f"\n{'=' * 60}")
            print("Rebuilding vault index database...")
            print(f"{'=' * 60}\n")

        # Create build command with all required arguments
        build_cmd = BuildCommand()
        build_args = Namespace(
            force=True,  # Force full rebuild
            incremental=False,  # Not incremental
            no_hash=False,  # Include hashing for duplicate detection
            max_hash_size=100,  # Default max hash size in MB
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


def get_database_stats(db_path: Optional[Path] = None) -> dict:
    """
    Get statistics about the vault database.

    Args:
        db_path: Path to vault.db file. If None, uses vault.db in vault root

    Returns:
        Dictionary with database statistics

    Example:
        >> from pathlib import Path
        >> from vault_manager.core.database import get_database_stats
        >> stats = get_database_stats(Path('vault.db'))
        >> print(f"Total files: {stats['total_files']}")
    """
    try:
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()

            stats = {}

            # Get total files
            cursor.execute("SELECT COUNT(*) FROM files")
            stats["total_files"] = cursor.fetchone()[0]

            # Get total tags
            cursor.execute("SELECT COUNT(DISTINCT tag) FROM file_tags")
            stats["total_tags"] = cursor.fetchone()[0]

            # Get total links
            cursor.execute("SELECT COUNT(*) FROM links")
            stats["total_links"] = cursor.fetchone()[0]

            # Get files with frontmatter
            cursor.execute("SELECT COUNT(*) FROM files WHERE has_frontmatter = 1")
            stats["files_with_frontmatter"] = cursor.fetchone()[0]

            # Get metadata
            cursor.execute("SELECT key, value FROM metadata")
            for key, value in cursor.fetchall():
                stats[key] = value

            return stats

    except Exception as e:
        return {"error": str(e)}


def database_exists(vault_root: Optional[Path] = None) -> bool:
    """
    Check if vault.db exists.

    Args:
        vault_root: Path to vault root directory. If None, uses get_vault_root()

    Returns:
        True if database exists, False otherwise
    """
    db_path = get_database_path(vault_root)
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
    skip: bool = False, message: Optional[str] = None, silent: bool = False
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


def auto_rebuild_after():
    """
    Decorator to auto-rebuild database after command execution.

    This decorator wraps command execute methods to automatically
    rebuild the database after the command completes, unless the
    --no-rebuild flag is set.

    Returns:
        Decorated function that rebuilds database after execution

    Examples:
        >> from vault_manager.core.database import auto_rebuild_after
        >> from vault_manager.core.command import Command
        >>
        >> class PurgeCommand(Command):
        ...     @auto_rebuild_after()
        ...     def execute(self, args):
        ...         # Remove tags from files
        ...         ...
        ...         # Database will be auto-rebuilt after this returns

        >> class RenameCommand(Command):
        ...     @auto_rebuild_after()
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
            skip_rebuild = getattr(args, "no_rebuild", False)
            rebuild_if_needed(skip=skip_rebuild)

            return result

        return wrapper

    return decorator
