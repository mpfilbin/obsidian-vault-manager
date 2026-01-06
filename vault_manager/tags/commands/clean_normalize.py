#!/usr/bin/env python3
"""
Clean Normalize command - Normalize tag casing to lowercase.

This module implements the clean normalize subcommand which converts all tags
to lowercase for consistency across the vault.
"""

import sys
from argparse import ArgumentParser, Namespace
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from . import Command
from ..common import get_vault_root
from vault_manager.core.frontmatter import FrontmatterManager
from vault_manager.core.vault import iter_markdown_files, validate_directory


class CleanNormalizeCommand(Command):
    """Command to normalize tag casing to lowercase."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the clean normalize command."""
        parser.add_argument(
            'directory',
            help='Directory to process (relative to vault root, use "." for entire vault)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without modifying files or database'
        )
        parser.add_argument(
            '--no-rebuild',
            action='store_true',
            help='Skip automatic database rebuild (rebuild manually with "vault index build")'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the clean normalize command to lowercase all tags."""
        vault_root = get_vault_root()
        dry_run = args.dry_run

        # Validate directory
        target_dir = validate_directory(args.directory, vault_root)

        print(f"\n{'='*60}")
        print(f"Tag Case Normalization Tool")
        print(f"{'='*60}")
        print(f"Vault: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE MODE'}")
        print(f"{'='*60}\n")

        # Process all markdown files in the vault
        print("Scanning for tags with non-lowercase characters...\n")
        stats = self._process_directory(target_dir, vault_root, dry_run, confirm_phase=True)

        # Display summary
        self._print_summary(stats, dry_run)

        # If no tags were found, exit
        if stats['files_modified'] == 0:
            print("\nAll tags are already lowercase.")
            return

        # Show confirmation prompt (only in live mode)
        if not dry_run:
            if not self._confirm_normalize(stats):
                print("\nOperation cancelled by user.")
                return

            # Actually normalize the tags
            print("\nNormalizing tag casing in files...")
            stats = self._process_directory(target_dir, vault_root, dry_run=False, confirm_phase=False)
            self._print_summary(stats, dry_run=False)

            # Rebuild the database
            if stats['files_modified'] > 0:
                if args.no_rebuild:
                    print(f"\n{'='*60}")
                    print("⚠ Database Rebuild Skipped")
                    print(f"{'='*60}")
                    print("\nThe vault.db database was NOT updated.")
                    print("To update the database, run: vault index build")
                    print(f"{'='*60}")
                else:
                    self._rebuild_database()
        else:
            print("\nTo apply these changes, run the command without --dry-run flag.")

    def _process_directory(
        self,
        directory: Path,
        vault_root: Path,
        dry_run: bool,
        confirm_phase: bool = True
    ) -> Dict:
        """
        Process all markdown files in the directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            dry_run: If True, don't modify files
            confirm_phase: If True, this is the preview phase before confirmation

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'files_modified': 0,
            'files_failed': 0,
            'total_tags_normalized': 0,
            'case_changes': Counter(),  # old_tag -> count
            'failed_files': []
        }

        # Use iter_markdown_files for memory-efficient traversal
        additional_ignores = {'Excalidraw', 'Calendar'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            stats['total_files'] += 1

            try:
                success, normalized_count, changes = self._normalize_file(
                    file_path,
                    vault_root,
                    dry_run or confirm_phase
                )

                if normalized_count > 0:
                    stats['files_modified'] += 1
                    stats['total_tags_normalized'] += normalized_count

                    for old_tag, new_tag in changes:
                        stats['case_changes'][f"{old_tag} → {new_tag}"] += 1

                    # Show progress (only during actual normalization, not confirmation)
                    if not confirm_phase:
                        relative_path = file_path.relative_to(vault_root)
                        mode_prefix = "[DRY RUN] Would normalize in" if dry_run else "Normalized in"
                        print(f"{mode_prefix} {relative_path}")
                        for old_tag, new_tag in changes:
                            print(f"  {old_tag} → {new_tag}")

                if not success:
                    stats['files_failed'] += 1

            except Exception as e:
                stats['files_failed'] += 1
                stats['failed_files'].append((file_path, str(e)))

        return stats

    def _normalize_file(
        self,
        file_path: Path,
        vault_root: Path,
        dry_run: bool
    ) -> Tuple[bool, int, List[Tuple[str, str]]]:
        """
        Normalize tag casing in a single file.

        Args:
            file_path: Path to the markdown file
            vault_root: Root directory of the vault
            dry_run: If True, don't modify the file

        Returns:
            Tuple of (success: bool, normalized_count: int, changes: List[(old, new)])
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter using FrontmatterManager
            frontmatter_dict, body = FrontmatterManager.extract(content)

            if frontmatter_dict is None:
                return True, 0, []

            # Normalize tags in frontmatter dict
            updated_dict, normalized_count, changes = self._normalize_tags_in_frontmatter(frontmatter_dict)

            # If no tags were changed, skip this file
            if normalized_count == 0:
                return True, 0, []

            # Serialize back to markdown using FrontmatterManager
            updated_content = FrontmatterManager.serialize(updated_dict, body)

            # Write back to file (unless dry-run)
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

            return True, normalized_count, changes

        except Exception as e:
            return False, 0, []

    def _normalize_tags_in_frontmatter(
        self,
        frontmatter_dict: Dict
    ) -> Tuple[Dict, int, List[Tuple[str, str]]]:
        """
        Normalize tag casing to lowercase in frontmatter dictionary.

        Args:
            frontmatter_dict: Parsed frontmatter dictionary

        Returns:
            Tuple of (updated_dict, normalized_count, changes: List[(old, new)])
        """
        # Get current tags
        if 'tags' not in frontmatter_dict:
            return frontmatter_dict, 0, []

        current_tags = frontmatter_dict['tags']

        # Handle different tag formats
        if current_tags is None:
            return frontmatter_dict, 0, []

        if isinstance(current_tags, str):
            current_tags = [current_tags]
        elif not isinstance(current_tags, list):
            return frontmatter_dict, 0, []

        # Normalize tags to lowercase
        normalized_tags = []
        changes = []
        normalized_count = 0

        for tag in current_tags:
            normalized_tag = tag.lower()
            normalized_tags.append(normalized_tag)

            if tag != normalized_tag:
                changes.append((tag, normalized_tag))
                normalized_count += 1

        # If no tags were changed, return original
        if normalized_count == 0:
            return frontmatter_dict, 0, []

        # Create updated dictionary with normalized tags
        updated_dict = frontmatter_dict.copy()
        updated_dict['tags'] = normalized_tags

        return updated_dict, normalized_count, changes

    def _confirm_normalize(self, stats: Dict) -> bool:
        """
        Show confirmation prompt before normalizing tags.

        Args:
            stats: Statistics dictionary from processing

        Returns:
            True if user confirms, False otherwise
        """
        print(f"\n{'='*60}")
        print("Confirmation Required")
        print(f"{'='*60}")
        print(f"\nFound tags to normalize:")
        print(f"  Files affected: {stats['files_modified']}")
        print(f"  Tags to change: {stats['total_tags_normalized']}")

        if stats['case_changes']:
            print(f"\nMost common changes:")
            for change, count in list(stats['case_changes'].most_common(10)):
                print(f"  - {change}: {count} occurrence{'s' if count != 1 else ''}")

        response = input("\nProceed with normalization? (y/n): ").strip().lower()
        return response == 'y'

    def _print_summary(self, stats: Dict, dry_run: bool) -> None:
        """Print summary statistics."""
        print(f"\n{'='*60}")
        print("Tag Case Normalization Summary")
        print(f"{'='*60}")
        print(f"\nStatistics:")
        print(f"  Total files scanned: {stats['total_files']}")
        print(f"  Files modified: {stats['files_modified']}")
        print(f"  Total tags normalized: {stats['total_tags_normalized']}")

        if stats['case_changes']:
            print(f"\nCase changes:")
            for change, count in stats['case_changes'].most_common(20):
                print(f"  - {change}: {count} occurrence{'s' if count != 1 else ''}")

        if stats['files_failed'] > 0:
            print(f"\nFailed files: {stats['files_failed']}")
            if stats['failed_files']:
                print("\nFiles that failed to process:")
                for file_path, error in stats['failed_files'][:10]:
                    print(f"  - {file_path}: {error}")
                if len(stats['failed_files']) > 10:
                    print(f"  ... and {len(stats['failed_files']) - 10} more")

        print(f"\n{'='*60}")

    def _rebuild_database(self) -> None:
        """Rebuild the vault index database after normalizing tags."""
        from vault_manager.core.database import rebuild_vault_database
        rebuild_vault_database()
