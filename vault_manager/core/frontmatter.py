"""
Frontmatter and YAML utilities for Obsidian markdown files.

This module provides functions for extracting, parsing, and manipulating
YAML frontmatter in markdown files, as well as tag-specific operations.
"""

import re
from typing import Optional, Tuple, List


def extract_frontmatter(content: str) -> Tuple[Optional[str], str]:
    """
    Extract YAML frontmatter from markdown content.

    Args:
        content: Full markdown file content

    Returns:
        Tuple of (frontmatter, body)
        - frontmatter: YAML content without --- delimiters, or None if not found
        - body: Markdown content after frontmatter

    Examples:
        >>> content = "---\\ntitle: Test\\n---\\n# Hello"
        >>> fm, body = extract_frontmatter(content)
        >>> fm
        'title: Test'
        >>> body
        '# Hello'

    Note:
        Handles both Unix (\\n) and Windows (\\r\\n) line endings by normalizing
        to Unix-style before processing.
    """
    # Normalize line endings to Unix-style for cross-platform compatibility
    # This ensures the regex works correctly on Windows, macOS, Linux, and Android
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if not match:
        return None, content

    frontmatter = match.group(1)
    body = content[match.end():]

    return frontmatter, body


def extract_tags_from_frontmatter(content: str) -> List[str]:
    """
    Extract tags from YAML frontmatter.

    Handles both inline array format and list format:
    - Inline: tags: [foo, bar]
    - List:   tags:\\n  - foo\\n  - bar

    Args:
        content: Full markdown content with frontmatter

    Returns:
        List of tags (without # prefix), sorted alphabetically

    Examples:
        >>> content = "---\\ntags:\\n  - foo\\n  - bar\\n---\\nContent"
        >>> extract_tags_from_frontmatter(content)
        ['bar', 'foo']
        >>> content = "---\\ntags: [baz, qux]\\n---\\nContent"
        >>> extract_tags_from_frontmatter(content)
        ['baz', 'qux']
    """
    frontmatter, _ = extract_frontmatter(content)

    if not frontmatter:
        return []

    tags = set()
    lines = frontmatter.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith('tags:'):
            tags_value = line.split('tags:', 1)[1].strip()

            # Handle inline array format: tags: [foo, bar]
            if tags_value.startswith('[') and tags_value.endswith(']'):
                tags_str = tags_value[1:-1]
                inline_tags = [t.strip().strip('"').strip("'") for t in tags_str.split(',')]
                tags.update([t for t in inline_tags if t])
                break

            # Handle list format
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()

                # Stop at next property or end
                if next_line and not next_line.startswith('-') and ':' in next_line:
                    i -= 1
                    break

                if next_line.startswith('-'):
                    tag = next_line[1:].strip().strip('"').strip("'")
                    # Remove # prefix if present (shouldn't be, but handle it)
                    if tag.startswith('#'):
                        tag = tag[1:]
                    if tag:
                        tags.add(tag)

                i += 1
            break

        i += 1

    return sorted(tags)


def needs_quoting(value: str) -> bool:
    """
    Check if a YAML value needs quoting.

    Args:
        value: String value to check

    Returns:
        True if value should be quoted in YAML

    Examples:
        >>> needs_quoting('simple')
        False
        >>> needs_quoting('2024')
        True
        >>> needs_quoting('has:colon')
        True
    """
    if not value:
        return True

    # Values starting with special YAML characters
    if value[0] in {'-', '?', ':', '#', '&', '*', '!', '|', '>', '%', '@', '`'}:
        return True

    # Values containing special characters
    if any(char in value for char in {':', '{', '}', '[', ']', ',', '&', '*', '#', '?', '|', '-', '<', '>', '=', '!', '%', '@'}):
        return True

    # Numeric values
    if value.isdigit() or value.replace('.', '', 1).isdigit():
        return True

    # Boolean-like values
    if value.lower() in {'true', 'false', 'yes', 'no', 'on', 'off'}:
        return True

    return False


def format_tag_name(tag: str) -> str:
    """
    Format tag name for YAML output (with quoting if needed).

    Args:
        tag: Tag name (without # prefix)

    Returns:
        Formatted tag name (quoted if necessary)

    Examples:
        >>> format_tag_name('software-development')
        'software-development'
        >>> format_tag_name('2024')
        '"2024"'
    """
    if needs_quoting(tag):
        return f'"{tag}"'
    return tag


def is_valid_obsidian_tag(tag: str) -> bool:
    """
    Validate tag against Obsidian's tag rules.

    Obsidian tag rules:
    - Must contain only: letters, numbers, underscore (_), hyphen (-), slash (/)
    - Must contain at least one letter or underscore (cannot be all numeric)
    - Cannot be empty

    Args:
        tag: Tag to validate (without # prefix)

    Returns:
        True if tag is valid

    Examples:
        >>> is_valid_obsidian_tag("software-development")
        True
        >>> is_valid_obsidian_tag("2024")
        False
        >>> is_valid_obsidian_tag("y2024")
        True
        >>> is_valid_obsidian_tag("nested/tag")
        True
    """
    if not tag:
        return False

    # Check for valid characters only
    if not re.match(r'^[a-zA-Z0-9_/-]+$', tag):
        return False

    # Must contain at least one letter or underscore
    has_letter_or_underscore = any(c.isalpha() or c == '_' for c in tag)

    return has_letter_or_underscore


def is_sensitive_note(content: str) -> bool:
    """
    Check if a note is marked as sensitive in its frontmatter.

    Checks for 'sensitive: true' property in YAML frontmatter. Notes marked
    as sensitive will be skipped by AI-powered features (tag generation,
    summarization) to prevent sending sensitive content to external APIs.

    Args:
        content: Full markdown content with frontmatter

    Returns:
        True if note has sensitive: true in frontmatter, False otherwise

    Examples:
        >>> content = "---\\nsensitive: true\\n---\\nSecret content"
        >>> is_sensitive_note(content)
        True
        >>> content = "---\\nsensitive: false\\n---\\nPublic content"
        >>> is_sensitive_note(content)
        False
        >>> content = "---\\ntags: [foo]\\n---\\nNormal content"
        >>> is_sensitive_note(content)
        False
    """
    frontmatter, _ = extract_frontmatter(content)

    if not frontmatter:
        return False

    # Look for sensitive property with true value
    # Match variations: sensitive: true, sensitive: True, sensitive: "true", etc.
    sensitive_pattern = r'^sensitive:\s*(?:true|True|TRUE|yes|Yes|YES)\s*$'

    for line in frontmatter.split('\n'):
        if re.match(sensitive_pattern, line.strip()):
            return True

    return False
