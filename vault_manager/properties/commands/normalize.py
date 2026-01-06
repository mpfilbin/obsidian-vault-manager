"""
Normalize command - Standardize frontmatter properties.

This module implements the normalize command which standardizes frontmatter
properties across notes according to defined rules.
"""

import sys
import yaml
from argparse import ArgumentParser, Namespace
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from . import Command
from ..common import get_vault_root, extract_frontmatter
from vault_manager.core.vault import iter_markdown_files
from vault_manager.core.file_ops import atomic_update


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

        # Process directory
        stats = self._process_directory(target_dir, vault_root, args.dry_run)

        # Print summary
        self._print_summary(stats, args.dry_run)

        if not args.dry_run and stats['files_changed'] > 0:
            print(f"\nDone! Modified {stats['files_changed']} file{'s' if stats['files_changed'] != 1 else ''}.")
        elif args.dry_run and stats['files_changed'] > 0:
            print(f"\nDry run complete. {stats['files_changed']} file{'s' if stats['files_changed'] != 1 else ''} would be modified.")
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

        if error_msg:
            return False, [error_msg]
        elif not success and not changes:
            return True, []
        else:
            return success, changes

    def _process_directory(self, directory: Path, vault_root: Path, dry_run: bool = False) -> Dict:
        """
        Recursively process all markdown files in a directory.

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'files_changed': 0,
            'files_skipped_no_frontmatter': 0,
            'files_skipped_no_changes': 0,
            'files_failed': 0,
            'failed_files': [],
            'change_counts': Counter()
        }

        print(f"\n{'DRY RUN - ' if dry_run else ''}Processing markdown files...")

        # Use iter_markdown_files for memory-efficient traversal
        additional_ignores = {'Excalidraw', 'Calendar'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            stats['total_files'] += 1
            relative_path = file_path.relative_to(vault_root)

            # Normalize the file
            success, changes = self._normalize_file(file_path, vault_root, dry_run)

            if not success:
                if "No frontmatter found" in changes[0]:
                    stats['files_skipped_no_frontmatter'] += 1
                else:
                    stats['files_failed'] += 1
                    stats['failed_files'].append((str(relative_path), changes[0]))
                    print(f"  Failed: {relative_path} - {changes[0]}")
            elif not changes:
                stats['files_skipped_no_changes'] += 1
            else:
                stats['files_changed'] += 1
                for change in changes:
                    stats['change_counts'][change] += 1

                mode = "Would modify" if dry_run else "Modified"
                print(f"  {mode}: {relative_path}")
                for change in changes:
                    print(f"    - {change}")

        return stats

    def _print_summary(self, stats: Dict, dry_run: bool = False) -> None:
        """Print summary of normalization results."""
        print("\n" + "=" * 60)
        print(f"{'DRY RUN ' if dry_run else ''}SUMMARY")
        print("=" * 60)
        print(f"Total markdown files: {stats['total_files']}")
        print(f"Files changed: {stats['files_changed']}")
        print(f"Files skipped (no frontmatter): {stats['files_skipped_no_frontmatter']}")
        print(f"Files skipped (no changes needed): {stats['files_skipped_no_changes']}")
        print(f"Files failed: {stats['files_failed']}")

        if stats['change_counts']:
            print(f"\nChanges applied:")
            for change, count in stats['change_counts'].most_common():
                print(f"  - {change}: {count}")

        if stats['failed_files']:
            print(f"\nFailed files ({len(stats['failed_files'])}):")
            for file_path, error in stats['failed_files']:
                print(f"  - {file_path}: {error}")

        if dry_run and stats['files_changed'] > 0:
            print("\n" + "=" * 60)
            print("This was a DRY RUN - no files were actually modified.")
            print("Run without --dry-run to apply changes.")
            print("=" * 60)
