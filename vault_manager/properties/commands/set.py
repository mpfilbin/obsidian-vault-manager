#!/usr/bin/env python3
"""
Command to set/update a property across markdown files.

This command adds or updates a specified property with a given value
across all files in a directory, with optional filtering by tags.
"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import List, Optional, Tuple

from vault_manager.core.command import Command
from vault_manager.core.vault import get_vault_root, iter_markdown_files, count_markdown_files
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.file_ops import safe_read, atomic_update
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary


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

        # Process all markdown files with DryRunContext
        print("Processing files...\n")
        with DryRunContext(dry_run) as ctx:
            self._process_directory(
                target_dir,
                vault_root,
                property_name,
                value,
                overwrite,
                required_tags,
                ctx
            )

            # Display summary
            additional_info = f"Property: {property_name} = {value}"
            if required_tags:
                additional_info += f"\nFiltered by tags: {', '.join(sorted(required_tags))}"
            print_dry_run_summary(ctx, additional_info=additional_info)

        if ctx.stats.files_modified == 0:
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
        ctx: DryRunContext
    ) -> None:
        """
        Process all markdown files in the directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            property_name: Name of the property to set
            value: Value to set
            overwrite: Whether to overwrite existing properties
            required_tags: Set of tags that files must have (all of them)
            ctx: DryRunContext for tracking operations
        """
        # Get all markdown files
        additional_ignores = {'Excalidraw', 'Calendar'}

        # Count files first for progress tracking
        total_files = count_markdown_files(
            directory,
            vault_root,
            additional_ignores=additional_ignores,
            exclude_excalidraw=True
        )
        ctx.stats.increment('total_files', total_files)

        # Process each file using iterator (memory-efficient)
        for file_path in iter_markdown_files(
            directory,
            vault_root,
            additional_ignores=additional_ignores,
            exclude_excalidraw=True
        ):
            try:
                ctx.stats.increment('files_processed')

                # Check if file has required tags (if filtering)
                if required_tags:
                    file_tags = self._get_file_tags(file_path)
                    if not required_tags.issubset(set(file_tags)):
                        ctx.stats.increment('files_skipped_no_tags')
                        continue
                    ctx.stats.increment('files_matched_tags')

                # Set property in file
                success, modified = self._set_property_in_file(
                    file_path,
                    vault_root,
                    property_name,
                    value,
                    overwrite,
                    ctx.dry_run
                )

                if modified:
                    ctx.stats.increment('files_modified')
                    ctx.record_change(
                        file_path,
                        f"Set property '{property_name}' = '{value}'"
                    )
                    relative_path = file_path.relative_to(vault_root)
                    mode_prefix = "[DRY RUN] Would set in" if ctx.dry_run else "Set in"
                    print(f"{mode_prefix} {relative_path}")
                elif not success:
                    ctx.stats.increment('files_failed')
                else:
                    # File was skipped because it already has the property
                    ctx.stats.increment('files_skipped_has_property')

            except Exception as e:
                ctx.stats.increment('files_failed')
                ctx.stats.increment('failed_file_count')
                relative_path = file_path.relative_to(vault_root)
                print(f"  ✗ Failed: {relative_path} ({e})")

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

        tags = FrontmatterManager.extract_tags_from_frontmatter(content)
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
