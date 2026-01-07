"""
Step definitions for Tags Query Command BDD tests.
"""

import io
import sqlite3
import sys
import pytest
from argparse import Namespace
from pytest_bdd import scenarios, given, when, then, parsers

from vault_manager.tags.commands.query import QueryCommand

# Load scenarios from feature file
@pytest.mark.bdd
def test_feature():
    scenarios('../features/tags_query.feature')

@pytest.fixture
def context():
    """Context shared between steps."""
    return {
        'vault': None,
        'db_path': None,
        'output': None,
        'command': QueryCommand(),
    }


# Given steps

@given('a vault database with tag data')
def have_vault_db_with_tag_data(temp_vault, vault_database, context):
    context['vault'] = temp_vault
    context['db_path'] = vault_database

    # Base metadata
    conn = sqlite3.connect(context['db_path'])
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ('vault_path', str(temp_vault)))
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, datetime('now'))", ('generated',))
    conn.commit()
    conn.close()


@given(parsers.parse('the database has {count:d} tags'))
def database_has_n_tags(context, count):
    # Populate tags table with `count` unique tags
    conn = sqlite3.connect(context['db_path'])
    cursor = conn.cursor()
    for i in range(count):
        cursor.execute("INSERT OR REPLACE INTO tags (tag) VALUES (?)", (f"tag-{i}",))
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ('total_tags', str(count)))
    conn.commit()
    conn.close()


@given(parsers.parse('{count:d} files with tags'))
def files_with_tags(context, count):
    # Create files and link them with at least one tag
    conn = sqlite3.connect(context['db_path'])
    cursor = conn.cursor()

    tagged_files = 0
    for i in range(count):
        fname = f"file-{i}.md"
        cursor.execute("INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified, has_frontmatter) VALUES (?, 10, datetime('now'), 1)", (fname,))
        # assign two tags to each file to simulate tag instances
        cursor.execute("INSERT INTO file_tags (tag, file_path) VALUES (?, ?)", (f"tag-{i%10}", fname))
        cursor.execute("INSERT INTO file_tags (tag, file_path) VALUES (?, ?)", (f"tag-{(i+1)%10}", fname))
        tagged_files += 1

    # metadata for stats
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ('total_files', str(count)))
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ('total_tagged_files', str(tagged_files)))
    # rough total tag instances = 2 per file
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ('total_tag_instances', str(tagged_files*2)))

    conn.commit()
    conn.close()


@given('no vault database exists')
def no_vault_db_exists(temp_vault, context):
    context['vault'] = temp_vault
    context['db_path'] = temp_vault / 'vault.db'
    # Ensure the database file does not exist
    try:
        if context['db_path'].exists():
            context['db_path'].unlink()
    except Exception:
        pass


@given('a populated tag database')
def populated_tag_database(context):
    # ensure base tags and files exist for custom SQL
    conn = sqlite3.connect(context['db_path'])
    cursor = conn.cursor()
    # add some tags
    for t in ['alpha', 'beta', 'gamma']:
        cursor.execute("INSERT OR REPLACE INTO tags (tag) VALUES (?)", (t,))
    conn.commit()
    conn.close()


@given('tags with usage counts:')
def tags_with_usage_counts(context, datatable):
    # datatable: header + rows [ ['tag','count'], ['software-architecture','45'], ... ]
    conn = sqlite3.connect(context['db_path'])
    cursor = conn.cursor()

    # create files to match counts; distribute file names
    for row in datatable[1:]:
        tag = row[0]
        count = int(row[1])
        cursor.execute("INSERT OR REPLACE INTO tags (tag) VALUES (?)", (tag,))
        for i in range(count):
            fname = f"{tag}-{i}.md"
            cursor.execute("INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified, has_frontmatter) VALUES (?, 10, datetime('now'), 1)", (fname,))
            cursor.execute("INSERT INTO file_tags (tag, file_path) VALUES (?, ?)", (tag, fname))

    conn.commit()
    conn.close()


@given(parsers.parse('files tagged with "{tag1}" and "{tag2}":'))
def files_tagged_with_two(context, tag1, tag2, datatable):
    conn = sqlite3.connect(context['db_path'])
    cursor = conn.cursor()

    # Ensure tags exist
    for t in [tag1, tag2]:
        cursor.execute("INSERT OR REPLACE INTO tags (tag) VALUES (?)", (t,))

    # rows contain single column 'file'
    for row in datatable[1:]:
        fname = row[0]
        cursor.execute("INSERT OR REPLACE INTO files (file_path, size_bytes, last_modified, has_frontmatter) VALUES (?, 10, datetime('now'), 1)", (fname,))
        cursor.execute("INSERT INTO file_tags (tag, file_path) VALUES (?, ?)", (tag1, fname))
        cursor.execute("INSERT INTO file_tags (tag, file_path) VALUES (?, ?)", (tag2, fname))

    conn.commit()
    conn.close()


# When steps

@when(parsers.parse('I run "vault tags query --stats"'))
def run_query_stats(context, monkeypatch):
    # Capture stdout
    buf = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', buf)
    # Mock database path used by query module
    monkeypatch.setattr('vault_manager.tags.commands.query.get_database_path', lambda: context['db_path'])
    # Execute
    args = Namespace(sql=None, most_used=None, least_used=None, files_with=None, files_with_any=None, tag_info=None, stats=True)
    try:
        context['command'].execute(args)
    except SystemExit:
        # capture output for missing DB scenario
        pass
    context['output'] = buf.getvalue()


@when(parsers.parse('I run "vault tags query --most-used {n:d}"'))
def run_query_most_used(context, monkeypatch, n):
    buf = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', buf)
    monkeypatch.setattr('vault_manager.tags.commands.query.get_database_path', lambda: context['db_path'])
    args = Namespace(sql=None, most_used=n, least_used=None, files_with=None, files_with_any=None, tag_info=None, stats=False)
    context['command'].execute(args)
    context['output'] = buf.getvalue()


@when(parsers.parse('I run "vault tags query --files-with {tag1} {tag2}"'))
def run_query_files_with(context, monkeypatch, tag1, tag2):
    buf = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', buf)
    monkeypatch.setattr('vault_manager.tags.commands.query.get_database_path', lambda: context['db_path'])
    args = Namespace(sql=None, most_used=None, least_used=None, files_with=[tag1, tag2], files_with_any=None, tag_info=None, stats=False)
    context['command'].execute(args)
    context['output'] = buf.getvalue()


@when(parsers.parse('I run "vault tags query --sql \'{sql}\'"'))
def run_query_custom_sql(context, monkeypatch, sql):
    buf = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', buf)
    monkeypatch.setattr('vault_manager.tags.commands.query.get_database_path', lambda: context['db_path'])
    args = Namespace(sql=sql, most_used=None, least_used=None, files_with=None, files_with_any=None, tag_info=None, stats=False)
    # Handle potential sys.exit from SQL errors
    try:
        context['command'].execute(args)
    except SystemExit:
        pass
    context['output'] = buf.getvalue()


# Then steps

@then(parsers.parse('the output should show "{n}" unique tags'))
def output_shows_unique_tags(context, n):
    assert context['output'] is not None
    assert f"Unique tags: {n}" in context['output']


@then('the output should show tag distribution statistics')
def output_shows_distribution(context):
    assert context['output'] is not None
    assert "Tag Distribution:" in context['output']
    assert "Single-use" in context['output']
    assert "High-use" in context['output']


@then(parsers.parse('the output should list "{tag}" first'))
def output_list_first(context, tag):
    assert context['output'] is not None
    lines = [l for l in context['output'].splitlines() if l.strip()]
    # find numbered lines
    ranked = [l for l in lines if l.lstrip().startswith('1.')]
    assert any(tag in l for l in ranked), f"Expected first entry to include {tag}"


@then(parsers.parse('the output should list "{tag}" second'))
def output_list_second(context, tag):
    assert context['output'] is not None
    lines = [l for l in context['output'].splitlines() if l.strip()]
    ranked = [l for l in lines if l.lstrip().startswith('2.')]
    assert any(tag in l for l in ranked), f"Expected second entry to include {tag}"


@then(parsers.parse('the output should list "{tag}" third'))
def output_list_third(context, tag):
    assert context['output'] is not None
    lines = [l for l in context['output'].splitlines() if l.strip()]
    ranked = [l for l in lines if l.lstrip().startswith('3.')]
    assert any(tag in l for l in ranked), f"Expected third entry to include {tag}"


@then(parsers.parse('the output should not list "{tag}"'))
def output_not_list_tag(context, tag):
    assert context['output'] is not None
    assert tag not in context['output']


@then(parsers.parse('the output should list "{file}"'))
def output_list_file(context, file):
    assert context['output'] is not None
    # Output prints wiki-links [[Name]] without .md extension
    expected = f"[[{file[:-3]}]]" if file.endswith('.md') else f"[[{file}]]"
    assert expected in context['output']


@then('the output should show query results')
def output_shows_query_results(context):
    assert context['output'] is not None
    assert "row" in context['output'] or "row" in context['output'].lower()


@then(parsers.parse('the command should fail with error "{msg}"'))
def command_should_fail_with_error(context, msg):
    assert context['output'] is not None
    assert msg in context['output']

