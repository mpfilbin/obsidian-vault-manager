"""
Validate command - Validate YAML frontmatter structure and content.

This module implements the validate command which checks frontmatter against
Obsidian's property rules and generates a report of invalid frontmatter.
"""

import re
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

from . import Command
from ..common import get_vault_root
from vault_manager.core.frontmatter import FrontmatterManager
from vault_manager.core.vault import iter_markdown_files, validate_directory

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class ValidationIssue:
    """Represents a validation issue found in frontmatter."""
    def __init__(self, severity: str, issue_type: str, message: str):
        self.severity = severity  # 'error' or 'warning'
        self.issue_type = issue_type
        self.message = message


class ValidateCommand(Command):
    """Command to validate YAML frontmatter in markdown files."""

    # Deprecated singular properties (should be plural as of Obsidian 1.9)
    DEPRECATED_PROPERTIES = {
        'tag': 'tags',
        'alias': 'aliases',
        'cssclass': 'cssclasses'
    }

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the validate command."""
        parser.add_argument(
            'directory',
            nargs='?',
            default='.',
            help='Directory to validate (relative to vault root, use "." for entire vault)'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the validate command to check frontmatter."""
        # Check for yaml library
        if not HAS_YAML:
            print("Error: PyYAML library not installed")
            print("\nInstall it with:")
            print("  pip install pyyaml")
            sys.exit(1)

        # Get vault root
        vault_root = get_vault_root()

        # Validate directory
        target_dir = validate_directory(args.directory, vault_root)

        # Display header
        print("=" * 60)
        print("Validate YAML Frontmatter")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Ignored directories: .obsidian, .trash, .backup, Excalidraw")

        # Validate files
        issues_by_file = self._validate_directory(target_dir, vault_root)

        # Generate report
        self._generate_report(vault_root, issues_by_file)

        # Print summary
        self._print_summary(issues_by_file)

    def _extract_frontmatter_raw(self, content: str) -> Tuple[str, str, int, int]:
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

    def _validate_yaml_syntax(self, frontmatter_text: str) -> List[ValidationIssue]:
        """Validate that frontmatter is valid YAML."""
        issues = []

        if not frontmatter_text.strip():
            issues.append(ValidationIssue(
                'warning',
                'empty_frontmatter',
                'Frontmatter is empty'
            ))
            return issues

        try:
            parsed = yaml.safe_load(frontmatter_text)
            if parsed is None:
                issues.append(ValidationIssue(
                    'warning',
                    'empty_frontmatter',
                    'Frontmatter parses to null/empty'
                ))
            elif not isinstance(parsed, dict):
                issues.append(ValidationIssue(
                    'error',
                    'invalid_yaml_structure',
                    f'Frontmatter must be a dictionary, got {type(parsed).__name__}'
                ))
        except yaml.YAMLError as e:
            issues.append(ValidationIssue(
                'error',
                'yaml_syntax_error',
                f'YAML syntax error: {str(e)}'
            ))

        return issues

    def _validate_property_names(self, frontmatter_text: str) -> List[ValidationIssue]:
        """Validate property names for uniqueness and check for deprecated names."""
        issues = []

        try:
            parsed = yaml.safe_load(frontmatter_text)
            if not isinstance(parsed, dict):
                return issues

            # Check for duplicate property names (case-sensitive)
            seen_properties = set()
            for prop in parsed.keys():
                if prop in seen_properties:
                    issues.append(ValidationIssue(
                        'error',
                        'duplicate_property',
                        f'Duplicate property name: {prop}'
                    ))
                seen_properties.add(prop)

            # Check for deprecated singular properties
            for deprecated, replacement in self.DEPRECATED_PROPERTIES.items():
                if deprecated in parsed:
                    issues.append(ValidationIssue(
                        'warning',
                        'deprecated_property',
                        f"Deprecated property '{deprecated}' (use '{replacement}' instead, plural form as of Obsidian 1.9)"
                    ))

        except yaml.YAMLError:
            # YAML syntax errors are caught elsewhere
            pass

        return issues

    def _validate_tags(self, frontmatter_text: str) -> List[ValidationIssue]:
        """Validate tags property - must not contain hashtags and should be present."""
        issues = []

        try:
            parsed = yaml.safe_load(frontmatter_text)
            if not isinstance(parsed, dict):
                return issues

            # Check if tags property exists (either 'tags' or deprecated 'tag')
            has_tags = 'tags' in parsed or 'tag' in parsed

            if not has_tags:
                issues.append(ValidationIssue(
                    'warning',
                    'missing_tags',
                    'Frontmatter does not contain tags property'
                ))
                return issues

            # Check both 'tags' and deprecated 'tag'
            for tag_key in ['tags', 'tag']:
                if tag_key not in parsed:
                    continue

                tags_value = parsed[tag_key]

                # Check if tags property is empty
                if tags_value is None or (isinstance(tags_value, list) and len(tags_value) == 0):
                    issues.append(ValidationIssue(
                        'warning',
                        'empty_tags',
                        'Tags property exists but is empty'
                    ))
                    continue

                # Normalize to list
                if isinstance(tags_value, str):
                    tags_list = [tags_value]
                elif isinstance(tags_value, list):
                    tags_list = tags_value
                else:
                    continue

                # Check each tag for hashtags
                for tag in tags_list:
                    if not isinstance(tag, str):
                        continue

                    if tag.startswith('#'):
                        issues.append(ValidationIssue(
                            'error',
                            'invalid_tag_format',
                            f"Tag contains hashtag: '{tag}' (remove # prefix in YAML)"
                        ))

        except yaml.YAMLError:
            pass

        return issues

    def _validate_links(self, frontmatter_text: str) -> List[ValidationIssue]:
        """Validate that wiki-links are properly quoted."""
        issues = []

        # Pattern to detect unquoted wiki-links in YAML
        # This is a heuristic check - looks for [[...]] not within quotes
        lines = frontmatter_text.split('\n')

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            # Check for wiki-links
            if '[[' in line:
                # Check if it appears to be unquoted
                # Simple heuristic: if the line contains [[ but doesn't have proper quotes around it
                if not re.search(r'["\'].*\[\[.*\]\].*["\']', line):
                    # Check if it's in a list item or value
                    if ':' in line or line.strip().startswith('-'):
                        issues.append(ValidationIssue(
                            'warning',
                            'unquoted_link',
                            f'Line {line_num}: Wiki-link should be quoted to avoid YAML parsing issues'
                        ))

        return issues

    def _validate_no_markdown(self, frontmatter_text: str) -> List[ValidationIssue]:
        """Check for Markdown syntax in property values (not supported)."""
        issues = []

        try:
            parsed = yaml.safe_load(frontmatter_text)
            if not isinstance(parsed, dict):
                return issues

            # Check for common Markdown patterns in values
            markdown_patterns = [
                (r'\*\*.*\*\*', 'bold'),
                (r'\*.*\*', 'italic'),
                (r'`.*`', 'code'),
                (r'^\s*#+\s', 'heading'),
                (r'^\s*-\s\[[ x]\]', 'checkbox'),
            ]

            for key, value in parsed.items():
                if not isinstance(value, str):
                    continue

                for pattern, md_type in markdown_patterns:
                    if re.search(pattern, value, re.MULTILINE):
                        issues.append(ValidationIssue(
                            'warning',
                            'markdown_in_property',
                            f"Property '{key}' contains Markdown ({md_type}), which is not supported in property values"
                        ))
                        break  # Only report once per property

        except yaml.YAMLError:
            pass

        return issues

    def _validate_frontmatter_position(self, content: str, file_path: Path) -> List[ValidationIssue]:
        """Validate that frontmatter is at the very top of the file."""
        issues = []

        if not content.startswith('---'):
            # Check if there's frontmatter somewhere else in the file
            if '\n---\n' in content and '\n---' in content[content.find('\n---\n') + 5:]:
                issues.append(ValidationIssue(
                    'error',
                    'frontmatter_not_at_top',
                    'Frontmatter must be at the very top of the file (found --- delimiters but not at start)'
                ))

        return issues

    def _validate_file(self, file_path: Path, vault_root: Path) -> List[ValidationIssue]:
        """Validate a single file's frontmatter."""
        all_issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check frontmatter position
            all_issues.extend(self._validate_frontmatter_position(content, file_path))

            # Extract frontmatter
            frontmatter_text, body, start_line, end_line = self._extract_frontmatter_raw(content)

            if frontmatter_text is None:
                # No frontmatter found - add as warning
                all_issues.append(ValidationIssue(
                    'warning',
                    'missing_frontmatter',
                    'File does not contain YAML frontmatter'
                ))
                return all_issues

            # Validate YAML syntax
            all_issues.extend(self._validate_yaml_syntax(frontmatter_text))

            # If YAML is valid, run additional checks
            syntax_errors = [i for i in all_issues if i.issue_type == 'yaml_syntax_error']
            if not syntax_errors:
                all_issues.extend(self._validate_property_names(frontmatter_text))
                all_issues.extend(self._validate_tags(frontmatter_text))
                all_issues.extend(self._validate_links(frontmatter_text))
                all_issues.extend(self._validate_no_markdown(frontmatter_text))

        except Exception as e:
            all_issues.append(ValidationIssue(
                'error',
                'file_read_error',
                f'Error reading file: {str(e)}'
            ))

        return all_issues

    def _validate_directory(self, directory: Path, vault_root: Path) -> Dict[str, List[ValidationIssue]]:
        """Validate all markdown files in a directory."""
        issues_by_file = {}
        total_files = 0
        files_with_issues = 0

        print("\nValidating frontmatter...")

        # Use iter_markdown_files for memory-efficient traversal
        additional_ignores = {'Excalidraw'}
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores):
            total_files += 1
            relative_path = str(file_path.relative_to(vault_root))

            issues = self._validate_file(file_path, vault_root)

            if issues:
                issues_by_file[relative_path] = issues
                files_with_issues += 1
                error_count = sum(1 for i in issues if i.severity == 'error')
                warning_count = sum(1 for i in issues if i.severity == 'warning')
                print(f"  ✗ {relative_path}: {error_count} error(s), {warning_count} warning(s)")

        print(f"\nScanned {total_files} files, found {files_with_issues} with issues")

        return issues_by_file

    def _generate_report(self, vault_root: Path, issues_by_file: Dict[str, List[ValidationIssue]]) -> None:
        """Generate markdown report of invalid frontmatter."""
        report_path = vault_root / 'invalid-frontmatter.md'

        # Build report content
        lines = []
        lines.append("---")
        lines.append("tags:")
        lines.append("  - vault-maintenance")
        lines.append("  - validation")
        lines.append("  - no-tasks")
        lines.append("generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("---")
        lines.append("")
        lines.append("# Invalid Frontmatter Report")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Vault:** `{vault_root}`")
        lines.append("")

        # Summary
        total_files = len(issues_by_file)
        total_errors = sum(
            1 for issues in issues_by_file.values()
            for issue in issues if issue.severity == 'error'
        )
        total_warnings = sum(
            1 for issues in issues_by_file.values()
            for issue in issues if issue.severity == 'warning'
        )

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Files with issues:** {total_files}")
        lines.append(f"- **Total errors:** {total_errors}")
        lines.append(f"- **Total warnings:** {total_warnings}")
        lines.append("")

        # Files with issues
        lines.append("## Files with Issues")
        lines.append("")

        for file_path in sorted(issues_by_file.keys()):
            issues = issues_by_file[file_path]
            note_path = file_path[:-3] if file_path.endswith('.md') else file_path

            error_count = sum(1 for i in issues if i.severity == 'error')
            warning_count = sum(1 for i in issues if i.severity == 'warning')

            lines.append(f"### [[{note_path}]]")
            lines.append("")
            lines.append(f"**Errors:** {error_count} | **Warnings:** {warning_count}")
            lines.append("")

            for issue in issues:
                severity_icon = "🔴" if issue.severity == 'error' else "⚠️"
                lines.append(f"- [ ] {severity_icon} **{issue.issue_type}**: {issue.message}")

            lines.append("")

        # Write report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"\nReport generated: {report_path}")

    def _print_summary(self, issues_by_file: Dict[str, List[ValidationIssue]]) -> None:
        """Print summary of validation results."""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        if not issues_by_file:
            print("✓ All files have valid frontmatter!")
            return

        total_errors = sum(
            1 for issues in issues_by_file.values()
            for issue in issues if issue.severity == 'error'
        )
        total_warnings = sum(
            1 for issues in issues_by_file.values()
            for issue in issues if issue.severity == 'warning'
        )

        print(f"Files with issues: {len(issues_by_file)}")
        print(f"Total errors: {total_errors}")
        print(f"Total warnings: {total_warnings}")
        print("")
        print("See 'invalid-frontmatter.md' for detailed report")
