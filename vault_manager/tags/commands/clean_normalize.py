#!/usr/bin/env python3
"""
Clean Normalize command - Normalize tag casing to lowercase.

This module implements the clean normalize subcommand which converts all tags
to lowercase for consistency across the vault.
"""

from argparse import ArgumentParser, Namespace
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from . import Command
from ..common import get_vault_root
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.vault import iter_markdown_files, validate_directory
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.database import auto_rebuild_after
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary


class CleanNormalizeCommand(Command):
    """Command to normalize tag casing to lowercase."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the clean normalize command."""
        parser.add_argument(
            'directory',
            help='Directory to process (relative to vault root, use "." for entire vault)'
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

    @auto_rebuild_after("tag case normalization")
    def execute(self, args: Namespace) -> None:
        """Execute the clean normalize command to lowercase all tags."""
        vault_root = get_vault_root()

        # Validate directory
        target_dir = validate_directory(args.directory, vault_root)

        print(f"\n{'='*60}")
        print(f"Tag Case Normalization Tool")
        print(f"{'='*60}")
        print(f"Vault: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE MODE'}")
        print(f"{'='*60}\n")

        # Process all markdown files in the vault
        print("Scanning for tags with non-lowercase characters...\n")

        with DryRunContext(args.dry_run) as ctx:
            case_changes = self._process_directory(target_dir, vault_root, ctx)

            # If no tags were found, exit early
            if ctx.stats.files_modified == 0:
                print("\nAll tags are already lowercase.")
                return

            # Show confirmation prompt (only in live mode)
            if not args.dry_run:
                if not self._confirm_normalize(ctx, case_changes):
                    print("\nOperation cancelled by user.")
                    return

                # Actually normalize the tags
                print("\nNormalizing tag casing in files...")
                self._process_directory(target_dir, vault_root, ctx, confirm_phase=False)

            # Display summary
            self._print_custom_summary(ctx, case_changes)
            print_dry_run_summary(ctx)

    def _process_directory(
        self,
        directory: Path,
        vault_root: Path,
        ctx: DryRunContext,
        confirm_phase: bool = True
    ) -> Counter:
        """
        Process all markdown files in the directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            ctx: DryRunContext for tracking operations
            confirm_phase: If True, this is the preview phase before confirmation

        Returns:
            Counter with case change counts
        """
        case_changes = Counter()
        failed_files = []

        # Use iter_markdown_files for memory-efficient traversal
        additional_ignores = {'Excalidraw', 'Calendar'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            ctx.stats.increment('total_files')

            try:
                success, normalized_count, changes = self._normalize_file(
                    file_path,
                    vault_root,
                    ctx.dry_run or confirm_phase
                )

                if normalized_count > 0:
                    ctx.stats.increment('files_modified')
                    ctx.stats.increment('total_tags_normalized', normalized_count)

                    for old_tag, new_tag in changes:
                        case_changes[f"{old_tag} → {new_tag}"] += 1

                    ctx.record_change(
                        file_path,
                        f"Normalized {normalized_count} tag(s)",
                        changes=changes
                    )

                    # Show progress (only during actual normalization, not confirmation)
                    if not confirm_phase:
                        relative_path = file_path.relative_to(vault_root)
                        mode_prefix = "[DRY RUN] Would normalize in" if ctx.dry_run else "Normalized in"
                        print(f"{mode_prefix} {relative_path}")
                        for old_tag, new_tag in changes:
                            print(f"  {old_tag} → {new_tag}")

                if not success:
                    ctx.stats.increment('files_failed')

            except Exception as e:
                ctx.stats.increment('files_failed')
                failed_files.append((file_path, str(e)))

        # Store failed files in context for reporting
        if failed_files:
            ctx.stats.custom_stats['failed_files'] = failed_files

        return case_changes

    def _normalize_file(
        self,
        file_path: Path,
        vault_root: Path,
        dry_run: bool
    ) -> Tuple[bool, int, List[Tuple[str, str]]]:
        """
        Normalize tag casing in a single file.

        Args:
            file_path: Path to the markdown file
            vault_root: Root directory of the vault
            dry_run: If True, don't modify the file

        Returns:
            Tuple of (success: bool, normalized_count: int, changes: List[(old, new)])
        """
        normalized_count = 0
        changes = []

        def updater(content: str) -> Optional[str]:
            nonlocal normalized_count, changes

            # Extract frontmatter using FrontmatterManager
            frontmatter_dict, body = FrontmatterManager.extract(content)

            if frontmatter_dict is None:
                return None

            # Normalize tags in frontmatter dict
            updated_dict, count, chgs = self._normalize_tags_in_frontmatter(frontmatter_dict)

            # If no tags were changed, skip this file
            if count == 0:
                return None

            normalized_count = count
            changes = chgs

            # Serialize back to markdown using FrontmatterManager
            return FrontmatterManager.serialize(updated_dict, body)

        success = atomic_update(file_path, updater, dry_run=dry_run, silent=True)
        return success, normalized_count, changes

    def _normalize_tags_in_frontmatter(
        self,
        frontmatter_dict: Dict
    ) -> Tuple[Dict, int, List[Tuple[str, str]]]:
        """
        Normalize tag casing to lowercase in frontmatter dictionary.

        Args:
            frontmatter_dict: Parsed frontmatter dictionary

        Returns:
            Tuple of (updated_dict, normalized_count, changes: List[(old, new)])
        """
        # Get current tags
        if 'tags' not in frontmatter_dict:
            return frontmatter_dict, 0, []

        current_tags = frontmatter_dict['tags']

        # Handle different tag formats
        if current_tags is None:
            return frontmatter_dict, 0, []

        if isinstance(current_tags, str):
            current_tags = [current_tags]
        elif not isinstance(current_tags, list):
            return frontmatter_dict, 0, []

        # Normalize tags to lowercase
        normalized_tags = []
        changes = []
        normalized_count = 0

        for tag in current_tags:
            normalized_tag = tag.lower()
            normalized_tags.append(normalized_tag)

            if tag != normalized_tag:
                changes.append((tag, normalized_tag))
                normalized_count += 1

        # If no tags were changed, return original
        if normalized_count == 0:
            return frontmatter_dict, 0, []

        # Create updated dictionary with normalized tags
        updated_dict = frontmatter_dict.copy()
        updated_dict['tags'] = normalized_tags

        return updated_dict, normalized_count, changes

    def _confirm_normalize(self, ctx: DryRunContext, case_changes: Counter) -> bool:
        """
        Show confirmation prompt before normalizing tags.

        Args:
            ctx: DryRunContext with statistics
            case_changes: Counter with case change counts

        Returns:
            True if user confirms, False otherwise
        """
        print(f"\n{'='*60}")
        print("Confirmation Required")
        print(f"{'='*60}")
        print(f"\nFound tags to normalize:")
        print(f"  Files affected: {ctx.stats.files_modified}")
        print(f"  Tags to change: {ctx.stats.custom_stats.get('total_tags_normalized', 0)}")

        if case_changes:
            print(f"\nMost common changes:")
            for change, count in list(case_changes.most_common(10)):
                print(f"  - {change}: {count} occurrence{'s' if count != 1 else ''}")

        response = input("\nProceed with normalization? (y/n): ").strip().lower()
        return response == 'y'

    def _print_custom_summary(self, ctx: DryRunContext, case_changes: Counter) -> None:
        """Print custom summary statistics for tag normalization."""
        print(f"\n{'='*60}")
        print("Tag Case Normalization Details")
        print(f"{'='*60}")

        if case_changes:
            print(f"\nCase changes:")
            for change, count in case_changes.most_common(20):
                print(f"  - {change}: {count} occurrence{'s' if count != 1 else ''}")

        failed_files = ctx.stats.custom_stats.get('failed_files', [])
        if failed_files:
            print(f"\nFiles that failed to process:")
            for file_path, error in failed_files[:10]:
                print(f"  - {file_path}: {error}")
            if len(failed_files) > 10:
                print(f"  ... and {len(failed_files) - 10} more")

        print(f"\n{'='*60}")

