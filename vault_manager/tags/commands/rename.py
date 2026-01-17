#!/usr/bin/env python3
"""
Command to rename a tag across all markdown files and database.

This command replaces all occurrences of an old tag with a new tag,
updates the files' frontmatter, and rebuilds the vault index database.
"""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from vault_manager.core.command import Command
from vault_manager.core.database import VaultDatabase, auto_rebuild_after
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.vault import count_markdown_files, iter_markdown_files


class RenameCommand(Command):
    """Command to rename a tag across all markdown files and database."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the rename command."""
        parser.add_argument("old_tag", help="Tag to rename (case-sensitive)")
        parser.add_argument("new_tag", help="New tag name (case-sensitive)")
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
        """Execute the rename command to replace a tag."""
        vault_root = VaultDatabase().vault_root
        old_tag = args.old_tag
        new_tag = args.new_tag

        # Validate new tag name
        if not FrontmatterManager.is_valid_obsidian_tag(new_tag):
            print(f"\nError: '{new_tag}' is not a valid Obsidian tag.")
            print("\nTag requirements:")
            print("  - Only letters, numbers, underscore (_), hyphen (-), slash (/)")
            print("  - Must contain at least one letter or underscore")
            print("\nExamples of valid tags: software-development, y2024, nested/tag")
            sys.exit(1)

        # Check if old and new tags are the same
        if old_tag == new_tag:
            print(f"\nError: Old tag and new tag are identical: '{old_tag}'")
            sys.exit(1)

        print(f"\n{'=' * 60}")
        print("Tag Rename Tool")
        print(f"{'=' * 60}")
        print(f"Vault: {vault_root}")
        print(f"Rename: '{old_tag}' → '{new_tag}'")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE MODE'}")
        print(f"{'=' * 60}\n")

        # Process all markdown files in the vault
        print("Scanning vault for tags to rename...\n")

        with DryRunContext(args.dry_run) as ctx:
            conflict_files = self._process_vault(vault_root, old_tag, new_tag, ctx)

            # If no tags were found, exit early
            if ctx.stats.files_modified == 0:
                print(f"\nNo files found with tag '{old_tag}'.")
                return

            # Show confirmation prompt (only in live mode)
            if not args.dry_run:
                if not self._confirm_rename(ctx, old_tag, new_tag, conflict_files):
                    print("\nOperation cancelled by user.")
                    return

                # Actually rename the tags
                print("\nRenaming tags in files...")
                self._process_vault(vault_root, old_tag, new_tag, ctx, confirm_phase=False)

            # Display summary
            self._print_custom_summary(ctx, old_tag, new_tag, conflict_files)
            print_dry_run_summary(ctx)

    def _process_vault(
        self,
        vault_root: Path,
        old_tag: str,
        new_tag: str,
        ctx: DryRunContext,
        confirm_phase: bool = True,
    ) -> List[Path]:
        """
        Process all markdown files in the vault.

        Args:
            vault_root: Root directory of the vault
            old_tag: Tag to rename
            new_tag: New tag name
            ctx: DryRunContext for tracking operations
            confirm_phase: If True, this is the preview phase before confirmation

        Returns:
            List of files with tag conflicts
        """
        conflict_files = []
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
                success, renamed, has_conflict = self._rename_file(
                    file_path, old_tag, new_tag, ctx.dry_run or confirm_phase
                )

                if renamed:
                    ctx.stats.increment("files_modified")
                    ctx.stats.increment("total_tags_renamed")

                    ctx.record_change(
                        file_path,
                        f"Renamed '{old_tag}' → '{new_tag}'",
                        old_tag=old_tag,
                        new_tag=new_tag,
                        has_conflict=has_conflict,
                    )

                    # Show progress (only during actual rename, not confirmation)
                    if not confirm_phase:
                        relative_path = file_path.relative_to(vault_root)
                        mode_prefix = "[DRY RUN] Would rename in" if ctx.dry_run else "Renamed in"
                        conflict_note = (
                            " [CONFLICT: new tag already exists]" if has_conflict else ""
                        )
                        print(f"{mode_prefix} {relative_path}{conflict_note}")

                if has_conflict:
                    ctx.stats.increment("files_with_conflicts")
                    conflict_files.append(file_path.relative_to(vault_root))

                if not success:
                    ctx.stats.increment("files_failed")

            except Exception as e:
                ctx.stats.increment("files_failed")
                failed_files.append((file_path, str(e)))

        # Store failed files in context for reporting
        if failed_files:
            ctx.stats.custom_stats["failed_files"] = failed_files

        return conflict_files

    def _rename_file(
        self, file_path: Path, old_tag: str, new_tag: str, dry_run: bool
    ) -> Tuple[bool, bool, bool]:
        """
        Rename a tag in a single file.

        Args:
            file_path: Path to the markdown file
            old_tag: Tag to rename
            new_tag: New tag name
            dry_run: If True, don't modify the file

        Returns:
            Tuple of (success: bool, renamed: bool, has_conflict: bool)
        """
        renamed = False
        has_conflict = False

        def updater(content: str) -> Optional[str]:
            nonlocal renamed, has_conflict

            # Extract frontmatter using FrontmatterManager
            frontmatter_dict, body = FrontmatterManager.extract(content)

            if frontmatter_dict is None:
                return None

            # Rename tag in frontmatter dict
            updated_dict, was_renamed, conflict = self._rename_tag_in_frontmatter(
                frontmatter_dict, old_tag, new_tag
            )

            # If tag wasn't found, skip this file
            if not was_renamed:
                return None

            renamed = was_renamed
            has_conflict = conflict

            # Serialize back to markdown using FrontmatterManager
            return FrontmatterManager.serialize(updated_dict, body)

        success = atomic_update(file_path, updater, dry_run=dry_run, silent=True)
        return success, renamed, has_conflict

    def _rename_tag_in_frontmatter(
        self, frontmatter_dict: Dict, old_tag: str, new_tag: str
    ) -> Tuple[Dict, bool, bool]:
        """
        Rename a tag in frontmatter dictionary.

        Args:
            frontmatter_dict: Parsed frontmatter dictionary
            old_tag: Tag to rename
            new_tag: New tag name

        Returns:
            Tuple of (updated_dict, renamed: bool, has_conflict: bool)
        """
        # Get current tags
        if "tags" not in frontmatter_dict:
            return frontmatter_dict, False, False

        current_tags = frontmatter_dict["tags"]

        # Handle different tag formats
        if current_tags is None:
            return frontmatter_dict, False, False

        if isinstance(current_tags, str):
            current_tags = [current_tags]
        elif not isinstance(current_tags, list):
            return frontmatter_dict, False, False

        # Check if old tag exists
        if old_tag not in current_tags:
            return frontmatter_dict, False, False

        # Check if new tag already exists (conflict)
        has_conflict = new_tag in current_tags

        # Replace old tag with new tag
        updated_tags = []
        for tag in current_tags:
            if tag == old_tag:
                # Only add new tag if it's not already in the list (avoid duplicates)
                if not has_conflict:
                    updated_tags.append(new_tag)
                # If conflict, skip adding (effectively removes old tag)
            else:
                updated_tags.append(tag)

        # Create updated dictionary with new tags
        updated_dict = frontmatter_dict.copy()
        updated_dict["tags"] = updated_tags

        return updated_dict, True, has_conflict

    def _confirm_rename(
        self, ctx: DryRunContext, old_tag: str, new_tag: str, conflict_files: List[Path]
    ) -> bool:
        """
        Show confirmation prompt before renaming tags.

        Args:
            ctx: DryRunContext with statistics
            old_tag: Tag being renamed
            new_tag: New tag name
            conflict_files: List of files with tag conflicts

        Returns:
            True if user confirms, False otherwise
        """
        print(f"\n{'=' * 60}")
        print("Confirmation Required")
        print(f"{'=' * 60}")
        print("\nRename operation:")
        print(f"  '{old_tag}' → '{new_tag}'")
        print(f"\nAffected files: {ctx.stats.files_modified}")
        print(f"Total renames: {ctx.stats.custom_stats.get('total_tags_renamed', 0)}")

        conflicts = ctx.stats.custom_stats.get("files_with_conflicts", 0)
        if conflicts > 0:
            print(f"\n⚠ Warning: {conflicts} file(s) already have tag '{new_tag}'")
            print(f"  In these files, '{old_tag}' will be removed to avoid duplicates.")
            if conflict_files:
                print("\n  Files with conflicts:")
                for file_path in conflict_files[:5]:
                    print(f"    - {file_path}")
                if len(conflict_files) > 5:
                    print(f"    ... and {len(conflict_files) - 5} more")

        response = input("\nProceed with rename? (y/n): ").strip().lower()
        return response == "y"

    def _print_custom_summary(
        self, ctx: DryRunContext, old_tag: str, new_tag: str, conflict_files: List[Path]
    ) -> None:
        """Print custom summary statistics for tag rename."""
        print(f"\n{'=' * 60}")
        print("Tag Rename Details")
        print(f"{'=' * 60}")
        print(f"\nRename: '{old_tag}' → '{new_tag}'")

        conflicts = ctx.stats.custom_stats.get("files_with_conflicts", 0)
        if conflicts > 0:
            print(f"\n⚠ Conflicts (files already containing '{new_tag}'):")
            print(f"  Files with conflicts: {conflicts}")
            if conflict_files:
                print("\n  Affected files:")
                for file_path in conflict_files[:10]:
                    print(f"    - {file_path}")
                if len(conflict_files) > 10:
                    print(f"    ... and {len(conflict_files) - 10} more")

        failed_files = ctx.stats.custom_stats.get("failed_files", [])
        if failed_files:
            print("\nFiles that failed to process:")
            for file_path, error in failed_files[:10]:
                print(f"  - {file_path}: {error}")
            if len(failed_files) > 10:
                print(f"  ... and {len(failed_files) - 10} more")

        print(f"\n{'=' * 60}")
