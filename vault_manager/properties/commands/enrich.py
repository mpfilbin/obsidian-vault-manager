"""
Enrich command - Consolidated content enhancement operations.

This module implements the enrich command which provides subcommands for
adding AI-generated summaries and finding related notes.
"""

import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from . import Command


class EnrichCommand(Command):
    """Command to enrich notes with AI-generated content and metadata."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the enrich command."""
        # Create subparsers for enrich subcommands
        subparsers = parser.add_subparsers(
            dest='enrich_subcommand',
            help='Content enhancement operation to perform',
            required=True
        )

        # Import subcommand classes
        from .summarize import SummarizeCommand
        from .relate import RelateCommand

        # Summaries subcommand
        summaries_parser = subparsers.add_parser(
            'summaries',
            help='Generate and add AI summary properties to notes',
            formatter_class=RawDescriptionHelpFormatter,
            description='Use Claude API to generate concise 2-4 sentence summaries and add them to frontmatter.'
        )
        SummarizeCommand.configure_parser(summaries_parser)

        # Related subcommand
        related_parser = subparsers.add_parser(
            'related',
            help='Analyze and add related note links based on similarity',
            formatter_class=RawDescriptionHelpFormatter,
            description='Analyze notes using hybrid similarity algorithm and add related property with wiki-links.'
        )
        RelateCommand.configure_parser(related_parser)

    def execute(self, args: Namespace) -> None:
        """Execute the appropriate enrich subcommand."""
        # Import subcommand classes
        from .summarize import SummarizeCommand
        from .relate import RelateCommand

        # Map subcommands to their command classes
        subcommand_map = {
            'summaries': SummarizeCommand,
            'related': RelateCommand,
        }

        # Get the appropriate command class
        subcommand = args.enrich_subcommand
        if subcommand not in subcommand_map:
            print(f"Error: Unknown enrich subcommand: {subcommand}")
            sys.exit(1)

        # Execute the subcommand
        command_class = subcommand_map[subcommand]
        command = command_class()
        command.execute(args)
