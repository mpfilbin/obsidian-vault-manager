"""
Link extraction and resolution for vault indexing.

This module provides the LinkExtractor class which extracts and resolves
all types of links from markdown files (wiki-links, markdown links, image embeds).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from vault_manager.core import get_vault_root

EXTERNAL_URL_PROTOCOLS = ('http://', 'https://', 'file://', '//', 'ftp://', 'mailto:')

# Link type constants
LINK_TYPE_WIKI = 'wiki'
LINK_TYPE_MARKDOWN = 'markdown'
LINK_TYPE_IMAGE_WIKI = 'image_wiki'
LINK_TYPE_IMAGE_MARKDOWN = 'image_markdown'



# Regex patterns for link extraction
# Wiki-links: [[Note]] or [[Note|Display Text]]
WIKI_LINK_PATTERN = re.compile(r'\[\[([^]|]+)(?:\|([^]]+))?]]')

# Markdown links: [text](url)
MARKDOWN_LINK_PATTERN = re.compile(r'\[([^]]+)]\(([^)]+)\)')

# Image embeds (wiki): ![[image.png]] or ![[image.png|alt text]]
IMAGE_WIKI_PATTERN = re.compile(r'!\[\[([^]|]+)(?:\|([^]]+))?]]')

# Image embeds (markdown): ![alt](path)
IMAGE_MARKDOWN_PATTERN = re.compile(r'!\[([^]]*)]\(([^)]+)\)')


@dataclass
class Link:
    """
    Represents a link from one file to another (3NF normalized).

    Attributes:
        source_file: Relative path of file containing the link
        target_file: Relative path of target file (None if unresolved)
        link_type: Type of link ('wiki', 'markdown', 'image_wiki', 'image_markdown')
        link_text: Display text or alt text (if any)
        line_number: Line number where link appears (None if not tracked)
        raw_target: Raw link target text before resolution

    Note:
        is_resolved can be derived from: target_file IS NOT NULL
        This follows 3NF - no derived attributes stored.
    """
    source_file: str
    target_file: Optional[str]
    link_type: str
    link_text: Optional[str]
    line_number: Optional[int] = None
    raw_target: str = ''


class LinkExtractor:
    """
    Extractor for finding and resolving links in markdown files.

    Handles multiple link formats:
    - Wiki-links: [[Note Name]] or [[Note Name|Display Text]]
    - Markdown links: [display text](url/path)
    - Image embeds (wiki): ![[image.png]] or ![[image.png|alt text]]
    - Image embeds (markdown): ![alt text](image.png)
    """

    def __init__(self, vault_root: Optional[Path] = None):
        """
        Initialize the link extractor.

        Args:
            vault_root: Vault root directory (defaults to auto-detected)
        """
        self.vault_root = vault_root or get_vault_root()
        self._filename_index: Optional[Dict[str, List[Path]]] = None

    def build_filename_index(self, all_files: Set[str]) -> None:
        """
        Build an index mapping filenames to their full paths for fast resolution.

        Args:
            all_files: Set of all relative file paths in vault

        Note:
            Used for Obsidian-style filename-only link resolution
        """
        self._filename_index = {}

        for relative_path in all_files:
            full_path = self.vault_root / relative_path
            filename = full_path.name

            if filename not in self._filename_index:
                self._filename_index[filename] = []
            self._filename_index[filename].append(full_path)

    def extract_links(self, content: str, source_file: str) -> List[Link]:
        """
        Extract all links from markdown content.

        Args:
            content: Full markdown file content
            source_file: Relative path of source file

        Returns:
            List of Link objects

        Note:
            Automatically resolves link targets to absolute paths
        """
        links = []
        source_path = self.vault_root / source_file

        # Extract wiki-links
        for match in WIKI_LINK_PATTERN.finditer(content):
            target_text = match.group(1).strip()
            display_text = match.group(2).strip() if match.group(2) else None

            # Skip image embeds (handled separately)
            start_pos = match.start()
            if start_pos > 0 and content[start_pos - 1] == '!':
                continue

            target_path = self.resolve_link_target(target_text, source_path)

            links.append(Link(
                source_file=source_file,
                target_file=target_path,
                link_type=LINK_TYPE_WIKI,
                link_text=display_text,
                raw_target=target_text
            ))

        # Extract markdown links
        for match in MARKDOWN_LINK_PATTERN.finditer(content):
            display_text = match.group(1).strip()
            target_text = match.group(2).strip()

            # Skip image embeds (handled separately)
            start_pos = match.start()
            if start_pos > 0 and content[start_pos - 1] == '!':
                continue

            # Skip external URLs (we only track internal links)
            if target_text.startswith(('http://', 'https://', '//', 'ftp://', 'mailto:')):
                continue

            target_path = self.resolve_link_target(target_text, source_path)

            links.append(Link(
                source_file=source_file,
                target_file=target_path,
                link_type=LINK_TYPE_MARKDOWN,
                link_text=display_text,
                raw_target=target_text
            ))

        # Extract image embeds (wiki-style)
        for match in IMAGE_WIKI_PATTERN.finditer(content):
            target_text = match.group(1).strip()
            alt_text = match.group(2).strip() if match.group(2) else None

            target_path = self.resolve_link_target(target_text, source_path)

            links.append(Link(
                source_file=source_file,
                target_file=target_path,
                link_type=LINK_TYPE_IMAGE_WIKI,
                link_text=alt_text,
                raw_target=target_text
            ))

        # Extract image embeds (markdown-style)
        for match in IMAGE_MARKDOWN_PATTERN.finditer(content):
            alt_text = match.group(1).strip() if match.group(1) else None
            target_text = match.group(2).strip()

            # Skip external URLs
            if target_text.startswith(EXTERNAL_URL_PROTOCOLS):
                continue

            target_path = self.resolve_link_target(target_text, source_path)

            links.append(Link(
                source_file=source_file,
                target_file=target_path,
                link_type=LINK_TYPE_IMAGE_MARKDOWN,
                link_text=alt_text,
                raw_target=target_text
            ))

        return links

    def resolve_link_target(self, link_text: str, source_file: Path) -> Optional[str]:
        """
        Resolve a link to its target file path.

        Resolution order:
        1. Skip external URLs
        2. Try relative to source file directory
        3. Try relative to vault root
        4. Try filename-only search (Obsidian behavior)

        Args:
            link_text: Raw link target text
            source_file: Absolute path to source file

        Returns:
            Relative path to target file (from vault root), or None if not found

        Examples:
            >> resolve_link_target('Note.md', Path('/vault/Personal/Source.md'))
            'Personal/Note.md'
            >> resolve_link_target('../Other/Target', Path('/vault/Personal/Source.md'))
            'Other/Target.md'
            >> resolve_link_target('NonExistent', Path('/vault/Source.md'))
            None
        """
        # Clean link text
        link_text = link_text.strip()

        # Skip external URLs
        if link_text.startswith(EXTERNAL_URL_PROTOCOLS):
            return None

        # Remove anchor fragments and query parameters
        link_text = link_text.split('#')[0].split('?')[0]

        if not link_text:
            return None

        # Add .md extension if missing and no extension present (wiki-links)
        link_path = Path(link_text)
        if not link_path.suffix:
            link_text = f"{link_text}.md"
            link_path = Path(link_text)

        # Try relative to source file directory
        target = (source_file.parent / link_text).resolve()
        if target.exists() and target.is_file():
            try:
                if target.is_relative_to(self.vault_root):
                    return str(target.relative_to(self.vault_root))
            except ValueError:
                pass

        # Try relative to vault root
        target = (self.vault_root / link_text).resolve()
        if target.exists() and target.is_file():
            try:
                return str(target.relative_to(self.vault_root))
            except ValueError:
                pass

        # Try filename-only search (Obsidian's behavior)
        if self._filename_index:
            filename = link_path.name
            if filename in self._filename_index:
                candidates = self._filename_index[filename]
                if candidates:
                    # Return first match (Obsidian behavior)
                    try:
                        return str(candidates[0].relative_to(self.vault_root))
                    except ValueError:
                        pass

        # Not found
        return None

    def extract_wiki_links(self, content: str) -> Set[str]:
        """
        Extract just wiki-link targets (without resolution).

        Args:
            content: Markdown file content

        Returns:
            Set of wiki-link target strings

        Note:
            Used for related notes calculation (compatibility with existing tools)
        """
        links = set()

        # Pattern for wiki-links: [[link]] or [[link|display]]
        for match in WIKI_LINK_PATTERN.finditer(content):
            # Skip image embeds
            start_pos = match.start()
            if start_pos > 0 and content[start_pos - 1] == '!':
                continue

            link = match.group(1).strip()

            # Normalize link (remove .md extension if present)
            if link.endswith('.md'):
                link = link[:-3]

            links.add(link)

        return links
