"""
Broken links command - Find broken wiki-links in markdown files.

This module implements the broken-links command which identifies unresolved
wiki-links in the vault and generates a markdown report.
"""

from argparse import ArgumentParser, Namespace
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ...core.database import VaultDatabase
from . import Command


class BrokenLinksCommand(Command):
    """Command to find and report broken wiki-links."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the broken-links command."""
        pass  # No arguments needed

    def execute(self, args: Namespace) -> None:
        """Execute the broken-links command."""
        print("Finding broken links...")

        with VaultDatabase() as db:
            db.require_exists("index broken-links")

            # Query broken links from database (3NF: compute is_resolved from target_file)
            rows = db.query('''
                SELECT source_file, link_text, link_type, line_number
                FROM links
                WHERE target_file IS NULL
                ORDER BY source_file, line_number
            ''')

            if not rows:
                print("\n✓ No broken links found!")
                return

            # Group by source file (exclude broken-links.md itself)
            broken_by_file = defaultdict(list)
            for source_file, link_text, link_type, line_number in rows:
                # Skip broken links from the broken-links.md report itself
                if source_file == 'broken-links.md':
                    continue

                broken_by_file[source_file].append({
                    'link_text': link_text,
                    'link_type': link_type,
                    'line_number': line_number
                })

            # Calculate statistics from filtered data
            total_broken = sum(len(links) for links in broken_by_file.values())
            affected_files = len(broken_by_file)

            if total_broken == 0:
                print("\n✓ No broken links found!")
                return

            print(f"Found {total_broken} broken links in {affected_files} files")

            # Generate report
            print("\nGenerating report...")
            report = self._generate_report(broken_by_file, db.vault_root)

            # Write to broken-links.md
            output_file = db.vault_root / 'broken-links.md'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)

            print(f"\nReport written to: {output_file}")
            print("\nDone!")

    def _generate_report(self, broken_by_file: Dict[str, List[dict]], vault_root: Path) -> str:
        """
        Generate markdown report of broken links.

        Args:
            broken_by_file: Dictionary mapping source files to lists of broken links
            vault_root: Path to vault root

        Returns:
            Markdown report content
        """
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_broken = sum(len(links) for links in broken_by_file.values())
        affected_files = len(broken_by_file)

        lines = [
            "---",
            "tags:",
            "  - vault-management",
            "  - broken-links",
            "---",
            "",
            "# Broken Wiki-Links",
            "",
            f"**Generated:** {now}",
            f"**Vault:** `{vault_root}`",
            "",
            "## Statistics",
            "",
            f"- Total broken links: {total_broken}",
            f"- Files with broken links: {affected_files}",
            "",
            "## Broken Links by File",
            "",
            "The following files contain broken wiki-links:",
            "",
        ]

        # Sort files alphabetically
        sorted_files = sorted(broken_by_file.items(), key=lambda x: x[0].lower())

        # Detailed breakdown section
        for source_file, links in sorted_files:
            # Convert file path to wiki-link format (remove .md extension)
            wiki_link = source_file[:-3] if source_file.endswith('.md') else source_file

            lines.append(f"### [[{wiki_link}]]")
            lines.append("")
            lines.append(f"**File:** [[{wiki_link}]]")
            lines.append(f"**Broken links:** {len(links)}")
            lines.append("")

            # Group links by line number for better readability
            for link in sorted(links, key=lambda x: x['line_number'] or 0):
                line_info = f" (line {link['line_number']})" if link['line_number'] else ""
                link_type = link['link_type']

                # Format the link text
                if link_type == 'wiki':
                    lines.append(f"- `[[{link['link_text']}]]`{line_info}")
                elif link_type == 'markdown':
                    lines.append(f"- `[...]({link['link_text']})`{line_info}")
                else:
                    lines.append(f"- `{link['link_text']}`{line_info}")

            lines.append("")

        lines.extend([
            "---",
            "",
            "*Generated by `vault index broken-links`*",
            ""
        ])

        return '\n'.join(lines)
