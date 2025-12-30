"""
Tag Management Tool for Obsidian Vault

This package provides commands to manage and analyze tags in your vault.

Commands:
    tagless         Generate report of files without tags
    tags            Generate detailed tag inventory with file lists
    add             Use AI to generate and add tags to notes

Usage:
    python -m Library.tags <command> [options]

Examples:
    python -m Library.tags tagless
    python -m Library.tags tags --summary
    python -m Library.tags add Personal --dry-run
"""

__version__ = '2.0.0'
__author__ = 'Claude Code'
