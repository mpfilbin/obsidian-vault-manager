#!/usr/bin/env python3
"""
Property Management Tool for Obsidian Vault - CLI Entry Point

This module provides the command-line interface for property management operations
using argparse for argument parsing and the command pattern for dispatch.
"""

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter


def create_parser() -> ArgumentParser:
    """
    Create and configure the argument parser with subcommands.

    Returns:
        Configured ArgumentParser instance
    """
    parser = ArgumentParser(
        prog='vault properties',
        description='Property Management Tool for Obsidian Vault',
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vault properties enrich summaries Personal --dry-run
  vault properties enrich related Personal --max-related=3
  vault properties enrich related "Personal/Note.md" --dry-run
  vault properties clean normalize Personal --dry-run
  vault properties clean deduplicate . --dry-run
  vault properties clean remove author Personal --dry-run
  vault properties validate .
  vault properties repair --dry-run
  vault properties repair --backup
  vault properties init . --dry-run
  vault properties init Personal

The script will:
- Recursively process all .md files in the specified directory
- Skip files in .obsidian, .trash, .backup, Excalidraw, and Calendar directories
- Skip .excalidraw.md files
- Generate content, analyze relationships, or audit frontmatter
        """
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        help='Available commands'
    )

    # Import commands here to avoid circular imports
    from .commands.enrich import EnrichCommand
    from .commands.clean import CleanCommand
    from .commands.validate import ValidateCommand
    from .commands.repair import RepairCommand
    from .commands.set import SetCommand
    from .commands.audit import AuditCommand
    from .commands.init import InitCommand

    # Enrich command (consolidates summaries and related notes)
    enrich_parser = subparsers.add_parser(
        'enrich',
        help='Enrich notes with AI-generated content and metadata'
    )
    EnrichCommand.configure_parser(enrich_parser)

    # Clean command (consolidates normalize, deduplicate, remove)
    clean_parser = subparsers.add_parser(
        'clean',
        help='Clean and standardize frontmatter properties'
    )
    CleanCommand.configure_parser(clean_parser)

    # Validate command (includes missing frontmatter check)
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate YAML frontmatter structure and content'
    )
    ValidateCommand.configure_parser(validate_parser)

    # Repair command
    repair_parser = subparsers.add_parser(
        'repair',
        help='Repair frontmatter issues from validation report'
    )
    RepairCommand.configure_parser(repair_parser)

    # Set command
    set_parser = subparsers.add_parser(
        'set',
        help='Set/update a property across multiple files'
    )
    SetCommand.configure_parser(set_parser)

    # Audit command
    audit_parser = subparsers.add_parser(
        'audit',
        help='Generate comprehensive property usage report'
    )
    AuditCommand.configure_parser(audit_parser)

    # Init command
    init_parser = subparsers.add_parser(
        'init',
        help='Initialize YAML frontmatter in files that have none'
    )
    InitCommand.configure_parser(init_parser)

    return parser


def main() -> None:
    """
    Main entry point for the property management tool.

    Parses command-line arguments and dispatches to the appropriate command.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Import commands
    from .commands.enrich import EnrichCommand
    from .commands.clean import CleanCommand
    from .commands.validate import ValidateCommand
    from .commands.repair import RepairCommand
    from .commands.set import SetCommand
    from .commands.audit import AuditCommand
    from .commands.init import InitCommand

    # Map command names to command classes
    command_map = {
        'enrich': EnrichCommand,
        'clean': CleanCommand,
        'validate': ValidateCommand,
        'repair': RepairCommand,
        'set': SetCommand,
        'audit': AuditCommand,
        'init': InitCommand,
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
