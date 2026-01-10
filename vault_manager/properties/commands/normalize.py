"""
Normalize command - Standardize frontmatter properties.

This module implements the normalize command which standardizes frontmatter
properties across notes according to defined rules.
"""

import sys
import yaml
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from . import Command
from ..common import get_vault_root, extract_frontmatter
from vault_manager.core.vault import iter_markdown_files
from vault_manager.core.file_ops import atomic_update
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary


class NormalizeCommand(Command):
    """Command to normalize frontmatter properties across notes."""

    # Properties to remove
    REMOVE_PROPERTIES = {'author', 'title', 'description', 'created', 'published'}

    # Properties to keep (preferred order)
    PREFERRED_ORDER = ['tags', 'summary', 'related', 'source']

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the normalize command."""
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
        """Execute the normalize command to standardize frontmatter properties."""
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
        print("Normalize Frontmatter Properties")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Ignored directories: .obsidian, .trash, Excalidraw, Calendar")
        print(f"Ignored file types: .excalidraw.md")
        print("\nNormalization rules:")
        print(f"  - Remove: {', '.join(sorted(self.REMOVE_PROPERTIES))}")
        print(f"  - Rename: url → source")
        print(f"  - Reorder: {', '.join(self.PREFERRED_ORDER)}, then others alphabetically")

        # Process directory with DryRunContext
        with DryRunContext(args.dry_run) as ctx:
            self._process_directory(target_dir, vault_root, ctx)

            # Print summary
            additional_info = f"Remove: {', '.join(sorted(self.REMOVE_PROPERTIES))}\nRename: url → source"
            print_dry_run_summary(ctx, additional_info=additional_info)

        # Final message
        if ctx.stats.files_modified > 0:
            if not args.dry_run:
                print(f"\nDone! Modified {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''}.")
            else:
                print(f"\nDry run complete. {ctx.stats.files_modified} file{'s' if ctx.stats.files_modified != 1 else ''} would be modified.")
        else:
            print("\nNo changes needed.")

    def _normalize_frontmatter(self, frontmatter_dict: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Normalize frontmatter properties.

        Returns:
            Tuple of (normalized_dict, list_of_changes)
        """
        normalized = {}
        changes = []

        # Process each property
        for key, value in frontmatter_dict.items():
            # Skip properties that should be removed
            if key in self.REMOVE_PROPERTIES:
                changes.append(f"Removed '{key}'")
                continue

            # Rename 'url' to 'source'
            if key == 'url':
                # Only rename if 'source' doesn't already exist
                if 'source' not in frontmatter_dict:
                    normalized['source'] = value
                    changes.append(f"Renamed 'url' to 'source'")
                else:
                    changes.append(f"Removed 'url' (kept existing 'source')")
                continue

            # Keep all other properties
            normalized[key] = value

        # Reorder properties: preferred properties first, then others alphabetically
        ordered = {}

        # Add preferred properties in order (if they exist)
        for prop in self.PREFERRED_ORDER:
            if prop in normalized:
                ordered[prop] = normalized[prop]

        # Add remaining properties alphabetically
        for key in sorted(normalized.keys()):
            if key not in self.PREFERRED_ORDER:
                ordered[key] = normalized[key]

        return ordered, changes

    def _normalize_file(self, file_path: Path, vault_root: Path, dry_run: bool = False) -> Tuple[bool, List[str]]:
        """
        Normalize frontmatter in a single file.

        Returns:
            Tuple of (success, list_of_changes)
        """
        changes = []
        error_msg = None

        def updater(content: str) -> Optional[str]:
            nonlocal changes, error_msg

            # Extract frontmatter
            frontmatter_text, body = extract_frontmatter(content)

            if frontmatter_text is None:
                error_msg = "No frontmatter found"
                return None

            # Parse frontmatter as YAML
            try:
                frontmatter_dict = yaml.safe_load(frontmatter_text) or {}
            except yaml.YAMLError as e:
                error_msg = f"YAML parsing error: {e}"
                return None

            # Normalize the frontmatter
            normalized_dict, chgs = self._normalize_frontmatter(frontmatter_dict)

            # If no changes, skip
            if not chgs:
                return None

            changes = chgs

            # Convert back to YAML
            normalized_yaml = yaml.dump(normalized_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)

            # Remove trailing newline that yaml.dump adds
            normalized_yaml = normalized_yaml.rstrip('\n')

            # Reconstruct file
            return f"---\n{normalized_yaml}\n---\n{body}"

        success = atomic_update(file_path, updater, dry_run=dry_run, silent=True)

        if error_msg and isinstance(error_msg, str):
            return False, [error_msg]
        elif not success and not changes:
            return True, []
        else:
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

        # Use iter_markdown_files for memory-efficient traversal
        additional_ignores = {'Excalidraw', 'Calendar'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            ctx.stats.increment('total_files')
            relative_path = file_path.relative_to(vault_root)

            # Normalize the file
            success, changes = self._normalize_file(file_path, vault_root, ctx.dry_run)

            if not success:
                if "No frontmatter found" in changes[0]:
                    ctx.stats.increment('files_skipped_no_frontmatter')
                else:
                    ctx.stats.increment('files_failed')
                    print(f"  Failed: {relative_path} - {changes[0]}")
            elif not changes:
                ctx.stats.increment('files_skipped_no_changes')
            else:
                ctx.stats.increment('files_modified')
                for change in changes:
                    ctx.stats.increment(f'change_{change}')

                ctx.record_change(file_path, f"Normalized: {', '.join(changes)}", changes=changes)
                mode = "Would modify" if ctx.dry_run else "Modified"
                print(f"  {mode}: {relative_path}")
                for change in changes:
                    print(f"    - {change}")
