"""
Broken command - Find notes with missing image references.

This module implements the broken command which scans markdown files
for image references and reports any images that don't exist in the vault.
"""

import os
import re
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime

from . import Command
from ..common import get_vault_root, is_ignored_path, IMAGE_EXTENSIONS
from vault_manager.core.vault import iter_markdown_files, count_markdown_files


class BrokenCommand(Command):
    """Command to find notes with broken image references."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the broken command."""
        parser.add_argument(
            '--output',
            default='broken-image-refs.md',
            help='Output filename (default: broken-image-refs.md)'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the broken command to find notes with missing images."""
        vault_root = get_vault_root()

        print("=" * 60)
        print("Find Notes with Missing Local Image References")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Output file: {args.output}")
        print(f"Scope: Local vault images only (external URLs ignored)")
        print(f"Ignored directories: .obsidian, .trash, Excalidraw")

        # Find all images in vault
        print("\nScanning vault for images...")
        image_files = self._find_all_images(vault_root)
        print(f"Found {len(image_files)} images in vault")

        # Find all image references in markdown files
        print("\nScanning markdown files for image references...")
        broken_refs = self._find_broken_image_references(vault_root, image_files)

        # Generate report
        self._generate_report(vault_root, broken_refs, args.output)

        # Print summary
        total_notes = len(broken_refs)
        total_broken = sum(len(refs) for refs in broken_refs.values())

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Notes with broken image references: {total_notes}")
        print(f"Total broken image references: {total_broken}")

        if total_notes > 0:
            print(f"\nReport generated: {args.output}")
        else:
            print("\n✓ No broken image references found!")

    def _find_all_images(self, vault_root: Path) -> Set[str]:
        """
        Find all image files in the vault.

        Args:
            vault_root: Root directory of the vault

        Returns:
            Set of image filenames (basename only, case-insensitive)
        """
        image_files = set()

        for root, dirs, files in os.walk(vault_root):
            root_path = Path(root)

            # Skip ignored directories
            if is_ignored_path(root_path, vault_root):
                dirs[:] = []
                continue

            # Collect image files
            for filename in files:
                if any(filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
                    # Store both the filename and the full relative path
                    # This helps with resolving references
                    image_files.add(filename.lower())
                    rel_path = root_path.relative_to(vault_root) / filename
                    image_files.add(str(rel_path).lower().replace('\\', '/'))

        return image_files

    def _find_broken_image_references(
        self,
        vault_root: Path,
        image_files: Set[str]
    ) -> Dict[Path, List[Tuple[str, int, str]]]:
        """
        Find all broken image references in markdown files.

        Args:
            vault_root: Root directory of the vault
            image_files: Set of existing image filenames (case-insensitive)

        Returns:
            Dictionary mapping file paths to list of (reference, line_number, format) tuples
        """
        broken_refs = {}

        for file_path in iter_markdown_files(vault_root, vault_root, additional_ignores={'Excalidraw'}, exclude_excalidraw=False):
            refs = self._extract_broken_image_refs(file_path, vault_root, image_files)

            if refs:
                broken_refs[file_path] = refs

        return broken_refs

    def _extract_broken_image_refs(
        self,
        file_path: Path,
        vault_root: Path,
        image_files: Set[str]
    ) -> List[Tuple[str, int, str]]:
        """
        Extract broken local image references from a markdown file.

        Only detects local vault images (wiki-links and local file paths),
        ignoring external URLs and remote images.

        Args:
            file_path: Path to markdown file
            vault_root: Root directory of the vault
            image_files: Set of existing image filenames

        Returns:
            List of (reference, line_number, format_type) tuples for broken references
        """
        broken = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                # Find wiki-link image embeds: ![[image.png]]
                # This is the primary format for local Obsidian images
                wiki_refs = re.findall(r'!\[\[([^\]]+?\.(png|jpg|jpeg|gif|svg|webp|bmp|ico))(?:\|[^\]]*)?\]\]', line, re.IGNORECASE)
                for ref, _ in wiki_refs:
                    if not self._image_exists(ref, file_path, vault_root, image_files):
                        broken.append((f'![[{ref}]]', line_num, 'wiki-link'))

                # Find markdown image syntax with LOCAL paths only (not URLs)
                # Matches: ![alt](path/to/image.png) but NOT ![alt](http://...)
                md_refs = re.findall(r'!\[([^\]]*)\]\(([^)]+?\.(png|jpg|jpeg|gif|svg|webp|bmp|ico))\)', line, re.IGNORECASE)
                for alt, ref, _ in md_refs:
                    # Skip if it's a URL (http://, https://, ftp://, etc.)
                    if re.match(r'^[a-z]+://', ref, re.IGNORECASE):
                        continue

                    if not self._image_exists(ref, file_path, vault_root, image_files):
                        broken.append((f'![{alt}]({ref})', line_num, 'markdown'))

        except Exception as e:
            print(f"Warning: Error reading {file_path}: {e}")

        return broken

    def _image_exists(
        self,
        ref: str,
        note_path: Path,
        vault_root: Path,
        image_files: Set[str]
    ) -> bool:
        """
        Check if an image reference exists in the vault.

        Args:
            ref: Image reference (filename or path)
            note_path: Path to the note containing the reference
            vault_root: Root directory of the vault
            image_files: Set of existing image filenames

        Returns:
            True if image exists, False otherwise
        """
        ref_lower = ref.lower()

        # Check if it's just a filename (Obsidian style)
        if '/' not in ref and '\\' not in ref:
            return ref_lower in image_files

        # Check relative path from note directory
        note_dir = note_path.parent
        abs_path = (note_dir / ref).resolve()

        if abs_path.exists():
            return True

        # Check relative to vault root
        vault_path = vault_root / ref.replace('\\', '/')
        if vault_path.exists():
            return True

        # Check if the relative path exists in our image set
        clean_ref = ref.replace('\\', '/').lower()
        return clean_ref in image_files

    def _generate_report(
        self,
        vault_root: Path,
        broken_refs: Dict[Path, List[Tuple[str, int, str]]],
        output_file: str
    ) -> None:
        """
        Generate markdown report of broken image references.

        Args:
            vault_root: Root directory of the vault
            broken_refs: Dictionary of files with broken references
            output_file: Output filename
        """
        output_path = vault_root / output_file

        # Count statistics
        total_notes = len(broken_refs)
        total_broken = sum(len(refs) for refs in broken_refs.values())

        with open(output_path, 'w', encoding='utf-8') as f:
            # Write frontmatter
            f.write("---\n")
            f.write("tags:\n")
            f.write("  - vault-management\n")
            f.write("  - broken-images\n")
            f.write("---\n")
            f.write("# Notes with Missing Local Image References\n\n")

            # Write metadata
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Vault:** `{vault_root}`\n")
            f.write(f"**Scope:** Local vault images only (external URLs ignored)\n\n")

            # Write statistics
            f.write("## Statistics\n\n")
            f.write(f"- Notes with broken image references: {total_notes}\n")
            f.write(f"- Total broken image references: {total_broken}\n\n")

            if not broken_refs:
                f.write("✓ No broken image references found!\n")
                return

            # Write broken references grouped by file
            f.write("## Notes with Broken Image References\n\n")

            for file_path in sorted(broken_refs.keys()):
                refs = broken_refs[file_path]
                rel_path = file_path.relative_to(vault_root)
                note_name = file_path.stem

                f.write(f"### [[{note_name}]]\n\n")
                f.write(f"**File:** `{rel_path}`\n")
                f.write(f"**Missing images:** {len(refs)}\n\n")

                for ref, line_num, format_type in refs:
                    f.write(f"- `{ref}` (line {line_num}, format: {format_type})\n")

                f.write("\n")

        print(f"\nReport written to: {output_path}")
