"""
Property Management Tool for Obsidian Vault

This package provides commands to manage frontmatter properties in your vault.

Commands:
    summarize     Use AI to generate and add summary properties to notes
    relate        Analyze and add related note links based on similarity
    missing       Find and report notes without YAML frontmatter
    normalize     Standardize frontmatter properties across notes

Usage:
    vault properties <command> [options]

Examples:
    vault properties summarize Personal --dry-run
    vault properties relate Personal --max-related=3
    vault properties missing Personal
    vault properties normalize Personal --dry-run
"""

__version__ = '2.0.0'
__author__ = 'Claude Code'
