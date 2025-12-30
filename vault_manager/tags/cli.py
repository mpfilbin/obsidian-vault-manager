#!/usr/bin/env python3
"""
Tag Management Tool for Obsidian Vault - CLI Entry Point

This module provides the command-line interface for tag management operations
using argparse for argument parsing and the command pattern for dispatch.
"""

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from .commands import Command
from .commands.missing import MissingCommand
from .commands.tags_inventory import TagsInventoryCommand
from .commands.add import AddCommand
from .commands.clean import CleanCommand
from .commands.query import QueryCommand
from .commands.purge import PurgeCommand
from .commands.rename import RenameCommand
from .commands.similar import SimilarCommand
from .commands.visualize import VisualizeCommand
from .commands.reorganize import ReorganizeCommand


def create_parser() -> ArgumentParser:
    """
    Create and configure the argument parser with subcommands.

    Returns:
        Configured ArgumentParser instance
    """
    parser = ArgumentParser(
        prog='vault tags',
        description='Tag Management Tool for Obsidian Vault',
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vault tags missing
  vault tags update
  vault tags add Personal --dry-run
  vault tags add "Personal/Software Development" --overwrite
  vault tags clean . --dry-run
  vault tags clean Personal
  vault tags query --stats
  vault tags query --most-used 10

The script will:
- Scan all .md files in the vault
- Ignore files in .obsidian and Excalidraw/Scripts directories
- Extract tags from YAML frontmatter only
- For .excalidraw.md files, ignore inline tags (only check frontmatter)
        """
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        help='Available commands'
    )

    # Missing command (was: tagless)
    missing_parser = subparsers.add_parser(
        'missing',
        help='Generate report of files missing tags'
    )
    MissingCommand.configure_parser(missing_parser)

    # Update command (was: tags)
    update_parser = subparsers.add_parser(
        'update',
        help='Update vault index with tag data'
    )
    TagsInventoryCommand.configure_parser(update_parser)

    # Add command
    add_parser = subparsers.add_parser(
        'add',
        help='Use AI to generate and add tags to notes'
    )
    AddCommand.configure_parser(add_parser)

    # Clean command
    clean_parser = subparsers.add_parser(
        'clean',
        help='Remove invalid tags that don\'t conform to Obsidian rules'
    )
    CleanCommand.configure_parser(clean_parser)

    # Query command
    query_parser = subparsers.add_parser(
        'query',
        help='Query the tag database with SQL or predefined queries'
    )
    QueryCommand.configure_parser(query_parser)

    # Purge command
    purge_parser = subparsers.add_parser(
        'purge',
        help='Remove specified tags from all files and database'
    )
    PurgeCommand.configure_parser(purge_parser)

    # Rename command
    rename_parser = subparsers.add_parser(
        'rename',
        help='Rename a tag across all files and database'
    )
    RenameCommand.configure_parser(rename_parser)

    # Similar command
    similar_parser = subparsers.add_parser(
        'similar',
        help='Find similar tags for consolidation'
    )
    SimilarCommand.configure_parser(similar_parser)

    # Visualize command
    visualize_parser = subparsers.add_parser(
        'visualize',
        help='Generate Mermaid diagram of tag hierarchy'
    )
    VisualizeCommand.configure_parser(visualize_parser)

    # Reorganize command
    reorganize_parser = subparsers.add_parser(
        'reorganize',
        help='Suggest hierarchical reorganization of flat tags'
    )
    ReorganizeCommand.configure_parser(reorganize_parser)

    return parser


def main() -> None:
    """
    Main entry point for the tag management tool.

    Parses command-line arguments and dispatches to the appropriate command.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Map command names to command classes
    command_map = {
        'missing': MissingCommand,  # Renamed from 'tagless'
        'update': TagsInventoryCommand,  # Renamed from 'tags'
        'add': AddCommand,
        'clean': CleanCommand,
        'query': QueryCommand,
        'purge': PurgeCommand,
        'rename': RenameCommand,
        'similar': SimilarCommand,
        'visualize': VisualizeCommand,
        'reorganize': ReorganizeCommand,
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
        sys.exit(1)


if __name__ == '__main__':
    main()
