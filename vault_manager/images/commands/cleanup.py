"""
Cleanup command - Move checked orphaned images to trash.

This module implements the cleanup command which processes the orphaned-images.md
file and moves checked-off images to the .trash directory.
"""

import re
import shutil
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import List

from . import Command
from ..common import get_vault_root


class CleanupCommand(Command):
    """Command to move checked orphaned images to .trash directory."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the cleanup command."""
        # Cleanup command has no additional arguments
        pass

    def execute(self, args: Namespace) -> None:
        """Execute the cleanup command to move checked images to trash."""
        print("Cleaning up orphaned images...")
        print("=" * 60)

        vault_root = get_vault_root()
        orphaned_file = vault_root / 'orphaned-images.md'
        trash_dir = vault_root / '.trash'

        # Parse the orphaned-images.md file
        print(f"\nReading {orphaned_file.name}...")
        checked_files = self._parse_orphaned_images_file(orphaned_file)

        if not checked_files:
            print("\nNo checked items found in orphaned-images.md")
            print("Check items using '- [x]' to mark them for deletion")
            return

        print(f"Found {len(checked_files)} checked items")

        # Create .trash directory if it doesn't exist
        trash_dir.mkdir(exist_ok=True)

        # Move files to trash
        print(f"\nMoving files to .trash...")
        moved_files = []
        failed_files = []
        processed_dirs = set()

        for file_path_str in checked_files:
            file_path = vault_root / file_path_str

            if not file_path.exists():
                print(f"  Warning: File not found: {file_path_str}")
                failed_files.append(file_path_str)
                continue

            print(f"  Moving: {file_path_str}")

            # Remember the parent directory for cleanup
            parent_dir = file_path.parent

            if self._move_file_to_trash(file_path, vault_root, trash_dir):
                moved_files.append(file_path_str)
                processed_dirs.add(parent_dir)
            else:
                failed_files.append(file_path_str)

        # Clean up empty directories
        if processed_dirs:
            print(f"\nCleaning up empty directories...")
            for directory in sorted(processed_dirs, key=lambda d: len(d.parts), reverse=True):
                self._cleanup_empty_directories(directory, vault_root)

        # Update the orphaned-images.md file
        if moved_files:
            self._update_orphaned_images_file(orphaned_file, moved_files)

        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total checked items: {len(checked_files)}")
        print(f"Successfully moved: {len(moved_files)}")
        print(f"Failed: {len(failed_files)}")

        if failed_files:
            print(f"\nFailed files:")
            for file_path in failed_files:
                print(f"  - {file_path}")

        print(f"\nFiles moved to: {trash_dir.relative_to(vault_root)}/")
        print("\nDone!")

    def _parse_orphaned_images_file(self, file_path: Path) -> List[str]:
        """
        Parse the orphaned-images.md file and extract file paths from checked items.

        Returns:
            List of file paths that are checked off
        """
        checked_files = []

        if not file_path.exists():
            print(f"Warning: {file_path} not found!")
            return checked_files

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Pattern to match checked items with wiki-links
            pattern = r'^\s*- \[x\] \[\[([^\]|]+)\|[^\]]*\]\]'

            for line in content.split('\n'):
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    file_path_str = match.group(1)
                    checked_files.append(file_path_str)

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

        return checked_files

    def _move_file_to_trash(self, file_path: Path, vault_root: Path, trash_dir: Path) -> bool:
        """
        Move a file to the .trash directory, preserving its relative path structure.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get relative path from vault root
            relative_path = file_path.relative_to(vault_root)

            # Create destination path in .trash
            trash_path = trash_dir / relative_path

            # Create parent directory if it doesn't exist
            trash_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            shutil.move(str(file_path), str(trash_path))

            return True

        except Exception as e:
            print(f"  Error moving {file_path}: {e}")
            return False

    def _cleanup_empty_directories(self, directory: Path, vault_root: Path) -> None:
        """Remove empty directories after moving files."""
        try:
            # Don't remove the vault root or .trash
            if directory == vault_root or directory.name == '.trash':
                return

            # Only process directories under vault root
            if not directory.is_relative_to(vault_root):
                return

            # Check if directory is empty
            if directory.exists() and directory.is_dir():
                if not any(directory.iterdir()):
                    directory.rmdir()
                    print(f"  Removed empty directory: {directory.relative_to(vault_root)}")

                    # Recursively check parent directory
                    self._cleanup_empty_directories(directory.parent, vault_root)

        except Exception as e:
            print(f"  Warning: Could not remove directory {directory}: {e}")

    def _update_orphaned_images_file(self, file_path: Path, moved_files: List[str]) -> None:
        """Update orphaned-images.md file to remove checked items that were moved."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Create a set of moved file paths for quick lookup
            moved_set = set(moved_files)

            # Filter out lines for moved files
            new_lines = []
            for line in lines:
                # Check if this line contains a moved file
                pattern = r'^\s*- \[x\] \[\[([^\]|]+)\|[^\]]*\]\]'
                match = re.match(pattern, line, re.IGNORECASE)

                if match:
                    file_path_str = match.group(1)
                    if file_path_str in moved_set:
                        # Skip this line
                        continue

                new_lines.append(line)

            # Write updated content back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            print(f"\nUpdated {file_path.name} to remove moved files")

        except Exception as e:
            print(f"Warning: Could not update {file_path}: {e}")
