"""
Build command - Build or rebuild the vault index database.

This module implements the build command which scans the entire vault
and creates/updates the vault.db SQLite database with comprehensive indexing.
"""

import sqlite3
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ...core import get_vault_root
from ...core.database import VaultDatabase
from ..common import is_text_file
from ..linker import Link, LinkExtractor
from ..scanner import FileInfo, FileScanner
from . import Command


class BuildCommand(Command):
    """Command to build or rebuild the vault index database."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the build command."""
        parser.add_argument(
            "--incremental",
            action="store_true",
            help="Only update files modified since last build (faster)",
        )
        parser.add_argument(
            "--force", action="store_true", help="Force full rebuild even if database exists"
        )
        parser.add_argument(
            "--no-hash",
            action="store_true",
            help="Skip content hashing (faster but no duplicate detection)",
        )
        parser.add_argument(
            "--max-hash-size",
            type=int,
            default=100,
            metavar="MB",
            help="Maximum file size to hash in MB (default: 100)",
        )

    def execute(self, args: Namespace) -> None:
        """Execute the build command to create/update vault index."""
        print("=" * 60)
        print("Building Vault Index Database")
        print("=" * 60)

        vault_root = get_vault_root()
        db = VaultDatabase()
        db_path = db.db_path

        # Check if incremental build is requested
        if args.incremental and not args.force:
            if not db.exists():
                print("\nIncremental build requested but database doesn't exist.")
                print("Performing full build instead...\n")
                args.incremental = False

        # Phase 1: Scan Files
        print("\n[Phase 1/5] Scanning vault files...")
        print(f"  Vault root: {vault_root}")
        print(f"  Hash files: {'No' if args.no_hash else 'Yes'}")

        if not args.no_hash:
            print(f"  Max hash size: {args.max_hash_size} MB")

        scanner = FileScanner(
            vault_root=vault_root, hash_files=not args.no_hash, max_hash_size_mb=args.max_hash_size
        )

        files = scanner.scan_vault()
        print(f"✓ Scanned {len(files)} files")

        # Phase 2: Extract Links
        print("\n[Phase 2/5] Extracting links from markdown files...")

        # Filter markdown files (compute extension from path)
        markdown_files = {path: info for path, info in files.items() if path.endswith(".md")}

        link_extractor = LinkExtractor(vault_root)
        link_extractor.build_filename_index(set(files.keys()))

        all_links = self._extract_all_links(markdown_files, link_extractor, vault_root)
        print(f"✓ Extracted {len(all_links)} links from {len(markdown_files)} markdown files")

        # Phase 3: Create Database
        print("\n[Phase 3/5] Creating database...")

        try:
            self._create_database(db_path, force=args.force)
            print(f"✓ Database initialized: {db_path}")
        except Exception as e:
            print(f"✗ Error creating database: {e}")
            return

        # Phase 4: Populate Tables
        print("\n[Phase 4/5] Populating database tables...")

        try:
            with db:  # Enter context manager to establish connection
                with db.transaction() as conn:
                    # Populate files table
                    self._populate_files_table(conn, files)
                    print(f"  ✓ Files table: {len(files)} entries")

                    # Populate tags and file_tags tables
                    tags_count = self._populate_tags_tables(conn, files)
                    print(f"  ✓ Tags table: {tags_count} unique tags")

                    # Populate links table
                    self._populate_links_table(conn, all_links)
                    print(f"  ✓ Links table: {len(all_links)} links")

                    # Update metadata
                    self._populate_metadata_table(conn, files, all_links, db.vault_root)
                    print("  ✓ Metadata table: statistics recorded")

                    # Transaction automatically commits on successful exit
                print("✓ All tables populated successfully")

        except Exception as e:
            # Transaction automatically rolled back on exception
            print(f"\n✗ Error populating database: {e}")
            print("All changes rolled back.")
            return

        # Phase 5: Optimize
        print("\n[Phase 5/5] Optimizing database...")

        try:
            # VACUUM and ANALYZE must run outside a transaction
            with db:
                conn = db._connection
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
            print("✓ Database optimized")
        except Exception as e:
            print(f"Warning: Optimization failed: {e}")

        # Print Summary
        print("\n" + "=" * 60)
        print("Build Complete!")
        print("=" * 60)
        self._print_summary(files, all_links, db.db_path)

    def _extract_all_links(
        self, markdown_files: Dict[str, FileInfo], link_extractor: LinkExtractor, vault_root: Path
    ) -> List[Link]:
        """Extract links from all markdown files."""
        all_links = []
        count = 0

        for relative_path, file_info in markdown_files.items():
            file_path = vault_root / relative_path

            if not is_text_file(file_path):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                links = link_extractor.extract_links(content, relative_path)
                all_links.extend(links)

                # Update link count in file_info
                file_info.link_count = len(links)

                count += 1
                if count % 50 == 0:
                    print(f"  Processed {count}/{len(markdown_files)} markdown files...")

            except (OSError, UnicodeDecodeError) as e:
                print(f"  Warning: Could not read {relative_path}: {e}")

        return all_links

    def _create_database(self, db_path: Path, force: bool = False) -> None:
        """
        Create database and schema.

        Uses centralized database connection management to ensure
        connections are properly closed.
        """
        # Remove existing database if force rebuild
        if force and db_path.exists():
            db_path.unlink()
            print("  Removed existing database")

        with VaultDatabase(vault_root=db_path.parent) as db_temp:
            conn = db_temp._connection
            cursor = conn.cursor()

            # Create tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    file_path TEXT PRIMARY KEY,
                    size_bytes INTEGER NOT NULL,
                    content_hash TEXT,
                    last_modified TEXT NOT NULL,
                    created TEXT,
                    has_frontmatter INTEGER DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    tag TEXT PRIMARY KEY
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_tags (
                    tag TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    PRIMARY KEY (tag, file_path),
                    FOREIGN KEY (tag) REFERENCES tags(tag) ON DELETE CASCADE,
                    FOREIGN KEY (file_path) REFERENCES files(file_path) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT NOT NULL,
                    target_file TEXT,
                    link_type TEXT NOT NULL,
                    link_text TEXT,
                    line_number INTEGER,
                    FOREIGN KEY (source_file) REFERENCES files(file_path) ON DELETE CASCADE,
                    FOREIGN KEY (target_file) REFERENCES files(file_path) ON DELETE SET NULL
                )
            """)

            # Create normalized views (3NF: compute derived values)
            self._create_views(cursor)

            # Create indexes
            self._create_indexes(cursor)

            conn.commit()
            # Connection automatically closed on context exit

    def _create_views(self, cursor: sqlite3.Cursor) -> None:
        """
        Create normalized views for convenient querying of derived values.

        These views provide backward compatibility and convenience while
        maintaining strict 3NF in the base tables.
        """
        # View: tags_with_counts - tags with computed file_count
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS tags_with_counts AS
            SELECT
                ft.tag,
                COUNT(*) as file_count
            FROM file_tags ft
            GROUP BY ft.tag
        """)

        # View: links_extended - links with computed is_resolved flag
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS links_extended AS
            SELECT
                l.id,
                l.source_file,
                l.target_file,
                l.link_type,
                l.link_text,
                l.line_number,
                CASE WHEN l.target_file IS NOT NULL THEN 1 ELSE 0 END as is_resolved
            FROM links l
        """)

    def _create_indexes(self, cursor: sqlite3.Cursor) -> None:
        """Create performance indexes."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash)",
            "CREATE INDEX IF NOT EXISTS idx_files_modified ON files(last_modified DESC)",
            "CREATE INDEX IF NOT EXISTS idx_file_tags_tag ON file_tags(tag)",
            "CREATE INDEX IF NOT EXISTS idx_file_tags_file ON file_tags(file_path)",
            "CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_file)",
            "CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_file)",
            "CREATE INDEX IF NOT EXISTS idx_links_type ON links(link_type)",
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

    def _populate_files_table(self, conn: sqlite3.Connection, files: Dict[str, FileInfo]) -> None:
        """Populate the files table (3NF normalized - no derived columns)."""
        cursor = conn.cursor()

        file_data = [
            (
                info.file_path,
                info.size_bytes,
                info.content_hash,
                info.last_modified,
                info.created,
                1 if info.has_frontmatter else 0,
            )
            for info in files.values()
        ]

        cursor.executemany(
            """
            INSERT OR REPLACE INTO files
            (file_path, size_bytes, content_hash, last_modified, created, has_frontmatter)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            file_data,
        )

    def _populate_tags_tables(self, conn: sqlite3.Connection, files: Dict[str, FileInfo]) -> int:
        """Populate tags and file_tags tables."""
        cursor = conn.cursor()

        # Collect all tags and their file associations
        tag_to_files = defaultdict(list)

        for file_path, file_info in files.items():
            for tag in file_info.tags:
                tag_to_files[tag].append(file_path)

        # Insert into tags table (3NF normalized - no file_count)
        tags_data = [(tag,) for tag in tag_to_files.keys()]
        cursor.executemany("INSERT OR REPLACE INTO tags (tag) VALUES (?)", tags_data)

        # Insert into file_tags table
        file_tags_data = []
        for tag, file_paths in tag_to_files.items():
            for file_path in file_paths:
                file_tags_data.append((tag, file_path))

        cursor.executemany(
            "INSERT OR REPLACE INTO file_tags (tag, file_path) VALUES (?, ?)", file_tags_data
        )

        return len(tag_to_files)

    def _populate_links_table(self, conn: sqlite3.Connection, links: List[Link]) -> None:
        """Populate the links table (3NF normalized - no is_resolved)."""
        cursor = conn.cursor()

        # Get all valid file paths from files table
        cursor.execute("SELECT file_path FROM files")
        valid_files = {row[0] for row in cursor.fetchall()}

        links_data = []
        for link in links:
            # Only include target_file if it exists in files table
            # Otherwise set to NULL (broken link to file outside vault or in ignored dir)
            target_file = link.target_file if link.target_file in valid_files else None

            links_data.append(
                (link.source_file, target_file, link.link_type, link.link_text, link.line_number)
            )

        cursor.executemany(
            """
            INSERT INTO links
            (source_file, target_file, link_type, link_text, line_number)
            VALUES (?, ?, ?, ?, ?)
        """,
            links_data,
        )

    def _populate_metadata_table(
        self,
        conn: sqlite3.Connection,
        files: Dict[str, FileInfo],
        links: List[Link],
        vault_root: Path,
    ) -> None:
        """Populate the metadata table with statistics."""
        cursor = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Count markdown files (compute extension from file_path)
        md_files = sum(1 for f in files.values() if f.file_path.endswith(".md"))

        # Count unique tags
        cursor.execute("SELECT COUNT(*) FROM tags")
        total_tags = cursor.fetchone()[0]

        metadata = {
            "generated": now,
            "vault_path": str(vault_root),
            "database_version": "1.0.0",
            "total_files": str(len(files)),
            "total_md_files": str(md_files),
            "total_tags": str(total_tags),
            "total_links": str(len(links)),
        }

        cursor.executemany(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", list(metadata.items())
        )

    def _print_summary(self, files: Dict[str, FileInfo], links: List[Link], db_path: Path) -> None:
        """Print build summary statistics (3NF normalized)."""
        # Compute extension from file_path
        md_files = sum(1 for f in files.values() if f.file_path.endswith(".md"))
        total_size = sum(f.size_bytes for f in files.values())
        hashed_files = sum(1 for f in files.values() if f.content_hash)

        print(f"\nDatabase: {db_path}")
        print(f"  Size: {db_path.stat().st_size / 1024:.1f} KB")
        print("\nFiles:")
        print(f"  Total: {len(files)}")
        print(f"  Markdown: {md_files}")
        print(f"  Total size: {total_size / (1024 * 1024):.1f} MB")
        print(f"  Hashed: {hashed_files}")
        print("\nLinks:")
        print(f"  Total: {len(links)}")
        # Compute is_resolved from target_file IS NOT NULL
        resolved = sum(1 for link in links if link.target_file is not None)
        print(f"  Resolved: {resolved}")
        print(f"  Broken: {len(links) - resolved}")
        print("")
