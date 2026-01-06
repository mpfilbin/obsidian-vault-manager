#!/usr/bin/env python3
"""
Command to set/update a property across markdown files.

This command adds or updates a specified property with a given value
across all files in a directory, with optional filtering by tags.
"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from vault_manager.core.command import Command
from vault_manager.core.vault import get_vault_root, iter_markdown_files, count_markdown_files
from vault_manager.core.frontmatter import extract_tags_from_frontmatter, FrontmatterManager
from vault_manager.core.file_ops import safe_read, atomic_update


class SetCommand(Command):
    """Command to set/update a property across markdown files."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the set command."""
        parser.add_argument(
            'property_name',
            help='Name of the property to set'
        )
        parser.add_argument(
            'value',
            help='Value to set for the property'
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
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite property if it already exists (default: skip files with property)'
        )
        parser.add_argument(
            '--files-with',
            nargs='+',
            metavar='TAG',
            help='Only process files that have ALL of the specified tags'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the set command to add/update a property."""
        vault_root = get_vault_root()
        property_name = args.property_name
        value = args.value
        directory = args.directory
        dry_run = args.dry_run
        overwrite = args.overwrite
        required_tags = set(args.files_with) if args.files_with else None

        # Validate directory
        if directory == '.':
            target_dir = vault_root
        else:
            target_dir = vault_root / directory

        if not target_dir.exists():
            print(f"Error: Directory not found: {directory}")
            sys.exit(1)

        if not target_dir.is_dir():
            print(f"Error: Not a directory: {directory}")
            sys.exit(1)

        print(f"\n{'='*60}")
        print(f"Property Set Tool")
        print(f"{'='*60}")
        print(f"Vault: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Property: {property_name}")
        print(f"Value: {value}")
        print(f"Overwrite existing: {'Yes' if overwrite else 'No'}")
        if required_tags:
            print(f"Filter by tags: {', '.join(sorted(required_tags))}")
        print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE MODE'}")
        print(f"{'='*60}\n")

        # Process all markdown files
        print("Processing files...\n")
        stats = self._process_directory(
            target_dir,
            vault_root,
            property_name,
            value,
            overwrite,
            required_tags,
            dry_run
        )

        # Display summary
        self._print_summary(stats, property_name, value, dry_run)

        if stats['files_modified'] == 0:
            if required_tags:
                print(f"\nNo files found matching the specified tags.")
            else:
                print(f"\nNo files modified (all files already have property '{property_name}').")
            print("Use --overwrite to update existing properties.")

    def _process_directory(
        self,
        directory: Path,
        vault_root: Path,
        property_name: str,
        value: str,
        overwrite: bool,
        required_tags: Optional[set],
        dry_run: bool
    ) -> Dict:
        """
        Process all markdown files in the directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            property_name: Name of the property to set
            value: Value to set
            overwrite: Whether to overwrite existing properties
            required_tags: Set of tags that files must have (all of them)
            dry_run: If True, don't modify files

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'files_with_frontmatter': 0,
            'files_matched_tags': 0,
            'files_modified': 0,
            'files_skipped_has_property': 0,
            'files_skipped_no_tags': 0,
            'files_failed': 0,
            'failed_files': []
        }

        # Get all markdown files
        additional_ignores = {'Excalidraw', 'Calendar'}

        # Count files first for progress tracking
        stats['total_files'] = count_markdown_files(
            directory,
            vault_root,
            additional_ignores=additional_ignores,
            exclude_excalidraw=True
        )

        # Process each file using iterator (memory-efficient)
        for file_path in iter_markdown_files(
            directory,
            vault_root,
            additional_ignores=additional_ignores,
            exclude_excalidraw=True
        ):
            try:
                # Check if file has required tags (if filtering)
                if required_tags:
                    file_tags = self._get_file_tags(file_path)
                    if not required_tags.issubset(set(file_tags)):
                        stats['files_skipped_no_tags'] += 1
                        continue
                    stats['files_matched_tags'] += 1

                # Set property in file
                success, modified = self._set_property_in_file(
                    file_path,
                    vault_root,
                    property_name,
                    value,
                    overwrite,
                    dry_run
                )

                if modified:
                    stats['files_modified'] += 1
                    relative_path = file_path.relative_to(vault_root)
                    mode_prefix = "[DRY RUN] Would set in" if dry_run else "Set in"
                    print(f"{mode_prefix} {relative_path}")
                elif not success:
                    stats['files_failed'] += 1
                else:
                    # File was skipped because it already has the property
                    stats['files_skipped_has_property'] += 1

            except Exception as e:
                stats['files_failed'] += 1
                stats['failed_files'].append((file_path, str(e)))

        return stats

    def _get_file_tags(self, file_path: Path) -> List[str]:
        """
        Extract tags from a file's frontmatter.

        Args:
            file_path: Path to the markdown file

        Returns:
            List of tags in the file
        """
        content = safe_read(file_path, silent=True)
        if content is None:
            return []

        tags = extract_tags_from_frontmatter(content)
        return tags

    def _set_property_in_file(
        self,
        file_path: Path,
        vault_root: Path,
        property_name: str,
        value: str,
        overwrite: bool,
        dry_run: bool
    ) -> Tuple[bool, bool]:
        """
        Set a property in a single file.

        Args:
            file_path: Path to the markdown file
            vault_root: Root directory of the vault
            property_name: Name of the property to set
            value: Value to set
            overwrite: Whether to overwrite existing properties
            dry_run: If True, don't modify the file

        Returns:
            Tuple of (success: bool, modified: bool)
        """
        modified = False

        def updater(content: str) -> Optional[str]:
            nonlocal modified

            # Check if property already exists (unless overwrite is enabled)
            if not overwrite and FrontmatterManager.has_property(content, property_name):
                return None  # Skip, not an error

            # Update property using FrontmatterManager
            updated_content, was_modified = FrontmatterManager.update_property(
                content, property_name, value
            )

            if not was_modified:
                return None

            modified = True
            return updated_content

        success = atomic_update(file_path, updater, dry_run=dry_run, silent=True)
        return success, modified

    def _print_summary(self, stats: Dict, property_name: str, value: str, dry_run: bool) -> None:
        """Print summary statistics."""
        print(f"\n{'='*60}")
        print("Property Set Summary")
        print(f"{'='*60}")
        print(f"\nProperty: {property_name} = {value}")
        print(f"\nStatistics:")
        print(f"  Total files scanned: {stats['total_files']}")
        if stats.get('files_matched_tags', 0) > 0 or stats.get('files_skipped_no_tags', 0) > 0:
            print(f"  Files matching tags: {stats['files_matched_tags']}")
            print(f"  Files skipped (tags): {stats['files_skipped_no_tags']}")
        print(f"  Files modified: {stats['files_modified']}")
        print(f"  Files skipped (already has property): {stats['files_skipped_has_property']}")

        if stats['files_failed'] > 0:
            print(f"\n  Failed files: {stats['files_failed']}")
            if stats['failed_files']:
                print("\n  Files that failed to process:")
                for file_path, error in stats['failed_files'][:10]:
                    print(f"    - {file_path}: {error}")
                if len(stats['failed_files']) > 10:
                    print(f"    ... and {len(stats['failed_files']) - 10} more")

        print(f"\n{'='*60}")

        if dry_run:
            print("\nTo apply these changes, run the command without --dry-run flag.")
