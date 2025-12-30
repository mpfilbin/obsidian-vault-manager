"""
Clean command - Consolidated frontmatter cleanup operations.

This module implements the clean command which provides subcommands for
normalizing, deduplicating, and removing properties from frontmatter.
"""

import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from . import Command


class CleanCommand(Command):
    """Command to clean and standardize frontmatter properties."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the clean command."""
        # Create subparsers for clean subcommands
        subparsers = parser.add_subparsers(
            dest='clean_subcommand',
            help='Cleanup operation to perform',
            required=True
        )

        # Import subcommand classes
        from .normalize import NormalizeCommand
        from .deduplicate import DeduplicateCommand
        from .remove import RemoveCommand

        # Normalize subcommand
        normalize_parser = subparsers.add_parser(
            'normalize',
            help='Standardize frontmatter properties across notes',
            formatter_class=RawDescriptionHelpFormatter,
            description='Standardize frontmatter properties by removing, renaming, and reordering properties.'
        )
        NormalizeCommand.configure_parser(normalize_parser)

        # Deduplicate subcommand
        deduplicate_parser = subparsers.add_parser(
            'deduplicate',
            help='Remove duplicate frontmatter properties',
            formatter_class=RawDescriptionHelpFormatter,
            description='Remove duplicate property keys from frontmatter, keeping only the last occurrence.'
        )
        DeduplicateCommand.configure_parser(deduplicate_parser)

        # Remove subcommand
        remove_parser = subparsers.add_parser(
            'remove',
            help='Remove a specific property from frontmatter',
            formatter_class=RawDescriptionHelpFormatter,
            description='Remove a specified property from YAML frontmatter across all notes.'
        )
        RemoveCommand.configure_parser(remove_parser)

    def execute(self, args: Namespace) -> None:
        """Execute the appropriate clean subcommand."""
        # Import subcommand classes
        from .normalize import NormalizeCommand
        from .deduplicate import DeduplicateCommand
        from .remove import RemoveCommand

        # Map subcommands to their command classes
        subcommand_map = {
            'normalize': NormalizeCommand,
            'deduplicate': DeduplicateCommand,
            'remove': RemoveCommand,
        }

        # Get the appropriate command class
        subcommand = args.clean_subcommand
        if subcommand not in subcommand_map:
            print(f"Error: Unknown clean subcommand: {subcommand}")
            sys.exit(1)

        # Execute the subcommand
        command_class = subcommand_map[subcommand]
        command = command_class()
        command.execute(args)
