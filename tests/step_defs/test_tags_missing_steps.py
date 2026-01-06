"""
Step definitions for Missing Tags Command BDD tests.
"""

import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from argparse import Namespace

from vault_manager.tags.commands.missing import MissingCommand

# Load scenarios from feature file
scenarios('../features/tags_missing.feature')


# Context to store test state
@pytest.fixture
def context():
    """Test context to share state between steps."""
    return {
        'vault': None,
        'notes': [],
        'report_path': None,
        'report_content': None,
        'command': MissingCommand(),
    }


# Given steps

@given('a test vault with markdown files')
def test_vault_with_files(temp_vault, context):
    """Create a test vault directory."""
    context['vault'] = temp_vault


@given(parsers.parse('a note "{filename}" with no frontmatter'))
def note_no_frontmatter(context, filename):
    """Create a note without frontmatter."""
    note_path = context['vault'] / filename
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Test Note\n\nContent without frontmatter.")
    context['notes'].append(filename)


@given(parsers.parse('a note "{filename}" with frontmatter but no tags'))
def note_frontmatter_no_tags(context, filename):
    """Create a note with frontmatter but no tags."""
    note_path = context['vault'] / filename
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("""---
title: Test Note
---

# Test Note

Content with frontmatter but no tags.
""")
    context['notes'].append(filename)


@given(parsers.parse('a note "{filename}" with tags in frontmatter'))
def note_with_tags(context, filename):
    """Create a note with tags."""
    note_path = context['vault'] / filename
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("""---
tags:
  - test-tag
  - example
---

# Test Note

Content with tags.
""")
    context['notes'].append(filename)


@given(parsers.parse('a note "{filename}" without tags'))
def note_without_tags_generic(context, filename):
    """Create a note without tags (generic step)."""
    note_path = context['vault'] / filename
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Test Note\n\nContent without tags.")
    context['notes'].append(filename)


@given(parsers.parse('{count:d} notes without tags'))
def multiple_notes_without_tags(context, count):
    """Create multiple notes without tags."""
    for i in range(count):
        filename = f"tagless_{i}.md"
        note_path = context['vault'] / filename
        note_path.write_text(f"# Note {i}\n\nNo tags.")
        context['notes'].append(filename)


@given(parsers.parse('{count:d} notes with tags'))
def multiple_notes_with_tags(context, count):
    """Create multiple notes with tags."""
    for i in range(count):
        filename = f"tagged_{i}.md"
        note_path = context['vault'] / filename
        note_path.write_text(f"""---
tags:
  - test
---

# Note {i}

With tags.
""")
        context['notes'].append(filename)


@given('an empty vault')
def empty_vault(context, temp_vault):
    """Use an empty vault."""
    context['vault'] = temp_vault


# When steps

@when('I run the missing tags command')
def run_missing_tags_command(context, mock_vault_root, monkeypatch):
    """Execute the missing tags command."""
    # Mock vault root to use test vault
    # Patch in the commands.missing module where it's actually used
    monkeypatch.setattr(
        "vault_manager.tags.commands.missing.get_vault_root",
        lambda: context['vault']
    )

    # Execute command
    args = Namespace()
    context['command'].execute(args)

    # Read generated report
    context['report_path'] = context['vault'] / 'tagless-notes.md'
    if context['report_path'].exists():
        context['report_content'] = context['report_path'].read_text()


# Then steps

@then(parsers.parse('the report should list "{filename}"'))
def report_lists_file(context, filename):
    """Verify the report lists the specified file."""
    assert context['report_content'] is not None
    # Convert to wiki-link format
    wiki_link = f"[[{filename[:-3]}]]" if filename.endswith('.md') else f"[[{filename}]]"
    assert wiki_link in context['report_content'], \
        f"Expected {wiki_link} in report but not found"


@then(parsers.parse('the report should not list "{filename}"'))
def report_does_not_list_file(context, filename):
    """Verify the report does not list the specified file."""
    assert context['report_content'] is not None
    wiki_link = f"[[{filename[:-3]}]]" if filename.endswith('.md') else f"[[{filename}]]"
    assert wiki_link not in context['report_content'], \
        f"Expected {wiki_link} NOT in report but found it"


@then(parsers.parse('a report file "{filename}" should be created'))
def report_file_created(context, filename):
    """Verify the report file was created."""
    report_path = context['vault'] / filename
    assert report_path.exists(), f"Report file {filename} was not created"
    context['report_path'] = report_path
    context['report_content'] = report_path.read_text()


@then(parsers.parse('the report should show "{count}" files without tags'))
def report_shows_tagless_count(context, count):
    """Verify the report shows the correct count of files without tags."""
    assert context['report_content'] is not None
    assert f"Files without tags: {count}" in context['report_content']


@then(parsers.parse('the report should show "{count}" files with tags'))
def report_shows_tagged_count(context, count):
    """Verify the report shows the correct count of files with tags."""
    assert context['report_content'] is not None
    assert f"Files with tags: {count}" in context['report_content']


@then(parsers.parse('the report should show "{count}" total files'))
def report_shows_total_count(context, count):
    """Verify the report shows the correct total file count."""
    assert context['report_content'] is not None
    assert f"Total markdown files: {count}" in context['report_content']


@then(parsers.parse('the report should contain wiki-link "{wiki_link}"'))
def report_contains_wiki_link(context, wiki_link):
    """Verify the report contains the specified wiki-link."""
    assert context['report_content'] is not None
    assert wiki_link in context['report_content'], \
        f"Expected wiki-link {wiki_link} in report but not found"
