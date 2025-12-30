#!/usr/bin/env python3
"""
Vault Index Tool for Obsidian Vault - CLI Entry Point

This module provides the command-line interface for vault indexing operations
using argparse for argument parsing and the command pattern for dispatch.
"""

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from .commands import Command
from .commands.build import BuildCommand
from .commands.duplicates import DuplicatesCommand
from .commands.rename import RenameCommand
from .commands.broken_links import BrokenLinksCommand


def create_parser() -> ArgumentParser:
    """
    Create and configure the argument parser with subcommands.

    Returns:
        Configured ArgumentParser instance
    """
    parser = ArgumentParser(
        prog='vault index',
        description='Vault Index Tool for Obsidian Vault',
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build full index
  vault index build

  # Incremental update (only changed files)
  vault index build --incremental

  # Build without content hashing (faster)
  vault index build --no-hash

  # Force full rebuild
  vault index build --force

  # Find duplicate files
  vault index duplicates find

  # Cleanup checked duplicates
  vault index duplicates cleanup

  # Find files with mangled names (underscores, plus signs)
  vault index rename find

  # Rename files and update links
  vault index rename apply

  # Find broken wiki-links
  vault index broken-links

The vault.db database tracks:
- All files (markdown, images, PDFs, etc.)
- Tags and file-tag relationships
- Links between files (wiki-links, markdown links, images)
- Duplicate files (content-based via SHA-256 hashes)
- Orphaned files (no incoming links)
- Broken links

Database location: vault.db (in vault root)
        """
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        help='Available commands'
    )

    # Build command
    build_parser = subparsers.add_parser(
        'build',
        help='Build or rebuild the vault index database'
    )
    BuildCommand.configure_parser(build_parser)

    # Duplicates command
    duplicates_parser = subparsers.add_parser(
        'duplicates',
        help='Find and cleanup duplicate files'
    )
    DuplicatesCommand.configure_parser(duplicates_parser)

    # Rename command
    rename_parser = subparsers.add_parser(
        'rename',
        help='Fix mangled filenames (underscores, plus signs)'
    )
    RenameCommand.configure_parser(rename_parser)

    # Broken links command
    broken_links_parser = subparsers.add_parser(
        'broken-links',
        help='Find and report broken wiki-links'
    )
    BrokenLinksCommand.configure_parser(broken_links_parser)

    # TODO: Add query, stats, check commands in future phases

    return parser


def main() -> None:
    """
    Main entry point for the vault index tool.

    Parses command-line arguments and dispatches to the appropriate command.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Map command names to command classes
    command_map = {
        'build': BuildCommand,
        'duplicates': DuplicatesCommand,
        'rename': RenameCommand,
        'broken-links': BrokenLinksCommand,
        # TODO: Add other commands (query, stats, check)
    }

    # Get the command class
    command_class = command_map.get(args.command)

    if command_class is None:
        print(f"Error: Unknown command '{args.command}'")
        parser.print_help()
        sys.exit(1)

    # Instantiate and execute the command
    try:
        command = command_class()
        command.execute(args)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
