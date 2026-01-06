"""
Pytest configuration and shared fixtures for Library tests.

This module provides common fixtures for testing vault management commands.
"""

import pytest
import sqlite3
from pathlib import Path
from typing import Dict


@pytest.fixture
def temp_vault(tmp_path):
    """
    Create a temporary vault directory for testing.

    Returns:
        Path: Path to temporary vault directory
    """
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture
def vault_with_notes(temp_vault):
    """
    Create a temporary vault with sample markdown notes.

    Returns:
        Dict with 'path' (vault path) and 'notes' (list of created note paths)
    """
    notes = []

    # Create notes with tags
    note_with_tags = temp_vault / "note_with_tags.md"
    note_with_tags.write_text("""---
tags:
  - test-tag
  - software-development
---

# Note With Tags

This note has tags.
""")
    notes.append(note_with_tags)

    # Create note without frontmatter
    note_no_frontmatter = temp_vault / "note_no_frontmatter.md"
    note_no_frontmatter.write_text("# Note Without Frontmatter\n\nJust content.")
    notes.append(note_no_frontmatter)

    # Create note with frontmatter but no tags
    note_no_tags = temp_vault / "note_no_tags.md"
    note_no_tags.write_text("""---
title: Note Without Tags
---

# Note Without Tags

This note has frontmatter but no tags.
""")
    notes.append(note_no_tags)

    return {
        'path': temp_vault,
        'notes': notes
    }


@pytest.fixture
def vault_database(temp_vault):
    """
    Create a temporary vault database for testing.

    Returns:
        Path: Path to vault.db file
    """
    db_path = temp_vault / "vault.db"

    # Create database with schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            size INTEGER,
            extension TEXT,
            mtime REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag TEXT PRIMARY KEY,
            file_count INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_tags (
            file_path TEXT,
            tag TEXT,
            FOREIGN KEY (file_path) REFERENCES files(path),
            FOREIGN KEY (tag) REFERENCES tags(tag)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            source_file TEXT,
            target_file TEXT,
            link_text TEXT,
            link_type TEXT,
            is_resolved INTEGER DEFAULT 1,
            line_number INTEGER,
            FOREIGN KEY (source_file) REFERENCES files(path)
        )
    """)

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def populated_database(vault_database):
    """
    Create a database populated with sample data.

    Returns:
        Path: Path to populated vault.db file
    """
    conn = sqlite3.connect(vault_database)
    cursor = conn.cursor()

    # Insert sample tags
    tags_data = [
        ('software-architecture', 45),
        ('software-development', 38),
        ('security', 25),
        ('design-principles', 20),
        ('algorithms', 15),
    ]
    cursor.executemany("INSERT INTO tags (tag, file_count) VALUES (?, ?)", tags_data)

    # Insert sample files
    files_data = [
        ('SOLID Principles.md', 1024, '.md', 1234567890.0),
        ('Clean Code.md', 2048, '.md', 1234567891.0),
        ('Security Best Practices.md', 1536, '.md', 1234567892.0),
    ]
    cursor.executemany("INSERT INTO files (path, size, extension, mtime) VALUES (?, ?, ?, ?)", files_data)

    # Insert file-tag relationships
    file_tags_data = [
        ('SOLID Principles.md', 'software-architecture'),
        ('SOLID Principles.md', 'design-principles'),
        ('Clean Code.md', 'software-development'),
        ('Security Best Practices.md', 'security'),
    ]
    cursor.executemany("INSERT INTO file_tags (file_path, tag) VALUES (?, ?)", file_tags_data)

    conn.commit()
    conn.close()

    return vault_database


@pytest.fixture
def mock_vault_root(monkeypatch, temp_vault):
    """
    Mock get_vault_root to return temp vault path.

    Args:
        monkeypatch: pytest monkeypatch fixture
        temp_vault: Temporary vault directory
    """
    def mock_get_vault_root():
        return temp_vault

    # Mock vault_manager.core.vault.get_vault_root
    monkeypatch.setattr("vault_manager.core.vault.get_vault_root", mock_get_vault_root)

    return temp_vault


@pytest.fixture
def mock_database_path(monkeypatch, vault_database):
    """
    Mock get_database_path to return temp database path.

    Args:
        monkeypatch: pytest monkeypatch fixture
        vault_database: Temporary vault database
    """
    def mock_get_database_path():
        return vault_database

    # Mock vault_manager.core.database.get_database_path
    monkeypatch.setattr("vault_manager.core.database.get_database_path", mock_get_database_path)

    return vault_database


@pytest.fixture
def captured_output():
    """
    Fixture to capture command output.

    Returns:
        List to collect output lines
    """
    return []


@pytest.fixture
def sample_frontmatter():
    """
    Sample YAML frontmatter strings for testing.

    Returns:
        Dict: Dictionary of frontmatter examples
    """
    return {
        'valid_with_tags': """---
title: Test Note
tags:
  - test
  - example
---
""",
        'valid_no_tags': """---
title: Test Note
author: Test Author
---
""",
        'invalid_yaml': """---
title: "Unclosed quote
tags:
  - test
---
""",
        'empty': """---
---
""",
        'no_frontmatter': "# Just a heading\n\nNo frontmatter here."
    }


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """
    Reset environment variables for each test.

    This fixture runs automatically before each test.
    """
    # Remove API keys to prevent accidental API calls in tests
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
