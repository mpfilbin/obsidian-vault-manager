"""
Repair command - Fix frontmatter issues in checked entries from validation report.

This module implements the repair command which reads the invalid-frontmatter.md
report and attempts to fix issues for checked entries.
"""

import re
import shutil
import sys
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from . import Command
from ..common import get_vault_root
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary

try:
    import yaml
    HAS_YAML = True
except ImportError:
    yaml = None
    HAS_YAML = False


class RepairCommand(Command):
    """Command to repair frontmatter issues from validation report."""

    # Deprecated singular properties (should be plural as of Obsidian 1.9)
    DEPRECATED_PROPERTIES = {
        'tag': 'tags',
        'alias': 'aliases',
        'cssclass': 'cssclasses'
    }

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the repair command."""
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Backup files to .backup directory before repairing'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate repairs without modifying files'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the repair command to fix frontmatter issues."""
        # Check for yaml library
        if not HAS_YAML:
            print("Error: PyYAML library not installed")
            print("\nInstall it with:")
            print("  pip install pyyaml")
            sys.exit(1)

        # Get vault root
        vault_root = get_vault_root()
        report_path = vault_root / 'invalid-frontmatter.md'

        # Check if report exists
        if not report_path.exists():
            print("Error: invalid-frontmatter.md not found")
            print("\nRun validation first:")
            print("  vault properties validate")
            sys.exit(1)

        # Display header
        print("=" * 60)
        print("Repair Frontmatter Issues")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Report: {report_path}")
        if args.dry_run:
            print("Mode: DRY RUN (simulation only)")
        else:
            print(f"Mode: LIVE {'with backup' if args.backup else 'without backup'}")
        print()

        # Parse checked items from report
        checked_items = self._parse_checked_items(report_path, vault_root)

        if not checked_items:
            print("No checked items found in report")
            print("Check items in invalid-frontmatter.md to repair them")
            return

        print(f"Found {len(checked_items)} file(s) with checked issues to repair")
        print()

        # Backup directory setup
        backup_dir = None
        if args.backup and not args.dry_run:
            backup_dir = vault_root / '.backup'
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = backup_dir / f'repair_{timestamp}'
            backup_dir.mkdir(exist_ok=True)
            print(f"Backup directory: {backup_dir}")
            print()

        # Repair files with DryRunContext
        with DryRunContext(args.dry_run) as ctx:
            ctx.stats.increment('total_files', len(checked_items))

            for file_path, issues in checked_items.items():
                print(f"Processing: {file_path}")

                full_path = vault_root / file_path
                if not full_path.exists():
                    print(f"  ✗ File not found: {file_path}")
                    ctx.stats.increment('files_failed')
                    continue

                # Backup file if requested
                if backup_dir and not args.dry_run:
                    try:
                        backup_file_path = backup_dir / file_path
                        backup_file_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(full_path, backup_file_path)
                        ctx.stats.increment('files_backed_up')
                        print(f"  ✓ Backed up to: {backup_file_path.relative_to(vault_root)}")
                    except Exception as e:
                        print(f"  ✗ Backup failed: {e}")
                        ctx.stats.increment('files_failed')
                        continue

                # Attempt repair
                try:
                    repaired = self._repair_file(full_path, issues, args.dry_run)
                    if repaired:
                        ctx.stats.increment('files_modified')
                        ctx.record_change(full_path, f"Repaired frontmatter issues")
                        if args.dry_run:
                            print(f"  ✓ Would repair (dry-run)")
                        else:
                            print(f"  ✓ Repaired")
                    else:
                        ctx.stats.increment('files_skipped')
                        print(f"  ○ No repairs applied (may require manual intervention)")
                except Exception as e:
                    print(f"  ✗ Repair failed: {e}")
                    ctx.stats.increment('files_failed')

                print()

            # Print summary
            additional_info = None
            if ctx.stats.custom_stats.get('files_backed_up', 0) > 0:
                additional_info = f"Files backed up: {ctx.stats.custom_stats['files_backed_up']}"
            print_dry_run_summary(ctx, additional_info=additional_info)

    def _parse_checked_items(self, report_path: Path, vault_root: Path) -> Dict[str, List[Tuple[str, str]]]:
        """
        Parse the invalid-frontmatter.md report to extract checked items.

        Returns:
            Dict mapping file_path to list of (issue_type, message) tuples
        """
        checked_items = defaultdict(list)

        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        current_file = None
        in_all_files_section = False

        for i, line in enumerate(lines):
            # Track when we enter the "Files with Issues" section
            if line.strip() == "## Files with Issues":
                in_all_files_section = True
                continue

            # Only parse checked items in the "Files with Issues" section
            if not in_all_files_section:
                continue

            # Detect file headers: ### [[note_path]]
            if line.startswith('### [['):
                match = re.search(r'### \[\[(.*?)\]\]', line)
                if match:
                    note_path = match.group(1)
                    # Convert note path back to file path
                    current_file = note_path + '.md'
                continue

            # Detect checked issue items: - [x] 🔴 **issue_type**: message
            if current_file and line.strip().startswith('- [x]'):
                # Parse the issue line
                # Pattern: - [x] 🔴 **issue_type**: message
                match = re.search(r'- \[x\].*?\*\*(.*?)\*\*:\s*(.*)', line)
                if match:
                    issue_type = match.group(1)
                    message = match.group(2)
                    checked_items[current_file].append((issue_type, message))

        return dict(checked_items)

    def _strip_markdown(self, text: str) -> str:
        """
        Remove markdown formatting from text.

        Args:
            text: Text potentially containing markdown

        Returns:
            Plain text with markdown formatting removed
        """
        # Remove bold (**text** or __text__)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)

        # Remove italic (*text* or _text_)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)

        # Remove inline code (`code`)
        text = re.sub(r'`(.+?)`', r'\1', text)

        # Remove links [text](url) - keep just the text
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

        # Remove wiki-links [[link]] or [[link|display]]
        text = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', lambda m: m.group(2) or m.group(1), text)

        # Remove strikethrough (~~text~~)
        text = re.sub(r'~~(.+?)~~', r'\1', text)

        # Remove headings (# text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        return text

    def _extract_frontmatter_raw(self, content: str) -> Tuple[Optional[str], str, int, int]:
        """
        Extract raw frontmatter text from markdown content.

        Returns:
            Tuple of (frontmatter_text, body, start_line, end_line)
            Returns (None, content, 0, 0) if no frontmatter found
        """
        # Frontmatter must be at the very top
        if not content.startswith('---'):
            return None, content, 0, 0

        # Find the closing ---
        lines = content.split('\n')
        if len(lines) < 3:
            return None, content, 0, 0

        # Find closing delimiter
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                end_idx = i
                break

        if end_idx is None:
            return None, content, 0, 0

        frontmatter_lines = lines[1:end_idx]
        frontmatter_text = '\n'.join(frontmatter_lines)
        body = '\n'.join(lines[end_idx + 1:])

        return frontmatter_text, body, 1, end_idx

    def _repair_file(self, file_path: Path, issues: List[Tuple[str, str]], dry_run: bool) -> bool:
        """
        Repair a file's frontmatter issues.

        Returns:
            True if repairs were applied, False otherwise
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        repairs_applied = False

        # Extract frontmatter
        frontmatter_text, body, start_line, end_line = self._extract_frontmatter_raw(content)

        # Check if we need to create missing frontmatter
        if frontmatter_text is None:
            # Check if any issue is missing_frontmatter or missing_tags
            has_missing_fm = any(issue_type == 'missing_frontmatter' for issue_type, _ in issues)

            if has_missing_fm:
                # Create new frontmatter with empty tags
                frontmatter = {'tags': []}
                yaml_str = yaml.dump(
                    frontmatter,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False
                )
                content = f"---\n{yaml_str}---\n{content}"
                repairs_applied = True
                print(f"  ✓ Fixed: missing_frontmatter (created empty frontmatter)")

                if not dry_run:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                return repairs_applied
            else:
                # No frontmatter and not a missing_frontmatter issue - can't repair
                return False

        # Parse frontmatter
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                frontmatter = {}
        except yaml.YAMLError:
            # YAML syntax errors require manual intervention
            print(f"  ! YAML syntax error - requires manual fix")
            return False

        # Apply repairs based on issue types
        for issue_type, message in issues:
            if issue_type == 'deprecated_property':
                if self._repair_deprecated_property(frontmatter, message):
                    repairs_applied = True
                    print(f"  ✓ Fixed: {issue_type}")

            elif issue_type == 'invalid_tag_format':
                if self._repair_invalid_tag_format(frontmatter, message):
                    repairs_applied = True
                    print(f"  ✓ Fixed: {issue_type}")

            elif issue_type == 'duplicate_property':
                # This is handled by deduplication logic below
                repairs_applied = True
                print(f"  ✓ Fixed: {issue_type} (deduplicated)")

            elif issue_type == 'empty_frontmatter':
                if not frontmatter or all(v is None for v in frontmatter.values()):
                    # Remove empty frontmatter
                    content = body
                    repairs_applied = True
                    print(f"  ✓ Fixed: {issue_type} (removed empty frontmatter)")

            elif issue_type == 'unquoted_link':
                if self._repair_unquoted_links(frontmatter):
                    repairs_applied = True
                    print(f"  ✓ Fixed: {issue_type}")

            elif issue_type == 'markdown_in_property':
                if self._repair_markdown_in_property(frontmatter, message):
                    repairs_applied = True
                    print(f"  ✓ Fixed: {issue_type}")

            elif issue_type == 'missing_tags':
                # Add empty tags property if missing
                if 'tags' not in frontmatter and 'tag' not in frontmatter:
                    frontmatter['tags'] = []
                    repairs_applied = True
                    print(f"  ✓ Fixed: {issue_type} (added empty tags property)")

            elif issue_type == 'empty_tags':
                # Empty tags is just a warning, no auto-repair needed
                print(f"  ! Skipped: {issue_type} (manual input required)")

            else:
                print(f"  ! Cannot auto-repair: {issue_type}")

        # If repairs were applied, rebuild the content
        if repairs_applied and frontmatter_text is not None:
            # Serialize frontmatter back to YAML
            try:
                # Remove None values and empty lists (except 'tags' which we keep as placeholder)
                cleaned_frontmatter = {
                    k: v for k, v in frontmatter.items()
                    if v is not None and (k == 'tags' or (v != [] and v != ''))
                }

                if cleaned_frontmatter:
                    yaml_str = yaml.dump(
                        cleaned_frontmatter,
                        default_flow_style=False,
                        allow_unicode=True,
                        sort_keys=False
                    )
                    content = f"---\n{yaml_str}---\n{body}"
                else:
                    # Frontmatter is now empty, remove it
                    content = body

            except Exception as e:
                print(f"  ✗ Error serializing YAML: {e}")
                return False

        # Write repaired content
        if repairs_applied and not dry_run and content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        return repairs_applied

    def _repair_deprecated_property(self, frontmatter: dict, message: str) -> bool:
        """Repair deprecated property names by renaming to plural form."""
        # Extract deprecated property from message
        # Message format: "Deprecated property 'tag' (use 'tags' instead...)"
        match = re.search(r"Deprecated property '(.*?)'", message)
        if not match:
            return False

        deprecated = match.group(1)
        if deprecated not in self.DEPRECATED_PROPERTIES:
            return False

        replacement = self.DEPRECATED_PROPERTIES[deprecated]

        # Only rename if the deprecated property exists
        if deprecated in frontmatter:
            # If replacement already exists, merge values
            if replacement in frontmatter:
                # Merge the values
                old_val = frontmatter[deprecated]
                new_val = frontmatter[replacement]

                # Convert to lists
                old_list = old_val if isinstance(old_val, list) else [old_val]
                new_list = new_val if isinstance(new_val, list) else [new_val]

                # Merge and deduplicate
                merged = list(dict.fromkeys(old_list + new_list))
                frontmatter[replacement] = merged
            else:
                # Just rename
                frontmatter[replacement] = frontmatter[deprecated]

            # Remove deprecated property
            del frontmatter[deprecated]
            return True

        return False

    def _repair_invalid_tag_format(self, frontmatter: dict, message: str) -> bool:
        """Remove hashtag prefixes from tags in YAML frontmatter."""
        # Extract the invalid tag from message
        # Message format: "Tag contains hashtag: '#tag' (remove # prefix in YAML)"
        match = re.search(r"Tag contains hashtag: '(#.*?)'", message)
        if not match:
            return False

        invalid_tag = match.group(1)
        fixed_tag = invalid_tag.lstrip('#')

        # Check both 'tags' and 'tag' properties
        repaired = False
        for tag_key in ['tags', 'tag']:
            if tag_key not in frontmatter:
                continue

            tags_value = frontmatter[tag_key]

            # Handle string
            if isinstance(tags_value, str):
                if tags_value == invalid_tag:
                    frontmatter[tag_key] = fixed_tag
                    repaired = True

            # Handle list
            elif isinstance(tags_value, list):
                new_tags = []
                for tag in tags_value:
                    if isinstance(tag, str) and tag == invalid_tag:
                        new_tags.append(fixed_tag)
                        repaired = True
                    else:
                        new_tags.append(tag)
                frontmatter[tag_key] = new_tags

        return repaired

    def _repair_unquoted_links(self, frontmatter: dict) -> bool:
        """Add quotes around wiki-links in frontmatter values."""
        repaired = False

        for key, value in frontmatter.items():
            if isinstance(value, str) and '[[' in value and ']]' in value:
                # Value contains wiki-links - ensure it's properly quoted
                # This is implicit in YAML serialization, so just flag as repaired
                repaired = True

            elif isinstance(value, list):
                # Check list items
                for i, item in enumerate(value):
                    if isinstance(item, str) and '[[' in item and ']]' in item:
                        repaired = True

        return repaired

    def _repair_markdown_in_property(self, frontmatter: dict, message: str) -> bool:
        """Strip markdown formatting from property values."""
        # Extract the property name from message
        # Message format: "Property 'summary' contains Markdown (code), which is not supported in property values"
        match = re.search(r"Property '(.*?)' contains Markdown", message)
        if not match:
            return False

        property_name = match.group(1)

        # Check if property exists
        if property_name not in frontmatter:
            return False

        # Get the property value
        value = frontmatter[property_name]

        # Strip markdown based on value type
        if isinstance(value, str):
            # Strip markdown from string
            cleaned_value = self._strip_markdown(value)
            if cleaned_value != value:
                frontmatter[property_name] = cleaned_value
                return True

        elif isinstance(value, list):
            # Strip markdown from all string items in list
            repaired = False
            cleaned_list = []
            for item in value:
                if isinstance(item, str):
                    cleaned_item = self._strip_markdown(item)
                    if cleaned_item != item:
                        repaired = True
                    cleaned_list.append(cleaned_item)
                else:
                    cleaned_list.append(item)

            if repaired:
                frontmatter[property_name] = cleaned_list
                return True

        return False
