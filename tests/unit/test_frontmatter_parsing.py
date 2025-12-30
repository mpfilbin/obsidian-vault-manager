"""
Unit tests for frontmatter parsing functionality.

These tests verify the core frontmatter extraction logic used across
multiple commands.
"""

import pytest
from vault_manager.core.frontmatter import (
    extract_frontmatter,
    extract_tags_from_frontmatter,
    needs_quoting,
    format_tag_name,
    is_valid_obsidian_tag
)


class TestExtractFrontmatter:
    """Test frontmatter extraction from markdown content."""

    def test_extract_valid_frontmatter(self):
        """Test extracting valid YAML frontmatter."""
        content = """---
title: Test Note
tags:
  - test
  - example
---

# Content
"""
        frontmatter, body = extract_frontmatter(content)
        assert frontmatter is not None
        assert 'title: Test Note' in frontmatter
        assert 'tags:' in frontmatter
        assert '# Content' in body

    def test_extract_frontmatter_windows_line_endings(self):
        """Test extracting frontmatter with Windows CRLF line endings."""
        # Simulate Windows-style \r\n line endings
        content = "---\r\ntitle: Windows Test\r\ntags:\r\n  - windows\r\n---\r\n\r\n# Content\r\n"
        frontmatter, body = extract_frontmatter(content)
        assert frontmatter is not None
        assert 'title: Windows Test' in frontmatter
        assert 'tags:' in frontmatter
        assert '# Content' in body

    def test_extract_frontmatter_mixed_line_endings(self):
        """Test extracting frontmatter with mixed line endings."""
        # Simulate file with mixed \r\n and \n (can happen after editing on different platforms)
        content = "---\r\ntitle: Mixed\ntags:\r\n  - test\n---\n# Content"
        frontmatter, body = extract_frontmatter(content)
        assert frontmatter is not None
        assert 'title: Mixed' in frontmatter

    def test_extract_no_frontmatter(self):
        """Test content without frontmatter."""
        content = "# Just Content\n\nNo frontmatter here."
        frontmatter, body = extract_frontmatter(content)
        assert frontmatter is None
        assert body == content

    def test_extract_empty_frontmatter(self):
        """Test empty frontmatter block."""
        content = """---
---

# Content
"""
        frontmatter, body = extract_frontmatter(content)
        # Empty frontmatter may return None or empty string
        assert frontmatter is None or frontmatter == ""
        assert '# Content' in body

    def test_frontmatter_not_at_start(self):
        """Test frontmatter not at the beginning of file."""
        content = """
Some content first

---
title: Test
---
"""
        frontmatter, body = extract_frontmatter(content)
        assert frontmatter is None


class TestExtractTagsFromFrontmatter:
    """Test tag extraction from frontmatter."""

    def test_extract_list_format_tags(self):
        """Test extracting tags in list format."""
        content = """---
tags:
  - software-development
  - testing
---

Content
"""
        tags = extract_tags_from_frontmatter(content)
        assert len(tags) == 2
        assert 'software-development' in tags
        assert 'testing' in tags
        # Tags should be sorted
        assert tags == sorted(tags)

    def test_extract_inline_array_tags(self):
        """Test extracting tags in inline array format."""
        content = """---
tags: [foo, bar, baz]
---

Content
"""
        tags = extract_tags_from_frontmatter(content)
        assert len(tags) == 3
        assert 'foo' in tags
        assert 'bar' in tags
        assert 'baz' in tags

    def test_extract_no_tags(self):
        """Test content with frontmatter but no tags."""
        content = """---
title: Test
author: Someone
---

Content
"""
        tags = extract_tags_from_frontmatter(content)
        assert tags == []

    def test_extract_no_frontmatter(self):
        """Test content without frontmatter."""
        content = "# Just content"
        tags = extract_tags_from_frontmatter(content)
        assert tags == []

    def test_extract_tags_with_quotes(self):
        """Test extracting quoted tags."""
        content = """---
tags:
  - "quoted-tag"
  - 'single-quoted'
  - unquoted
---

Content
"""
        tags = extract_tags_from_frontmatter(content)
        assert 'quoted-tag' in tags
        assert 'single-quoted' in tags
        assert 'unquoted' in tags

    def test_remove_hash_prefix(self):
        """Test that # prefix is removed from tags."""
        content = """---
tags:
  - #hashtag
  - normal
---

Content
"""
        tags = extract_tags_from_frontmatter(content)
        assert 'hashtag' in tags
        assert 'normal' in tags
        assert '#hashtag' not in tags


class TestNeedsQuoting:
    """Test YAML value quoting logic."""

    def test_simple_value_no_quotes(self):
        """Test that simple values don't need quoting."""
        assert needs_quoting('simple') is False
        assert needs_quoting('test') is False

    def test_numeric_values_need_quotes(self):
        """Test that numeric values need quoting."""
        assert needs_quoting('2024') is True
        assert needs_quoting('123') is True
        assert needs_quoting('3.14') is True

    def test_boolean_values_need_quotes(self):
        """Test that boolean-like values need quoting."""
        assert needs_quoting('true') is True
        assert needs_quoting('false') is True
        assert needs_quoting('yes') is True
        assert needs_quoting('no') is True

    def test_special_characters_need_quotes(self):
        """Test that values with special chars need quoting."""
        assert needs_quoting('has:colon') is True
        assert needs_quoting('has-hyphen') is True
        assert needs_quoting('[brackets]') is True
        assert needs_quoting('{braces}') is True

    def test_empty_value_needs_quotes(self):
        """Test that empty values need quoting."""
        assert needs_quoting('') is True


class TestFormatTagName:
    """Test tag name formatting for YAML."""

    def test_format_simple_tag(self):
        """Test formatting simple tag name (no special chars)."""
        result = format_tag_name('test')
        assert result == 'test'

    def test_format_numeric_tag(self):
        """Test formatting numeric tag (needs quotes)."""
        result = format_tag_name('2024')
        assert result == '"2024"'

    def test_format_tag_with_special_chars(self):
        """Test formatting tag with special characters."""
        result = format_tag_name('tag:with:colons')
        assert result == '"tag:with:colons"'


class TestIsValidObsidianTag:
    """Test Obsidian tag validation."""

    def test_valid_tags(self):
        """Test valid tag names."""
        assert is_valid_obsidian_tag('software-development') is True
        assert is_valid_obsidian_tag('test') is True
        assert is_valid_obsidian_tag('_test') is True
        assert is_valid_obsidian_tag('test123') is True
        assert is_valid_obsidian_tag('nested/tag') is True

    def test_invalid_all_numeric(self):
        """Test that all-numeric tags are invalid."""
        assert is_valid_obsidian_tag('2024') is False
        assert is_valid_obsidian_tag('123') is False

    def test_invalid_empty(self):
        """Test that empty tags are invalid."""
        assert is_valid_obsidian_tag('') is False

    def test_invalid_special_characters(self):
        """Test that tags with special characters are invalid."""
        assert is_valid_obsidian_tag('tag with spaces') is False
        assert is_valid_obsidian_tag('tag@email') is False
        assert is_valid_obsidian_tag('tag#hash') is False

    def test_valid_with_underscore(self):
        """Test that tags with underscores are valid."""
        assert is_valid_obsidian_tag('_prefix') is True
        assert is_valid_obsidian_tag('under_score') is True

    def test_valid_numeric_with_letter(self):
        """Test numeric tags with at least one letter."""
        assert is_valid_obsidian_tag('y2024') is True
        assert is_valid_obsidian_tag('tag123') is True


@pytest.mark.parametrize("content,expected_count", [
    ("---\ntags:\n  - test\n---\n", 1),
    ("---\ntags: [a, b, c]\n---\n", 3),
    ("# No frontmatter", 0),
    ("---\ntitle: Test\n---\n", 0),
])
def test_extract_tags_parametrized(content, expected_count):
    """Parametrized test for tag extraction."""
    tags = extract_tags_from_frontmatter(content)
    assert len(tags) == expected_count


@pytest.mark.parametrize("tag,is_valid", [
    ("software-development", True),
    ("2024", False),
    ("y2024", True),
    ("_test", True),
    ("test with spaces", False),
    ("", False),
])
def test_tag_validation_parametrized(tag, is_valid):
    """Parametrized test for tag validation."""
    assert is_valid_obsidian_tag(tag) == is_valid
