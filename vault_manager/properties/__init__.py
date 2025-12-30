"""
Property Management Tool for Obsidian Vault

This package provides commands to manage frontmatter properties in your vault.

Commands:
    summarize     Use AI to generate and add summary properties to notes
    relate        Analyze and add related note links based on similarity
    missing       Find and report notes without YAML frontmatter
    normalize     Standardize frontmatter properties across notes

Usage:
    python -m Library.properties <command> [options]

Examples:
    python -m Library.properties summarize Personal --dry-run
    python -m Library.properties relate Personal --max-related=3
    python -m Library.properties missing Personal
    python -m Library.properties normalize Personal --dry-run
"""

__version__ = '2.0.0'
__author__ = 'Claude Code'
