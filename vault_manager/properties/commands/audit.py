#!/usr/bin/env python3
"""
Command to audit frontmatter properties across the vault.

This command scans all markdown files, analyzes frontmatter properties,
and generates a comprehensive markdown report with statistics and usage patterns.
"""

import re
import yaml
from argparse import ArgumentParser, Namespace
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from vault_manager.core.command import Command
from vault_manager.core.vault import get_vault_root, iter_markdown_files, count_markdown_files


class AuditCommand(Command):
    """Command to audit frontmatter properties across the vault."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the audit command."""
        parser.add_argument(
            '--output',
            default='property-audit.md',
            help='Output file name (default: property-audit.md)'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the audit command to analyze properties."""
        vault_root = get_vault_root()
        output_file = vault_root / args.output

        print(f"\n{'='*60}")
        print(f"Property Audit Tool")
        print(f"{'='*60}")
        print(f"Vault: {vault_root}")
        print(f"Output: {output_file.name}")
        print(f"{'='*60}\n")

        # Scan all markdown files
        print("Scanning vault for properties...\n")
        property_data = self._scan_vault(vault_root)

        # Generate report
        print("Generating report...\n")
        report = self._generate_report(vault_root, property_data)

        # Write report to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"✓ Report generated: {output_file.name}")
        print(f"\nSummary:")
        print(f"  Total files scanned: {property_data['total_files']}")
        print(f"  Files with frontmatter: {property_data['files_with_frontmatter']}")
        print(f"  Unique properties: {len(property_data['properties'])}")
        print(f"\n{'='*60}")

    def _scan_vault(self, vault_root: Path) -> Dict:
        """
        Scan all markdown files and collect property data.

        Args:
            vault_root: Root directory of the vault

        Returns:
            Dictionary with property statistics and data
        """
        data = {
            'total_files': 0,
            'files_with_frontmatter': 0,
            'files_without_frontmatter': 0,
            'properties': {},  # property_name -> PropertyInfo
        }

        # Get all markdown files
        additional_ignores = {'Excalidraw'}

        # Count files first for progress tracking
        data['total_files'] = count_markdown_files(
            vault_root,
            vault_root,
            additional_ignores=additional_ignores,
            exclude_excalidraw=True
        )

        # Process each file using iterator (memory-efficient)
        for file_path in iter_markdown_files(
            vault_root,
            vault_root,
            additional_ignores=additional_ignores,
            exclude_excalidraw=True
        ):
            try:
                content = file_path.read_text(encoding='utf-8')
                frontmatter_dict = self._extract_frontmatter_dict(content)

                if frontmatter_dict is None:
                    data['files_without_frontmatter'] += 1
                    continue

                data['files_with_frontmatter'] += 1

                # Process each property in this file
                for prop_name, prop_value in frontmatter_dict.items():
                    if prop_name not in data['properties']:
                        data['properties'][prop_name] = {
                            'count': 0,
                            'types': Counter(),
                            'values': Counter(),
                            'example_files': [],
                            'list_sizes': Counter(),
                            'numeric_values': [],
                        }

                    prop_info = data['properties'][prop_name]
                    prop_info['count'] += 1

                    # Determine type
                    prop_type = self._get_type_name(prop_value)
                    prop_info['types'][prop_type] += 1

                    # Store value information based on type
                    if prop_type == 'list':
                        prop_info['list_sizes'][len(prop_value)] += 1
                        # Store list items
                        for item in prop_value:
                            if isinstance(item, str):
                                prop_info['values'][item] += 1
                    elif prop_type in ('string', 'boolean'):
                        prop_info['values'][str(prop_value)] += 1
                    elif prop_type == 'number':
                        prop_info['numeric_values'].append(prop_value)
                        prop_info['values'][str(prop_value)] += 1
                    elif prop_type == 'null':
                        prop_info['values']['null'] += 1

                    # Store example files (up to 5)
                    if len(prop_info['example_files']) < 5:
                        relative_path = file_path.relative_to(vault_root)
                        prop_info['example_files'].append(str(relative_path))

            except Exception as e:
                # Skip files that can't be processed
                continue

        return data

    def _extract_frontmatter_dict(self, content: str) -> Dict:
        """
        Extract frontmatter as a dictionary.

        Args:
            content: Full file content

        Returns:
            Dictionary of frontmatter properties, or None if no frontmatter
        """
        frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            return Dict()

        frontmatter_text = match.group(1)

        try:
            frontmatter_dict = yaml.safe_load(frontmatter_text)
            return frontmatter_dict if isinstance(frontmatter_dict, dict) else None
        except yaml.YAMLError:
            return Dict()

    def _get_type_name(self, value: Any) -> str:
        """
        Get a human-readable type name for a value.

        Args:
            value: The value to check

        Returns:
            Type name string
        """
        if value is None:
            return 'null'
        elif isinstance(value, bool):
            return 'boolean'
        elif isinstance(value, int) or isinstance(value, float):
            return 'number'
        elif isinstance(value, str):
            return 'string'
        elif isinstance(value, list):
            return 'list'
        elif isinstance(value, dict):
            return 'object'
        else:
            return 'unknown'

    def _generate_report(self, vault_root: Path, data: Dict) -> str:
        """
        Generate markdown report from property data.

        Args:
            vault_root: Root directory of the vault
            data: Property data from scanning

        Returns:
            Markdown report as string
        """
        lines = []

        # Header
        lines.append("---")
        lines.append("tags:")
        lines.append("  - vault-management")
        lines.append("  - property-audit")
        lines.append("---")
        lines.append("")
        lines.append("# Frontmatter Property Audit Report")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Vault:** `{vault_root}`")
        lines.append("")

        # Summary Statistics
        lines.append("## Summary Statistics")
        lines.append("")
        lines.append(f"- **Total files scanned:** {data['total_files']}")
        lines.append(f"- **Files with frontmatter:** {data['files_with_frontmatter']}")
        lines.append(f"- **Files without frontmatter:** {data['files_without_frontmatter']}")
        lines.append(f"- **Unique properties:** {len(data['properties'])}")
        lines.append("")

        # Property Overview Table
        lines.append("## Property Overview")
        lines.append("")
        lines.append("| Property | Files | Primary Type | Values |")
        lines.append("|----------|-------|--------------|--------|")

        # Sort properties by usage count (descending)
        sorted_props = sorted(
            data['properties'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )

        for prop_name, prop_info in sorted_props:
            primary_type = prop_info['types'].most_common(1)[0][0]
            unique_values = len(prop_info['values'])
            lines.append(f"| `{prop_name}` | {prop_info['count']} | {primary_type} | {unique_values} |")

        lines.append("")

        # Detailed Property Analysis
        lines.append("## Detailed Property Analysis")
        lines.append("")

        for prop_name, prop_info in sorted_props:
            lines.append(f"### `{prop_name}`")
            lines.append("")

            # Basic stats
            lines.append(f"**Usage:** {prop_info['count']} files")
            lines.append("")

            # Type distribution
            lines.append("**Data Types:**")
            for type_name, type_count in prop_info['types'].most_common():
                percentage = (type_count / prop_info['count']) * 100
                lines.append(f"- {type_name}: {type_count} ({percentage:.1f}%)")
            lines.append("")

            # Type-specific analysis
            primary_type = prop_info['types'].most_common(1)[0][0]

            if primary_type == 'list':
                # List analysis
                lines.append("**List Sizes:**")
                for size, count in sorted(prop_info['list_sizes'].items()):
                    lines.append(f"- {size} items: {count} files")
                lines.append("")

                # Most common list items
                if prop_info['values']:
                    lines.append("**Most Common List Items:**")
                    for value, count in prop_info['values'].most_common(10):
                        lines.append(f"- `{value}`: {count} occurrences")
                    lines.append("")

            elif primary_type == 'number':
                # Numeric analysis
                if prop_info['numeric_values']:
                    nums = prop_info['numeric_values']
                    lines.append("**Numeric Range:**")
                    lines.append(f"- Min: {min(nums)}")
                    lines.append(f"- Max: {max(nums)}")
                    lines.append(f"- Average: {sum(nums) / len(nums):.2f}")
                    lines.append("")

                    # Show unique values if not too many
                    unique_values = sorted(set(nums))
                    if len(unique_values) <= 20:
                        lines.append("**Unique Values:**")
                        lines.append(f"- {', '.join(map(str, unique_values))}")
                        lines.append("")

            elif primary_type == 'string':
                # String analysis
                unique_count = len(prop_info['values'])
                lines.append(f"**Unique Values:** {unique_count}")
                lines.append("")

                # Show values if not too many
                if unique_count <= 20:
                    lines.append("**All Values:**")
                    for value, count in sorted(prop_info['values'].items()):
                        lines.append(f"- `{value}`: {count} files")
                    lines.append("")
                else:
                    # Show most common values
                    lines.append("**Most Common Values:**")
                    for value, count in prop_info['values'].most_common(20):
                        lines.append(f"- `{value}`: {count} files")
                    lines.append("")

            elif primary_type == 'boolean':
                # Boolean distribution
                lines.append("**Value Distribution:**")
                for value, count in prop_info['values'].items():
                    percentage = (count / prop_info['count']) * 100
                    lines.append(f"- `{value}`: {count} files ({percentage:.1f}%)")
                lines.append("")

            # Example files
            if prop_info['example_files']:
                lines.append("**Example Files:**")
                for file_path in prop_info['example_files'][:5]:
                    # Convert to wiki-link
                    file_name = Path(file_path).stem
                    lines.append(f"- [[{file_name}]] (`{file_path}`)")
                lines.append("")

            lines.append("---")
            lines.append("")

        return '\n'.join(lines)
