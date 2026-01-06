"""
Clean Invalid command - Remove invalid tags from notes.

This module implements the clean invalid subcommand which removes tags that don't
conform to Obsidian's tag validation rules.
"""

import sys
from argparse import ArgumentParser, Namespace
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from . import Command
from ..common import get_vault_root
from vault_manager.core.frontmatter import FrontmatterManager, is_valid_obsidian_tag
from vault_manager.core.vault import iter_markdown_files


class CleanInvalidCommand(Command):
    """Command to remove invalid tags from note frontmatter."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the clean invalid command."""
        parser.add_argument(
            'directory',
            help='Directory to process (relative to vault root, use "." for entire vault)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without modifying files'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the clean invalid command to remove invalid tags."""
        # Get vault root
        vault_root = get_vault_root()

        # Resolve directory path
        if args.directory == '.':
            target_dir = vault_root
        else:
            target_dir = vault_root / args.directory

        # Validate directory
        if not target_dir.exists():
            print(f"Error: Directory not found: {args.directory}")
            print(f"Looking for: {target_dir}")
            sys.exit(1)

        if not target_dir.is_dir():
            print(f"Error: Not a directory: {args.directory}")
            sys.exit(1)

        # Display header
        print("=" * 60)
        print("Remove Invalid Tags from Notes")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Ignored directories: .obsidian, .trash, Excalidraw, Calendar")
        print()
        print("Obsidian Tag Rules:")
        print("  - Must contain only: letters, numbers, underscore (_), hyphen (-), slash (/)")
        print("  - Must contain at least one non-numerical character (letter or underscore)")
        print("  - Examples: #1984 (invalid), #y1984 (valid), #_test (valid)")

        # Process directory
        stats = self._process_directory(target_dir, vault_root, args.dry_run)

        # Print summary
        self._print_summary(stats, args.dry_run)

        if not args.dry_run and stats['files_modified'] > 0:
            print(f"\nDone! Modified {stats['files_modified']} file{'s' if stats['files_modified'] != 1 else ''}.")
        elif args.dry_run and stats['files_modified'] > 0:
            print(f"\nDry run complete. {stats['files_modified']} file{'s' if stats['files_modified'] != 1 else ''} would be modified.")
        else:
            print("\nNo invalid tags found.")

    def _clean_tags_from_frontmatter(self, frontmatter_dict: Optional[Dict]) -> Tuple[Optional[Dict], List[str], List[str]]:
        """
        Remove invalid tags from frontmatter dictionary.

        Args:
            frontmatter_dict: Parsed frontmatter dictionary

        Returns:
            Tuple of (updated_dict, valid_tags, removed_tags)
        """
        if frontmatter_dict is None:
            return None, [], []

        # Extract current tags
        tags = frontmatter_dict.get('tags', [])
        if not tags:
            return frontmatter_dict, [], []

        # Ensure tags is a list
        if isinstance(tags, str):
            tags = [tags]
        elif not isinstance(tags, list):
            return frontmatter_dict, [], []

        # Validate and filter tags
        valid_tags = []
        removed_tags = []

        for tag in tags:
            tag_str = str(tag).strip()
            if is_valid_obsidian_tag(tag_str):
                valid_tags.append(tag_str)
            else:
                removed_tags.append(tag_str)

        # If no tags were removed, return None to indicate no changes
        if not removed_tags:
            return None, valid_tags, []

        # Create updated dictionary
        updated_dict = frontmatter_dict.copy()

        # Update with valid tags only
        if valid_tags:
            updated_dict['tags'] = valid_tags
        else:
            # Remove tags field entirely if no valid tags remain
            if 'tags' in updated_dict:
                del updated_dict['tags']

        return updated_dict, valid_tags, removed_tags

    def _clean_file(self, file_path: Path, vault_root: Path, dry_run: bool = False) -> Tuple[bool, List[str]]:
        """
        Clean invalid tags from a single file.

        Returns:
            Tuple of (success, list_of_removed_tags)
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter using FrontmatterManager
            frontmatter_dict, body = FrontmatterManager.extract(content)

            if frontmatter_dict is None:
                return True, []

            # Clean tags from frontmatter
            updated_dict, valid_tags, removed_tags = self._clean_tags_from_frontmatter(frontmatter_dict)

            # If no tags were removed, skip
            if not removed_tags:
                return True, []

            # Serialize back to markdown
            updated_content = FrontmatterManager.serialize(updated_dict, body)

            # Write back if not dry run
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

            return True, removed_tags

        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
            return False, []

    def _process_directory(self, directory: Path, vault_root: Path, dry_run: bool = False) -> Dict:
        """
        Recursively process all markdown files in a directory.

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'files_with_frontmatter': 0,
            'files_modified': 0,
            'files_failed': 0,
            'total_tags_removed': 0,
            'invalid_tag_counts': Counter(),
            'failed_files': []
        }

        print(f"\n{'DRY RUN - ' if dry_run else ''}Processing markdown files...")

        # Use iter_markdown_files for memory-efficient traversal
        additional_ignores = {'Excalidraw', 'Calendar'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            stats['total_files'] += 1
            relative_path = file_path.relative_to(vault_root)

            # Clean the file
            success, removed_tags = self._clean_file(file_path, vault_root, dry_run)

            if not success:
                stats['files_failed'] += 1
                stats['failed_files'].append(str(relative_path))
            elif removed_tags:
                stats['files_modified'] += 1
                stats['total_tags_removed'] += len(removed_tags)
                for tag in removed_tags:
                    stats['invalid_tag_counts'][tag] += 1

                mode = "Would remove from" if dry_run else "Removed from"
                print(f"  {mode}: {relative_path}")
                for tag in removed_tags:
                    print(f"    - '{tag}' (invalid)")

        return stats

    def _print_summary(self, stats: Dict, dry_run: bool = False) -> None:
        """Print summary of cleaning results."""
        print("\n" + "=" * 60)
        print(f"{'DRY RUN ' if dry_run else ''}SUMMARY")
        print("=" * 60)
        print(f"Total markdown files scanned: {stats['total_files']}")
        print(f"Files modified: {stats['files_modified']}")
        print(f"Files failed: {stats['files_failed']}")
        print(f"Total invalid tags removed: {stats['total_tags_removed']}")

        if stats['invalid_tag_counts']:
            print(f"\nInvalid tags removed (top 20):")
            for tag, count in stats['invalid_tag_counts'].most_common(20):
                print(f"  - '{tag}': {count} occurrence{'s' if count != 1 else ''}")

        if stats['failed_files']:
            print(f"\nFailed files ({len(stats['failed_files'])})::")
            for file_path in stats['failed_files']:
                print(f"  - {file_path}")

        if dry_run and stats['files_modified'] > 0:
            print("\n" + "=" * 60)
            print("This was a DRY RUN - no files were actually modified.")
            print("Run without --dry-run to apply changes.")
            print("=" * 60)
