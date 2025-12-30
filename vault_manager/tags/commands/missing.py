"""
Missing tags command - Generate report of notes without tags.

This module implements the missing command which scans the vault for markdown
files without tags in their frontmatter.
"""

from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from .import Command
from ..common import get_vault_root, is_ignored_path, extract_tags_from_frontmatter


class MissingCommand(Command):
    """Command to generate a report of files missing tags."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the missing tags command."""
        # Missing command has no additional arguments
        pass

    def execute(self, args: Namespace) -> None:
        """Execute the missing tags command."""
        print("Scanning vault for notes missing tags...")

        # Scan the vault
        tagless_files, total_files, tagged_files = self._scan_vault()

        print(f"Found {total_files} total markdown files")
        print(f"  - {tagged_files} files with tags")
        print(f"  - {len(tagless_files)} files missing tags")

        # Generate report
        report = self._generate_report(tagless_files, total_files, tagged_files)

        # Write to tagless-notes.md
        vault_root = get_vault_root()
        output_file = vault_root / 'tagless-notes.md'

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\nReport written to: {output_file}")
        print("Done!")

    def _has_tags_in_frontmatter(self, content: str) -> bool:
        """
        Check if content has tags in its YAML frontmatter.

        Returns:
            True if the file has tags in frontmatter, False otherwise
        """
        tags = extract_tags_from_frontmatter(content)
        return len(tags) > 0

    def _scan_vault(self) -> Tuple[List[str], int, int]:
        """
        Scan the vault for markdown files and identify those without tags.

        Returns:
            Tuple of (tagless_files, total_files, tagged_files)
        """
        vault_root = get_vault_root()
        tagless_files = []
        total_files = 0
        tagged_files = 0

        # Walk through all markdown files
        for md_file in vault_root.rglob('*.md'):
            # Skip ignored paths
            if is_ignored_path(md_file, vault_root):
                continue

            total_files += 1

            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for tags in frontmatter
                if self._has_tags_in_frontmatter(content):
                    tagged_files += 1
                else:
                    # Store relative path from vault root
                    relative_path = md_file.relative_to(vault_root)
                    tagless_files.append(str(relative_path))

            except Exception as e:
                print(f"Warning: Could not read {md_file}: {e}")

        # Sort tagless files for consistent output
        tagless_files.sort()

        return tagless_files, total_files, tagged_files

    def _generate_report(self, tagless_files: List[str], total_files: int, tagged_files: int) -> str:
        """
        Generate the missing tags notes report as markdown with wiki-links.

        Returns:
            The report content as a markdown string
        """
        vault_root = get_vault_root()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tagless_count = len(tagless_files)

        report_lines = [
            "---",
            "tags:",
            "  - vault-management",
            "  - tagless",
            "---",
            "",
            "# Notes Without Tags",
            "",
            f"**Generated:** {now}",
            f"**Vault:** `{vault_root}`",
            f"**Ignored directories:** `.obsidian`, `Excalidraw/Scripts`",
            "",
            "## Statistics",
            "",
            f"- Total markdown files: {total_files}",
            f"- Files with tags: {tagged_files}",
            f"- Files without tags: {tagless_count}",
            "",
            "## Files Without Tags",
            "",
        ]

        if tagless_count == 0:
            report_lines.append("No files without tags found! All markdown files have tags.")
        else:
            report_lines.append("The following files do not have tags in their frontmatter:")
            report_lines.append("")
            # Add wiki-links for each tagless file (without .md extension)
            for file_path in tagless_files:
                # Remove .md extension for wiki-link
                file_path_no_ext = file_path[:-3] if file_path.endswith('.md') else file_path
                report_lines.append(f"- [[{file_path_no_ext}]]")

        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("*Generated by `vault tags missing`*")

        return '\n'.join(report_lines) + '\n'
