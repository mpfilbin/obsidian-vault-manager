"""
Unit tests for the properties init command.

Tests verify that `vault properties init` adds tags: [] frontmatter to
markdown files that have none, leaves files with existing frontmatter
untouched, supports --dry-run, and respects directory scope and ignore
rules.
"""

from argparse import Namespace
from unittest.mock import patch

from vault_manager.properties.cli import create_parser
from vault_manager.properties.commands.init import InitCommand


def _run_init(vault_path, directory=".", dry_run=False):
    with patch(
        "vault_manager.properties.commands.init.get_vault_root",
        return_value=vault_path,
    ):
        cmd = InitCommand()
        args = Namespace(directory=directory, dry_run=dry_run)
        cmd.execute(args)


class TestInitCommand:
    def test_adds_frontmatter_to_file_without_it(self, vault_with_notes):
        vault_path = vault_with_notes['path']
        target = vault_path / "note_no_frontmatter.md"
        original = target.read_text(encoding="utf-8")

        _run_init(vault_path)

        updated = target.read_text(encoding="utf-8")
        assert updated == f"---\ntags: []\n---\n{original}"

    def test_leaves_file_with_tags_untouched(self, vault_with_notes):
        vault_path = vault_with_notes['path']
        target = vault_path / "note_with_tags.md"
        original = target.read_text(encoding="utf-8")

        _run_init(vault_path)

        assert target.read_text(encoding="utf-8") == original

    def test_leaves_frontmatter_without_tags_untouched(self, vault_with_notes):
        vault_path = vault_with_notes['path']
        target = vault_path / "note_no_tags.md"
        original = target.read_text(encoding="utf-8")

        _run_init(vault_path)

        assert target.read_text(encoding="utf-8") == original

    def test_dry_run_does_not_write(self, vault_with_notes):
        vault_path = vault_with_notes['path']
        target = vault_path / "note_no_frontmatter.md"
        original = target.read_text(encoding="utf-8")

        _run_init(vault_path, dry_run=True)

        assert target.read_text(encoding="utf-8") == original

    def test_dry_run_reports_would_initialize(self, vault_with_notes, capsys):
        vault_path = vault_with_notes['path']

        _run_init(vault_path, dry_run=True)

        output = capsys.readouterr().out
        assert "Would initialize" in output
        assert "note_no_frontmatter.md" in output

    def test_respects_directory_scope(self, temp_vault):
        subdir_a = temp_vault / "DirA"
        subdir_b = temp_vault / "DirB"
        subdir_a.mkdir()
        subdir_b.mkdir()

        file_a = subdir_a / "a.md"
        file_b = subdir_b / "b.md"
        file_a.write_text("# A\n", encoding="utf-8")
        file_b.write_text("# B\n", encoding="utf-8")

        _run_init(temp_vault, directory="DirA")

        assert file_a.read_text(encoding="utf-8") == "---\ntags: []\n---\n# A\n"
        assert file_b.read_text(encoding="utf-8") == "# B\n"

    def test_skips_ignored_directories(self, temp_vault):
        excalidraw_dir = temp_vault / "Excalidraw"
        excalidraw_dir.mkdir()
        ignored_file = excalidraw_dir / "drawing.md"
        ignored_file.write_text("# Drawing\n", encoding="utf-8")

        _run_init(temp_vault)

        assert ignored_file.read_text(encoding="utf-8") == "# Drawing\n"

    def test_leaves_adjacent_empty_frontmatter_delimiters_untouched(self, temp_vault):
        target = temp_vault / "empty_frontmatter.md"
        target.write_text("---\n---\n# Heading\n", encoding="utf-8")

        _run_init(temp_vault)

        assert target.read_text(encoding="utf-8") == "---\n---\n# Heading\n"


class TestInitCommandCliWiring:
    def test_init_subcommand_is_registered(self):
        parser = create_parser()

        args = parser.parse_args(["init", "Personal", "--dry-run"])

        assert args.command == "init"
        assert args.directory == "Personal"
        assert args.dry_run is True

    def test_init_subcommand_defaults(self):
        parser = create_parser()

        args = parser.parse_args(["init"])

        assert args.command == "init"
        assert args.directory is None
        assert args.dry_run is False
