#!/usr/bin/env python3
"""
Command to purge specified tags from all markdown files and database.

This command removes one or more specified tags from all files in the vault,
updates the files' frontmatter, and rebuilds the vault index database.
"""

import sys
from argparse import ArgumentParser, Namespace
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from vault_manager.core.command import Command
from vault_manager.core.vault import get_vault_root, iter_markdown_files, count_markdown_files
from vault_manager.core.frontmatter import FrontmatterManager


class PurgeCommand(Command):
    """Command to purge specified tags from all markdown files and database."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the purge command."""
        parser.add_argument(
            'tags',
            nargs='+',
            help='One or more tags to purge from the vault (case-sensitive)'
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
        """Execute the purge command to remove specified tags."""
        vault_root = get_vault_root()
        tags_to_purge = set(args.tags)  # Convert to set for faster lookup
        dry_run = args.dry_run

        print(f"\n{'='*60}")
        print(f"Tag Purge Tool")
        print(f"{'='*60}")
        print(f"Vault: {vault_root}")
        print(f"Tags to purge: {', '.join(sorted(tags_to_purge))}")
        print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE MODE'}")
        print(f"{'='*60}\n")

        # Process all markdown files in the vault
        print("Scanning vault for tags to purge...\n")
        stats = self._process_vault(vault_root, tags_to_purge, dry_run)

        # Display summary
        self._print_summary(stats, tags_to_purge, dry_run)

        # If no tags were found, exit
        if stats['total_tags_removed'] == 0:
            print("\nNo matching tags found in vault.")
            return

        # Show confirmation prompt (only in live mode)
        if not dry_run:
            if not self._confirm_purge(stats):
                print("\nOperation cancelled by user.")
                return

            # Actually purge the tags
            print("\nPurging tags from files...")
            stats = self._process_vault(vault_root, tags_to_purge, dry_run=False, confirm_phase=False)
            self._print_summary(stats, tags_to_purge, dry_run=False)

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

    def _process_vault(
        self,
        vault_root: Path,
        tags_to_purge: set,
        dry_run: bool,
        confirm_phase: bool = True
    ) -> Dict:
        """
        Process all markdown files in the vault.

        Args:
            vault_root: Root directory of the vault
            tags_to_purge: Set of tags to remove
            dry_run: If True, don't modify files
            confirm_phase: If True, this is the preview phase before confirmation

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'files_with_frontmatter': 0,
            'files_modified': 0,
            'files_failed': 0,
            'total_tags_removed': 0,
            'purged_tag_counts': Counter(),
            'failed_files': []
        }

        # Get all markdown files (excluding ignored directories)
        additional_ignores = {'Excalidraw'}

        # Count files first for progress tracking
        stats['total_files'] = count_markdown_files(
            vault_root,
            vault_root,
            additional_ignores=additional_ignores,
            exclude_excalidraw=True
        )

        # Process each file using iterator (memory-efficient)
        for file_path in iter_markdown_files(
            vault_root,
            vault_root,
            additional_ignores=additional_ignores,
            exclude_excalidraw=True
        ):
            try:
                success, removed_tags = self._purge_file(
                    file_path,
                    vault_root,
                    tags_to_purge,
                    dry_run or confirm_phase
                )

                if removed_tags:
                    stats['files_modified'] += 1
                    stats['total_tags_removed'] += len(removed_tags)
                    stats['purged_tag_counts'].update(removed_tags)

                    # Show progress (only during actual purge, not confirmation)
                    if not confirm_phase:
                        relative_path = file_path.relative_to(vault_root)
                        mode_prefix = "[DRY RUN] Would remove from" if dry_run else "Removed from"
                        tags_str = ", ".join(removed_tags)
                        print(f"{mode_prefix} {relative_path}: {tags_str}")

                if not success:
                    stats['files_failed'] += 1

            except Exception as e:
                stats['files_failed'] += 1
                stats['failed_files'].append((file_path, str(e)))

        return stats

    def _purge_file(
        self,
        file_path: Path,
        vault_root: Path,
        tags_to_purge: set,
        dry_run: bool
    ) -> Tuple[bool, List[str]]:
        """
        Purge specified tags from a single file.

        Args:
            file_path: Path to the markdown file
            vault_root: Root directory of the vault
            tags_to_purge: Set of tags to remove
            dry_run: If True, don't modify the file

        Returns:
            Tuple of (success: bool, removed_tags: List[str])
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter using FrontmatterManager
            frontmatter_dict, body = FrontmatterManager.extract(content)

            if frontmatter_dict is None:
                return True, []

            # Purge tags from frontmatter dict
            updated_dict, removed_tags = self._purge_tags_from_frontmatter(
                frontmatter_dict,
                tags_to_purge
            )

            # If no tags were removed, skip this file
            if not removed_tags:
                return True, []

            # Serialize back to markdown using FrontmatterManager
            updated_content = FrontmatterManager.serialize(updated_dict, body)

            # Write back to file (unless dry-run)
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

            return True, removed_tags

        except Exception as e:
            return False, []

    def _purge_tags_from_frontmatter(
        self,
        frontmatter_dict: Dict,
        tags_to_purge: set
    ) -> Tuple[Dict, List[str]]:
        """
        Remove specified tags from frontmatter dictionary.

        Args:
            frontmatter_dict: Parsed frontmatter dictionary
            tags_to_purge: Set of tags to remove

        Returns:
            Tuple of (updated_dict, removed_tags)
        """
        # Get current tags
        if 'tags' not in frontmatter_dict:
            return frontmatter_dict, []

        current_tags = frontmatter_dict['tags']

        # Handle different tag formats
        if current_tags is None:
            return frontmatter_dict, []

        if isinstance(current_tags, str):
            current_tags = [current_tags]
        elif not isinstance(current_tags, list):
            return frontmatter_dict, []

        # Filter out tags to purge (case-sensitive exact match)
        removed_tags = []
        updated_tags = []

        for tag in current_tags:
            if tag in tags_to_purge:
                removed_tags.append(tag)
            else:
                updated_tags.append(tag)

        # If no tags were removed, return original
        if not removed_tags:
            return frontmatter_dict, []

        # Create updated dictionary with remaining tags
        # Keep empty list if all tags removed (per user requirement)
        updated_dict = frontmatter_dict.copy()
        updated_dict['tags'] = updated_tags

        return updated_dict, removed_tags

    def _confirm_purge(self, stats: Dict) -> bool:
        """
        Show confirmation prompt before purging tags.

        Args:
            stats: Statistics dictionary from processing

        Returns:
            True if user confirms, False otherwise
        """
        print(f"\n{'='*60}")
        print("Confirmation Required")
        print(f"{'='*60}")
        print(f"\nFound tags to purge:")

        for tag, count in stats['purged_tag_counts'].most_common():
            print(f"  - {tag}: {count} occurrence{'s' if count != 1 else ''}")

        print(f"\nTotal: {stats['total_tags_removed']} tag{'s' if stats['total_tags_removed'] != 1 else ''} "
              f"will be removed from {stats['files_modified']} file{'s' if stats['files_modified'] != 1 else ''}")

        response = input("\nProceed with purge? (y/n): ").strip().lower()
        return response == 'y'

    def _print_summary(self, stats: Dict, tags_to_purge: set, dry_run: bool) -> None:
        """Print summary statistics."""
        print(f"\n{'='*60}")
        print("Tag Purge Summary")
        print(f"{'='*60}")
        print(f"\nStatistics:")
        print(f"  Total files scanned: {stats['total_files']}")
        print(f"  Files modified: {stats['files_modified']}")
        print(f"  Total tags removed: {stats['total_tags_removed']}")

        if stats['purged_tag_counts']:
            print(f"\nTags purged:")
            for tag, count in stats['purged_tag_counts'].most_common():
                print(f"  - {tag}: {count} occurrence{'s' if count != 1 else ''}")

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
        """Rebuild the vault index database after purging tags."""
        from vault_manager.core.database import rebuild_vault_database
        rebuild_vault_database()
