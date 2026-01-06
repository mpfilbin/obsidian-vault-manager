"""
Remove-alt command - Remove alt text from image embeds.

This module implements the remove-alt command which removes alt text from
wiki-link image embeds in markdown files.
"""

import re
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, Tuple

from . import Command
from ..common import get_vault_root, IMAGE_EXTENSIONS
from vault_manager.core.vault import iter_markdown_files


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

        # Process directory
        stats = self._process_directory(target_dir, vault_root, args.dry_run)

        # Print summary
        self._print_summary(stats, args.dry_run)

        if not args.dry_run and stats['modified_files'] > 0:
            print(f"\nDone! Modified {stats['modified_files']} file{'s' if stats['modified_files'] != 1 else ''}.")
        elif args.dry_run and stats['modified_files'] > 0:
            print(f"\nDry run complete. {stats['modified_files']} file{'s' if stats['modified_files'] != 1 else ''} would be modified.")
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
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # Process content
            modified_content, changes = self._remove_alt_text_from_content(original_content)

            # If no changes, return early
            if changes == 0:
                return True, 0

            # Write back if not dry run
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)

            return True, changes

        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
            return False, 0

    def _process_directory(self, directory: Path, vault_root: Path, dry_run: bool = False) -> Dict:
        """
        Recursively process all markdown files in a directory.

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'processed_files': 0,
            'modified_files': 0,
            'total_changes': 0,
            'failed_files': [],
            'modified_file_list': []
        }

        print(f"\n{'DRY RUN - ' if dry_run else ''}Processing markdown files...")

        for file_path in iter_markdown_files(directory, vault_root, additional_ignores={'Excalidraw'}, exclude_excalidraw=False):
            stats['total_files'] += 1

            # Process the file
            success, changes = self._process_file(file_path, dry_run)

            if success:
                stats['processed_files'] += 1
                if changes > 0:
                    stats['modified_files'] += 1
                    stats['total_changes'] += changes
                    relative_path = file_path.relative_to(vault_root)
                    stats['modified_file_list'].append((str(relative_path), changes))

                    mode = "Would modify" if dry_run else "Modified"
                    print(f"  {mode}: {relative_path} ({changes} change{'s' if changes != 1 else ''})")
            else:
                stats['failed_files'].append(str(file_path.relative_to(vault_root)))

        return stats

    def _print_summary(self, stats: Dict, dry_run: bool = False) -> None:
        """Print summary of alt text removal results."""
        print("\n" + "=" * 60)
        print(f"{'DRY RUN ' if dry_run else ''}SUMMARY")
        print("=" * 60)
        print(f"Total markdown files: {stats['total_files']}")
        print(f"Successfully processed: {stats['processed_files']}")
        print(f"Files modified: {stats['modified_files']}")
        print(f"Total changes: {stats['total_changes']}")

        if stats['failed_files']:
            print(f"\nFailed files ({len(stats['failed_files'])}):")
            for file_path in stats['failed_files']:
                print(f"  - {file_path}")

        if dry_run and stats['modified_files'] > 0:
            print("\n" + "=" * 60)
            print("This was a DRY RUN - no files were actually modified.")
            print("Run without --dry-run to apply changes.")
            print("=" * 60)
