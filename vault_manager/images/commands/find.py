"""
Find command - Locate orphaned images.

This module implements the find command which scans the vault for image files
that are not referenced in any markdown file.
"""

import os
import re
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

from . import Command
from ..common import get_vault_root, is_ignored_path, IMAGE_EXTENSIONS


class FindCommand(Command):
    """Command to find orphaned images not referenced in markdown files."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the find command."""
        # Find command has no additional arguments
        pass

    def execute(self, args: Namespace) -> None:
        """Execute the find command to locate orphaned images."""
        print("Scanning vault for orphaned images...")

        vault_root = get_vault_root()

        # Find all images
        print("\n1. Finding all image files...")
        all_images = self._find_all_images(vault_root)
        print(f"   Found {len(all_images)} total image files")

        # Build filename index for fast lookups
        print("\n2. Building filename index...")
        filename_index = self._build_filename_index(all_images)
        print(f"   Indexed {len(filename_index)} unique filenames")

        # Find referenced images
        print("\n3. Scanning markdown files for image references...")
        referenced_images = self._find_referenced_images(vault_root, filename_index)
        print(f"   Found {len(referenced_images)} referenced images")

        # Find orphaned images
        print("\n4. Identifying orphaned images...")
        orphaned_images = sorted(all_images - referenced_images)
        orphaned_count = len(orphaned_images)
        print(f"   Found {orphaned_count} orphaned images")

        # Generate report
        print("\n5. Generating report...")
        report = self._generate_report(orphaned_images, all_images, referenced_images, vault_root)

        # Write to orphaned-images.md
        output_file = vault_root / 'orphaned-images.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\nReport written to: {output_file}")
        print("Done!")

    def _find_all_images(self, vault_root: Path) -> Set[Path]:
        """Find all image files in the vault."""
        images = set()

        print("  Walking directory tree...")
        for root, dirs, files in os.walk(vault_root):
            root_path = Path(root)

            # Skip ignored directories
            if is_ignored_path(root_path, vault_root):
                dirs[:] = []
                continue

            # Check each file
            for filename in files:
                if Path(filename).suffix.lower() in IMAGE_EXTENSIONS:
                    images.add(root_path / filename)

        return images

    def _build_filename_index(self, all_images: Set[Path]) -> Dict[str, List[Path]]:
        """
        Build an index mapping filenames to their full paths.
        Used for Obsidian-style filename-only references.
        """
        index = defaultdict(list)
        for img_path in all_images:
            index[img_path.name].append(img_path)
        return dict(index)

    def _extract_image_references(self, content: str, md_file_path: Path, vault_root: Path,
                                  filename_index: Dict[str, List[Path]]) -> Set[Path]:
        """
        Extract image file references from markdown content.

        Handles multiple formats:
        - ![alt](path/to/image.png)
        - ![[image.png]]
        - ![[path/to/image.png]]
        - <img src="path/to/image.png">
        """
        referenced_images = set()

        # Pattern 1: Markdown syntax ![alt](path)
        markdown_pattern = r'!\[.*?\]\((.*?)\)'
        for match in re.finditer(markdown_pattern, content):
            img_path = match.group(1)
            # Remove any URL parameters or anchors
            img_path = img_path.split('?')[0].split('#')[0]
            referenced_images.add(img_path)

        # Pattern 2: Obsidian wiki-link syntax ![[path]]
        wiki_pattern = r'!\[\[(.*?)\]\]'
        for match in re.finditer(wiki_pattern, content):
            img_path = match.group(1)
            # Remove any display text after |
            img_path = img_path.split('|')[0]
            referenced_images.add(img_path)

        # Pattern 3: HTML img tags
        html_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        for match in re.finditer(html_pattern, content, re.IGNORECASE):
            img_path = match.group(1)
            img_path = img_path.split('?')[0].split('#')[0]
            referenced_images.add(img_path)

        # Resolve all paths
        resolved_images = set()
        md_dir = md_file_path.parent

        for img_path in referenced_images:
            # Skip external URLs
            if img_path.startswith(('http://', 'https://', '//')):
                continue

            # Try relative to markdown file
            absolute_path = (md_dir / img_path).resolve()
            if absolute_path.exists() and absolute_path.is_file():
                resolved_images.add(absolute_path)
                continue

            # Try relative to vault root
            absolute_path = (vault_root / img_path).resolve()
            if absolute_path.exists() and absolute_path.is_file():
                resolved_images.add(absolute_path)
                continue

            # Try finding file with same name (Obsidian style)
            if filename_index:
                img_name = Path(img_path).name
                if img_name in filename_index:
                    resolved_images.add(filename_index[img_name][0])

        return resolved_images

    def _find_referenced_images(self, vault_root: Path, filename_index: Dict[str, List[Path]]) -> Set[Path]:
        """Scan all markdown files and collect referenced images."""
        referenced_images = set()
        md_count = 0

        print("  Walking directory tree for markdown files...")
        for root, dirs, files in os.walk(vault_root):
            root_path = Path(root)

            # Skip ignored directories
            if is_ignored_path(root_path, vault_root):
                dirs[:] = []
                continue

            # Process markdown files
            for filename in files:
                if not filename.endswith('.md'):
                    continue

                md_file = root_path / filename
                md_count += 1

                if md_count % 100 == 0:
                    print(f"    Processed {md_count} markdown files...")

                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    images = self._extract_image_references(content, md_file, vault_root, filename_index)
                    referenced_images.update(images)

                except Exception as e:
                    print(f"  Warning: Could not read {md_file}: {e}")

        print(f"  Total markdown files processed: {md_count}")
        return referenced_images

    def _build_directory_tree(self, orphaned_images: List[Path], vault_root: Path) -> Dict:
        """Build a hierarchical directory tree structure from orphaned images."""
        tree = {}

        for img_path in sorted(orphaned_images):
            relative_path = img_path.relative_to(vault_root)
            parts = relative_path.parts

            # Navigate/build the tree
            current = tree
            for i, part in enumerate(parts):
                if part not in current:
                    # Determine if this is a file or directory
                    is_file = (i == len(parts) - 1)
                    current[part] = {} if not is_file else None
                current = current[part] if current[part] is not None else current

        return tree

    def _format_tree_as_markdown(self, tree: Dict, indent_level: int = 0, current_path: str = "") -> List[str]:
        """Format the directory tree as markdown with checkboxes only on files."""
        lines = []
        indent = "  " * indent_level

        # Sort items: directories first, then files
        items = sorted(tree.items(), key=lambda x: (x[1] is None, x[0]))

        for name, subtree in items:
            if subtree is None:
                # File - create wiki-link with checkbox
                full_path = f"{current_path}/{name}" if current_path else name
                lines.append(f"{indent}- [ ] [[{full_path}|{name}]]")
            else:
                # Directory - no checkbox
                lines.append(f"{indent}- {name}/")
                new_path = f"{current_path}/{name}" if current_path else name
                lines.extend(self._format_tree_as_markdown(subtree, indent_level + 1, new_path))

        return lines

    def _generate_report(self, orphaned_images: List[Path], all_images: Set[Path],
                        referenced_images: Set[Path], vault_root: Path) -> str:
        """Generate the orphaned images markdown report."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        orphaned_count = len(orphaned_images)
        total_images = len(all_images)
        referenced_count = len(referenced_images)

        # Build directory tree
        tree = self._build_directory_tree(orphaned_images, vault_root)

        # Generate markdown
        lines = [
            "---",
            "tags:",
            "  - vault-management",
            "  - images",
            "  - orphaned-files",
            "---",
            "",
            "# Orphaned Images",
            "",
            f"**Generated:** {now}",
            f"**Vault:** `{vault_root}`",
            f"**Ignored directories:** `.obsidian`, `.trash`, `Excalidraw`",
            "",
            "## Statistics",
            "",
            f"- Total images: {total_images}",
            f"- Referenced images: {referenced_count}",
            f"- Orphaned images: {orphaned_count}",
            "",
            "## Orphaned Image Files",
            "",
        ]

        if orphaned_count == 0:
            lines.append("No orphaned images found! All images are referenced in markdown files.")
        else:
            lines.append("The following image files are not referenced in any markdown file:")
            lines.append("")
            lines.extend(self._format_tree_as_markdown(tree))

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*Generated by `python -m Library.images find`*")

        return '\n'.join(lines) + '\n'
