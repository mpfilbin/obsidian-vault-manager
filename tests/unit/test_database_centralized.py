#!/usr/bin/env python3
"""
Unit tests for centralized database access utilities.

Tests all new database utilities in vault_manager.core.database including:
- Database path utilities
- Connection management
- Query helpers
- Transaction support
"""

import sqlite3

import pytest

from vault_manager.core.database import (
    configure_connection,
    ensure_database_path,
    execute_many,
    execute_query,
    execute_single,
    execute_write,
    get_database_connection,
    get_database_path,
    transaction,
)


class TestDatabasePathUtilities:
    """Test database path resolution and management."""

    def test_get_database_path_with_vault_root(self, temp_vault):
        """get_database_path should return vault.db in specified vault root."""
        db_path = get_database_path(temp_vault)
        assert db_path == temp_vault / 'vault.db'
        assert db_path.parent == temp_vault

    def test_get_database_path_without_vault_root(self, mock_vault_root):
        """get_database_path should use get_vault_root() when vault_root is None."""
        # mock_vault_root fixture already monkeypatches get_vault_root()
        db_path = get_database_path()
        assert db_path == mock_vault_root / 'vault.db'

    def test_ensure_database_path_creates_parent_directory(self, tmp_path):
        """ensure_database_path should create parent directory if it doesn't exist."""
        non_existent_vault = tmp_path / "new_vault"
        assert not non_existent_vault.exists()

        db_path = ensure_database_path(non_existent_vault)

        assert db_path == non_existent_vault / 'vault.db'
        assert non_existent_vault.exists()
        assert non_existent_vault.is_dir()

    def test_ensure_database_path_with_existing_directory(self, temp_vault):
        """ensure_database_path should work with existing directories."""
        db_path = ensure_database_path(temp_vault)

        assert db_path == temp_vault / 'vault.db'
        assert temp_vault.exists()


class TestConnectionConfiguration:
    """Test database connection configuration."""

    def test_configure_connection_enables_foreign_keys(self, temp_vault):
        """configure_connection should enable foreign keys pragma."""
        db_path = temp_vault / 'test.db'
        conn = sqlite3.connect(str(db_path))

        # Foreign keys are disabled by default
        cursor = conn.cursor()
        cursor.execute('PRAGMA foreign_keys')
        assert cursor.fetchone()[0] == 0

        # Configure should enable them
        configure_connection(conn)

        cursor.execute('PRAGMA foreign_keys')
        assert cursor.fetchone()[0] == 1

        conn.close()


class TestDatabaseConnection:
    """Test get_database_connection context manager."""

    def test_connection_opens_and_closes(self, temp_vault):
        """Connection should be open inside context and closed after."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            # Connection should be open
            assert isinstance(conn, sqlite3.Connection)
            # Should be able to execute queries
            conn.execute("SELECT 1")

        # Connection should be closed after context (accessing it should fail)
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_connection_enables_foreign_keys(self, temp_vault):
        """Connection should have foreign keys enabled automatically."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('PRAGMA foreign_keys')
            assert cursor.fetchone()[0] == 1

    def test_connection_uses_default_path(self, mock_vault_root):
        """Connection should use vault.db from vault root when db_path is None."""
        # mock_vault_root fixture already monkeypatches get_vault_root()
        db_path = mock_vault_root / 'vault.db'

        # Create empty database
        db_path.touch()

        with get_database_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_connection_closes_on_error(self, temp_vault):
        """Connection should close even when error occurs."""
        db_path = temp_vault / 'test.db'

        conn_ref = None
        try:
            with get_database_connection(db_path) as conn:
                conn_ref = conn
                raise ValueError("Test error")
        except ValueError:
            pass

        # Connection should still be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn_ref.execute("SELECT 1")

    def test_read_only_mode(self, temp_vault):
        """Connection should reject writes in read-only mode."""
        db_path = temp_vault / 'test.db'

        # Create database with table
        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        # Open in read-only mode
        with get_database_connection(db_path, read_only=True) as conn:
            # Read should work
            conn.execute("SELECT * FROM test")

            # Write should fail
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("INSERT INTO test (id) VALUES (1)")

    def test_read_only_mode_nonexistent_database(self, temp_vault):
        """Read-only mode should raise FileNotFoundError for nonexistent database."""
        db_path = temp_vault / 'nonexistent.db'

        with pytest.raises(FileNotFoundError):
            with get_database_connection(db_path, read_only=True) as conn:
                pass


class TestTransaction:
    """Test transaction context manager."""

    def test_transaction_commits_on_success(self, temp_vault):
        """Transaction should commit changes on successful exit."""
        db_path = temp_vault / 'test.db'

        # Create table
        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        # Insert in transaction
        with transaction(db_path) as conn:
            conn.execute("INSERT INTO test (id, value) VALUES (?, ?)", (1, "test"))

        # Verify commit occurred
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM test WHERE id = 1")
            assert cursor.fetchone()[0] == "test"

    def test_transaction_rolls_back_on_error(self, temp_vault):
        """Transaction should rollback changes on exception."""
        db_path = temp_vault / 'test.db'

        # Create table
        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        # Try transaction that fails
        try:
            with transaction(db_path) as conn:
                conn.execute("INSERT INTO test (id, value) VALUES (?, ?)", (1, "test"))
                # Force an error
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Verify rollback occurred (table should be empty)
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 0

    def test_transaction_atomic_multi_insert(self, temp_vault):
        """Transaction should make multiple operations atomic."""
        db_path = temp_vault / 'test.db'

        # Create tables
        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE tags (tag TEXT PRIMARY KEY)")
            conn.execute("CREATE TABLE file_tags (file_path TEXT, tag TEXT)")
            conn.commit()

        # Atomic insert into both tables
        with transaction(db_path) as conn:
            conn.execute("INSERT INTO tags (tag) VALUES (?)", ("newtag",))
            conn.execute("INSERT INTO file_tags (file_path, tag) VALUES (?, ?)",
                        ("note.md", "newtag"))

        # Verify both inserts succeeded
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tags")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT COUNT(*) FROM file_tags")
            assert cursor.fetchone()[0] == 1

    def test_transaction_uses_default_path(self, mock_vault_root):
        """Transaction should use vault.db from vault root when db_path is None."""
        # mock_vault_root fixture already monkeypatches get_vault_root()
        db_path = mock_vault_root / 'vault.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        with transaction() as conn:
            conn.execute("INSERT INTO test (id) VALUES (1)")

        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 1


class TestExecuteQuery:
    """Test execute_query helper function."""

    def test_execute_query_returns_all_rows(self, temp_vault):
        """execute_query should return all matching rows."""
        db_path = temp_vault / 'test.db'

        # Setup database
        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'a'), (2, 'b'), (3, 'c')")
            conn.commit()

        # Query all rows
        results = execute_query("SELECT * FROM test ORDER BY id", db_path=db_path)

        assert len(results) == 3
        assert results[0] == (1, 'a')
        assert results[1] == (2, 'b')
        assert results[2] == (3, 'c')

    def test_execute_query_with_parameters(self, temp_vault):
        """execute_query should support parameterized queries."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'a'), (2, 'b'), (3, 'c')")
            conn.commit()

        results = execute_query(
            "SELECT * FROM test WHERE id > ? ORDER BY id",
            (1,),
            db_path=db_path
        )

        assert len(results) == 2
        assert results[0] == (2, 'b')
        assert results[1] == (3, 'c')

    def test_execute_query_empty_results(self, temp_vault):
        """execute_query should return empty list when no matches."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        results = execute_query("SELECT * FROM test", db_path=db_path)

        assert results == []


class TestExecuteSingle:
    """Test execute_single helper function."""

    def test_execute_single_returns_one_row(self, temp_vault):
        """execute_single should return single matching row."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'a'), (2, 'b')")
            conn.commit()

        result = execute_single(
            "SELECT value FROM test WHERE id = ?",
            (1,),
            db_path=db_path
        )

        assert result == ('a',)

    def test_execute_single_returns_empty_tuple_when_no_match(self, temp_vault):
        """execute_single should return empty tuple when no matching rows."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        result = execute_single(
            "SELECT value FROM test WHERE id = ?",
            (99,),
            db_path=db_path
        )

        assert result == ()
        assert len(result) == 0

    def test_execute_single_with_count(self, temp_vault):
        """execute_single should work for aggregate queries like COUNT."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1), (2), (3)")
            conn.commit()

        result = execute_single("SELECT COUNT(*) FROM test", db_path=db_path)

        assert result == (3,)


class TestExecuteWrite:
    """Test execute_write helper function."""

    def test_execute_write_insert(self, temp_vault):
        """execute_write should insert rows and return count."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        rows = execute_write(
            "INSERT INTO test (id, value) VALUES (?, ?)",
            (1, "test"),
            db_path=db_path
        )

        assert rows == 1

        # Verify insert
        result = execute_single("SELECT value FROM test WHERE id = 1", db_path=db_path)
        assert result == ("test",)

    def test_execute_write_update(self, temp_vault):
        """execute_write should update rows and return count."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'old'), (2, 'old')")
            conn.commit()

        rows = execute_write(
            "UPDATE test SET value = ? WHERE value = ?",
            ("new", "old"),
            db_path=db_path
        )

        assert rows == 2

        # Verify update
        results = execute_query("SELECT value FROM test", db_path=db_path)
        assert all(r[0] == 'new' for r in results)

    def test_execute_write_delete(self, temp_vault):
        """execute_write should delete rows and return count."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'a'), (2, 'b'), (3, 'c')")
            conn.commit()

        rows = execute_write(
            "DELETE FROM test WHERE id > ?",
            (1,),
            db_path=db_path
        )

        assert rows == 2

        # Verify deletion
        result = execute_single("SELECT COUNT(*) FROM test", db_path=db_path)
        assert result == (1,)

    def test_execute_write_commits_automatically(self, temp_vault):
        """execute_write should automatically commit changes."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        execute_write(
            "INSERT INTO test (id, value) VALUES (?, ?)",
            (1, "test"),
            db_path=db_path
        )

        # Open new connection to verify commit
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 1


class TestExecuteMany:
    """Test execute_many helper function."""

    def test_execute_many_batch_insert(self, temp_vault):
        """execute_many should insert multiple rows efficiently."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        data = [(1, 'a'), (2, 'b'), (3, 'c')]
        rows = execute_many(
            "INSERT INTO test (id, value) VALUES (?, ?)",
            data,
            db_path=db_path
        )

        assert rows == 3

        # Verify all inserts
        results = execute_query("SELECT * FROM test ORDER BY id", db_path=db_path)
        assert len(results) == 3
        assert results == data

    def test_execute_many_batch_update(self, temp_vault):
        """execute_many should update multiple rows efficiently."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'a'), (2, 'b'), (3, 'c')")
            conn.commit()

        updates = [('A', 1), ('B', 2), ('C', 3)]
        rows = execute_many(
            "UPDATE test SET value = ? WHERE id = ?",
            updates,
            db_path=db_path
        )

        assert rows == 3

        # Verify updates
        results = execute_query("SELECT value FROM test ORDER BY id", db_path=db_path)
        assert results == [('A',), ('B',), ('C',)]

    def test_execute_many_empty_list(self, temp_vault):
        """execute_many should handle empty parameter list."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        rows = execute_many(
            "INSERT INTO test (id, value) VALUES (?, ?)",
            [],
            db_path=db_path
        )

        # SQLite executemany with empty list returns -1
        assert rows == -1 or rows == 0

    def test_execute_many_commits_automatically(self, temp_vault):
        """execute_many should automatically commit all changes."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.commit()

        data = [(1, 'a'), (2, 'b')]
        execute_many(
            "INSERT INTO test (id, value) VALUES (?, ?)",
            data,
            db_path=db_path
        )

        # Open new connection to verify commit
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 2
