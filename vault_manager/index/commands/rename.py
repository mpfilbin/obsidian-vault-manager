"""
Rename command - Fix mangled filenames by replacing underscores and plus signs.

This module implements the rename command which identifies files with
underscores or plus signs in their names and provides functionality to
rename them with spaces instead.
"""

import os
import re
import sqlite3
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import List, Tuple

from . import Command
from ..common import get_vault_root, get_database_path


class RenameCommand(Command):
    """Command to fix mangled filenames."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the rename command."""
        subparsers = parser.add_subparsers(
            dest='subcommand',
            required=True,
            help='Rename sub-commands'
        )

        # Find subcommand
        find_parser = subparsers.add_parser(
            'find',
            help='Find files with mangled names (preview)'
        )

        # Apply subcommand
        apply_parser = subparsers.add_parser(
            'apply',
            help='Rename files and update links'
        )
        apply_parser.add_argument(
            '--no-link-update',
            action='store_true',
            help='Skip updating links in markdown files'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the rename command."""
        if args.subcommand == 'find':
            self._find_mangled_names()
        elif args.subcommand == 'apply':
            self._apply_renames(update_links=not args.no_link_update)

    def _is_valid_filename(self, filename: str) -> Tuple[bool, str]:
        """
        Check if a filename is valid across Windows, macOS, and Linux.

        Args:
            filename: The filename to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for empty filename
        if not filename or filename.strip() == '':
            return False, "Filename is empty"

        # Check for reserved directory names
        if filename in {'.', '..'}:
            return False, "Reserved directory name"

        # Forbidden characters across all platforms:
        # - Windows: < > : " / \ | ? *
        # - Linux: / (path separator), null
        # - macOS: / (path separator), : (converted to / by HFS+), null
        # We use the superset (most restrictive) for cross-platform compatibility
        forbidden_chars = '<>:"/\\|?*'
        for char in forbidden_chars:
            if char in filename:
                return False, f"Contains forbidden character: '{char}'"

        # Check for null character (forbidden on all platforms)
        if '\0' in filename:
            return False, "Contains null character"

        # Check for control characters (ASCII 0-31)
        # Problematic on all platforms
        for i, char in enumerate(filename):
            if ord(char) < 32:
                return False, f"Contains control character at position {i}"

        # Check for trailing dots or spaces (problematic on Windows)
        if filename.endswith('.') or filename.endswith(' '):
            return False, "Ends with dot or space (invalid on Windows)"

        # Check maximum filename length (255 bytes on most filesystems)
        # This is the limit for ext4 (Linux), APFS (macOS), NTFS (Windows)
        if len(filename.encode('utf-8')) > 255:
            return False, f"Filename too long ({len(filename.encode('utf-8'))} bytes, max 255)"

        # Check for reserved names on Windows (case-insensitive)
        name_without_ext = filename.rsplit('.', 1)[0].upper()
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        if name_without_ext in reserved_names:
            return False, f"Reserved name on Windows: {name_without_ext}"

        return True, ""

    def _should_skip_file(self, file_path: str, filename: str) -> bool:
        """
        Check if a file should be skipped from renaming.

        Args:
            file_path: Full relative path to file
            filename: Just the filename

        Returns:
            True if file should be skipped
        """
        # Skip files in Library/ directory (code, not content)
        if file_path.startswith('Library/'):
            return True

        # Skip files in _resources directories
        if '/_resources' in file_path or file_path.startswith('_resources/'):
            return True

        # Skip Python files with double underscores (Python convention)
        if '__' in filename:
            return True

        # Skip URL-encoded filenames (https%3A%2F%2F...)
        if filename.startswith('http') and '%' in filename:
            return True

        return False

    def _clean_filename(self, filename: str) -> str:
        """
        Clean a filename by replacing underscores and plus signs with spaces.

        Args:
            filename: Original filename

        Returns:
            Cleaned filename with _ and + replaced by spaces
        """
        # Replace underscores and plus signs with spaces
        cleaned = filename.replace('_', ' ').replace('+', ' ')

        # Clean up multiple consecutive spaces
        cleaned = re.sub(r' +', ' ', cleaned)

        return cleaned

    def _get_mangled_files(self) -> List[Tuple[str, str]]:
        """
        Get list of files with mangled names and their proposed new names.

        Returns:
            List of tuples: (old_path, new_path)
        """
        db_path = get_database_path()
        if not db_path.exists():
            print(f"Error: Database not found at {db_path}")
            print("Run 'vault index build' first to create the database.")
            return []

        # Query all files from database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT file_path FROM files ORDER BY file_path')
        all_files = [row[0] for row in cursor.fetchall()]
        conn.close()

        vault_root = get_vault_root()
        renames = []

        for file_path in all_files:
            path = Path(file_path)
            original_name = path.name

            # Skip files that shouldn't be renamed
            if self._should_skip_file(file_path, original_name):
                continue

            cleaned_name = self._clean_filename(original_name)

            # Check if name would change
            if original_name != cleaned_name:
                # Validate the cleaned filename
                is_valid, error_msg = self._is_valid_filename(cleaned_name)
                if not is_valid:
                    # Skip files where the cleaned name would be invalid
                    print(f"  ⚠ Skipping {file_path}: cleaned name invalid - {error_msg}")
                    continue

                new_path = str(path.parent / cleaned_name) if path.parent != Path('.') else cleaned_name

                # Check if target already exists
                target = vault_root / new_path
                if target.exists() and str(new_path) not in all_files:
                    # File exists on disk but not in database (probably in ignored dir)
                    continue

                renames.append((file_path, new_path))

        return renames

    def _find_mangled_names(self) -> None:
        """Find and generate report of files with mangled names."""
        print("Finding files with mangled names...")

        renames = self._get_mangled_files()

        if not renames:
            print("\nNo files with mangled names found!")
            return

        print(f"Found {len(renames)} files with mangled names")

        # Generate report
        print("\nGenerating report...")
        report = self._generate_report(renames)

        # Write to renames.md
        vault_root = get_vault_root()
        output_file = vault_root / 'renames.md'

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"✓ Report written to: {output_file}")
        print("\nNext steps:")
        print("1. Review renames.md")
        print("2. Check boxes next to files to rename")
        print("3. Run: vault index rename apply")

    def _generate_report(self, renames: List[Tuple[str, str]]) -> str:
        """Generate markdown report for renames."""
        from collections import defaultdict
        from datetime import datetime

        # Group by directory
        by_directory = defaultdict(list)
        for old_path, new_path in renames:
            directory = str(Path(old_path).parent) if Path(old_path).parent != Path('.') else 'Root'
            by_directory[directory].append((old_path, new_path))

        # Build report header
        vault_root = get_vault_root()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = [
            "---",
            "tags:",
            "  - vault-management",
            "  - renames",
            "  - files",
            "---",
            "",
            "# Mangled Filenames",
            "",
            f"**Generated:** {now}",
            f"**Vault:** `{vault_root}`",
            "",
            "## Statistics",
            "",
            f"- Files with mangled names: {len(renames)}",
            f"- Directories affected: {len(by_directory)}",
            "",
            "## Files to Rename",
            "",
            "*Check boxes next to files you want to rename. Underscores (_) and plus signs (+) will be replaced with spaces.*",
            ""
        ]

        # Group by directory
        for directory in sorted(by_directory.keys()):
            files = by_directory[directory]

            # Show directory header
            lines.append(f"### {directory}")
            lines.append("")
            lines.append(f"*{len(files)} file(s) in this directory*")
            lines.append("")

            # List files with checkboxes
            for old_path, new_path in files:
                old_name = Path(old_path).name
                new_name = Path(new_path).name

                lines.append(f"- [ ] **`{old_name}`** → `{new_name}`")
                lines.append(f"  - Full path: `{old_path}`")
                lines.append("")

        # Add instructions
        lines.extend([
            "---",
            "",
            "## Instructions",
            "",
            "1. Review the proposed renames above",
            "2. Check `[ ]` boxes next to files you want to rename",
            "3. Run: `vault index rename apply`",
            "4. Links in markdown files will be automatically updated",
            "5. After renaming, run: `vault index build` to update the database",
            "",
            "---",
            "",
            "*Generated by `vault index rename find`*"
        ])

        return '\n'.join(lines) + '\n'

    def _apply_renames(self, update_links: bool = True) -> None:
        """
        Apply renames to files and optionally update links.

        Args:
            update_links: Whether to update links in markdown files
        """
        print("Applying renames...")

        vault_root = get_vault_root()
        report_file = vault_root / 'renames.md'

        if not report_file.exists():
            print(f"Error: renames.md not found at {report_file}")
            print("Run 'vault index rename find' first to generate the report.")
            return

        # Parse report for checked items
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract checked items: - [x] **`old_name`** → `new_name`
        #   - Full path: `old_path`
        # Pattern matches across newline with indentation
        pattern = r'- \[x\] \*\*`([^`]+)`\*\* → `([^`]+)`[^\n]*\n\s+- Full path: `([^`]+)`'
        checked_renames = []

        for match in re.finditer(pattern, content, re.MULTILINE):
            old_name = match.group(1)
            new_name = match.group(2)
            old_path = match.group(3)

            # Construct new path
            path = Path(old_path)
            new_path = str(path.parent / new_name) if path.parent != Path('.') else new_name

            checked_renames.append((old_path, new_path))

        if not checked_renames:
            print("No files checked for renaming.")
            print("Please check boxes in renames.md next to files you want to rename.")
            return

        print(f"Found {len(checked_renames)} files marked for renaming")

        renamed_files = []
        skipped_files = []
        failed_files = []

        print(f"\nRenaming {len(checked_renames)} files...\n")

        for old_path, new_path in checked_renames:
            source = vault_root / old_path
            target = vault_root / new_path

            # Validate new filename
            new_filename = Path(new_path).name
            is_valid, error_msg = self._is_valid_filename(new_filename)
            if not is_valid:
                print(f"  ⚠ Skip: Invalid filename - {old_path}")
                print(f"         → {error_msg}")
                skipped_files.append((old_path, f"Invalid filename: {error_msg}"))
                continue

            if not source.exists():
                print(f"  ⚠ Skip: Source not found - {old_path}")
                skipped_files.append((old_path, "Source not found"))
                continue

            if target.exists() and old_path != new_path:
                print(f"  ⚠ Skip: Target already exists - {new_path}")
                skipped_files.append((old_path, "Target exists"))
                continue

            # Create parent directory if needed
            target.parent.mkdir(parents=True, exist_ok=True)

            try:
                os.rename(str(source), str(target))
                renamed_files.append((old_path, new_path))
                print(f"  ✓ Renamed: {old_path}")
                print(f"         → {new_path}")
            except Exception as e:
                failed_files.append((old_path, str(e)))
                print(f"  ✗ Error: {old_path} - {e}")

        # Update links in markdown files
        if update_links and renamed_files:
            print("\nUpdating links in markdown files...")
            self._update_links(renamed_files)

        # Update report (remove renamed items)
        if renamed_files:
            new_lines = []
            renamed_old_paths = {old_path for old_path, _ in renamed_files}

            i = 0
            lines = content.split('\n')
            while i < len(lines):
                line = lines[i]

                # Check if this is a checked rename item
                match = re.match(pattern, line)
                if match and match.group(3) in renamed_old_paths:
                    # Skip this line and the next line (Full path)
                    i += 2
                    # Skip empty line if present
                    if i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue

                new_lines.append(line)
                i += 1

            with open(report_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))

        # Print summary
        print("\n" + "=" * 80)
        print("Rename Summary")
        print("=" * 80)
        print(f"Successfully renamed: {len(renamed_files)} files")
        print(f"Skipped: {len(skipped_files)} files")
        print(f"Failed: {len(failed_files)} files")

        if skipped_files:
            print("\nSkipped files:")
            for path, reason in skipped_files:
                print(f"  - {path}: {reason}")

        if failed_files:
            print("\nFailed files:")
            for path, error in failed_files:
                print(f"  - {path}: {error}")

        if renamed_files:
            print("\nReport updated: renames.md")
            print("\n⚠ Important: Run 'vault index build' to update the database.")

    def _update_links(self, renames: List[Tuple[str, str]]) -> None:
        """
        Update links in markdown files to reflect renamed files.

        Args:
            renames: List of (old_path, new_path) tuples
        """
        # Create mapping of old filename -> new filename (just the name, not full path)
        name_map = {}
        for old_path, new_path in renames:
            old_name = Path(old_path).name
            new_name = Path(new_path).name
            name_map[old_name] = new_name

        vault_root = get_vault_root()
        updated_files = []

        # Get all markdown files
        db_path = get_database_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM files WHERE file_path LIKE '%.md'")
        md_files = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Update links in each markdown file
        for md_path in md_files:
            file_path = vault_root / md_path

            if not file_path.exists():
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content

                # Update wiki-links and image embeds
                # Pattern: [[filename]] or [[filename|alias]] or ![[filename]]
                for old_name, new_name in name_map.items():
                    # Escape special regex characters in filenames
                    escaped_old = re.escape(old_name)

                    # Replace wiki-links: [[old_name]] and [[old_name|alias]]
                    content = re.sub(
                        rf'\[\[{escaped_old}(\|[^\]]+)?\]\]',
                        lambda m: f'[[{new_name}{m.group(1) if m.group(1) else ""}]]',
                        content
                    )

                    # Replace image embeds: ![[old_name]] and ![[old_name|alias]]
                    content = re.sub(
                        rf'!\[\[{escaped_old}(\|[^\]]+)?\]\]',
                        lambda m: f'![[{new_name}{m.group(1) if m.group(1) else ""}]]',
                        content
                    )

                # Write back if changed
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    updated_files.append(md_path)
                    print(f"  ✓ Updated links in: {md_path}")

            except Exception as e:
                print(f"  ✗ Error updating {md_path}: {e}")

        if updated_files:
            print(f"\nUpdated links in {len(updated_files)} markdown files")
        else:
            print("\nNo links needed updating")
