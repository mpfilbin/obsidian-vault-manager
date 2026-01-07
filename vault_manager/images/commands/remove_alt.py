"""
Remove-alt command - Remove alt text from image embeds.

This module implements the remove-alt command which removes alt text from
wiki-link image embeds in markdown files.
"""

import re
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Tuple, Optional

from . import Command
from ..common import get_vault_root, IMAGE_EXTENSIONS
from vault_manager.core.vault import iter_markdown_files
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary


class RemoveAltCommand(Command):
    """Command to remove alt text from wiki-link image embeds."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the remove-alt command."""
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
        """Execute the remove-alt command to remove alt text from image embeds."""
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
        print("Remove Image Alt Text from Wiki-Links")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Ignored directories: .obsidian, .trash, Excalidraw")

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
            print("\nNo changes needed.")

    def _remove_alt_text_from_content(self, content: str) -> Tuple[str, int]:
        """
        Remove alt text from wiki-link image embeds.

        Returns:
            Tuple of (modified_content, number_of_changes)
        """
        changes = 0

        # Build pattern for image extensions
        ext_pattern = '|'.join(re.escape(ext) for ext in IMAGE_EXTENSIONS)

        # Match ![[...image.ext|alt text]]
        pattern = r'!\[\[([^\]|]+(?:' + ext_pattern + r'))\|(.*?)\]\]'

        def replacer(match):
            nonlocal changes
            file_path = match.group(1)
            changes += 1
            return f'![[{file_path}]]'

        modified_content = re.sub(pattern, replacer, content, flags=re.IGNORECASE | re.DOTALL)

        return modified_content, changes

    def _process_file(self, file_path: Path, dry_run: bool = False) -> Tuple[bool, int]:
        """
        Process a single markdown file to remove image alt text.

        Returns:
            Tuple of (success, number_of_changes)
        """
        changes = 0

        def updater(content: str) -> Optional[str]:
            nonlocal changes

            # Process content
            modified_content, chgs = self._remove_alt_text_from_content(content)

            # If no changes, return early
            if chgs == 0:
                return None

            changes = chgs
            return modified_content

        success = atomic_update(file_path, updater, dry_run=dry_run)
        return success, changes

    def _process_directory(self, directory: Path, vault_root: Path, ctx: DryRunContext) -> None:
        """
        Recursively process all markdown files in a directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            ctx: DryRunContext for tracking operations
        """
        print(f"\n{'DRY RUN - ' if ctx.dry_run else ''}Processing markdown files...")

        for file_path in iter_markdown_files(directory, vault_root, additional_ignores={'Excalidraw'}, exclude_excalidraw=False):
            ctx.stats.increment('total_files')

            # Process the file
            success, changes = self._process_file(file_path, ctx.dry_run)

            if success:
                ctx.stats.increment('files_processed')
                if changes > 0:
                    ctx.stats.increment('files_modified')
                    ctx.stats.increment('total_changes', changes)
                    relative_path = file_path.relative_to(vault_root)

                    ctx.record_change(file_path, f"Removed alt text from {changes} image{'s' if changes != 1 else ''}")
                    mode = "Would modify" if ctx.dry_run else "Modified"
                    print(f"  {mode}: {relative_path} ({changes} change{'s' if changes != 1 else ''})")
            else:
                ctx.stats.increment('files_failed')
                relative_path = file_path.relative_to(vault_root)
                print(f"  ✗ Failed: {relative_path}")
