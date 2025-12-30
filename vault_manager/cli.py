#!/usr/bin/env python3
"""
Unified Vault Management CLI

This module provides the top-level command-line interface for all vault
management operations. It delegates to domain-specific CLI modules using
the domain delegation pattern.

Command Structure:
    vault <domain> <command> [args]

Domains:
    tags       - Tag management and validation
    images     - Image organization and cleanup
    properties - Frontmatter properties management
    index      - Vault indexing and link resolution
"""

import sys
import traceback
import importlib
from argparse import ArgumentParser, RawDescriptionHelpFormatter


def create_parser() -> ArgumentParser:
    """
    Create and configure the top-level argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = ArgumentParser(
        prog='vault',
        description='Unified Vault Management CLI for Obsidian',
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Specify vault path
  vault --vault-path ~/Documents/MyVault tags missing
  vault -v ~/Documents/MyVault tags query --stats

  # Tag management
  vault tags missing              # Find notes without tags
  vault tags update               # Update vault index
  vault tags add Personal         # AI-generate tags
  vault tags clean . --dry-run    # Remove invalid tags
  vault tags query --stats        # Tag statistics

  # Image management
  vault images find               # Find orphaned images
  vault images cleanup            # Remove checked orphaned images
  vault images remove-alt .       # Remove image alt text

  # Frontmatter properties
  vault properties enrich summaries Personal --dry-run
  vault properties enrich related Personal
  vault properties clean normalize . --dry-run
  vault properties clean deduplicate .
  vault properties clean remove author .
  vault properties validate       # Validate frontmatter
  vault properties repair --backup

  # Vault indexing
  vault index build               # Build vault index
  vault index build --force       # Force full rebuild
  vault index duplicates find     # Find duplicate files
  vault index duplicates cleanup  # Remove checked duplicates
  vault index rename find         # Find mangled filenames
  vault index rename apply        # Fix mangled filenames
  vault index broken-links        # Find broken wiki-links

Configuration:
  # Set default vault
  export VAULT_PATH=~/Documents/MyVault

  # Or create config file
  mkdir -p ~/.config/vault-manager
  echo "vault_path: ~/Documents/MyVault" > ~/.config/vault-manager/config.yaml

Installation:
  pip install obsidian-vault-manager       # From PyPI (when published)
  pip install obsidian-vault-manager[ai]   # With AI features
  pip install -e ".[dev]"                  # Development mode

For more information on a specific domain:
  vault <domain> --help
        """
    )

    # Global options (before domain)
    parser.add_argument(
        '-v', '--vault-path',
        dest='vault_path',
        metavar='PATH',
        help='Path to Obsidian vault (overrides config and environment)'
    )

    parser.add_argument(
        '--no-interactive',
        action='store_true',
        help='Disable interactive prompts (fail if vault not found)'
    )

    # Create subparsers for domains
    # Use add_help=False to let domain CLIs handle their own help
    subparsers = parser.add_subparsers(
        dest='domain',
        required=True,
        help='Vault management domain'
    )

    # Register domains
    subparsers.add_parser(
        'tags',
        help='Tag management and validation',
        add_help=False
    )

    subparsers.add_parser(
        'images',
        help='Image organization and cleanup',
        add_help=False
    )

    subparsers.add_parser(
        'properties',
        help='Frontmatter properties management',
        add_help=False
    )

    subparsers.add_parser(
        'index',
        help='Vault indexing and link resolution',
        add_help=False
    )

    return parser


def main() -> None:
    """
    Main entry point for the unified vault CLI.

    Parses the domain argument and delegates to the appropriate
    domain-specific CLI module.
    """
    from vault_manager.config import resolve_vault_path
    from vault_manager.core.vault import set_vault_root

    parser = create_parser()

    # Parse known args to get domain and global options, leave rest for domain CLI
    args, remaining = parser.parse_known_args()

    # Resolve and set vault root path
    vault_path = resolve_vault_path(
        cli_arg=args.vault_path,
        allow_interactive=not args.no_interactive
    )
    set_vault_root(vault_path)

    # Map domain names to CLI module paths
    domain_map = {
        'tags': 'vault_manager.tags.cli',
        'images': 'vault_manager.images.cli',
        'properties': 'vault_manager.properties.cli',
        'index': 'vault_manager.index.cli',
    }

    # Get the domain CLI module
    cli_module_path = domain_map.get(args.domain)

    if cli_module_path is None:
        print(f"Error: Unknown domain '{args.domain}'")
        parser.print_help()
        sys.exit(1)

    # Import domain CLI module
    try:
        cli_module = importlib.import_module(cli_module_path)
    except ImportError as e:
        print(f"Error: Failed to import domain CLI '{args.domain}': {e}")
        traceback.print_exc()
        sys.exit(1)

    # Delegate to domain CLI by manipulating sys.argv
    # This makes the domain CLI think it was invoked directly
    original_argv = sys.argv
    try:
        # Set argv to simulate: vault <domain> <remaining args>
        sys.argv = [f'vault {args.domain}'] + remaining
        cli_module.main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Restore original argv
        sys.argv = original_argv


if __name__ == '__main__':
    main()
