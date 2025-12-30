"""
Image Management Tool for Obsidian Vault

This package provides commands to manage and clean up images in your vault.

Commands:
    find          Find images not referenced in any markdown file
    cleanup       Move checked-off orphaned images to .trash directory
    remove-alt    Remove alt text from wiki-link image embeds

Usage:
    python -m Library.images <command> [options]

Examples:
    python -m Library.images find
    python -m Library.images cleanup
    python -m Library.images remove-alt Personal --dry-run
"""

__version__ = '2.0.0'
__author__ = 'Claude Code'
