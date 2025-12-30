"""
Vault Index Package

Provides comprehensive indexing for Obsidian vault with SQLite database backend.

The vault.db database tracks:
- All files in the vault (markdown, images, PDFs, etc.)
- Tags and file-tag relationships
- Links between files (wiki-links, markdown links, image embeds)
- Duplicate files (content-based deduplication via SHA-256)
- Orphaned files (no incoming links)
- Broken links

Commands:
    build    - Build or rebuild the vault index database
    query    - Query the database with SQL or predefined queries
    stats    - Show vault statistics and database metrics
    check    - Check database integrity and find issues

Usage:
    python -m Library.index build              # Full rebuild
    python -m Library.index build --incremental  # Update changed files
    python -m Library.index query --orphans     # Find orphaned files
    python -m Library.index stats               # Show statistics

Database:
    vault.db - SQLite database in vault root

Tables:
    - metadata: Vault statistics and generation info
    - files: All files with metadata, hashes, timestamps
    - tags: Unique tags across vault
    - file_tags: Many-to-many tag-file relationships
    - links: File-to-file references with type tracking
    - duplicates: Files with identical content hashes
"""

__version__ = '1.0.0'
__author__ = 'Michael Filbin'
__database__ = 'vault.db'
