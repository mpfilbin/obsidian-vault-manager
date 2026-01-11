#!/usr/bin/env python3
"""
Command to purge specified tags from all markdown files and database.

This command removes one or more specified tags from all files in the vault,
updates the files' frontmatter, and rebuilds the vault index database.
"""

from argparse import ArgumentParser, Namespace
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from vault_manager.core.command import Command
from vault_manager.core.database import VaultDatabase, auto_rebuild_after
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.vault import count_markdown_files, iter_markdown_files


class PurgeCommand(Command):
    """Command to purge specified tags from all markdown files and database."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the purge command."""
        parser.add_argument(
            "tags", nargs="+", help="One or more tags to purge from the vault (case-sensitive)"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without modifying files or database",
        )
        parser.add_argument(
            "--no-rebuild",
            action="store_true",
            help='Skip automatic database rebuild (rebuild manually with "vault index build")',
        )

    @auto_rebuild_after()
    def execute(self, args: Namespace) -> None:
        """Execute the purge command to remove specified tags."""
        vault_root = VaultDatabase().vault_root
        tags_to_purge = set(args.tags)  # Convert to set for faster lookup

        print(f"\n{'=' * 60}")
        print("Tag Purge Tool")
        print(f"{'=' * 60}")
        print(f"Vault: {vault_root}")
        print(f"Tags to purge: {', '.join(sorted(tags_to_purge))}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE MODE'}")
        print(f"{'=' * 60}\n")

        # Process all markdown files in the vault
        print("Scanning vault for tags to purge...\n")

        with DryRunContext(args.dry_run) as ctx:
            tag_counts = self._process_vault(vault_root, tags_to_purge, ctx)

            # If no tags were found, exit early
            if ctx.stats.custom_stats.get("total_tags_removed", 0) == 0:
                print("\nNo matching tags found in vault.")
                return

            # Show confirmation prompt (only in live mode)
            if not args.dry_run:
                if not self._confirm_purge(ctx, tag_counts):
                    print("\nOperation cancelled by user.")
                    return

                # Actually purge the tags
                print("\nPurging tags from files...")
                self._process_vault(vault_root, tags_to_purge, ctx, confirm_phase=False)

            # Display summary
            self._print_custom_summary(ctx, tag_counts)
            print_dry_run_summary(ctx)

    def _process_vault(
        self, vault_root: Path, tags_to_purge: set, ctx: DryRunContext, confirm_phase: bool = True
    ) -> Counter:
        """
        Process all markdown files in the vault.

        Args:
            vault_root: Root directory of the vault
            tags_to_purge: Set of tags to remove
            ctx: DryRunContext for tracking operations
            confirm_phase: If True, this is the preview phase before confirmation

        Returns:
            Counter with tag removal counts
        """
        tag_counts = Counter()
        failed_files = []

        # Get all markdown files (excluding ignored directories)
        additional_ignores = {"Excalidraw"}

        # Count files first for progress tracking
        ctx.stats.total_files = count_markdown_files(
            vault_root, vault_root, additional_ignores=additional_ignores, exclude_excalidraw=True
        )

        # Process each file using iterator (memory-efficient)
        for file_path in iter_markdown_files(
            vault_root, vault_root, additional_ignores=additional_ignores, exclude_excalidraw=True
        ):
            try:
                success, removed_tags = self._purge_file(
                    file_path, vault_root, tags_to_purge, ctx.dry_run or confirm_phase
                )

                if removed_tags:
                    ctx.stats.increment("files_modified")
                    ctx.stats.increment("total_tags_removed", len(removed_tags))
                    tag_counts.update(removed_tags)

                    ctx.record_change(
                        file_path, f"Removed {len(removed_tags)} tag(s)", tags=removed_tags
                    )

                    # Show progress (only during actual purge, not confirmation)
                    if not confirm_phase:
                        relative_path = file_path.relative_to(vault_root)
                        mode_prefix = (
                            "[DRY RUN] Would remove from" if ctx.dry_run else "Removed from"
                        )
                        tags_str = ", ".join(removed_tags)
                        print(f"{mode_prefix} {relative_path}: {tags_str}")

                if not success:
                    ctx.stats.increment("files_failed")

            except Exception as e:
                ctx.stats.increment("files_failed")
                failed_files.append((file_path, str(e)))

        # Store failed files in context for reporting
        if failed_files:
            ctx.stats.custom_stats["failed_files"] = failed_files

        return tag_counts

    def _purge_file(
        self, file_path: Path, vault_root: Path, tags_to_purge: set, dry_run: bool
    ) -> Tuple[bool, List[str]]:
        """
        Purge specified tags from a single file.

        Args:
            file_path: Path to the markdown file
            vault_root: Root directory of the vault
            tags_to_purge: Set of tags to remove
            dry_run: If True, don't modify the file

        Returns:
            Tuple of (success: bool, removed_tags: List[str])
        """
        removed_tags = []

        def updater(content: str) -> Optional[str]:
            nonlocal removed_tags

            # Extract frontmatter using FrontmatterManager
            frontmatter_dict, body = FrontmatterManager.extract(content)

            if frontmatter_dict is None:
                return None

            # Purge tags from frontmatter dict
            updated_dict, tags_removed = self._purge_tags_from_frontmatter(
                frontmatter_dict, tags_to_purge
            )

            # If no tags were removed, skip this file
            if not tags_removed:
                return None

            removed_tags = tags_removed

            # Serialize back to markdown using FrontmatterManager
            return FrontmatterManager.serialize(updated_dict, body)

        success = atomic_update(file_path, updater, dry_run=dry_run, silent=True)
        return success, removed_tags

    def _purge_tags_from_frontmatter(
        self, frontmatter_dict: Dict, tags_to_purge: set
    ) -> Tuple[Dict, List[str]]:
        """
        Remove specified tags from frontmatter dictionary.

        Args:
            frontmatter_dict: Parsed frontmatter dictionary
            tags_to_purge: Set of tags to remove

        Returns:
            Tuple of (updated_dict, removed_tags)
        """
        # Get current tags
        if "tags" not in frontmatter_dict:
            return frontmatter_dict, []

        current_tags = frontmatter_dict["tags"]

        # Handle different tag formats
        if current_tags is None:
            return frontmatter_dict, []

        if isinstance(current_tags, str):
            current_tags = [current_tags]
        elif not isinstance(current_tags, list):
            return frontmatter_dict, []

        # Filter out tags to purge (case-sensitive exact match)
        removed_tags = []
        updated_tags = []

        for tag in current_tags:
            if tag in tags_to_purge:
                removed_tags.append(tag)
            else:
                updated_tags.append(tag)

        # If no tags were removed, return original
        if not removed_tags:
            return frontmatter_dict, []

        # Create updated dictionary with remaining tags
        # Keep empty list if all tags removed (per user requirement)
        updated_dict = frontmatter_dict.copy()
        updated_dict["tags"] = updated_tags

        return updated_dict, removed_tags

    def _confirm_purge(self, ctx: DryRunContext, tag_counts: Counter) -> bool:
        """
        Show confirmation prompt before purging tags.

        Args:
            ctx: DryRunContext with statistics
            tag_counts: Counter with tag removal counts

        Returns:
            True if user confirms, False otherwise
        """
        print(f"\n{'=' * 60}")
        print("Confirmation Required")
        print(f"{'=' * 60}")
        print("\nFound tags to purge:")

        for tag, count in tag_counts.most_common():
            print(f"  - {tag}: {count} occurrence{'s' if count != 1 else ''}")

        total_tags = ctx.stats.custom_stats.get("total_tags_removed", 0)
        print(
            f"\nTotal: {total_tags} tag{'s' if total_tags != 1 else ''} "
            f"will be removed from {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''}"
        )

        response = input("\nProceed with purge? (y/n): ").strip().lower()
        return response == "y"

    def _print_custom_summary(self, ctx: DryRunContext, tag_counts: Counter) -> None:
        """Print custom summary statistics for tag purge."""
        print(f"\n{'=' * 60}")
        print("Tag Purge Details")
        print(f"{'=' * 60}")

        if tag_counts:
            print("\nTags purged:")
            for tag, count in tag_counts.most_common():
                print(f"  - {tag}: {count} occurrence{'s' if count != 1 else ''}")

        failed_files = ctx.stats.custom_stats.get("failed_files", [])
        if failed_files:
            print("\nFiles that failed to process:")
            for file_path, error in failed_files[:10]:
                print(f"  - {file_path}: {error}")
            if len(failed_files) > 10:
                print(f"  ... and {len(failed_files) - 10} more")

        print(f"\n{'=' * 60}")
