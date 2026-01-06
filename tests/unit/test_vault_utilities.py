"""
Unit tests for vault utilities and directory traversal.

These tests verify the core vault operations including directory traversal,
file filtering, and ignore patterns.
"""

import pytest
from vault_manager.core.vault import (
    iter_markdown_files,
    count_markdown_files,
    get_markdown_files,
    is_ignored_path,
    validate_directory
)


@pytest.fixture
def temp_vault_structure(tmp_path):
    """Create a temporary vault structure for testing."""
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # Create regular markdown files
    (vault_root / "note1.md").write_text("# Note 1")
    (vault_root / "note2.md").write_text("# Note 2")

    # Create subdirectory with markdown files
    notes_dir = vault_root / "Notes"
    notes_dir.mkdir()
    (notes_dir / "sub_note1.md").write_text("# Sub Note 1")
    (notes_dir / "sub_note2.md").write_text("# Sub Note 2")

    # Create Excalidraw file
    (vault_root / "drawing.excalidraw.md").write_text("Excalidraw")
    (notes_dir / "diagram.excalidraw.md").write_text("Excalidraw")

    # Create ignored directories
    obsidian_dir = vault_root / ".obsidian"
    obsidian_dir.mkdir()
    (obsidian_dir / "config.md").write_text("Config")

    trash_dir = vault_root / ".trash"
    trash_dir.mkdir()
    (trash_dir / "deleted.md").write_text("Deleted")

    # Create additional ignore directory
    excalidraw_dir = vault_root / "Excalidraw"
    excalidraw_dir.mkdir()
    (excalidraw_dir / "drawing1.md").write_text("Drawing 1")

    # Create non-markdown files
    (vault_root / "readme.txt").write_text("Readme")
    (notes_dir / "data.json").write_text("{}")

    return vault_root


class TestIterMarkdownFiles:
    """Test iter_markdown_files iterator function."""

    def test_iter_all_markdown_files(self, temp_vault_structure):
        """Test iterating all markdown files."""
        vault_root = temp_vault_structure
        files = list(iter_markdown_files(vault_root, vault_root))

        # Should find 5 files (note1, note2, sub_note1, sub_note2, Excalidraw/drawing1.md)
        # Excludes: .excalidraw.md files, ignored directories (.obsidian, .trash), non-md files
        # Note: Excalidraw directory is NOT in default ignore list
        assert len(files) == 5
        assert all(f.suffix == '.md' for f in files)
        assert all(not f.name.endswith('.excalidraw.md') for f in files)

    def test_iter_with_excalidraw_included(self, temp_vault_structure):
        """Test iterating with Excalidraw files included."""
        vault_root = temp_vault_structure
        files = list(iter_markdown_files(
            vault_root, vault_root, exclude_excalidraw=False
        ))

        # Should find 7 files (5 regular + 2 .excalidraw.md files)
        assert len(files) == 7

    def test_iter_respects_ignored_directories(self, temp_vault_structure):
        """Test that ignored directories are skipped."""
        vault_root = temp_vault_structure
        files = list(iter_markdown_files(vault_root, vault_root))

        # Should not include files from .obsidian or .trash
        file_parts = [f.parts for f in files]
        assert not any('.obsidian' in parts for parts in file_parts)
        assert not any('.trash' in parts for parts in file_parts)

    def test_iter_with_additional_ignores(self, temp_vault_structure):
        """Test additional ignore directories."""
        vault_root = temp_vault_structure
        files = list(iter_markdown_files(
            vault_root, vault_root, additional_ignores={'Excalidraw'}
        ))

        # Should not include files from Excalidraw directory
        file_names = [f.name for f in files]
        assert 'drawing1.md' not in file_names

    def test_iter_with_progress_callback(self, temp_vault_structure):
        """Test progress callback is called for each file."""
        vault_root = temp_vault_structure
        called_files = []

        def progress_callback(file_path):
            called_files.append(file_path)

        files = list(iter_markdown_files(
            vault_root, vault_root, progress_callback=progress_callback
        ))

        assert len(called_files) == len(files)
        assert all(f in files for f in called_files)

    def test_iter_returns_iterator(self, temp_vault_structure):
        """Test that function returns an iterator, not a list."""
        vault_root = temp_vault_structure
        result = iter_markdown_files(vault_root, vault_root)

        # Should be a generator/iterator
        assert hasattr(result, '__iter__')
        assert hasattr(result, '__next__')

    def test_iter_subdirectory_only(self, temp_vault_structure):
        """Test iterating only a subdirectory."""
        vault_root = temp_vault_structure
        notes_dir = vault_root / "Notes"

        files = list(iter_markdown_files(notes_dir, vault_root))

        # Should only find files in Notes directory (2 files)
        assert len(files) == 2
        assert all('Notes' in str(f) for f in files)

    def test_iter_follows_symlinks(self, temp_vault_structure):
        """Test that symbolic links are followed by default."""
        vault_root = temp_vault_structure

        # Create a symlinked directory
        symlink_dir = vault_root / "LinkedNotes"
        target_dir = vault_root / "Notes"
        symlink_dir.symlink_to(target_dir)

        try:
            # Count files with symlinks followed (default)
            files_with_symlinks = list(iter_markdown_files(vault_root, vault_root))

            # Should include files from both the original Notes dir and the symlinked dir
            # Original Notes has 2 files, symlink points to same directory
            # So we should see files from both paths (4 total: 2 original + 2 via symlink)
            assert len(files_with_symlinks) >= 5  # At least original 5 + symlinked files

            # Count files without following symlinks
            files_no_symlinks = list(iter_markdown_files(
                vault_root, vault_root, follow_symlinks=False
            ))

            # Should only include the original 5 files
            assert len(files_no_symlinks) == 5

            # With symlinks, we should have more files
            assert len(files_with_symlinks) > len(files_no_symlinks)

        finally:
            # Clean up symlink
            if symlink_dir.exists():
                symlink_dir.unlink()


class TestCountMarkdownFiles:
    """Test count_markdown_files function."""

    def test_count_all_files(self, temp_vault_structure):
        """Test counting all markdown files."""
        vault_root = temp_vault_structure
        count = count_markdown_files(vault_root, vault_root)

        assert count == 5

    def test_count_with_excalidraw(self, temp_vault_structure):
        """Test counting with Excalidraw files included."""
        vault_root = temp_vault_structure
        count = count_markdown_files(
            vault_root, vault_root, exclude_excalidraw=False
        )

        assert count == 7

    def test_count_with_additional_ignores(self, temp_vault_structure):
        """Test counting with additional ignore directories."""
        vault_root = temp_vault_structure
        count = count_markdown_files(
            vault_root, vault_root, additional_ignores={'Notes'}
        )

        # Should only count root-level files (2 regular + 1 in Excalidraw dir = 3)
        assert count == 3

    def test_count_empty_directory(self, tmp_path):
        """Test counting in empty directory."""
        vault_root = tmp_path / "empty_vault"
        vault_root.mkdir()

        count = count_markdown_files(vault_root, vault_root)
        assert count == 0


class TestGetMarkdownFiles:
    """Test get_markdown_files function (backward compatibility)."""

    def test_get_returns_list(self, temp_vault_structure):
        """Test that function returns a list, not an iterator."""
        vault_root = temp_vault_structure
        files = get_markdown_files(vault_root, vault_root)

        assert isinstance(files, list)
        assert len(files) == 5

    def test_get_same_results_as_iter(self, temp_vault_structure):
        """Test that get_markdown_files returns same results as iter."""
        vault_root = temp_vault_structure

        list_files = get_markdown_files(vault_root, vault_root)
        iter_files = list(iter_markdown_files(vault_root, vault_root))

        # Sort for comparison since order might differ
        list_files_sorted = sorted(list_files, key=str)
        iter_files_sorted = sorted(iter_files, key=str)

        assert list_files_sorted == iter_files_sorted


class TestIsIgnoredPath:
    """Test is_ignored_path function."""

    def test_obsidian_directory_ignored(self, temp_vault_structure):
        """Test that .obsidian directory is ignored."""
        vault_root = temp_vault_structure
        obsidian_path = vault_root / ".obsidian" / "config.md"

        assert is_ignored_path(obsidian_path, vault_root) is True

    def test_trash_directory_ignored(self, temp_vault_structure):
        """Test that .trash directory is ignored."""
        vault_root = temp_vault_structure
        trash_path = vault_root / ".trash" / "deleted.md"

        assert is_ignored_path(trash_path, vault_root) is True

    def test_regular_file_not_ignored(self, temp_vault_structure):
        """Test that regular files are not ignored."""
        vault_root = temp_vault_structure
        regular_path = vault_root / "note1.md"

        assert is_ignored_path(regular_path, vault_root) is False

    def test_additional_ignores(self, temp_vault_structure):
        """Test additional ignore directories."""
        vault_root = temp_vault_structure
        excalidraw_path = vault_root / "Excalidraw" / "drawing1.md"

        # Not ignored by default
        assert is_ignored_path(excalidraw_path, vault_root) is False

        # Ignored when added to additional_ignores
        assert is_ignored_path(
            excalidraw_path, vault_root, additional_ignores={'Excalidraw'}
        ) is True

    def test_nested_ignored_directory(self, temp_vault_structure):
        """Test that nested paths in ignored directories are caught."""
        vault_root = temp_vault_structure
        nested_path = vault_root / ".obsidian" / "plugins" / "config.md"

        assert is_ignored_path(nested_path, vault_root) is True


class TestValidateDirectory:
    """Test validate_directory function."""

    def test_validate_dot_returns_vault_root(self, temp_vault_structure):
        """Test that '.' argument returns vault root."""
        vault_root = temp_vault_structure
        result = validate_directory('.', vault_root)

        assert result == vault_root

    def test_validate_existing_directory(self, temp_vault_structure):
        """Test validating an existing directory."""
        vault_root = temp_vault_structure
        result = validate_directory('Notes', vault_root)

        assert result == vault_root / 'Notes'
        assert result.exists()

    def test_validate_nonexistent_directory_exits(self, temp_vault_structure):
        """Test that validating non-existent directory exits."""
        vault_root = temp_vault_structure

        with pytest.raises(SystemExit):
            validate_directory('NonExistent', vault_root)

    def test_validate_file_not_directory_exits(self, temp_vault_structure):
        """Test that validating a file (not directory) exits."""
        vault_root = temp_vault_structure

        with pytest.raises(SystemExit):
            validate_directory('note1.md', vault_root)

    def test_validate_with_must_exist_false(self, temp_vault_structure):
        """Test validating with must_exist=False allows non-existent paths."""
        vault_root = temp_vault_structure
        result = validate_directory('Future', vault_root, must_exist=False)

        assert result == vault_root / 'Future'
        assert not result.exists()


@pytest.mark.parametrize("directory,expected_count", [
    (".", 5),  # Entire vault (includes Excalidraw/drawing1.md)
    ("Notes", 2),  # Subdirectory only
])
def test_count_parametrized(temp_vault_structure, directory, expected_count):
    """Parametrized test for counting files in different directories."""
    vault_root = temp_vault_structure
    target_dir = vault_root if directory == "." else vault_root / directory

    count = count_markdown_files(target_dir, vault_root)
    assert count == expected_count


@pytest.mark.parametrize("exclude_excalidraw,expected_count", [
    (True, 5),   # Excludes only .excalidraw.md files
    (False, 7),  # Includes .excalidraw.md files
])
def test_excalidraw_filtering_parametrized(
    temp_vault_structure, exclude_excalidraw, expected_count
):
    """Parametrized test for Excalidraw filtering."""
    vault_root = temp_vault_structure

    count = count_markdown_files(
        vault_root, vault_root, exclude_excalidraw=exclude_excalidraw
    )
    assert count == expected_count
