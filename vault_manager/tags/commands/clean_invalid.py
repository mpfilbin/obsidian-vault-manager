"""
Clean Invalid command - Remove invalid tags from notes.

This module implements the clean invalid subcommand which removes tags that don't
conform to Obsidian's tag validation rules.
"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from . import Command
from ..common import get_vault_root
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.vault import iter_markdown_files
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary


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

        # Process directory with DryRunContext
        with DryRunContext(args.dry_run) as ctx:
            self._process_directory(target_dir, vault_root, ctx)
            print_dry_run_summary(ctx)

        # Final message
        if ctx.stats.files_modified > 0:
            if not args.dry_run:
                print(f"\nDone! Modified {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''}.")
            else:
                print(f"\nDry run complete. {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''} would be modified.")
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
            if FrontmatterManager.is_valid_obsidian_tag(tag_str):
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
        removed_tags = []

        def updater(content: str) -> Optional[str]:
            nonlocal removed_tags

            # Extract frontmatter using FrontmatterManager
            frontmatter_dict, body = FrontmatterManager.extract(content)

            if frontmatter_dict is None:
                return None

            # Clean tags from frontmatter
            updated_dict, valid_tags, tags_removed = self._clean_tags_from_frontmatter(frontmatter_dict)

            # If no tags were removed, skip
            if not tags_removed:
                return None

            removed_tags = tags_removed

            # Serialize back to markdown
            return FrontmatterManager.serialize(updated_dict, body)

        success = atomic_update(file_path, updater, dry_run=dry_run)
        return success, removed_tags

    def _process_directory(self, directory: Path, vault_root: Path, ctx: DryRunContext) -> None:
        """
        Recursively process all markdown files in a directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            ctx: DryRunContext for tracking operations
        """
        print(f"\n{'DRY RUN - ' if ctx.dry_run else ''}Processing markdown files...")

        # Use iter_markdown_files for memory-efficient traversal
        additional_ignores = {'Excalidraw', 'Calendar'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            ctx.stats.increment('total_files')
            relative_path = file_path.relative_to(vault_root)

            # Clean the file
            success, removed_tags = self._clean_file(file_path, vault_root, ctx.dry_run)

            if not success:
                ctx.stats.increment('files_failed')
                print(f"  ✗ Failed: {relative_path}")
            elif removed_tags:
                ctx.stats.increment('files_modified')
                ctx.stats.increment('total_tags_removed', len(removed_tags))
                for tag in removed_tags:
                    ctx.stats.increment(f'invalid_tag_{tag}')

                ctx.record_change(file_path, f"Removed {len(removed_tags)} invalid tags", tags=removed_tags)
                mode = "Would remove from" if ctx.dry_run else "Removed from"
                print(f"  {mode}: {relative_path}")
                for tag in removed_tags:
                    print(f"    - '{tag}' (invalid)")

