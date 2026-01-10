"""
Remove command - Remove a specific property from frontmatter.

This module implements the remove command which removes a specified property
from YAML frontmatter across all notes in a directory.
"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Tuple, Optional

from . import Command
from ..common import get_vault_root
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.vault import iter_markdown_files
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary


class RemoveCommand(Command):
    """Command to remove a specific property from frontmatter."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the remove command."""
        parser.add_argument(
            'property_name',
            help='Name of the property to remove from frontmatter'
        )
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
        """Execute the remove command to delete a property from frontmatter."""
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

        # Validate property name
        property_name = args.property_name.strip()
        if not property_name:
            print("Error: Property name cannot be empty")
            sys.exit(1)

        # Display header
        print("=" * 60)
        print("Remove Property from Frontmatter")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Property to remove: '{property_name}'")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Ignored directories: .obsidian, .trash, Excalidraw, Calendar")
        print(f"Ignored file types: .excalidraw.md")

        # Process directory with DryRunContext
        with DryRunContext(args.dry_run) as ctx:
            self._process_directory(target_dir, vault_root, property_name, ctx)

            # Print summary
            print_dry_run_summary(
                ctx,
                additional_info=f"Property removed: '{property_name}'"
            )

        # Final message
        if ctx.stats.files_modified > 0:
            if not args.dry_run:
                print(f"\nDone! Modified {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''}.")
            else:
                print(f"\nDry run complete. {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''} would be modified.")
        else:
            print(f"\nNo files contain the property '{property_name}'.")

    def _update_file_frontmatter(self, file_path: Path, property_name: str,
                                dry_run: bool = False) -> Tuple[bool, bool]:
        """
        Update a file by removing the specified property from frontmatter.

        Args:
            file_path: Path to the markdown file
            property_name: Property to remove
            dry_run: If True, don't actually modify the file

        Returns:
            Tuple of (success, was_changed)
            - success: True if operation completed without errors
            - was_changed: True if the property was found and removed
        """
        was_removed = False

        def updater(content: str) -> Optional[str]:
            nonlocal was_removed

            # Remove property using FrontmatterManager
            updated_content, removed = FrontmatterManager.remove_property(
                content, property_name
            )

            if not removed:
                return None

            was_removed = True
            return updated_content

        success = atomic_update(file_path, updater, dry_run=dry_run)
        return success, was_removed

    def _process_directory(
        self,
        directory: Path,
        vault_root: Path,
        property_name: str,
        ctx: DryRunContext
    ) -> None:
        """
        Process all markdown files in a directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            property_name: Property to remove
            ctx: DryRunContext for tracking operations
        """
        print(f"\n{'DRY RUN - ' if ctx.dry_run else ''}Processing markdown files...")

        # Use iter_markdown_files for memory-efficient traversal
        additional_ignores = {'Excalidraw', 'Calendar'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            ctx.stats.increment('total_files')
            relative_path = str(file_path.relative_to(vault_root))

            success, was_changed = self._update_file_frontmatter(
                file_path, property_name, ctx.dry_run
            )

            if not success:
                ctx.stats.increment('files_failed')
                print(f"  ✗ Failed: {relative_path}")
            elif was_changed:
                ctx.stats.increment('files_modified')
                ctx.stats.increment('files_with_property')
                ctx.record_change(file_path, f"Removed property '{property_name}'")
                mode = "Would remove" if ctx.dry_run else "Removed"
                print(f"  ✓ {mode} '{property_name}': {relative_path}")
