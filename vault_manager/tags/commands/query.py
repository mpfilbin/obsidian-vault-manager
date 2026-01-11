"""
Query command - Query tag database with SQL.

This module implements the query command which allows querying the vault.db
SQLite database with predefined queries or custom SQL.
"""

import sys
from argparse import ArgumentParser, Namespace
from typing import List

from vault_manager.core.database import VaultDatabase

from . import Command


class QueryCommand(Command):
    """Command to query the tag database."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the query command."""
        parser.add_argument(
            '--sql',
            type=str,
            help='Execute custom SQL query'
        )
        parser.add_argument(
            '--most-used',
            type=int,
            metavar='N',
            help='Show N most used tags'
        )
        parser.add_argument(
            '--least-used',
            type=int,
            metavar='N',
            help='Show N least used tags'
        )
        parser.add_argument(
            '--files-with',
            nargs='+',
            metavar='TAG',
            help='Show files tagged with ALL specified tags'
        )
        parser.add_argument(
            '--files-with-any',
            nargs='+',
            metavar='TAG',
            help='Show files tagged with ANY of the specified tags'
        )
        parser.add_argument(
            '--tag-info',
            type=str,
            metavar='TAG',
            help='Show detailed information about a specific tag'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show database statistics'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the query command."""
        with VaultDatabase() as db:
            db.require_exists("tags query")

            # Determine which query to run
            if args.sql:
                self._execute_custom_sql(db, args.sql)
            elif args.most_used is not None:
                self._query_most_used(db, args.most_used)
            elif args.least_used is not None:
                self._query_least_used(db, args.least_used)
            elif args.files_with:
                self._query_files_with_all_tags(db, args.files_with)
            elif args.files_with_any:
                self._query_files_with_any_tags(db, args.files_with_any)
            elif args.tag_info:
                self._query_tag_info(db, args.tag_info)
            elif args.stats:
                self._query_stats(db)
            else:
                print("Error: No query specified")
                print("Use --help to see available query options")
                sys.exit(1)

    def _execute_custom_sql(self, db: VaultDatabase, sql: str) -> None:
        """Execute custom SQL query and display results."""
        print(f"Executing SQL query:\n{sql}\n")

        try:
            col_names, results = db.query_with_columns(sql)

            if not results:
                print("No results")
            else:
                # Print header
                print(" | ".join(col_names))
                print("-" * (sum(len(name) for name in col_names) + 3 * (len(col_names) - 1)))

                # Print rows
                for row in results:
                    print(" | ".join(str(val) for val in row))

                print(f"\n{len(results)} row{'s' if len(results) != 1 else ''} returned")

        except Exception as e:
            print(f"SQL Error: {e}")
            sys.exit(1)

    def _query_most_used(self, db: VaultDatabase, n: int) -> None:
        """Query for N most used tags (3NF: compute file_count from file_tags)."""
        print(f"Top {n} most used tags:\n")

        results = db.query('''
            SELECT ft.tag, COUNT(*) as file_count
            FROM file_tags ft
            GROUP BY ft.tag
            ORDER BY file_count DESC
            LIMIT ?
        ''', (n,))

        if not results:
            print("No tags found")
        else:
            # Calculate padding for alignment
            max_tag_len = max(len(tag) for tag, _ in results)

            for i, (tag, count) in enumerate(results, 1):
                print(f"{i:2d}. {tag:<{max_tag_len}} : {count:4d} files")

    def _query_least_used(self, db: VaultDatabase, n: int) -> None:
        """Query for N least used tags (3NF: compute file_count from file_tags)."""
        print(f"Top {n} least used tags:\n")

        results = db.query('''
            SELECT ft.tag, COUNT(*) as file_count
            FROM file_tags ft
            GROUP BY ft.tag
            ORDER BY file_count
            LIMIT ?
        ''', (n,))

        if not results:
            print("No tags found")
        else:
            # Calculate padding for alignment
            max_tag_len = max(len(tag) for tag, _ in results)

            for i, (tag, count) in enumerate(results, 1):
                print(f"{i:2d}. {tag:<{max_tag_len}} : {count:4d} file{'s' if count != 1 else ''}")

    def _query_files_with_all_tags(self, db: VaultDatabase, tags: List[str]) -> None:
        """Query for files tagged with ALL specified tags."""
        print(f"Files tagged with ALL of: {', '.join(tags)}\n")

        # Build parameterized query using GROUP BY and HAVING
        # This finds files that have all the specified tags
        placeholders = ','.join('?' * len(tags))
        query = f'''
            SELECT file_path
            FROM file_tags
            WHERE tag IN ({placeholders})
            GROUP BY file_path
            HAVING COUNT(DISTINCT tag) = ?
            ORDER BY file_path
        '''

        try:
            # Parameters: all tags + count of tags
            params = tuple(tags) + (len(tags),)
            results = db.query(query, params)

            if not results:
                print(f"No files found with all tags: {', '.join(tags)}")
            else:
                for file_path, in results:
                    print(f"- [[{file_path[:-3] if file_path.endswith('.md') else file_path}]]")

                print(f"\n{len(results)} file{'s' if len(results) != 1 else ''} found")

        except Exception as e:
            print(f"SQL Error: {e}")
            sys.exit(1)

    def _query_files_with_any_tags(self, db: VaultDatabase, tags: List[str]) -> None:
        """Query for files tagged with ANY of the specified tags."""
        print(f"Files tagged with ANY of: {', '.join(tags)}\n")

        # Build query with IN clause
        placeholders = ','.join('?' * len(tags))
        query = f'''
            SELECT DISTINCT file_path
            FROM file_tags
            WHERE tag IN ({placeholders})
            ORDER BY file_path
        '''

        try:
            results = db.query(query, tuple(tags))

            if not results:
                print(f"No files found with any of: {', '.join(tags)}")
            else:
                for file_path, in results:
                    print(f"- [[{file_path[:-3] if file_path.endswith('.md') else file_path}]]")

                print(f"\n{len(results)} file{'s' if len(results) != 1 else ''} found")

        except Exception as e:
            print(f"SQL Error: {e}")
            sys.exit(1)

    def _query_tag_info(self, db: VaultDatabase, tag: str) -> None:
        """Query detailed information about a specific tag (3NF: compute file_count)."""
        print(f"Tag: {tag}\n")

        # Get tag info (3NF: compute file_count from file_tags)
        result = db.query_single('''
            SELECT COUNT(*) as file_count
            FROM file_tags
            WHERE tag = ?
        ''', (tag,))

        if len(result) == 0 or result[0] == 0:
            print(f"Tag '{tag}' not found in database")
            return

        file_count = result[0]
        print(f"Files: {file_count}")

        # Get files with this tag
        files = db.query('''
            SELECT file_path
            FROM file_tags
            WHERE tag = ?
            ORDER BY file_path
        ''', (tag,))

        print(f"\nFiles tagged with '{tag}':\n")
        for file_path, in files:
            print(f"- [[{file_path[:-3] if file_path.endswith('.md') else file_path}]]")

    def _query_stats(self, db: VaultDatabase) -> None:
        """Query database statistics."""
        print("Tag Database Statistics\n")
        print("=" * 60)

        # Get metadata
        metadata_rows = db.query('SELECT key, value FROM metadata')
        metadata = dict(metadata_rows)

        print(f"Generated: {metadata.get('generated', 'Unknown')}")
        print(f"Vault: {metadata.get('vault_path', 'Unknown')}")
        print()

        print("Files:")
        print(f"  Total markdown files: {metadata.get('total_files', 'Unknown')}")
        print(f"  Files with tags: {metadata.get('total_tagged_files', 'Unknown')}")
        print()

        print("Tags:")
        print(f"  Unique tags: {metadata.get('total_tags', 'Unknown')}")
        print(f"  Total tag instances: {metadata.get('total_tag_instances', 'Unknown')}")

        # Calculate averages

        total_tagged_files = int(metadata.get('total_tagged_files', 0))
        total_tag_instances = int(metadata.get('total_tag_instances', 0))

        if total_tagged_files > 0:
            avg_tags = total_tag_instances / total_tagged_files
            print(f"  Average tags per file: {avg_tags:.2f}")

        # Tag distribution (3NF: compute file_count from file_tags)
        print("\nTag Distribution:")

        single_use = db.query_single('''
            SELECT COUNT(*)
            FROM (
                SELECT tag, COUNT(*) as file_count
                FROM file_tags
                GROUP BY tag
                HAVING file_count = 1
            )
        ''')[0]

        low_use = db.query_single('''
            SELECT COUNT(*)
            FROM (
                SELECT tag, COUNT(*) as file_count
                FROM file_tags
                GROUP BY tag
                HAVING file_count BETWEEN 2 AND 4
            )
        ''')[0]

        medium_use = db.query_single('''
            SELECT COUNT(*)
            FROM (
                SELECT tag, COUNT(*) as file_count
                FROM file_tags
                GROUP BY tag
                HAVING file_count BETWEEN 5 AND 9
            )
        ''')[0]

        high_use = db.query_single('''
            SELECT COUNT(*)
            FROM (
                SELECT tag, COUNT(*) as file_count
                FROM file_tags
                GROUP BY tag
                HAVING file_count >= 10
            )
        ''')[0]

        print(f"  Single-use (1 file): {single_use}")
        print(f"  Low-use (2-4 files): {low_use}")
        print(f"  Medium-use (5-9 files): {medium_use}")
        print(f"  High-use (10+ files): {high_use}")
