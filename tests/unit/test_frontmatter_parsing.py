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
    is_valid_obsidian_tag,
    FrontmatterManager
)


@pytest.mark.unit
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


class TestFrontmatterManager:
    """Test FrontmatterManager class for centralized frontmatter operations."""

    def test_extract_with_frontmatter(self):
        """Test extracting frontmatter returns dict and body."""
        content = "---\ntitle: Test\ntags:\n  - foo\n---\n# Content"
        fm_dict, body = FrontmatterManager.extract(content)
        assert fm_dict is not None
        assert fm_dict['title'] == 'Test'
        assert fm_dict['tags'] == ['foo']
        assert body == '# Content'

    def test_extract_without_frontmatter(self):
        """Test extracting from content without frontmatter."""
        content = "# Just content"
        fm_dict, body = FrontmatterManager.extract(content)
        assert fm_dict is None
        assert body == content

    def test_extract_empty_frontmatter(self):
        """Test extracting empty frontmatter.

        Note: Empty frontmatter (---\n---\n) is treated as no frontmatter
        because the regex requires at least some content between delimiters.
        """
        content = "---\n---\n# Content"
        fm_dict, body = FrontmatterManager.extract(content)
        # Empty frontmatter doesn't match the regex, so it's treated as no frontmatter
        assert fm_dict is None
        assert body == content

    def test_extract_malformed_yaml(self):
        """Test extracting malformed YAML returns None."""
        content = "---\ntitle: Test\ninvalid yaml: [unclosed\n---\n# Content"
        fm_dict, body = FrontmatterManager.extract(content)
        assert fm_dict is None
        assert body == '# Content'

    def test_serialize_with_dict(self):
        """Test serializing frontmatter dict back to markdown."""
        fm_dict = {'title': 'Test', 'tags': ['foo', 'bar']}
        body = '# Content'
        content = FrontmatterManager.serialize(fm_dict, body)
        assert content.startswith('---\n')
        assert 'title: Test' in content
        assert 'tags:' in content
        assert '# Content' in content

    def test_serialize_empty_dict(self):
        """Test serializing empty dict removes frontmatter."""
        body = '# Content'
        content = FrontmatterManager.serialize({}, body)
        assert content == body

    def test_serialize_none(self):
        """Test serializing None removes frontmatter."""
        body = '# Content'
        content = FrontmatterManager.serialize(None, body)
        assert content == body

    def test_update_property_add_new(self):
        """Test updating property that doesn't exist."""
        content = "---\ntitle: Test\n---\n# Content"
        updated, modified = FrontmatterManager.update_property(content, 'status', 'draft')
        assert modified is True
        assert 'status: draft' in updated

    def test_update_property_modify_existing(self):
        """Test updating existing property."""
        content = "---\ntitle: Test\nstatus: draft\n---\n# Content"
        updated, modified = FrontmatterManager.update_property(content, 'status', 'published')
        assert modified is True
        assert 'status: published' in updated
        assert 'status: draft' not in updated

    def test_update_property_no_change(self):
        """Test updating property with same value."""
        content = "---\ntitle: Test\nstatus: draft\n---\n# Content"
        updated, modified = FrontmatterManager.update_property(content, 'status', 'draft')
        assert modified is False

    def test_update_property_create_frontmatter(self):
        """Test updating property creates frontmatter if missing."""
        content = "# Just content"
        updated, modified = FrontmatterManager.update_property(content, 'title', 'Test')
        assert modified is True
        assert '---\n' in updated
        assert 'title: Test' in updated
        assert '# Just content' in updated

    def test_remove_property_exists(self):
        """Test removing existing property."""
        content = "---\ntitle: Test\nauthor: Me\n---\n# Content"
        updated, removed = FrontmatterManager.remove_property(content, 'author')
        assert removed is True
        assert 'author' not in updated
        assert 'title: Test' in updated

    def test_remove_property_not_exists(self):
        """Test removing non-existent property."""
        content = "---\ntitle: Test\n---\n# Content"
        updated, removed = FrontmatterManager.remove_property(content, 'author')
        assert removed is False
        assert updated == content

    def test_remove_property_no_frontmatter(self):
        """Test removing property from content without frontmatter."""
        content = "# Just content"
        updated, removed = FrontmatterManager.remove_property(content, 'title')
        assert removed is False
        assert updated == content

    def test_remove_last_property(self):
        """Test removing last property removes frontmatter entirely."""
        content = "---\ntitle: Test\n---\n# Content"
        updated, removed = FrontmatterManager.remove_property(content, 'title')
        assert removed is True
        assert '---' not in updated
        assert updated == '# Content'

    def test_bulk_update_multiple_properties(self):
        """Test updating multiple properties at once."""
        content = "---\ntitle: Test\n---\n# Content"
        updates = {'status': 'draft', 'priority': 'high'}
        updated, modified = FrontmatterManager.bulk_update(content, updates)
        assert modified is True
        assert 'status: draft' in updated
        assert 'priority: high' in updated

    def test_bulk_update_no_changes(self):
        """Test bulk update with all same values."""
        content = "---\ntitle: Test\nstatus: draft\n---\n# Content"
        updates = {'status': 'draft'}
        updated, modified = FrontmatterManager.bulk_update(content, updates)
        assert modified is False

    def test_bulk_update_creates_frontmatter(self):
        """Test bulk update creates frontmatter if missing."""
        content = "# Just content"
        updates = {'title': 'Test', 'status': 'draft'}
        updated, modified = FrontmatterManager.bulk_update(content, updates)
        assert modified is True
        assert 'title: Test' in updated
        assert 'status: draft' in updated

    def test_has_property_true(self):
        """Test checking for property that exists."""
        content = "---\ntitle: Test\n---\n# Content"
        assert FrontmatterManager.has_property(content, 'title') is True

    def test_has_property_false(self):
        """Test checking for property that doesn't exist."""
        content = "---\ntitle: Test\n---\n# Content"
        assert FrontmatterManager.has_property(content, 'author') is False

    def test_has_property_no_frontmatter(self):
        """Test checking property on content without frontmatter."""
        content = "# Just content"
        assert FrontmatterManager.has_property(content, 'title') is False

    def test_get_property_exists(self):
        """Test getting property value that exists."""
        content = "---\ntitle: Test\n---\n# Content"
        value = FrontmatterManager.get_property(content, 'title')
        assert value == 'Test'

    def test_get_property_not_exists(self):
        """Test getting property that doesn't exist returns None."""
        content = "---\ntitle: Test\n---\n# Content"
        value = FrontmatterManager.get_property(content, 'author')
        assert value is None

    def test_get_property_with_default(self):
        """Test getting property with default value."""
        content = "---\ntitle: Test\n---\n# Content"
        value = FrontmatterManager.get_property(content, 'author', 'Unknown')
        assert value == 'Unknown'

    def test_get_property_no_frontmatter(self):
        """Test getting property from content without frontmatter."""
        content = "# Just content"
        value = FrontmatterManager.get_property(content, 'title', 'Default')
        assert value == 'Default'

    def test_validate_yaml_valid(self):
        """Test validating valid YAML."""
        content = "---\ntitle: Test\ntags:\n  - foo\n---\n# Content"
        is_valid, error = FrontmatterManager.validate_yaml(content)
        assert is_valid is True
        assert error is None

    def test_validate_yaml_invalid(self):
        """Test validating invalid YAML."""
        content = "---\ntitle: Test\ninvalid: [unclosed\n---\n# Content"
        is_valid, error = FrontmatterManager.validate_yaml(content)
        assert is_valid is False
        assert error is not None
        assert isinstance(error, str)

    def test_validate_yaml_no_frontmatter(self):
        """Test validating content without frontmatter."""
        content = "# Just content"
        is_valid, error = FrontmatterManager.validate_yaml(content)
        assert is_valid is True
        assert error is None

    def test_preserve_property_order(self):
        """Test that property order is preserved (sort_keys=False)."""
        content = "---\nz_last: value\na_first: value\nm_middle: value\n---\n# Content"
        # Update shouldn't reorder
        updated, _ = FrontmatterManager.update_property(content, 'new_prop', 'value')
        fm_dict, _ = FrontmatterManager.extract(updated)
        keys = list(fm_dict.keys())
        # Original order should be maintained (z, a, m, new)
        assert keys[0] == 'z_last'
        assert keys[1] == 'a_first'
        assert keys[2] == 'm_middle'

    def test_unicode_support(self):
        """Test that Unicode characters are properly handled."""
        content = "---\ntitle: 测试\ndescription: Тест\n---\n# Content"
        fm_dict, body = FrontmatterManager.extract(content)
        assert fm_dict['title'] == '测试'
        assert fm_dict['description'] == 'Тест'

        # Test round-trip
        updated = FrontmatterManager.serialize(fm_dict, body)
        assert '测试' in updated
        assert 'Тест' in updated


@pytest.mark.parametrize("content,property,value,should_modify", [
    ("---\ntitle: Test\n---\n# Content", "status", "draft", True),
    ("---\ntitle: Test\nstatus: draft\n---\n# Content", "status", "draft", False),
    ("# Just content", "title", "Test", True),
])
def test_update_property_parametrized(content, property, value, should_modify):
    """Parametrized test for update_property."""
    updated, modified = FrontmatterManager.update_property(content, property, value)
    assert modified == should_modify
    if should_modify:
        assert f"{property}:" in updated or f"{property} :" in updated


@pytest.mark.parametrize("content,property,should_remove", [
    ("---\ntitle: Test\nauthor: Me\n---\n# Content", "author", True),
    ("---\ntitle: Test\n---\n# Content", "author", False),
    ("# Just content", "title", False),
])
def test_remove_property_parametrized(content, property, should_remove):
    """Parametrized test for remove_property."""
    updated, removed = FrontmatterManager.remove_property(content, property)
    assert removed == should_remove
