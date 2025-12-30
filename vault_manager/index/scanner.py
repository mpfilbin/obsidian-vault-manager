"""
File scanning logic for vault indexing.

This module provides the FileScanner class which scans all files in the vault
and extracts metadata needed for database population.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .common import (
    get_vault_root,
    is_ignored_path,
    is_ignored_file,
    compute_file_hash,
    is_text_file,
    format_timestamp
)


@dataclass
class FileInfo:
    """
    Metadata about a file in the vault (3NF normalized).

    Attributes:
        file_path: Relative path from vault root
        size_bytes: File size in bytes
        content_hash: SHA-256 hash (None if not hashed)
        last_modified: ISO 8601 timestamp of last modification
        created: ISO 8601 timestamp of creation (None if not available)
        has_frontmatter: Whether file has YAML frontmatter (markdown only)
        tags: List of tags (markdown files only)

    Note:
        extension can be derived from: Path(file_path).suffix
        tag_count can be derived from: len(tags)
        These follow 3NF - no derived attributes stored.
    """
    file_path: str
    size_bytes: int
    content_hash: Optional[str]
    last_modified: str
    created: Optional[str]
    has_frontmatter: bool = False
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class FileScanner:
    """
    Scanner for extracting file metadata from the vault.

    Scans all files (excluding ignored directories) and extracts:
    - File metadata (size, timestamps, extension)
    - Content hashes (SHA-256 for files < max_hash_size_mb)
    - Tags from frontmatter (markdown files only)
    """

    def __init__(self, vault_root: Optional[Path] = None, hash_files: bool = True, max_hash_size_mb: int = 100):
        """
        Initialize the file scanner.

        Args:
            vault_root: Vault root directory (defaults to auto-detected)
            hash_files: Whether to compute content hashes (default: True)
            max_hash_size_mb: Maximum file size to hash in MB (default: 100)
        """
        self.vault_root = vault_root or get_vault_root()
        self.hash_files = hash_files
        self.max_hash_size_mb = max_hash_size_mb

    def scan_vault(self) -> Dict[str, FileInfo]:
        """
        Scan all files in the vault and extract metadata.

        Returns:
            Dictionary mapping relative file paths to FileInfo objects

        Note:
            Ignores files in: .obsidian, .trash, .backup, Excalidraw directories
        """
        files = {}
        file_count = 0

        for root, dirs, filenames in os.walk(self.vault_root):
            root_path = Path(root)

            # Skip ignored directories
            if is_ignored_path(root_path, self.vault_root):
                dirs[:] = []
                continue

            for filename in filenames:
                file_path = root_path / filename

                # Skip ignored files (databases, cache files, OS files)
                if is_ignored_file(file_path, self.vault_root):
                    continue

                # Get relative path
                try:
                    relative_path = str(file_path.relative_to(self.vault_root))
                except ValueError:
                    continue

                # Extract file info
                file_info = self.extract_file_metadata(file_path, relative_path)
                if file_info:
                    files[relative_path] = file_info
                    file_count += 1

                    # Progress reporting (every 100 files)
                    if file_count % 100 == 0:
                        print(f"  Scanned {file_count} files...")

        return files

    def extract_file_metadata(self, file_path: Path, relative_path: str) -> Optional[FileInfo]:
        """
        Extract metadata for a single file.

        Args:
            file_path: Absolute path to file
            relative_path: Relative path from vault root

        Returns:
            FileInfo object, or None if file cannot be read
        """
        try:
            stat = file_path.stat()
            extension = file_path.suffix.lower()

            # Extract basic metadata
            size_bytes = stat.st_size
            last_modified = format_timestamp(stat.st_mtime)
            created = format_timestamp(stat.st_ctime) if hasattr(stat, 'st_birthtime') else None

            # Compute content hash if enabled
            content_hash = None
            if self.hash_files:
                content_hash = compute_file_hash(file_path, self.max_hash_size_mb)

            # Create base FileInfo (3NF normalized - no extension or tag_count)
            file_info = FileInfo(
                file_path=relative_path,
                size_bytes=size_bytes,
                content_hash=content_hash,
                last_modified=last_modified,
                created=created
            )

            # Extract tags from markdown files (compute extension from file_path)
            if relative_path.endswith('.md'):
                self._extract_markdown_metadata(file_path, file_info)

            return file_info

        except (OSError, PermissionError, FileNotFoundError) as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return None

    def _extract_markdown_metadata(self, file_path: Path, file_info: FileInfo) -> None:
        """
        Extract frontmatter tags and metadata from markdown file.

        Args:
            file_path: Path to markdown file
            file_info: FileInfo object to update

        Note:
            Modifies file_info in-place
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for frontmatter
            if content.startswith('---'):
                file_info.has_frontmatter = True
                tags = self._extract_tags_from_frontmatter(content)
                if tags:
                    file_info.tags = tags

        except (OSError, UnicodeDecodeError) as e:
            # Try with fallback encoding
            try:
                with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                    content = f.read()

                if content.startswith('---'):
                    file_info.has_frontmatter = True
                    tags = self._extract_tags_from_frontmatter(content)
                    if tags:
                        file_info.tags = tags
            except Exception:
                pass  # Skip if cannot read

    def _extract_tags_from_frontmatter(self, content: str) -> List[str]:
        """
        Extract tags from YAML frontmatter.

        Args:
            content: Full markdown file content

        Returns:
            List of tags found in frontmatter

        Note:
            Reuses logic from Library/tags/common.py for compatibility
        """
        # Match YAML frontmatter between --- delimiters
        frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            return []

        frontmatter_text = match.group(1)
        tags = []

        # Parse YAML to extract tags
        lines = frontmatter_text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for tags field
            if line.strip().startswith('tags:'):
                tags_value = line.split('tags:', 1)[1].strip()

                # Handle inline array format: tags: [tag1, tag2]
                if tags_value.startswith('[') and tags_value.endswith(']'):
                    tags_str = tags_value[1:-1]
                    inline_tags = [t.strip().strip('"').strip("'") for t in tags_str.split(',')]
                    tags.extend([t for t in inline_tags if t])
                    break

                # Check next lines for list items
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()

                    # If we hit a line that starts a new field
                    if next_line and not next_line.startswith('-') and ':' in next_line and not next_line.startswith(' '):
                        i -= 1
                        break

                    # If it's a tag item
                    if next_line.startswith('-'):
                        tag = next_line[1:].strip().strip('"').strip("'")
                        if tag:
                            tags.append(tag)
                    elif not next_line:
                        pass
                    elif next_line.startswith(' '):
                        pass
                    else:
                        i -= 1
                        break

                    i += 1
                break

            i += 1

        return tags
