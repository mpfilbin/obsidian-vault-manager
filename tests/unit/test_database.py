"""
Unit tests for database utilities module.

Tests database operations including:
- rebuild_vault_database(): rebuilding the vault index
- get_database_stats(): querying database statistics
- database_exists(): checking database presence
- require_database(): validating database exists before command execution
"""

import pytest
import sqlite3
from pathlib import Path
from argparse import Namespace
from vault_manager.core.database import (
    rebuild_vault_database,
    get_database_stats,
    database_exists,
    require_database,
    rebuild_if_needed,
    auto_rebuild_after,
)


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault directory."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture
def vault_database(temp_vault):
    """Create a vault.db database with sample data."""
    db_path = temp_vault / "vault.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create schema that mirrors vault/vault.db
    cursor.execute("""
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE files (
            file_path TEXT PRIMARY KEY,
            size_bytes INTEGER NOT NULL,
            content_hash TEXT,
            last_modified TEXT NOT NULL,
            created TEXT,
            has_frontmatter INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE tags (
            tag TEXT PRIMARY KEY
        )
    """)

    cursor.execute("""
        CREATE TABLE file_tags (
            tag TEXT NOT NULL,
            file_path TEXT NOT NULL,
            PRIMARY KEY (tag, file_path),
            FOREIGN KEY (tag) REFERENCES tags(tag) ON DELETE CASCADE,
            FOREIGN KEY (file_path) REFERENCES files(file_path) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            target_file TEXT,
            link_type TEXT NOT NULL,
            link_text TEXT,
            line_number INTEGER,
            FOREIGN KEY (source_file) REFERENCES files(file_path) ON DELETE CASCADE,
            FOREIGN KEY (target_file) REFERENCES files(file_path) ON DELETE SET NULL
        )
    """)

    # Insert sample data using explicit column lists
    cursor.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("last_updated", "2026-01-06")
    )

    files_rows = [
        ("note1.md", 1000, "hash1", "2026-01-06T00:00:00", None, 1),
        ("note2.md", 2000, "hash2", "2026-01-06T00:00:01", None, 1),
        ("note3.md", 1500, "hash3", "2026-01-06T00:00:02", None, 0),
    ]
    cursor.executemany(
        """
        INSERT INTO files (file_path, size_bytes, content_hash, last_modified, created, has_frontmatter)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        files_rows
    )

    cursor.executemany(
        "INSERT INTO tags (tag) VALUES (?)",
        [("test",), ("vault",)]
    )

    cursor.executemany(
        "INSERT INTO file_tags (tag, file_path) VALUES (?, ?)",
        [("test", "note1.md"), ("vault", "note1.md"), ("test", "note2.md")]
    )

    cursor.executemany(
        """
        INSERT INTO links (source_file, target_file, link_type, link_text, line_number)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            ("note1.md", "note2.md", "wikilink", "note2", 3),
            ("note2.md", "note3.md", "wikilink", "note3", 3),
        ]
    )

    conn.commit()
    conn.close()

    return db_path


@pytest.mark.unit
class TestDatabaseExists:
    """Tests for database_exists() function."""

    def test_database_exists_true(self, vault_database, temp_vault):
        """Test database_exists returns True when database exists."""
        assert database_exists(temp_vault) is True

    def test_database_exists_false(self, temp_vault):
        """Test database_exists returns False when database doesn't exist."""
        assert database_exists(temp_vault) is False

    def test_database_exists_with_path_object(self, vault_database, temp_vault):
        """Test database_exists works with Path object."""
        assert database_exists(Path(temp_vault)) is True


@pytest.mark.unit
class TestGetDatabaseStats:
    """Tests for get_database_stats() function."""

    def test_get_stats_basic(self, vault_database):
        """Test getting basic database statistics."""
        stats = get_database_stats(vault_database)

        assert stats['total_files'] == 3
        assert stats['total_tags'] == 2  # distinct: test, vault
        assert stats['total_links'] == 2
        assert stats['files_with_frontmatter'] == 2

    def test_get_stats_includes_metadata(self, vault_database):
        """Test that metadata is included in stats."""
        stats = get_database_stats(vault_database)

        assert 'last_updated' in stats
        assert stats['last_updated'] == '2026-01-06'

    def test_get_stats_nonexistent_database(self, tmp_path):
        """Test get_database_stats with nonexistent database."""
        nonexistent_db = tmp_path / "nonexistent.db"
        stats = get_database_stats(nonexistent_db)

        assert 'error' in stats
        assert isinstance(stats['error'], str)

    def test_get_stats_empty_database(self, temp_vault):
        """Test get_database_stats with empty database."""
        db_path = temp_vault / "empty.db"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create schema matching actual vault.db structure
        cursor.execute("""
            CREATE TABLE files (
                file_path TEXT PRIMARY KEY,
                has_frontmatter INTEGER DEFAULT 0
            )
        """)
        cursor.execute("CREATE TABLE file_tags (tag TEXT)")
        cursor.execute("CREATE TABLE links (source_file TEXT)")
        cursor.execute("CREATE TABLE metadata (key TEXT, value TEXT)")

        conn.commit()
        conn.close()

        stats = get_database_stats(db_path)

        assert stats['total_files'] == 0
        assert stats['total_tags'] == 0
        assert stats['total_links'] == 0
        assert stats['files_with_frontmatter'] == 0


@pytest.mark.unit
class TestRequireDatabase:
    """Tests for require_database() function."""

    def test_require_database_exists(self, vault_database, temp_vault, capsys):
        """Test require_database when database exists (should not exit)."""
        # Should not raise SystemExit
        require_database(temp_vault)

        # Should not print anything
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_require_database_missing(self, temp_vault, capsys):
        """Test require_database when database is missing (should exit)."""
        with pytest.raises(SystemExit) as exc_info:
            require_database(temp_vault)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "vault.db not found" in captured.out
        assert "vault tags update" in captured.out

    def test_require_database_custom_command_name(self, temp_vault, capsys):
        """Test require_database with custom command name in error."""
        with pytest.raises(SystemExit):
            require_database(temp_vault, command_name="custom-query")

        captured = capsys.readouterr()
        assert "custom-query" in captured.out


@pytest.mark.unit
class TestRebuildVaultDatabase:
    """Tests for rebuild_vault_database() function."""

    def test_rebuild_silent_mode(self, temp_vault, monkeypatch, capsys):
        """Test rebuild in silent mode suppresses output."""
        # Mock the BuildCommand
        class MockBuildCommand:
            def execute(self, args):
                pass

        # Mock the import
        import vault_manager.index.commands.build as build_module
        monkeypatch.setattr(build_module, 'BuildCommand', MockBuildCommand)

        result = rebuild_vault_database(silent=True)

        assert result is True
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_rebuild_verbose_mode(self, temp_vault, monkeypatch, capsys):
        """Test rebuild in verbose mode shows output."""
        # Mock the BuildCommand
        class MockBuildCommand:
            def execute(self, args):
                pass

        # Mock the import
        import vault_manager.index.commands.build as build_module
        monkeypatch.setattr(build_module, 'BuildCommand', MockBuildCommand)

        result = rebuild_vault_database(silent=False, verbose=False)

        assert result is True
        captured = capsys.readouterr()
        assert "Rebuilding vault index database" in captured.out
        assert "Database updated successfully" in captured.out

    def test_rebuild_creates_correct_args(self, temp_vault, monkeypatch):
        """Test rebuild creates correct arguments for BuildCommand."""
        received_args = []

        class MockBuildCommand:
            def execute(self, args):
                received_args.append(args)

        # Mock the import
        import vault_manager.index.commands.build as build_module
        monkeypatch.setattr(build_module, 'BuildCommand', MockBuildCommand)

        rebuild_vault_database(silent=True)

        assert len(received_args) == 1
        args = received_args[0]
        assert args.force is True
        assert args.incremental is False
        assert args.no_hash is False
        assert args.max_hash_size == 100

    def test_rebuild_handles_exception(self, temp_vault, monkeypatch, capsys):
        """Test rebuild handles exceptions gracefully."""
        # Mock the BuildCommand to raise an exception
        class MockBuildCommand:
            def execute(self, args):
                raise RuntimeError("Build failed")

        # Mock the import
        import vault_manager.index.commands.build as build_module
        monkeypatch.setattr(build_module, 'BuildCommand', MockBuildCommand)

        result = rebuild_vault_database(silent=False)

        assert result is False
        captured = capsys.readouterr()
        assert "Failed to rebuild database" in captured.out
        assert "vault index build" in captured.out

    def test_rebuild_exception_silent(self, temp_vault, monkeypatch, capsys):
        """Test rebuild exception handling in silent mode."""
        # Mock the BuildCommand to raise an exception
        class MockBuildCommand:
            def execute(self, args):
                raise RuntimeError("Build failed")

        # Mock the import
        import vault_manager.index.commands.build as build_module
        monkeypatch.setattr(build_module, 'BuildCommand', MockBuildCommand)

        result = rebuild_vault_database(silent=True)

        assert result is False
        captured = capsys.readouterr()
        assert captured.out == ""


@pytest.mark.unit
class TestRebuildIfNeeded:
    """Tests for rebuild_if_needed() function."""

    def test_rebuild_if_needed_normal(self, monkeypatch, capsys):
        """Test rebuild_if_needed performs rebuild when skip=False."""
        # Mock rebuild_vault_database
        rebuild_called = []

        def mock_rebuild(silent=False, verbose=False):
            rebuild_called.append(True)
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        result = rebuild_if_needed(skip=False)

        assert result is True
        assert len(rebuild_called) == 1

    def test_rebuild_if_needed_skip(self, monkeypatch, capsys):
        """Test rebuild_if_needed skips rebuild when skip=True."""
        # Mock rebuild_vault_database
        rebuild_called = []

        def mock_rebuild(silent=False, verbose=False):
            rebuild_called.append(True)
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        result = rebuild_if_needed(skip=True)

        assert result is True
        assert len(rebuild_called) == 0  # Not called

        captured = capsys.readouterr()
        assert "Database Rebuild Skipped" in captured.out
        assert "vault.db database was NOT updated" in captured.out

    def test_rebuild_if_needed_skip_with_custom_message(self, monkeypatch, capsys):
        """Test rebuild_if_needed with custom skip message."""
        # Mock rebuild_vault_database
        def mock_rebuild(silent=False, verbose=False):
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        custom_msg = "Custom skip message for testing"
        result = rebuild_if_needed(skip=True, message=custom_msg)

        assert result is True

        captured = capsys.readouterr()
        assert custom_msg in captured.out

    def test_rebuild_if_needed_silent(self, monkeypatch, capsys):
        """Test rebuild_if_needed in silent mode."""
        # Mock rebuild_vault_database
        def mock_rebuild(silent=False, verbose=False):
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        # Silent mode, no skip
        result = rebuild_if_needed(skip=False, silent=True)
        assert result is True

        # Silent mode, with skip
        result = rebuild_if_needed(skip=True, silent=True)
        assert result is True

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_rebuild_if_needed_rebuild_fails(self, monkeypatch, capsys):
        """Test rebuild_if_needed when rebuild fails."""
        # Mock rebuild_vault_database to fail
        def mock_rebuild(silent=False, verbose=False):
            return False

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        result = rebuild_if_needed(skip=False, silent=True)

        assert result is False


@pytest.mark.unit
class TestAutoRebuildAfter:
    """Tests for auto_rebuild_after() decorator."""

    def test_decorator_rebuilds_after_execution(self, monkeypatch):
        """Test decorator rebuilds database after command executes."""
        # Mock rebuild_vault_database
        rebuild_called = []

        def mock_rebuild(silent=False, verbose=False):
            rebuild_called.append(True)
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        # Create mock command with decorated execute method
        class MockCommand:
            @auto_rebuild_after("test operation")
            def execute(self, args):
                return "command executed"

        args = Namespace(no_rebuild=False)
        cmd = MockCommand()
        result = cmd.execute(args)

        assert result == "command executed"
        assert len(rebuild_called) == 1

    def test_decorator_skips_rebuild_when_flag_set(self, monkeypatch, capsys):
        """Test decorator skips rebuild when no_rebuild=True."""
        # Mock rebuild_vault_database
        rebuild_called = []

        def mock_rebuild(silent=False, verbose=False):
            rebuild_called.append(True)
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        # Create mock command with decorated execute method
        class MockCommand:
            @auto_rebuild_after("test operation")
            def execute(self, args):
                return "command executed"

        args = Namespace(no_rebuild=True)
        cmd = MockCommand()
        result = cmd.execute(args)

        assert result == "command executed"
        assert len(rebuild_called) == 0  # Not called

        captured = capsys.readouterr()
        assert "Database Rebuild Skipped" in captured.out

    def test_decorator_handles_missing_no_rebuild_flag(self, monkeypatch):
        """Test decorator handles args without no_rebuild attribute."""
        # Mock rebuild_vault_database
        rebuild_called = []

        def mock_rebuild(silent=False, verbose=False):
            rebuild_called.append(True)
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        # Create mock command with decorated execute method
        class MockCommand:
            @auto_rebuild_after("test operation")
            def execute(self, args):
                return "command executed"

        # Args without no_rebuild attribute
        args = Namespace()
        cmd = MockCommand()
        result = cmd.execute(args)

        assert result == "command executed"
        assert len(rebuild_called) == 1  # Should rebuild (default behavior)

    def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves original function metadata."""
        def original_execute(self, args):
            """Original docstring."""
            pass

        decorated = auto_rebuild_after("test")(original_execute)

        assert decorated.__name__ == "original_execute"
        assert decorated.__doc__ == "Original docstring."

    def test_decorator_with_exception_in_command(self, monkeypatch):
        """Test decorator still rebuilds even if command raises exception."""
        # Mock rebuild_vault_database
        rebuild_called = []

        def mock_rebuild(silent=False, verbose=False):
            rebuild_called.append(True)
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        # Create mock command that raises exception
        class MockCommand:
            @auto_rebuild_after("test operation")
            def execute(self, args):
                raise ValueError("Command failed")

        args = Namespace(no_rebuild=False)
        cmd = MockCommand()

        # Command should still raise the exception
        with pytest.raises(ValueError, match="Command failed"):
            cmd.execute(args)

        # But rebuild should NOT have been called (exception prevents completion)
        assert len(rebuild_called) == 0


@pytest.mark.unit
class TestIntegration:
    """Integration tests for database utilities."""

    def test_full_workflow(self, temp_vault, vault_database):
        """Test full workflow: check exists, get stats, require."""
        # Database exists
        assert database_exists(temp_vault) is True

        # Get stats
        stats = get_database_stats(vault_database)
        assert stats['total_files'] > 0

        # Require database (should not exit)
        require_database(temp_vault)

    def test_missing_database_workflow(self, temp_vault, capsys):
        """Test workflow with missing database."""
        # Database doesn't exist
        assert database_exists(temp_vault) is False

        # Get stats should return error
        db_path = temp_vault / "vault.db"
        stats = get_database_stats(db_path)
        assert 'error' in stats

        # Remove the database file that sqlite3.connect() created
        if db_path.exists():
            db_path.unlink()

        # Require database should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            require_database(temp_vault)

        assert exc_info.value.code == 1

        # Should show helpful error message
        captured = capsys.readouterr()
        assert "vault.db not found" in captured.out

    def test_rebuild_if_needed_workflow(self, monkeypatch):
        """Test rebuild_if_needed integrates correctly."""
        rebuild_called = []

        def mock_rebuild(silent=False, verbose=False):
            rebuild_called.append({'silent': silent, 'verbose': verbose})
            return True

        monkeypatch.setattr("vault_manager.core.database.rebuild_vault_database", mock_rebuild)

        # Normal rebuild
        rebuild_if_needed(skip=False)
        assert len(rebuild_called) == 1

        # Skip rebuild
        rebuild_if_needed(skip=True)
        assert len(rebuild_called) == 1  # Still only 1 (skipped)

        # Silent rebuild
        rebuild_if_needed(skip=False, silent=True)
        assert len(rebuild_called) == 2
        assert rebuild_called[1]['silent'] is True
