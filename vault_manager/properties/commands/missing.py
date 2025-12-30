"""
Missing command - Find notes without frontmatter.

This module implements the missing command which scans for markdown files
that don't have YAML frontmatter.
"""

import os
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from . import Command
from ..common import get_vault_root, is_ignored_path, extract_frontmatter


class MissingCommand(Command):
    """Command to find and report notes without YAML frontmatter."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the missing command."""
        parser.add_argument(
            'directory',
            nargs='?',
            default=None,
            help='Directory to scan (optional, defaults to entire vault)'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the missing command to find notes without frontmatter."""
        # Get vault root
        vault_root = get_vault_root()

        # Resolve directory path (default to entire vault)
        if args.directory is None or args.directory == '.':
            target_dir = vault_root
        else:
            target_dir = vault_root / args.directory

        # Validate directory if specified
        if args.directory and args.directory != '.':
            if not target_dir.exists():
                print(f"Error: Directory not found: {args.directory}")
                print(f"Looking for: {target_dir}")
                sys.exit(1)

            if not target_dir.is_dir():
                print(f"Error: Not a directory: {args.directory}")
                sys.exit(1)

        # Display header
        print("=" * 60)
        print("Find Notes Without Frontmatter")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Scan directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Ignored directories: .obsidian, .trash, Excalidraw, Calendar")
        print(f"Ignored file types: .excalidraw.md")

        # Scan for missing frontmatter
        print("\nScanning for notes without frontmatter...")
        missing_files, total_files, files_with_frontmatter = self._scan_for_missing_frontmatter(
            target_dir, vault_root
        )

        missing_count = len(missing_files)

        print(f"\nFound {total_files} total markdown files")
        print(f"  - {files_with_frontmatter} files with frontmatter")
        print(f"  - {missing_count} files without frontmatter")

        # Generate report
        print("\nGenerating report...")
        report = self._generate_report(
            missing_files, total_files, files_with_frontmatter, vault_root
        )

        # Write to missing-frontmatter.md
        output_file = vault_root / 'missing-frontmatter.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"Report written to: {output_file}")
        print("\nDone!")

    def _scan_for_missing_frontmatter(self, directory: Path, vault_root: Path) -> Tuple[List[str], int, int]:
        """
        Scan directory for markdown files without YAML frontmatter.

        Returns:
            Tuple of (missing_files, total_files, files_with_frontmatter)
        """
        missing_files = []
        total_files = 0
        files_with_frontmatter = 0

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            # Skip ignored directories
            if is_ignored_path(root_path, vault_root):
                dirs[:] = []
                continue

            # Process markdown files
            for filename in files:
                if not filename.endswith('.md'):
                    continue

                # Skip Excalidraw files
                if filename.endswith('.excalidraw.md'):
                    continue

                total_files += 1
                file_path = root_path / filename

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Check for frontmatter
                    frontmatter, _ = extract_frontmatter(content)

                    if frontmatter is not None:
                        files_with_frontmatter += 1
                    else:
                        # Store relative path from vault root
                        relative_path = file_path.relative_to(vault_root)
                        missing_files.append(str(relative_path))

                except Exception as e:
                    print(f"  Warning: Could not read {file_path}: {e}")

        # Sort missing files for consistent output
        missing_files.sort()

        return missing_files, total_files, files_with_frontmatter

    def _generate_report(self, missing_files: List[str], total_files: int,
                        files_with_frontmatter: int, vault_root: Path) -> str:
        """Generate the missing frontmatter report as a markdown file."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        missing_count = len(missing_files)

        report_lines = [
            "# Notes Without Frontmatter",
            "",
            f"**Generated:** {now}",
            f"**Vault:** `{vault_root}`",
            "",
            "## Summary",
            "",
            f"- **Total markdown files:** {total_files}",
            f"- **Files with frontmatter:** {files_with_frontmatter}",
            f"- **Files without frontmatter:** {missing_count}",
            "",
            "> [!info] Ignored Directories",
            "> `.obsidian`, `.trash`, `Excalidraw`, `Calendar`",
            "",
            "> [!info] Ignored File Types",
            "> `.excalidraw.md`",
            "",
            "## Files Missing Frontmatter",
            "",
        ]

        # Add all missing files as wiki-links
        for file_path in missing_files:
            # Remove .md extension for wiki-link format
            file_path_no_ext = file_path[:-3] if file_path.endswith('.md') else file_path
            report_lines.append(f"- [[{file_path_no_ext}]]")

        return '\n'.join(report_lines) + '\n'
