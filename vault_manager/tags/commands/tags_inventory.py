"""
Tags inventory command - Update vault tag index.

This module implements the tags command which calls the index build command
to update vault.db. All tag data is stored in the vault.db SQLite database.
"""

import sys
from argparse import ArgumentParser, Namespace

from vault_manager.core.database import VaultDatabase

from . import Command


class TagsInventoryCommand(Command):
    """Command to update the vault tag index in vault.db."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the tags command."""
        pass  # No arguments needed

    def execute(self, args: Namespace) -> None:
        """Execute the tags inventory command."""
        db = VaultDatabase()
        vault_root = db.vault_root
        old_db = vault_root / 'vault-tags.db'

        # Show migration notice if old database exists
        if old_db.exists():
            print("⚠️  Migration Notice:")
            print("   vault-tags.db is deprecated and will be removed.")
            print("   This command now uses vault.db for all tag data.")
            print("   You can safely delete vault-tags.db.")
            print()

        print("Building vault index...")

        # Run index build to update vault.db
        from vault_manager.index.cli import main as index_main

        # Save original argv
        original_argv = sys.argv

        try:
            # Call index build
            sys.argv = ['index', 'build']
            index_main()
        finally:
            # Restore original argv
            sys.argv = original_argv

        # Verify database was created
        if not db.exists():
            print("\nError: vault.db not found. Index build may have failed.")
            sys.exit(1)

        print("\nDone!")
        print(f"\nTag data is now available in: {db.db_path}")
        print("\nQuery the database with:")
        print("  vault tags query --stats")
        print("  vault tags query --most-used 10")
        print("  vault tags query --help")
