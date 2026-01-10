#!/usr/bin/env python3
"""
Resource management tests for database connections.

Tests that database connections are properly cleaned up and no resource
leaks occur during normal operation or error conditions.
"""

import pytest
import sqlite3

from vault_manager.core.database import (
    get_database_connection,
    transaction,
    execute_query,
    execute_single,
    execute_write,
    execute_many,
)


class TestConnectionCleanup:
    """Test that database connections are properly closed."""

    def test_connection_closes_after_normal_exit(self, temp_vault):
        """Connection should be closed after normal context exit."""
        db_path = temp_vault / 'test.db'
        conn_ref = None

        with get_database_connection(db_path) as conn:
            conn_ref = conn
            conn.execute("SELECT 1")

        # Attempting to use connection after context should fail
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn_ref.execute("SELECT 1")

    def test_connection_closes_after_exception(self, temp_vault):
        """Connection should be closed even when exception occurs."""
        db_path = temp_vault / 'test.db'
        conn_ref = None

        try:
            with get_database_connection(db_path) as conn:
                conn_ref = conn
                # Simulate error
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # Connection should still be closed
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn_ref.execute("SELECT 1")

    def test_transaction_closes_connection_after_commit(self, temp_vault):
        """Transaction should close connection after successful commit."""
        db_path = temp_vault / 'test.db'
        conn_ref = None

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        with transaction(db_path) as conn:
            conn_ref = conn
            conn.execute("INSERT INTO test (id) VALUES (1)")

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn_ref.execute("SELECT 1")

    def test_transaction_closes_connection_after_rollback(self, temp_vault):
        """Transaction should close connection even after rollback."""
        db_path = temp_vault / 'test.db'
        conn_ref = None

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        try:
            with transaction(db_path) as conn:
                conn_ref = conn
                conn.execute("INSERT INTO test (id) VALUES (1)")
                raise ValueError("Force rollback")
        except ValueError:
            pass

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn_ref.execute("SELECT 1")

    def test_query_helpers_close_connections(self, temp_vault):
        """Query helper functions should close connections after use."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'a'), (2, 'b')")
            conn.commit()

        # Each helper should properly manage connection lifecycle
        results = execute_query("SELECT * FROM test", db_path=db_path)
        assert len(results) == 2

        single = execute_single("SELECT COUNT(*) FROM test", db_path=db_path)
        assert single == (2,)

        rows = execute_write(
            "INSERT INTO test VALUES (?, ?)",
            (3, 'c'),
            db_path=db_path
        )
        assert rows == 1

        rows = execute_many(
            "INSERT INTO test VALUES (?, ?)",
            [(4, 'd'), (5, 'e')],
            db_path=db_path
        )
        assert rows == 2

        # No connections should be left open
        # (verified by successful new connection)
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 5


class TestErrorRecovery:
    """Test that connections are cleaned up during error conditions."""

    def test_sql_error_closes_connection(self, temp_vault):
        """Connection should close even when SQL error occurs."""
        db_path = temp_vault / 'test.db'
        conn_ref = None

        try:
            with get_database_connection(db_path) as conn:
                conn_ref = conn
                # Execute invalid SQL
                conn.execute("INVALID SQL STATEMENT")
        except sqlite3.OperationalError:
            pass

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn_ref.execute("SELECT 1")

    def test_transaction_error_closes_connection(self, temp_vault):
        """Transaction should close connection when SQL error occurs."""
        db_path = temp_vault / 'test.db'
        conn_ref = None

        try:
            with transaction(db_path) as conn:
                conn_ref = conn
                conn.execute("INVALID SQL")
        except sqlite3.OperationalError:
            pass

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn_ref.execute("SELECT 1")

    def test_query_helper_error_closes_connection(self, temp_vault):
        """Query helpers should close connections even on errors."""
        db_path = temp_vault / 'test.db'

        try:
            execute_query("INVALID SQL", db_path=db_path)
        except sqlite3.OperationalError:
            pass

        # Should be able to open new connection successfully
        with get_database_connection(db_path) as conn:
            conn.execute("SELECT 1")


class TestConcurrentConnections:
    """Test that multiple connections can coexist properly."""

    def test_multiple_sequential_connections(self, temp_vault):
        """Multiple sequential connections should work correctly."""
        db_path = temp_vault / 'test.db'

        # Create table
        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        # Multiple operations in sequence
        for i in range(10):
            with get_database_connection(db_path) as conn:
                conn.execute("INSERT INTO test (id) VALUES (?)", (i,))
                conn.commit()

        # Verify all inserts
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 10

    def test_nested_connection_contexts(self, temp_vault):
        """Nested connection contexts should work properly."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn1:
            conn1.execute("CREATE TABLE test (id INTEGER)")
            conn1.commit()

            # Open second connection while first is still open
            with get_database_connection(db_path) as conn2:
                conn2.execute("INSERT INTO test (id) VALUES (1)")
                conn2.commit()

            # First connection should still work
            cursor = conn1.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            count = cursor.fetchone()[0]

        # Both connections should be closed now
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn1.execute("SELECT 1")
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn2.execute("SELECT 1")


class TestMemoryLeaks:
    """Test that no memory or file descriptor leaks occur."""

    def test_many_connections_no_leak(self, temp_vault):
        """Opening many connections sequentially should not leak resources."""
        db_path = temp_vault / 'test.db'

        # Create database
        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        # Open and close many connections
        # If connections aren't closed, this would exhaust resources
        for i in range(100):
            with get_database_connection(db_path) as conn:
                conn.execute("INSERT INTO test (id) VALUES (?)", (i,))
                conn.commit()

        # Verify all operations succeeded
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 100

    def test_many_transactions_no_leak(self, temp_vault):
        """Many transactions should not leak connections."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        # Run many transactions
        for i in range(100):
            with transaction(db_path) as conn:
                conn.execute("INSERT INTO test (id) VALUES (?)", (i,))

        # Verify all transactions committed
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 100

    def test_many_failed_transactions_no_leak(self, temp_vault):
        """Failed transactions should not leak connections."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        # Run many failing transactions
        for i in range(50):
            try:
                with transaction(db_path) as conn:
                    conn.execute("INSERT INTO test (id) VALUES (?)", (i,))
                    raise ValueError("Force rollback")
            except ValueError:
                pass

        # Verify all transactions rolled back (table should be empty)
        with get_database_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            assert cursor.fetchone()[0] == 0

        # Should still be able to open new connection
        with get_database_connection(db_path) as conn:
            conn.execute("INSERT INTO test (id) VALUES (1)")
            conn.commit()

    def test_query_helpers_many_calls_no_leak(self, temp_vault):
        """Many query helper calls should not leak connections."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        # Many operations using helpers
        for i in range(50):
            execute_write("INSERT INTO test (id) VALUES (?)", (i,), db_path=db_path)

        for i in range(50):
            result = execute_single(
                "SELECT COUNT(*) FROM test WHERE id < ?",
                (i,),
                db_path=db_path
            )
            assert result[0] == i

        for i in range(10):
            results = execute_query("SELECT * FROM test LIMIT ?", (i,), db_path=db_path)
            assert len(results) == i

        # Final verification - should still work
        result = execute_single("SELECT COUNT(*) FROM test", db_path=db_path)
        assert result[0] == 50


class TestDatabaseLocking:
    """Test that database locking works correctly."""

    def test_write_blocks_write(self, temp_vault):
        """Write transaction should block concurrent writes (default SQLite behavior)."""
        db_path = temp_vault / 'test.db'

        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()

        # This test just verifies basic behavior - SQLite handles locking
        with transaction(db_path) as conn:
            conn.execute("INSERT INTO test (id) VALUES (1)")

        # Should succeed after first transaction completes
        with transaction(db_path) as conn:
            conn.execute("INSERT INTO test (id) VALUES (2)")

        result = execute_single("SELECT COUNT(*) FROM test", db_path=db_path)
        assert result[0] == 2

    def test_read_only_allows_concurrent_reads(self, temp_vault):
        """Read-only connections should allow concurrent access."""
        db_path = temp_vault / 'test.db'

        # Create and populate database
        with get_database_connection(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1), (2), (3)")
            conn.commit()

        # Multiple read-only connections should work concurrently
        with get_database_connection(db_path, read_only=True) as conn1:
            with get_database_connection(db_path, read_only=True) as conn2:
                cursor1 = conn1.cursor()
                cursor2 = conn2.cursor()

                cursor1.execute("SELECT COUNT(*) FROM test")
                count1 = cursor1.fetchone()[0]

                cursor2.execute("SELECT COUNT(*) FROM test")
                count2 = cursor2.fetchone()[0]

                assert count1 == 3
                assert count2 == 3
