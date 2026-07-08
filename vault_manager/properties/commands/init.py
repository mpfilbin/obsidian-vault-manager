"""
Init command - Initialize YAML frontmatter in files that have none.

This module implements the init command which adds a minimal frontmatter
block (tags: []) to markdown files that currently have no frontmatter at
all. Files that already have any frontmatter (even without a 'tags' key)
are left untouched.
"""

import re
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Optional, Tuple

from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.vault import iter_markdown_files

from ..common import extract_frontmatter, get_vault_root
from . import Command


class InitCommand(Command):
    """Command to initialize YAML frontmatter in files that have none."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the init command."""
        parser.add_argument(
            'directory',
            nargs='?',
            default=None,
            help='Directory to process (optional, defaults to entire vault)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without modifying files'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the init command to initialize frontmatter."""
        # Get vault root
        vault_root = get_vault_root()

        # Resolve directory path (default to entire vault)
        if args.directory is None or args.directory == '.':
            target_dir = vault_root
        else:
            target_dir = vault_root / args.directory

        # Validate directory if specified
        if args.directory and args.directory != '.':
            if not target_dir.exists():
                print(f"Error: Directory not found: {args.directory}")
                print(f"Looking for: {target_dir}")
                sys.exit(1)

            if not target_dir.is_dir():
                print(f"Error: Not a directory: {args.directory}")
                sys.exit(1)

        # Display header
        print("=" * 60)
        print("Initialize Frontmatter")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        relative_target = target_dir.relative_to(vault_root) if target_dir != vault_root else '.'
        print(f"Target directory: {relative_target}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print("Ignored directories: .obsidian, .trash, Excalidraw, Calendar")
        print("Ignored file types: .excalidraw.md")
        print("\nFiles with no frontmatter will get: tags: []")

        # Process directory with DryRunContext
        with DryRunContext(args.dry_run) as ctx:
            self._process_directory(target_dir, vault_root, ctx)
            print_dry_run_summary(ctx)

        # Final message
        if ctx.stats.files_modified > 0:
            plural = 's' if ctx.stats.files_modified != 1 else ''
            if not args.dry_run:
                print(f"\nDone! Modified {ctx.stats.files_modified} file{plural}.")
            else:
                count = ctx.stats.files_modified
                print(f"\nDry run complete. {count} file{plural} would be modified.")
        else:
            print("\nNo changes needed.")

    @staticmethod
    def _has_frontmatter(content: str) -> bool:
        """
        Check whether content has any YAML frontmatter block.

        Falls back to a direct regex check for adjacent '---' delimiters
        with no blank line between them (e.g. "---\\n---\\n"), a case
        FrontmatterManager.extract_frontmatter's regex does not match
        because it requires a body line between the delimiters.
        """
        frontmatter, _ = extract_frontmatter(content)
        if frontmatter is not None:
            return True

        normalized = content.replace('\r\n', '\n').replace('\r', '\n')
        return bool(re.match(r'^---\s*\n---\s*\n', normalized))

    def _init_file(self, file_path: Path, dry_run: bool = False) -> Tuple[bool, bool]:
        """
        Add tags: [] frontmatter to a single file if it has none.

        Returns:
            Tuple of (needs_init, success).
            - needs_init: True if the file had no frontmatter at all
            - success: True if the write succeeded (or dry-run, or no change needed)
        """
        needs_init = False

        def updater(content: str) -> Optional[str]:
            nonlocal needs_init

            if self._has_frontmatter(content):
                # Already has frontmatter (even without tags, or empty) - skip
                return None

            _, body = extract_frontmatter(content)
            needs_init = True
            return f"---\ntags: []\n---\n{body}"

        success = atomic_update(file_path, updater, dry_run=dry_run, silent=True)

        return needs_init, success

    def _process_directory(self, directory: Path, vault_root: Path, ctx: DryRunContext) -> None:
        """
        Recursively process all markdown files in a directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            ctx: DryRunContext for tracking operations
        """
        print(f"\n{'DRY RUN - ' if ctx.dry_run else ''}Scanning markdown files...")

        additional_ignores = {'Excalidraw', 'Calendar'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            ctx.stats.increment('total_files')
            relative_path = file_path.relative_to(vault_root)

            needs_init, success = self._init_file(file_path, ctx.dry_run)

            if not needs_init:
                ctx.stats.increment('files_skipped')
                continue

            if success:
                ctx.stats.increment('files_modified')
                ctx.record_change(file_path, "Initialized frontmatter with tags: []")
                mode = "Would initialize" if ctx.dry_run else "Initialized"
                print(f"  {mode}: {relative_path}")
            else:
                ctx.stats.increment('files_failed')
                print(f"  Failed: {relative_path}")
