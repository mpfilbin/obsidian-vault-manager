#!/usr/bin/env python3
"""
Image Management Tool for Obsidian Vault - CLI Entry Point

This module provides the command-line interface for image management operations
using argparse for argument parsing and the command pattern for dispatch.
"""

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from .commands import Command
from .commands.find import FindCommand
from .commands.cleanup import CleanupCommand
from .commands.remove_alt import RemoveAltCommand
from .commands.broken import BrokenCommand


def create_parser() -> ArgumentParser:
    """
    Create and configure the argument parser with subcommands.

    Returns:
        Configured ArgumentParser instance
    """
    parser = ArgumentParser(
        prog='vault images',
        description='Image Management Tool for Obsidian Vault',
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vault images find
  vault images broken
  vault images cleanup
  vault images remove-alt Personal --dry-run
  vault images remove-alt "Personal/Software Development"
  vault images remove-alt .  # Process entire vault

The script will:
- Scan for image files (.png, .jpg, .jpeg, .gif, .svg, .webp, .bmp, .ico)
- Ignore files in .obsidian, .trash, and Excalidraw directories
- Generate reports and perform cleanup operations
        """
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        help='Available commands'
    )

    # Find command
    find_parser = subparsers.add_parser(
        'find',
        help='Find images not referenced in any markdown file'
    )
    FindCommand.configure_parser(find_parser)

    # Broken command
    broken_parser = subparsers.add_parser(
        'broken',
        help='Find notes with missing image references'
    )
    BrokenCommand.configure_parser(broken_parser)

    # Cleanup command
    cleanup_parser = subparsers.add_parser(
        'cleanup',
        help='Move checked-off orphaned images to .trash directory'
    )
    CleanupCommand.configure_parser(cleanup_parser)

    # Remove-alt command
    remove_alt_parser = subparsers.add_parser(
        'remove-alt',
        help='Remove alt text from wiki-link image embeds'
    )
    RemoveAltCommand.configure_parser(remove_alt_parser)

    return parser


def main() -> None:
    """
    Main entry point for the image management tool.

    Parses command-line arguments and dispatches to the appropriate command.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Map command names to command classes
    command_map = {
        'find': FindCommand,
        'broken': BrokenCommand,
        'cleanup': CleanupCommand,
        'remove-alt': RemoveAltCommand,
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
