"""
Clean command - Consolidated tag cleanup operations.

This module implements the clean command which provides subcommands for
removing invalid tags and normalizing tag casing.
"""

import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from . import Command


class CleanCommand(Command):
    """Command to clean and standardize tags."""

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
        from .clean_invalid import CleanInvalidCommand
        from .clean_normalize import CleanNormalizeCommand

        # Invalid subcommand
        invalid_parser = subparsers.add_parser(
            'invalid',
            help='Remove tags that don\'t conform to Obsidian rules',
            formatter_class=RawDescriptionHelpFormatter,
            description='Remove tags that don\'t conform to Obsidian\'s tag validation rules.'
        )
        CleanInvalidCommand.configure_parser(invalid_parser)

        # Normalize subcommand
        normalize_parser = subparsers.add_parser(
            'normalize',
            help='Normalize tag casing to lowercase',
            formatter_class=RawDescriptionHelpFormatter,
            description='Convert all tags to lowercase for consistency across the vault.'
        )
        CleanNormalizeCommand.configure_parser(normalize_parser)

    def execute(self, args: Namespace) -> None:
        """Execute the appropriate clean subcommand."""
        # Import subcommand classes
        from .clean_invalid import CleanInvalidCommand
        from .clean_normalize import CleanNormalizeCommand

        # Map subcommands to their command classes
        subcommand_map = {
            'invalid': CleanInvalidCommand,
            'normalize': CleanNormalizeCommand,
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
