"""
Deduplicate command - Remove duplicate frontmatter properties.

This module implements the deduplicate command which removes duplicate
frontmatter keys, keeping only the last occurrence of each property.
"""

import yaml
from argparse import ArgumentParser, Namespace
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from . import Command
from ..common import get_vault_root
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.vault import iter_markdown_files, validate_directory
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary


class DeduplicateCommand(Command):
    """Command to remove duplicate frontmatter properties from notes."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the deduplicate command."""
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
        """Execute the deduplicate command to remove duplicate properties."""
        # Get vault root
        vault_root = get_vault_root()

        # Validate directory
        target_dir = validate_directory(args.directory, vault_root)

        # Display header
        print("=" * 60)
        print("Remove Duplicate Frontmatter Properties")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Ignored directories: .obsidian, .trash, Excalidraw, Calendar")
        print()
        print("Strategy: Keep last occurrence of duplicate properties")

        # Process directory with DryRunContext
        with DryRunContext(args.dry_run) as ctx:
            self._process_directory(target_dir, vault_root, ctx)

            # Print summary
            print_dry_run_summary(ctx, additional_info="Strategy: Keep last occurrence of duplicate properties")

        # Final message
        if ctx.stats.files_modified > 0:
            if not args.dry_run:
                print(f"\nDone! Modified {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''}.")
            else:
                print(f"\nDry run complete. {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''} would be modified.")
        else:
            print("\nNo duplicate properties found.")

    def _parse_frontmatter_raw(self, frontmatter: str) -> Tuple[OrderedDict, List[str]]:
        """
        Parse YAML frontmatter and detect duplicates.

        Returns:
            Tuple of (deduplicated_dict, list_of_duplicate_keys)
            The dict uses OrderedDict to preserve order, keeping last occurrence.
        """
        duplicates = []
        seen_keys = set()

        # Parse YAML while detecting duplicates
        # We'll parse it normally first to get values
        try:
            parsed = yaml.safe_load(frontmatter) or {}
        except yaml.YAMLError:
            return OrderedDict(), []

        # Now parse line by line to detect duplicates
        # This is necessary because yaml.safe_load silently overwrites duplicates
        lines = frontmatter.split('\n')
        keys_in_order = []

        for line in lines:
            # Check if line is a top-level key (not indented, contains ':')
            if line and not line.startswith(' ') and not line.startswith('-') and ':' in line:
                key = line.split(':', 1)[0].strip()
                if key:
                    if key in seen_keys:
                        if key not in duplicates:
                            duplicates.append(key)
                    else:
                        seen_keys.add(key)
                    keys_in_order.append(key)

        # Build deduplicated dict keeping last occurrence
        deduplicated = OrderedDict()
        for key in keys_in_order:
            if key in parsed:
                deduplicated[key] = parsed[key]

        return deduplicated, duplicates

    def _deduplicate_frontmatter(self, frontmatter: str) -> Tuple[Optional[Dict], List[str]]:
        """
        Remove duplicate properties from frontmatter.

        Returns:
            Tuple of (deduplicated_dict, list_of_duplicates_removed)
            Returns (None, []) if no duplicates found
        """
        deduplicated_dict, duplicates = self._parse_frontmatter_raw(frontmatter)

        # If no duplicates, return None to indicate no changes
        if not duplicates:
            return None, []

        # Return the deduplicated dict (serialization will be done by FrontmatterManager)
        return dict(deduplicated_dict), duplicates

    def _deduplicate_file(self, file_path: Path, vault_root: Path, dry_run: bool = False) -> Tuple[bool, List[str]]:
        """
        Remove duplicate properties from a single file.

        Returns:
            Tuple of (success, list_of_duplicates_removed)
        """
        duplicates = []

        def updater(content: str) -> Optional[str]:
            nonlocal duplicates

            # Extract frontmatter (need raw text for duplicate detection)
            from ..common import extract_frontmatter
            frontmatter_text, body = extract_frontmatter(content)

            if frontmatter_text is None:
                return None

            # Deduplicate frontmatter (returns dict or None)
            deduplicated_dict, dups = self._deduplicate_frontmatter(frontmatter_text)

            # If no duplicates found, skip
            if not dups:
                return None

            duplicates = dups

            # Serialize back to markdown using FrontmatterManager
            return FrontmatterManager.serialize(deduplicated_dict, body)

        success = atomic_update(file_path, updater, dry_run=dry_run)
        return success, duplicates

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

            # Deduplicate the file
            success, duplicates = self._deduplicate_file(file_path, vault_root, ctx.dry_run)

            if not success:
                ctx.stats.increment('files_failed')
                print(f"  ✗ Failed: {relative_path}")
            elif duplicates:
                ctx.stats.increment('files_modified')
                ctx.stats.increment('total_duplicates_removed', len(duplicates))
                for key in duplicates:
                    ctx.stats.increment(f'duplicate_property_{key}')

                ctx.record_change(file_path, f"Removed {len(duplicates)} duplicate properties", properties=duplicates)
                mode = "Would fix" if ctx.dry_run else "Fixed"
                print(f"  {mode}: {relative_path}")
                for key in duplicates:
                    print(f"    - Removed duplicate '{key}' property")
