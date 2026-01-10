"""
Unit tests for file operations module.

Tests safe file I/O operations including:
- safe_read(): reading files with error handling
- safe_write(): writing files with dry-run support
- atomic_update(): atomic read-update-write pattern
- safe_move(): moving/renaming files
"""

import pytest
from vault_manager.core.file_ops import (
    safe_read,
    safe_write,
    atomic_update,
    safe_move,
)


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file with sample content."""
    file_path = tmp_path / "test.md"
    file_path.write_text("# Test Note\n\nSome content.\n", encoding='utf-8')
    return file_path


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory."""
    return tmp_path

@pytest.mark.unit
class TestSafeRead:
    """Tests for safe_read() function."""

    def test_read_existing_file(self, temp_file):
        """Test reading an existing file."""
        content = safe_read(temp_file)
        assert content is not None
        assert content == "# Test Note\n\nSome content.\n"

    def test_read_nonexistent_file(self, temp_dir):
        """Test reading a file that doesn't exist."""
        nonexistent = temp_dir / "nonexistent.md"
        content = safe_read(nonexistent)
        assert content is None

    def test_read_nonexistent_file_silent(self, temp_dir, capsys):
        """Test silent mode suppresses error messages."""
        nonexistent = temp_dir / "nonexistent.md"
        content = safe_read(nonexistent, silent=True)
        assert content is None
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_read_with_custom_error_handler(self, temp_dir):
        """Test custom error handler is called."""
        errors = []

        def error_handler(path, error):
            errors.append((path, type(error).__name__))

        nonexistent = temp_dir / "nonexistent.md"
        content = safe_read(nonexistent, on_error=error_handler, silent=True)

        assert content is None
        assert len(errors) == 1
        assert errors[0][0] == nonexistent
        assert errors[0][1] == "FileNotFoundError"

    def test_read_permission_denied(self, temp_file):
        """Test handling of permission denied errors."""
        # Make file unreadable
        temp_file.chmod(0o000)

        try:
            content = safe_read(temp_file, silent=True)
            assert content is None
        finally:
            # Restore permissions for cleanup
            temp_file.chmod(0o644)

    def test_read_unicode_error(self, temp_dir):
        """Test handling of unicode decode errors."""
        # Create file with invalid UTF-8
        binary_file = temp_dir / "binary.md"
        binary_file.write_bytes(b'\x80\x81\x82')

        content = safe_read(binary_file, silent=True)
        assert content is None

    def test_read_with_different_encoding(self, temp_dir):
        """Test reading with non-UTF-8 encoding."""
        latin1_file = temp_dir / "latin1.md"
        latin1_file.write_text("café", encoding='latin-1')

        # Should fail with UTF-8
        safe_read(latin1_file, encoding='utf-8', silent=True)
        # May succeed or fail depending on content

        # Should succeed with correct encoding
        content = safe_read(latin1_file, encoding='latin-1')
        assert content == "café"


class TestSafeWrite:
    """Tests for safe_write() function."""

    def test_write_new_file(self, temp_dir):
        """Test writing a new file."""
        new_file = temp_dir / "new.md"
        content = "# New Note\n"

        success = safe_write(new_file, content)
        assert success is True
        assert new_file.exists()
        assert new_file.read_text() == content

    def test_overwrite_existing_file(self, temp_file):
        """Test overwriting an existing file."""
        new_content = "# Updated\n"

        success = safe_write(temp_file, new_content)
        assert success is True
        assert temp_file.read_text() == new_content

    def test_write_dry_run(self, temp_dir):
        """Test dry-run mode doesn't write."""
        new_file = temp_dir / "dry_run.md"
        content = "# Test\n"

        success = safe_write(new_file, content, dry_run=True)
        assert success is True
        assert not new_file.exists()

    def test_write_with_parent_creation(self, temp_dir):
        """Test creating parent directories."""
        nested_file = temp_dir / "subdir" / "nested" / "file.md"
        content = "# Nested\n"

        success = safe_write(nested_file, content, create_parents=True)
        assert success is True
        assert nested_file.exists()
        assert nested_file.read_text() == content

    def test_write_without_parent_creation(self, temp_dir):
        """Test writing fails when parent doesn't exist."""
        nested_file = temp_dir / "nonexistent" / "file.md"
        content = "# Test\n"

        success = safe_write(nested_file, content, create_parents=False, silent=True)
        assert success is False
        assert not nested_file.exists()

    def test_write_permission_denied(self, temp_dir):
        """Test handling permission errors."""
        # Create read-only directory
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        file_in_readonly = readonly_dir / "test.md"

        try:
            success = safe_write(file_in_readonly, "# Test\n", silent=True)
            assert success is False
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    def test_write_silent_mode(self, temp_dir, capsys):
        """Test silent mode suppresses error messages."""
        nested_file = temp_dir / "nonexistent" / "file.md"

        success = safe_write(nested_file, "# Test\n", create_parents=False, silent=True)
        assert success is False

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_write_with_custom_error_handler(self, temp_dir):
        """Test custom error handler is called."""
        errors = []

        def error_handler(path, error):
            errors.append((path, type(error).__name__))

        nested_file = temp_dir / "nonexistent" / "file.md"
        success = safe_write(
            nested_file,
            "# Test\n",
            create_parents=False,
            on_error=error_handler,
            silent=True
        )

        assert success is False
        assert len(errors) == 1
        assert errors[0][0] == nested_file


class TestAtomicUpdate:
    """Tests for atomic_update() function."""

    def test_simple_update(self, temp_file):
        """Test simple content update."""
        def add_footer(content):
            return content + "\n---\nFooter\n"

        success = atomic_update(temp_file, add_footer)
        assert success is True

        updated = temp_file.read_text()
        assert "Footer" in updated
        assert "# Test Note" in updated

    def test_update_with_no_changes(self, temp_file):
        """Test update that doesn't modify content."""
        original = temp_file.read_text()

        def no_change(content):
            return content  # Return unchanged

        success = atomic_update(temp_file, no_change)
        assert success is True
        assert temp_file.read_text() == original

    def test_update_dry_run(self, temp_file):
        """Test dry-run mode doesn't write."""
        original = temp_file.read_text()

        def add_footer(content):
            return content + "\n---\nFooter\n"

        success = atomic_update(temp_file, add_footer, dry_run=True)
        assert success is True
        assert temp_file.read_text() == original  # Unchanged

    def test_update_returns_none(self, temp_file):
        """Test updater returning None signals skip."""
        original = temp_file.read_text()

        def skip_update(content):
            return None  # Signal to skip

        success = atomic_update(temp_file, skip_update)
        assert success is False
        assert temp_file.read_text() == original

    def test_update_with_validation(self, temp_file):
        """Test update with validation logic."""
        def update_if_has_title(content):
            if "# Test Note" in content:
                return content.replace("Test Note", "Updated Note")
            return None

        success = atomic_update(temp_file, update_if_has_title)
        assert success is True

        updated = temp_file.read_text()
        assert "Updated Note" in updated

    def test_update_nonexistent_file(self, temp_dir):
        """Test updating nonexistent file fails."""
        nonexistent = temp_dir / "nonexistent.md"

        def add_footer(content):
            return content + "\nFooter\n"

        success = atomic_update(nonexistent, add_footer, silent=True)
        assert success is False

    def test_update_with_exception(self, temp_file):
        """Test updater function raising exception."""
        def broken_updater(content):
            raise ValueError("Something went wrong")

        success = atomic_update(temp_file, broken_updater, silent=True)
        assert success is False

    def test_update_with_error_handler(self, temp_file):
        """Test custom error handler for updater exceptions."""
        errors = []

        def error_handler(path, error):
            errors.append((path, type(error).__name__))

        def broken_updater(content):
            raise ValueError("Test error")

        success = atomic_update(
            temp_file,
            broken_updater,
            on_error=error_handler,
            silent=True
        )

        assert success is False
        assert len(errors) == 1
        assert errors[0][1] == "ValueError"

    def test_update_complex_transformation(self, temp_file):
        """Test complex content transformation."""
        def add_frontmatter(content):
            if content.startswith("---"):
                return content  # Already has frontmatter

            frontmatter = "---\ntags: [test]\n---\n\n"
            return frontmatter + content

        success = atomic_update(temp_file, add_frontmatter)
        assert success is True

        updated = temp_file.read_text()
        assert updated.startswith("---")
        assert "tags: [test]" in updated


class TestSafeMove:
    """Tests for safe_move() function."""

    def test_move_file(self, temp_file, temp_dir):
        """Test moving a file."""
        destination = temp_dir / "moved.md"

        success = safe_move(temp_file, destination)
        assert success is True
        assert not temp_file.exists()
        assert destination.exists()
        assert destination.read_text() == "# Test Note\n\nSome content.\n"

    def test_move_to_subdirectory(self, temp_file, temp_dir):
        """Test moving to nested subdirectory."""
        subdir = temp_dir / "subdir" / "nested"
        destination = subdir / "file.md"

        success = safe_move(temp_file, destination)
        assert success is True
        assert not temp_file.exists()
        assert destination.exists()

    def test_rename_file(self, temp_file):
        """Test renaming file in same directory."""
        destination = temp_file.parent / "renamed.md"

        success = safe_move(temp_file, destination)
        assert success is True
        assert not temp_file.exists()
        assert destination.exists()

    def test_move_dry_run(self, temp_file, temp_dir):
        """Test dry-run mode doesn't move."""
        destination = temp_dir / "moved.md"

        success = safe_move(temp_file, destination, dry_run=True)
        assert success is True
        assert temp_file.exists()  # Still exists
        assert not destination.exists()

    def test_move_nonexistent_source(self, temp_dir):
        """Test moving nonexistent file fails."""
        source = temp_dir / "nonexistent.md"
        destination = temp_dir / "dest.md"

        success = safe_move(source, destination, silent=True)
        assert success is False

    def test_move_to_existing_destination(self, temp_file, temp_dir):
        """Test moving to existing destination fails."""
        # Create destination
        destination = temp_dir / "existing.md"
        destination.write_text("# Existing\n")

        success = safe_move(temp_file, destination, silent=True)
        assert success is False
        assert temp_file.exists()  # Source unchanged
        assert destination.read_text() == "# Existing\n"  # Dest unchanged

    def test_move_with_overwrite(self, temp_file, temp_dir):
        """Test moving with overwrite flag."""
        # Create destination
        destination = temp_dir / "existing.md"
        destination.write_text("# Existing\n")

        original_content = temp_file.read_text()

        success = safe_move(temp_file, destination, overwrite=True)
        assert success is True
        assert not temp_file.exists()
        assert destination.exists()
        assert destination.read_text() == original_content

    def test_move_silent_mode(self, temp_dir, capsys):
        """Test silent mode suppresses errors."""
        source = temp_dir / "nonexistent.md"
        destination = temp_dir / "dest.md"

        success = safe_move(source, destination, silent=True)
        assert success is False

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_move_with_error_handler(self, temp_dir):
        """Test custom error handler."""
        errors = []

        def error_handler(path, error):
            errors.append((path, type(error).__name__))

        source = temp_dir / "nonexistent.md"
        destination = temp_dir / "dest.md"

        success = safe_move(
            source,
            destination,
            on_error=error_handler,
            silent=True
        )

        assert success is False
        assert len(errors) == 1
        assert errors[0][0] == source
        assert errors[0][1] == "FileNotFoundError"


class TestIntegration:
    """Integration tests combining multiple operations."""

    def test_read_update_write_pattern(self, temp_file):
        """Test common pattern: read -> modify -> write."""
        # Read
        content = safe_read(temp_file)
        assert content is not None

        # Modify
        updated = content.replace("Test Note", "Updated Note")

        # Write
        success = safe_write(temp_file, updated)
        assert success is True
        assert "Updated Note" in temp_file.read_text()

    def test_atomic_update_equivalent(self, temp_file):
        """Test atomic_update is equivalent to manual read-modify-write."""
        # Manual approach
        temp_file2 = temp_file.parent / "test2.md"
        temp_file2.write_text(temp_file.read_text())

        content = safe_read(temp_file)
        updated = content.replace("Test Note", "Updated Note")
        safe_write(temp_file, updated)

        # Atomic approach
        def updater(content):
            return content.replace("Test Note", "Updated Note")

        atomic_update(temp_file2, updater)

        # Both should produce same result
        assert temp_file.read_text() == temp_file2.read_text()

    def test_backup_and_restore(self, temp_file, temp_dir):
        """Test creating backup before modification."""
        backup = temp_dir / "backup.md"
        original_content = temp_file.read_text()

        # Create backup
        safe_move(temp_file, backup)
        assert backup.exists()
        assert not temp_file.exists()

        # Restore
        safe_move(backup, temp_file)
        assert temp_file.exists()
        assert temp_file.read_text() == original_content

    def test_dry_run_workflow(self, temp_file):
        """Test dry-run mode across operations."""
        original = temp_file.read_text()

        # All dry-run operations should succeed but not modify
        def updater(content):
            return content + "\nModified\n"

        atomic_update(temp_file, updater, dry_run=True)
        assert temp_file.read_text() == original

        new_file = temp_file.parent / "new.md"
        safe_write(new_file, "# New\n", dry_run=True)
        assert not new_file.exists()

        moved = temp_file.parent / "moved.md"
        safe_move(temp_file, moved, dry_run=True)
        assert temp_file.exists()
        assert not moved.exists()


@pytest.mark.unit
class TestErrorPrintStatements:
    """Test error print statements (for coverage of non-silent error paths)."""

    def test_safe_read_permission_error_prints(self, temp_file, capsys):
        """Test that permission errors print to stderr when not silent."""
        # Make file unreadable
        temp_file.chmod(0o000)
        try:
            result = safe_read(temp_file, silent=False)
            assert result is None
            captured = capsys.readouterr()
            assert "Permission denied" in captured.err
        finally:
            # Restore permissions for cleanup
            temp_file.chmod(0o644)

    def test_safe_read_unicode_error_prints(self, temp_dir, capsys):
        """Test that unicode decode errors print to stderr when not silent."""
        # Create a file with invalid UTF-8 bytes
        binary_file = temp_dir / "binary.bin"
        binary_file.write_bytes(b'\xff\xfe\xfd')

        result = safe_read(binary_file, silent=False)
        assert result is None
        captured = capsys.readouterr()
        assert "Could not decode file" in captured.err or "wrong encoding" in captured.err

    def test_safe_read_generic_error_prints(self, temp_dir, capsys, monkeypatch):
        """Test that generic exceptions print to stderr when not silent."""
        from pathlib import Path

        # Create a mock that raises a generic exception
        def mock_read_text(*args, **kwargs):
            raise RuntimeError("Mock error")

        monkeypatch.setattr(Path, "read_text", mock_read_text)

        test_file = temp_dir / "test.md"
        test_file.write_text("# Test\n")

        result = safe_read(test_file, silent=False)
        assert result is None
        captured = capsys.readouterr()
        assert "Error reading" in captured.err

    def test_safe_write_permission_error_prints(self, temp_dir, capsys):
        """Test that permission errors print to stderr when not silent."""
        # Create a read-only directory
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        try:
            test_file = readonly_dir / "test.md"
            result = safe_write(test_file, "# Test\n", silent=False)
            assert result is False
            captured = capsys.readouterr()
            assert "Permission denied" in captured.err
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    def test_safe_write_oserror_prints(self, temp_dir, capsys, monkeypatch):
        """Test that OS errors print to stderr when not silent."""
        from pathlib import Path

        # Create a mock that raises OSError
        def mock_write_text(*args, **kwargs):
            raise OSError("Mock OS error")

        monkeypatch.setattr(Path, "write_text", mock_write_text)

        test_file = temp_dir / "test.md"
        result = safe_write(test_file, "# Test\n", silent=False)
        assert result is False
        captured = capsys.readouterr()
        assert "Error writing" in captured.err

    def test_safe_write_generic_error_prints(self, temp_dir, capsys, monkeypatch):
        """Test that generic exceptions print to stderr when not silent."""
        from pathlib import Path

        # Create a mock that raises a generic exception
        def mock_write_text(*args, **kwargs):
            raise ValueError("Mock error")

        monkeypatch.setattr(Path, "write_text", mock_write_text)

        test_file = temp_dir / "test.md"
        result = safe_write(test_file, "# Test\n", silent=False)
        assert result is False
        captured = capsys.readouterr()
        assert "Error writing" in captured.err

    def test_atomic_update_updater_error_prints(self, temp_file, capsys):
        """Test that updater function errors print to stderr when not silent."""
        def failing_updater(content):
            raise ValueError("Updater failed")

        result = atomic_update(temp_file, failing_updater, silent=False)
        assert result is False
        captured = capsys.readouterr()
        assert "Error in updater function" in captured.err

    def test_safe_move_oserror_prints(self, temp_dir, capsys, monkeypatch):
        """Test that OS errors in move print to stderr when not silent."""
        from pathlib import Path

        # Create a mock that raises OSError
        def mock_rename(self, target):
            raise OSError("Mock move error")

        monkeypatch.setattr(Path, "rename", mock_rename)

        source = temp_dir / "source.md"
        source.write_text("# Source\n")
        dest = temp_dir / "dest.md"

        result = safe_move(source, dest, silent=False)
        assert result is False
        captured = capsys.readouterr()
        assert "Error moving" in captured.err

    def test_safe_move_generic_error_prints(self, temp_dir, capsys, monkeypatch):
        """Test that generic exceptions in move print to stderr when not silent."""
        from pathlib import Path

        # Create a mock that raises a generic exception
        def mock_rename(self, target):
            raise RuntimeError("Mock unexpected error")

        monkeypatch.setattr(Path, "rename", mock_rename)

        source = temp_dir / "source.md"
        source.write_text("# Source\n")
        dest = temp_dir / "dest.md"

        result = safe_move(source, dest, silent=False)
        assert result is False
        captured = capsys.readouterr()
        assert "Unexpected error moving" in captured.err


@pytest.mark.unit
class TestOnErrorCallbacks:
    """Test on_error callback execution for different exception types."""

    def test_safe_read_permission_error_callback(self, temp_file):
        """Test that on_error callback is called for permission errors."""
        errors = []

        def error_handler(path, error):
            errors.append((path, error))

        temp_file.chmod(0o000)
        try:
            result = safe_read(temp_file, on_error=error_handler, silent=True)
            assert result is None
            assert len(errors) == 1
            assert errors[0][0] == temp_file
            assert isinstance(errors[0][1], PermissionError)
        finally:
            temp_file.chmod(0o644)

    def test_safe_read_unicode_error_callback(self, temp_dir):
        """Test that on_error callback is called for unicode decode errors."""
        errors = []

        def error_handler(path, error):
            errors.append((path, error))

        # Create file with invalid UTF-8
        binary_file = temp_dir / "binary.bin"
        binary_file.write_bytes(b'\xff\xfe\xfd')

        result = safe_read(binary_file, on_error=error_handler, silent=True)
        assert result is None
        assert len(errors) == 1
        assert errors[0][0] == binary_file
        assert isinstance(errors[0][1], UnicodeDecodeError)

    def test_safe_read_generic_error_callback(self, temp_dir, monkeypatch):
        """Test that on_error callback is called for generic exceptions."""
        from pathlib import Path

        errors = []

        def error_handler(path, error):
            errors.append((path, error))

        # Create a mock that raises a generic exception
        def mock_read_text(*args, **kwargs):
            raise RuntimeError("Mock error")

        monkeypatch.setattr(Path, "read_text", mock_read_text)

        test_file = temp_dir / "test.md"
        test_file.write_text("# Test\n")

        result = safe_read(test_file, on_error=error_handler, silent=True)
        assert result is None
        assert len(errors) == 1
        assert errors[0][0] == test_file
        assert isinstance(errors[0][1], RuntimeError)

    def test_safe_write_permission_error_callback(self, temp_dir):
        """Test that on_error callback is called for permission errors."""
        errors = []

        def error_handler(path, error):
            errors.append((path, error))

        # Create read-only directory
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        try:
            test_file = readonly_dir / "test.md"
            result = safe_write(test_file, "# Test\n", on_error=error_handler, silent=True)
            assert result is False
            assert len(errors) == 1
            assert errors[0][0] == test_file
            assert isinstance(errors[0][1], PermissionError)
        finally:
            readonly_dir.chmod(0o755)

    def test_safe_write_generic_error_callback(self, temp_dir, monkeypatch):
        """Test that on_error callback is called for generic exceptions."""
        from pathlib import Path

        errors = []

        def error_handler(path, error):
            errors.append((path, error))

        # Create a mock that raises a generic exception
        def mock_write_text(*args, **kwargs):
            raise ValueError("Mock error")

        monkeypatch.setattr(Path, "write_text", mock_write_text)

        test_file = temp_dir / "test.md"
        result = safe_write(test_file, "# Test\n", on_error=error_handler, silent=True)
        assert result is False
        assert len(errors) == 1
        assert errors[0][0] == test_file
        assert isinstance(errors[0][1], ValueError)

    def test_safe_move_generic_error_callback(self, temp_dir, monkeypatch):
        """Test that on_error callback is called for generic exceptions."""
        from pathlib import Path

        errors = []

        def error_handler(path, error):
            errors.append((path, error))

        # Create a mock that raises a generic exception
        def mock_rename(self, target):
            raise RuntimeError("Mock unexpected error")

        monkeypatch.setattr(Path, "rename", mock_rename)

        source = temp_dir / "source.md"
        source.write_text("# Source\n")
        dest = temp_dir / "dest.md"

        result = safe_move(source, dest, on_error=error_handler, silent=True)
        assert result is False
        assert len(errors) == 1
        assert errors[0][0] == source
        assert isinstance(errors[0][1], RuntimeError)
