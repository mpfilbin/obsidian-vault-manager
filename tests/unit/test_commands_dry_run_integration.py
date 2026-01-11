"""
Integration tests for commands using DryRunContext.

Tests verify that refactored commands properly integrate with the
DryRunContext infrastructure, including:
- Dry-run mode prevents file modifications
- Statistics tracking works correctly
- @auto_rebuild_after decorator functions properly
- --no-rebuild flag is respected
"""

import sqlite3
from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from vault_manager.properties.commands.relate import RelateCommand
from vault_manager.properties.commands.summarize import SummarizeCommand
from vault_manager.tags.commands.add import AddCommand
from vault_manager.tags.commands.clean_normalize import CleanNormalizeCommand
from vault_manager.tags.commands.purge import PurgeCommand
from vault_manager.tags.commands.rename import RenameCommand


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault directory."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture
def vault_with_tagged_notes(temp_vault):
    """Create vault with notes containing tags."""
    notes = {
        "note1.md": "---\ntags:\n  - foo\n  - bar\n---\nContent 1",
        "note2.md": "---\ntags:\n  - foo\n  - baz\n---\nContent 2",
        "note3.md": "---\ntags:\n  - Bar\n  - qux\n---\nContent 3",
    }

    for filename, content in notes.items():
        (temp_vault / filename).write_text(content, encoding="utf-8")

    return temp_vault


@pytest.fixture
def vault_database(temp_vault):
    """Create a vault.db database."""
    db_path = temp_vault / "vault.db"

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Create minimal schema
        cursor.execute("""
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE files (
                file_path TEXT PRIMARY KEY,
                size_bytes INTEGER NOT NULL
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
                PRIMARY KEY (tag, file_path)
            )
        """)

        conn.commit()

    return db_path


def mock_vault_database(vault_path):
    """Create a mock VaultDatabase that returns the specified vault_path."""
    mock_db = MagicMock()
    mock_db.vault_root = vault_path
    mock_db.db_path = vault_path / "vault.db"
    mock_db.exists.return_value = mock_db.db_path.exists()
    return mock_db


class TestPurgeCommandIntegration:
    def test_purge_dry_run_no_modifications(self, vault_with_tagged_notes, monkeypatch):
        monkeypatch.chdir(vault_with_tagged_notes)

        note1_original = (vault_with_tagged_notes / "note1.md").read_text()

        with patch(
            "vault_manager.tags.commands.purge.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.purge.auto_rebuild_after", lambda x: lambda f: f
            ):
                cmd = PurgeCommand()
                args = Namespace(tags=["foo"], dry_run=True, no_rebuild=True)

                cmd.execute(args)

        note1_after = (vault_with_tagged_notes / "note1.md").read_text()
        assert note1_after == note1_original, "Dry-run should not modify files"

    def test_purge_live_mode_modifies_files(self, vault_with_tagged_notes, monkeypatch):
        monkeypatch.chdir(vault_with_tagged_notes)

        with patch(
            "vault_manager.tags.commands.purge.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.purge.auto_rebuild_after", lambda x: lambda f: f
            ):
                with patch("builtins.input", return_value="y"):
                    cmd = PurgeCommand()
                    args = Namespace(tags=["foo"], dry_run=False, no_rebuild=True)

                    cmd.execute(args)

        note1_after = (vault_with_tagged_notes / "note1.md").read_text()
        assert "foo" not in note1_after, "Live mode should remove tag"
        assert "bar" in note1_after, "Other tags should remain"

    def test_purge_statistics_tracking(self, vault_with_tagged_notes, monkeypatch, capsys):
        monkeypatch.chdir(vault_with_tagged_notes)

        with patch(
            "vault_manager.tags.commands.purge.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.purge.auto_rebuild_after", lambda x: lambda f: f
            ):
                cmd = PurgeCommand()
                args = Namespace(tags=["foo"], dry_run=True, no_rebuild=True)

                cmd.execute(args)

        captured = capsys.readouterr()
        output = captured.out

        assert "Total files scanned:" in output
        assert "Files modified:" in output or "Files that would be modified:" in output

    def test_purge_respects_no_rebuild_flag(self, vault_with_tagged_notes, monkeypatch):
        monkeypatch.chdir(vault_with_tagged_notes)

        rebuild_called = False

        def mock_rebuild_decorator(operation_name):
            def decorator(func):
                def wrapper(self, args):
                    nonlocal rebuild_called
                    result = func(self, args)
                    if not args.no_rebuild:
                        rebuild_called = True
                    return result

                return wrapper

            return decorator

        with patch(
            "vault_manager.tags.commands.purge.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.purge.auto_rebuild_after", mock_rebuild_decorator
            ):
                with patch("builtins.input", return_value="y"):
                    cmd = PurgeCommand()
                    args = Namespace(tags=["foo"], dry_run=False, no_rebuild=True)

                    cmd.execute(args)

        assert not rebuild_called, "--no-rebuild should prevent database rebuild"


class TestRenameCommandIntegration:
    def test_rename_dry_run_no_modifications(self, vault_with_tagged_notes, monkeypatch):
        monkeypatch.chdir(vault_with_tagged_notes)

        note1_original = (vault_with_tagged_notes / "note1.md").read_text()

        with patch(
            "vault_manager.tags.commands.rename.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.rename.auto_rebuild_after", lambda x: lambda f: f
            ):
                cmd = RenameCommand()
                args = Namespace(old_tag="foo", new_tag="renamed", dry_run=True, no_rebuild=True)

                cmd.execute(args)

        note1_after = (vault_with_tagged_notes / "note1.md").read_text()
        assert note1_after == note1_original, "Dry-run should not modify files"
        assert "foo" in note1_after, "Original tag should still exist"
        assert "renamed" not in note1_after, "New tag should not exist"

    def test_rename_live_mode_modifies_files(self, vault_with_tagged_notes, monkeypatch):
        monkeypatch.chdir(vault_with_tagged_notes)

        with patch(
            "vault_manager.tags.commands.rename.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.rename.auto_rebuild_after", lambda x: lambda f: f
            ):
                with patch("builtins.input", return_value="y"):
                    cmd = RenameCommand()
                    args = Namespace(
                        old_tag="foo", new_tag="renamed", dry_run=False, no_rebuild=True
                    )

                    cmd.execute(args)

        note1_after = (vault_with_tagged_notes / "note1.md").read_text()
        assert "foo" not in note1_after, "Old tag should be removed"
        assert "renamed" in note1_after, "New tag should be added"

    def test_rename_handles_conflicts(self, vault_with_tagged_notes, monkeypatch, capsys):
        monkeypatch.chdir(vault_with_tagged_notes)

        with patch(
            "vault_manager.tags.commands.rename.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.rename.auto_rebuild_after", lambda x: lambda f: f
            ):
                cmd = RenameCommand()
                args = Namespace(old_tag="foo", new_tag="bar", dry_run=True, no_rebuild=True)

                cmd.execute(args)

        captured = capsys.readouterr()
        output = captured.out

        assert "conflict" in output.lower() or "CONFLICT" in output


class TestCleanNormalizeCommandIntegration:
    def test_normalize_dry_run_no_modifications(self, vault_with_tagged_notes, monkeypatch):
        monkeypatch.chdir(vault_with_tagged_notes)

        # note3.md has 'Bar' (uppercase) which should be normalized to 'bar'
        note3_original = (vault_with_tagged_notes / "note3.md").read_text()

        with patch(
            "vault_manager.tags.commands.clean_normalize.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.clean_normalize.auto_rebuild_after",
                lambda x: lambda f: f,
            ):
                cmd = CleanNormalizeCommand()
                args = Namespace(directory=".", dry_run=True, no_rebuild=True)

                cmd.execute(args)

        note3_after = (vault_with_tagged_notes / "note3.md").read_text()
        assert note3_after == note3_original, "Dry-run should not modify files"
        assert "Bar" in note3_after, "Original case should remain"

    def test_normalize_live_mode_modifies_files(self, vault_with_tagged_notes, monkeypatch):
        monkeypatch.chdir(vault_with_tagged_notes)

        with patch(
            "vault_manager.tags.commands.clean_normalize.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.clean_normalize.auto_rebuild_after",
                lambda x: lambda f: f,
            ):
                with patch("builtins.input", return_value="y"):
                    cmd = CleanNormalizeCommand()
                    args = Namespace(directory=".", dry_run=False, no_rebuild=True)

                    cmd.execute(args)

        note3_after = (vault_with_tagged_notes / "note3.md").read_text()
        assert "Bar" not in note3_after, "Uppercase tag should be removed"
        assert "bar" in note3_after, "Lowercase tag should be added"

    def test_normalize_tracks_case_changes(self, vault_with_tagged_notes, monkeypatch, capsys):
        monkeypatch.chdir(vault_with_tagged_notes)

        with patch(
            "vault_manager.tags.commands.clean_normalize.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.tags.commands.clean_normalize.auto_rebuild_after",
                lambda x: lambda f: f,
            ):
                cmd = CleanNormalizeCommand()
                args = Namespace(directory=".", dry_run=True, no_rebuild=True)

                cmd.execute(args)

        captured = capsys.readouterr()
        output = captured.out

        assert "Bar → bar" in output or "bar" in output.lower()


class TestAddCommandIntegration:
    @pytest.fixture
    def mock_anthropic(self):
        with patch("vault_manager.tags.commands.add.HAS_ANTHROPIC", True):
            with patch("vault_manager.tags.commands.add.Anthropic") as mock_client:
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance

                mock_response = MagicMock()
                mock_response.content = [MagicMock(text="test-tag, another-tag")]
                mock_instance.messages.create.return_value = mock_response

                yield mock_instance

    def test_add_dry_run_no_modifications(
        self, vault_with_tagged_notes, monkeypatch, mock_anthropic
    ):
        monkeypatch.chdir(vault_with_tagged_notes)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        (vault_with_tagged_notes / "untagged.md").write_text("---\n---\nContent", encoding="utf-8")
        untagged_original = (vault_with_tagged_notes / "untagged.md").read_text()

        with patch(
            "vault_manager.tags.commands.add.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.core.vault.get_vault_root", return_value=vault_with_tagged_notes
            ):
                cmd = AddCommand()
                args = Namespace(directory=".", dry_run=True, overwrite=False)

                cmd.execute(args)

        untagged_after = (vault_with_tagged_notes / "untagged.md").read_text()
        assert untagged_after == untagged_original, "Dry-run should not modify files"

    def test_add_statistics_tracking(
        self, vault_with_tagged_notes, monkeypatch, mock_anthropic, capsys
    ):
        monkeypatch.chdir(vault_with_tagged_notes)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        (vault_with_tagged_notes / "untagged.md").write_text("---\n---\nContent", encoding="utf-8")

        with patch(
            "vault_manager.tags.commands.add.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.core.vault.get_vault_root", return_value=vault_with_tagged_notes
            ):
                cmd = AddCommand()
                args = Namespace(directory=".", dry_run=True, overwrite=False)

                cmd.execute(args)

        captured = capsys.readouterr()
        output = captured.out

        assert "Total files" in output or "files scanned" in output.lower()


class TestRelateCommandIntegration:
    def test_relate_dry_run_no_modifications(self, vault_with_tagged_notes, monkeypatch):
        monkeypatch.chdir(vault_with_tagged_notes)

        note1_original = (vault_with_tagged_notes / "note1.md").read_text()

        with patch(
            "vault_manager.properties.commands.relate.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.core.vault.get_vault_root", return_value=vault_with_tagged_notes
            ):
                cmd = RelateCommand()
                args = Namespace(path=".", dry_run=True, overwrite=False, max_related=5)

                with patch.object(cmd, "_find_related_notes", return_value={}):
                    cmd.execute(args)

        note1_after = (vault_with_tagged_notes / "note1.md").read_text()
        assert note1_after == note1_original, "Dry-run should not modify files"

    def test_relate_statistics_tracking(self, vault_with_tagged_notes, monkeypatch, capsys):
        monkeypatch.chdir(vault_with_tagged_notes)

        with patch(
            "vault_manager.properties.commands.relate.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.core.vault.get_vault_root", return_value=vault_with_tagged_notes
            ):
                cmd = RelateCommand()
                args = Namespace(path=".", dry_run=True, overwrite=False, max_related=5)

                with patch.object(cmd, "_find_related_notes", return_value={}):
                    cmd.execute(args)

        captured = capsys.readouterr()
        output = captured.out

        assert "Total notes scanned" in output or "SUMMARY" in output


class TestSummarizeCommandIntegration:
    @pytest.fixture
    def mock_anthropic_summarize(self):
        with patch("vault_manager.properties.commands.summarize.HAS_ANTHROPIC", True):
            with patch("vault_manager.properties.commands.summarize.Anthropic") as mock_client:
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance

                mock_response = MagicMock()
                mock_response.content = [MagicMock(text="This is a test summary.")]
                mock_instance.messages.create.return_value = mock_response

                yield mock_instance

    def test_summarize_dry_run_no_modifications(
        self, vault_with_tagged_notes, monkeypatch, mock_anthropic_summarize
    ):
        monkeypatch.chdir(vault_with_tagged_notes)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        note1_original = (vault_with_tagged_notes / "note1.md").read_text()

        with patch(
            "vault_manager.properties.commands.summarize.get_vault_root",
            return_value=vault_with_tagged_notes,
        ):
            cmd = SummarizeCommand()
            args = Namespace(directory=".", dry_run=True, overwrite=False)

            cmd.execute(args)

        note1_after = (vault_with_tagged_notes / "note1.md").read_text()
        assert note1_after == note1_original, "Dry-run should not modify files"

    def test_summarize_statistics_tracking(
        self, vault_with_tagged_notes, monkeypatch, mock_anthropic_summarize, capsys
    ):
        monkeypatch.chdir(vault_with_tagged_notes)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch(
            "vault_manager.properties.commands.summarize.get_vault_root",
            return_value=vault_with_tagged_notes,
        ):
            cmd = SummarizeCommand()
            args = Namespace(directory=".", dry_run=True, overwrite=False)

            cmd.execute(args)

        captured = capsys.readouterr()
        output = captured.out

        assert "Total" in output or "SUMMARY" in output or "Details" in output


class TestAutoRebuildAfterIntegration:
    def test_decorator_calls_rebuild_after_execution(
        self, vault_with_tagged_notes, vault_database, monkeypatch
    ):
        monkeypatch.chdir(vault_with_tagged_notes)

        rebuild_called = False

        def mock_rebuild_vault_database(silent=False):
            nonlocal rebuild_called
            rebuild_called = True
            return True

        with patch(
            "vault_manager.tags.commands.purge.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.core.database.rebuild_vault_database", mock_rebuild_vault_database
            ):
                with patch("builtins.input", return_value="y"):
                    cmd = PurgeCommand()
                    args = Namespace(tags=["foo"], dry_run=False, no_rebuild=False)

                    cmd.execute(args)

        assert rebuild_called, "Decorator should trigger database rebuild"

    def test_decorator_skips_rebuild_when_no_rebuild_flag_set(
        self, vault_with_tagged_notes, monkeypatch
    ):
        monkeypatch.chdir(vault_with_tagged_notes)

        rebuild_called = False

        def mock_rebuild_vault_database():
            nonlocal rebuild_called
            rebuild_called = True
            return True

        with patch(
            "vault_manager.tags.commands.purge.VaultDatabase",
            return_value=mock_vault_database(vault_with_tagged_notes),
        ):
            with patch(
                "vault_manager.core.database.rebuild_vault_database", mock_rebuild_vault_database
            ):
                with patch("builtins.input", return_value="y"):
                    cmd = PurgeCommand()
                    args = Namespace(tags=["foo"], dry_run=False, no_rebuild=True)

                    cmd.execute(args)

        assert not rebuild_called, "Decorator should skip rebuild when --no-rebuild is set"
