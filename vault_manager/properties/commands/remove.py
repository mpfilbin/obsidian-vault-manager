"""
Remove command - Remove a specific property from frontmatter.

This module implements the remove command which removes a specified property
from YAML frontmatter across all notes in a directory.
"""

import os
import sys
import yaml
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import Command
from ..common import get_vault_root, is_ignored_path, extract_frontmatter


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

        # Process directory
        stats = self._process_directory(target_dir, vault_root, property_name, args.dry_run)

        # Print summary
        self._print_summary(stats, property_name, args.dry_run)

        if not args.dry_run and stats['files_changed'] > 0:
            print(f"\nDone! Modified {stats['files_changed']} file{'s' if stats['files_changed'] != 1 else ''}.")
        elif args.dry_run and stats['files_changed'] > 0:
            print(f"\nDry run complete. {stats['files_changed']} file{'s' if stats['files_changed'] != 1 else ''} would be modified.")
        else:
            print(f"\nNo files contain the property '{property_name}'.")

    def _remove_property_from_frontmatter(self, frontmatter_dict: Dict[str, Any],
                                         property_name: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Remove a property from frontmatter dictionary.

        Args:
            frontmatter_dict: Parsed frontmatter dictionary
            property_name: Name of property to remove

        Returns:
            Tuple of (modified_dict, was_removed)
            - modified_dict: Updated dictionary without the property (None if no change)
            - was_removed: True if property was found and removed
        """
        if property_name not in frontmatter_dict:
            return None, False

        # Create a copy and remove the property
        modified = frontmatter_dict.copy()
        del modified[property_name]

        return modified, True

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
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter
            frontmatter_text, body = extract_frontmatter(content)

            if frontmatter_text is None:
                return True, False

            # Parse frontmatter
            try:
                frontmatter_dict = yaml.safe_load(frontmatter_text)
                if not isinstance(frontmatter_dict, dict):
                    return True, False
            except yaml.YAMLError:
                return True, False

            # Remove property
            modified_dict, was_removed = self._remove_property_from_frontmatter(
                frontmatter_dict, property_name
            )

            if not was_removed:
                return True, False

            # Convert back to YAML
            if modified_dict:
                # Still have properties - write them out
                new_frontmatter = yaml.dump(
                    modified_dict,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False
                ).rstrip('\n')
                updated_content = f"---\n{new_frontmatter}\n---\n{body}"
            else:
                # No properties left - remove frontmatter entirely
                updated_content = body

            # Write back if not dry run
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

            return True, True

        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
            return False, False

    def _process_directory(self, directory: Path, vault_root: Path,
                          property_name: str, dry_run: bool = False) -> Dict:
        """
        Process all markdown files in a directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            property_name: Property to remove
            dry_run: If True, preview changes without modifying files

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'files_with_frontmatter': 0,
            'files_with_property': 0,
            'files_changed': 0,
            'files_failed': 0,
            'files_skipped': 0
        }

        print(f"\n{'DRY RUN - ' if dry_run else ''}Processing markdown files...")

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            # Skip ignored directories
            if is_ignored_path(root_path, vault_root):
                dirs[:] = []
                continue

            for filename in files:
                if not filename.endswith('.md') or filename.endswith('.excalidraw.md'):
                    continue

                stats['total_files'] += 1
                file_path = root_path / filename
                relative_path = str(file_path.relative_to(vault_root))

                success, was_changed = self._update_file_frontmatter(
                    file_path, property_name, dry_run
                )

                if not success:
                    stats['files_failed'] += 1
                    print(f"  ✗ Failed: {relative_path}")
                elif was_changed:
                    stats['files_changed'] += 1
                    stats['files_with_property'] += 1
                    mode = "Would remove" if dry_run else "Removed"
                    print(f"  ✓ {mode} '{property_name}': {relative_path}")

        return stats

    def _print_summary(self, stats: Dict, property_name: str, dry_run: bool = False) -> None:
        """Print summary of processing results."""
        print("\n" + "=" * 60)
        print(f"{'DRY RUN ' if dry_run else ''}SUMMARY")
        print("=" * 60)
        print(f"Total markdown files: {stats['total_files']}")
        print(f"Files with property '{property_name}': {stats['files_with_property']}")
        print(f"Files modified: {stats['files_changed']}")
        print(f"Files failed: {stats['files_failed']}")

        if dry_run and stats['files_changed'] > 0:
            print("\n" + "=" * 60)
            print("This was a DRY RUN - no files were actually modified.")
            print("Run without --dry-run to apply changes.")
            print("=" * 60)
