"""
Step definitions for Broken Links Command BDD tests.
"""

import pytest
import sqlite3
from pytest_bdd import scenarios, given, when, then, parsers
from argparse import Namespace

from vault_manager.index.commands.broken_links import BrokenLinksCommand

# Load scenarios from feature file

@pytest.mark.bdd
def test_feature():
    scenarios('../features/index_broken_links.feature')

# Context to store test state
@pytest.fixture
def context():
    """Test context to share state between steps."""
    return {
        'vault': None,
        'database': None,
        'notes': {},
        'report_path': None,
        'report_content': None,
        'command': BrokenLinksCommand(),
    }


# Given steps

@given('a vault database with link data')
def vault_database_with_links(temp_vault, vault_database, context):
    """Set up a vault database with link data."""
    context['vault'] = temp_vault
    context['database'] = vault_database


@given(parsers.parse('a note "{filename}" with link "{link}"'))
def note_with_link(context, filename, link):
    """Create a note with a specific link."""
    note_path = context['vault'] / filename
    note_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract link text from wiki-link format
    link_text = link.strip('[]').strip()

    content = f"""# Test Note

This note contains a link to {link}.

Some more content.
"""
    note_path.write_text(content)
    context['notes'][filename] = note_path

    # Add to database
    conn = sqlite3.connect(context['database'])
    cursor = conn.cursor()

    # Add file to database
    cursor.execute("""
        INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified)
        VALUES (?, ?, datetime('now'))
    """, (filename, len(content)))

    # Add broken link (target_file is NULL for broken links)
    cursor.execute("""
        INSERT INTO links (source_file, target_file, link_type, link_text, line_number)
        VALUES (?, NULL, 'wiki', ?, 3)
    """, (filename, link_text))

    conn.commit()
    conn.close()


@given(parsers.parse('no note exists at "{filename}"'))
def no_note_exists(context, filename):
    """Verify that a note doesn't exist (used for broken link scenarios)."""
    note_path = context['vault'] / filename
    assert not note_path.exists(), f"Note {filename} should not exist"


@given(parsers.parse('a note "{filename}" with broken links'))
def note_with_broken_links_generic(context, filename):
    """Create a note with broken links (generic)."""
    note_path = context['vault'] / filename
    note_path.parent.mkdir(parents=True, exist_ok=True)

    content = """# Broken Links Test

This note has [[SomeLink]] and [[AnotherLink]].
"""
    note_path.write_text(content)
    context['notes'][filename] = note_path

    # Add to database
    conn = sqlite3.connect(context['database'])
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified)
        VALUES (?, ?, datetime('now'))
    """, (filename, len(content)))

    # Add broken links
    for link_text in ['SomeLink', 'AnotherLink']:
        cursor.execute("""
            INSERT INTO links (source_file, target_file, link_type, link_text, line_number)
            VALUES (?, NULL, 'wiki', ?, 3)
        """, (filename, link_text))

    conn.commit()
    conn.close()


@given('a note "note1.md" with broken links:')
def note1_with_broken_links_table(context, datatable):
    """Create note1.md with broken links from table."""
    filename = "note1.md"
    note_path = context['vault'] / filename
    note_path.write_text("# Note 1\n\nContent with broken links.")
    context['notes'][filename] = note_path

    conn = sqlite3.connect(context['database'])
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified)
        VALUES (?, 100, datetime('now'))
    """, (filename,))

    # Parse table and add links (skip header row at index 0)
    for row in datatable[1:]:
        link = row[0].strip('[]').strip()  # First column contains the link
        cursor.execute("""
            INSERT INTO links (source_file, target_file, link_type, link_text, line_number)
            VALUES (?, NULL, 'wiki', ?, 3)
        """, (filename, link))

    conn.commit()
    conn.close()


@given('a note "note2.md" with broken links:')
def note2_with_broken_links_table(context, datatable):
    """Create note2.md with broken links from table."""
    filename = "note2.md"
    note_path = context['vault'] / filename
    note_path.write_text("# Note 2\n\nContent with broken links.")
    context['notes'][filename] = note_path

    conn = sqlite3.connect(context['database'])
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified)
        VALUES (?, 100, datetime('now'))
    """, (filename,))

    # Parse table and add links (skip header row at index 0)
    for row in datatable[1:]:
        link = row[0].strip('[]').strip()  # First column contains the link
        cursor.execute("""
            INSERT INTO links (source_file, target_file, link_type, link_text, line_number)
            VALUES (?, NULL, 'wiki', ?, 3)
        """, (filename, link))

    conn.commit()
    conn.close()


@given('a note with a broken link on line 15')
def note_with_link_on_line(context):
    """Create a note with a broken link on line 15."""
    filename = "test-note.md"
    note_path = context['vault'] / filename

    content = "\n" * 14 + "This is line 15 with [[BrokenLink]].\n"
    note_path.write_text(content)
    context['notes'][filename] = note_path

    conn = sqlite3.connect(context['database'])
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified)
        VALUES (?, ?, datetime('now'))
    """, (filename, len(content)))

    cursor.execute("""
        INSERT INTO links (source_file, target_file, link_type, link_text, line_number)
        VALUES (?, NULL, 'wiki', ?, 15)
    """, (filename, 'BrokenLink'))

    conn.commit()
    conn.close()


@given('a broken link in "Personal/Software Architecture/SOLID.md"')
def broken_link_in_nested_path(context):
    """Create a broken link in a nested path."""
    filename = "Personal/Software Architecture/SOLID.md"
    note_path = context['vault'] / filename
    note_path.parent.mkdir(parents=True, exist_ok=True)

    content = """# SOLID Principles

See also [[DesignPatterns]] for more information.
"""
    note_path.write_text(content)
    context['notes'][filename] = note_path

    conn = sqlite3.connect(context['database'])
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified)
        VALUES (?, ?, datetime('now'))
    """, (filename, len(content)))

    cursor.execute("""
        INSERT INTO links (source_file, target_file, link_type, link_text, line_number)
        VALUES (?, NULL, 'wiki', ?, 3)
    """, (filename, 'DesignPatterns'))

    conn.commit()
    conn.close()


@given('all wiki-links resolve correctly')
def all_links_resolved(context):
    """Create notes with only resolved links."""
    # Create source note
    source = "source.md"
    source_path = context['vault'] / source
    source_path.write_text("# Source\n\nSee [[target]].")

    # Create target note
    target = "target.md"
    target_path = context['vault'] / target
    target_path.write_text("# Target\n\nContent.")

    context['notes'][source] = source_path
    context['notes'][target] = target_path

    conn = sqlite3.connect(context['database'])
    cursor = conn.cursor()

    # Add both files
    for filename in [source, target]:
        cursor.execute("""
            INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified)
            VALUES (?, 100, datetime('now'))
        """, (filename,))

    # Add resolved link (target_file is NOT NULL)
    cursor.execute("""
        INSERT INTO links (source_file, target_file, link_type, link_text, line_number)
        VALUES (?, ?, 'wiki', ?, 3)
    """, (source, target, 'target'))

    conn.commit()
    conn.close()


# When steps

@when('I run the broken-links command')
def run_broken_links_command(context, monkeypatch):
    """Execute the broken-links command."""
    # Mock get_vault_root and get_database_path
    monkeypatch.setattr(
        "vault_manager.index.commands.broken_links.get_vault_root",
        lambda: context['vault']
    )
    monkeypatch.setattr(
        "vault_manager.index.commands.broken_links.get_database_path",
        lambda: context['database']
    )

    # Execute command
    args = Namespace()
    context['command'].execute(args)

    # Read generated report
    context['report_path'] = context['vault'] / 'broken-links.md'
    if context['report_path'].exists():
        context['report_content'] = context['report_path'].read_text()
    else:
        context['report_content'] = None


# Then steps

@then(parsers.parse('the report should list "{link}" as broken'))
def report_lists_broken_link(context, link):
    """Verify the report lists the specified broken link."""
    assert context['report_content'] is not None, "Report was not generated"
    # Format as it appears in the report
    formatted_link = f"`{link}`"
    assert formatted_link in context['report_content'], \
        f"Expected {formatted_link} in report but not found"


@then(parsers.parse('the source should be "{filename}"'))
def report_shows_source(context, filename):
    """Verify the report shows the specified source file."""
    assert context['report_content'] is not None, "Report was not generated"
    # Convert to wiki-link format
    wiki_link = f"[[{filename[:-3]}]]" if filename.endswith('.md') else f"[[{filename}]]"
    assert wiki_link in context['report_content'], \
        f"Expected source {wiki_link} in report but not found"


@then(parsers.parse('the report should not include links from "{filename}"'))
def report_excludes_file(context, filename):
    """Verify the report excludes links from the specified file."""
    assert context['report_content'] is not None, "Report was not generated"
    wiki_link = f"[[{filename[:-3]}]]" if filename.endswith('.md') else f"[[{filename}]]"
    # The file should not appear as a source in the report
    assert wiki_link not in context['report_content'], \
        f"Expected {wiki_link} NOT in report but found it"


@then(parsers.parse('the report should show "{filename}" with {count:d} broken link'))
@then(parsers.parse('the report should show "{filename}" with {count:d} broken links'))
def report_shows_file_with_count(context, filename, count):
    """Verify the report shows the file with the correct number of broken links."""
    assert context['report_content'] is not None, "Report was not generated"
    wiki_link = f"[[{filename[:-3]}]]" if filename.endswith('.md') else f"[[{filename}]]"
    assert wiki_link in context['report_content'], \
        f"Expected {wiki_link} in report"
    assert f"**Broken links:** {count}" in context['report_content'], \
        f"Expected broken links count {count} in report"


@then(parsers.parse('the report should show line number "{line_number}"'))
def report_shows_line_number(context, line_number):
    """Verify the report shows the specified line number."""
    assert context['report_content'] is not None, "Report was not generated"
    assert f"(line {line_number})" in context['report_content'], \
        f"Expected line number {line_number} in report"


@then(parsers.parse('the report should contain "{wiki_link}"'))
def report_contains_wiki_link(context, wiki_link):
    """Verify the report contains the specified wiki-link."""
    assert context['report_content'] is not None, "Report was not generated"
    assert wiki_link in context['report_content'], \
        f"Expected {wiki_link} in report but not found"


@then(parsers.parse('the report should show "{count}" broken links'))
def report_shows_broken_count(context, count):
    """Verify the report shows the correct count of broken links."""
    if count == "0":
        # When there are no broken links, report is not generated
        assert context['report_content'] is None, \
            "Expected no report when there are 0 broken links"
    else:
        assert context['report_content'] is not None, "Report was not generated"
        assert f"Total broken links: {count}" in context['report_content'], \
            f"Expected total broken links: {count}"


@then(parsers.parse('the report should show "{count}" affected files'))
def report_shows_affected_files(context, count):
    """Verify the report shows the correct count of affected files."""
    if count == "0":
        # When there are no affected files, report is not generated
        assert context['report_content'] is None, \
            "Expected no report when there are 0 affected files"
    else:
        assert context['report_content'] is not None, "Report was not generated"
        assert f"Files with broken links: {count}" in context['report_content'], \
            f"Expected affected files: {count}"

