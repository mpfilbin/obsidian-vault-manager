"""
Summarize command - AI-generated summaries.

This module implements the summarize command which uses Claude API to generate
concise summaries for markdown files.
"""

import os
import re
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, Optional, Tuple

from . import Command
from ..common import get_vault_root
from vault_manager.core.frontmatter import is_sensitive_note
from vault_manager.core.vault import iter_markdown_files, count_markdown_files

# Try to import anthropic for AI features
try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class SummarizeCommand(Command):
    """Command to AI-generate and add summary properties to notes."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the summarize command."""
        parser.add_argument(
            'directory',
            help='Directory to process (relative to vault root, use "." for entire vault)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without modifying files'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Replace existing summaries instead of skipping files with summaries'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the summarize command to AI-generate summaries."""
        # Check for anthropic library
        if not HAS_ANTHROPIC:
            print("Error: anthropic library not installed")
            print("\nInstall it with:")
            print("  pip install anthropic")
            sys.exit(1)

        # Check for API key
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("Error: ANTHROPIC_API_KEY environment variable not set")
            print("\nSet it with:")
            print("  export ANTHROPIC_API_KEY='your-api-key'")
            sys.exit(1)

        # Get vault root
        vault_root = get_vault_root()

        # Resolve directory path
        if args.directory == '.':
            target_dir = vault_root
        else:
            target_dir = vault_root / args.directory

        # Validate directory
        if not target_dir.exists():
            print(f"Error: Directory not found: {args.directory}")
            print(f"Looking for: {target_dir}")
            sys.exit(1)

        if not target_dir.is_dir():
            print(f"Error: Not a directory: {args.directory}")
            sys.exit(1)

        # Display header
        print("=" * 60)
        print("Add AI-Generated Summaries to Markdown Files")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Overwrite: {'Yes' if args.overwrite else 'No (skip files with summaries)'}")
        print(f"Max recursion depth: 5 subdirectories")
        print(f"Ignored directories: .obsidian, .trash, Excalidraw, Calendar")
        print(f"Ignored file types: .excalidraw.md")
        print(f"Privacy: Skipping notes with 'sensitive: true' in frontmatter")

        # Process directory
        stats = self._process_directory(target_dir, vault_root, api_key, args.dry_run, args.overwrite)

        # Print summary
        self._print_summary(stats, args.dry_run)

        if not args.dry_run and stats['processed'] > 0:
            print(f"\nDone! Processed {stats['processed']} file{'s' if stats['processed'] != 1 else ''}.")
        elif args.dry_run and stats['processed'] > 0:
            print(f"\nDry run complete. {stats['processed']} file{'s' if stats['processed'] != 1 else ''} would be processed.")
        else:
            print("\nNo files processed.")

    def _extract_frontmatter_with_summary(self, content: str) -> Tuple[Optional[str], str, Optional[str]]:
        """
        Extract YAML frontmatter from markdown content.

        Returns:
            Tuple of (frontmatter, body, existing_summary)
        """
        frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            return None, content, None

        frontmatter = match.group(1)
        body = content[match.end():]

        # Check if summary already exists
        summary_match = re.search(r'^summary:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
        existing_summary = summary_match.group(1) if summary_match else None

        return frontmatter, body, existing_summary

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

    def _generate_summary(self, content: str, api_key: str) -> str:
        """
        Generate a summary using Claude API.

        Returns:
            Generated summary string (2-4 sentences)
        """
        client = Anthropic(api_key=api_key)

        prompt = f"""Analyze this Obsidian markdown note and generate a concise summary.

The summary should:
- Be 2-4 sentences long
- Capture the main concepts and key takeaways
- Mention specific technical details when relevant (design patterns, technologies, principles)
- Be informative enough to understand the note's content at a glance
- Use clear, professional language
- Use ONLY plain text - NO markdown formatting at all (no bold, italic, code, links, etc.)
- Avoid using special characters like asterisks, underscores, backticks, or brackets

Return ONLY the summary text in plain text format, nothing else.

Note content:
{content}"""

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Get the summary and strip any markdown that might have slipped through
        summary = message.content[0].text.strip()
        summary = self._strip_markdown(summary)

        return summary

    def _add_summary_to_frontmatter(self, frontmatter: str, summary: str) -> str:
        """
        Add summary field to YAML frontmatter.

        Returns:
            Updated frontmatter
        """
        # Escape quotes in summary
        summary_escaped = summary.replace('"', '\\"')

        # Add summary field at the end of frontmatter
        return f'{frontmatter}\nsummary: "{summary_escaped}"'

    def _update_file_with_summary(self, file_path: Path, summary: str, dry_run: bool = False) -> bool:
        """
        Update a file with a new summary in its frontmatter.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter
            frontmatter, body, _ = self._extract_frontmatter_with_summary(content)

            if frontmatter is None:
                print(f"  Warning: No frontmatter found in {file_path}")
                return False

            # Add summary to frontmatter
            updated_frontmatter = self._add_summary_to_frontmatter(frontmatter, summary)

            # Reconstruct file
            updated_content = f"---\n{updated_frontmatter}\n---\n{body}"

            # Write back if not dry run
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

            return True

        except Exception as e:
            print(f"  Error updating {file_path}: {e}")
            return False

    def _process_directory(self, directory: Path, vault_root: Path, api_key: str,
                          dry_run: bool = False, overwrite: bool = False, max_depth: int = 5) -> Dict:
        """
        Recursively process all markdown files in a directory.

        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'skipped_has_summary': 0,
            'skipped_no_frontmatter': 0,
            'skipped_sensitive': 0,
            'skipped_too_deep': 0,
            'processed': 0,
            'failed': 0,
            'failed_files': []
        }

        print(f"\n{'DRY RUN - ' if dry_run else ''}Processing markdown files (max depth: {max_depth})...")

        # Note: iter_markdown_files uses rglob which traverses all depths
        # We'll need to manually check depth since there's no max_depth parameter
        for file_path in iter_markdown_files(directory, vault_root, additional_ignores={'Excalidraw', 'Calendar'}, exclude_excalidraw=True):
            # Calculate current depth relative to target directory
            try:
                relative_to_target = file_path.parent.relative_to(directory)
                current_depth = len(relative_to_target.parts)
            except ValueError:
                current_depth = 0

            # Skip if we've exceeded max depth
            if current_depth > max_depth:
                continue

            stats['total_files'] += 1
            relative_path = file_path.relative_to(vault_root)

            try:
                # Read file
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check if note is marked as sensitive
                if is_sensitive_note(content):
                    print(f"  Skipping (sensitive): {relative_path}")
                    stats['skipped_sensitive'] += 1
                    continue

                # Extract frontmatter and check for existing summary
                frontmatter, body, existing_summary = self._extract_frontmatter_with_summary(content)

                if frontmatter is None:
                    print(f"  Skipping (no frontmatter): {relative_path}")
                    stats['skipped_no_frontmatter'] += 1
                    continue

                if existing_summary and not overwrite:
                    print(f"  Skipping (has summary): {relative_path}")
                    stats['skipped_has_summary'] += 1
                    continue

                # Generate summary
                print(f"  {'Would generate' if dry_run else 'Generating'} summary: {relative_path}")
                summary = self._generate_summary(content, api_key)
                print(f"    → {summary[:100]}{'...' if len(summary) > 100 else ''}")

                # Update file
                if self._update_file_with_summary(file_path, summary, dry_run):
                    stats['processed'] += 1
                else:
                    stats['failed'] += 1
                    stats['failed_files'].append(str(relative_path))

            except Exception as e:
                print(f"  Error processing {relative_path}: {e}")
                stats['failed'] += 1
                stats['failed_files'].append(str(relative_path))

        return stats

    def _print_summary(self, stats: Dict, dry_run: bool = False) -> None:
        """Print summary of processing results."""
        print("\n" + "=" * 60)
        print(f"{'DRY RUN ' if dry_run else ''}SUMMARY")
        print("=" * 60)
        print(f"Total markdown files: {stats['total_files']}")
        print(f"Skipped (has summary): {stats['skipped_has_summary']}")
        print(f"Skipped (no frontmatter): {stats['skipped_no_frontmatter']}")
        print(f"Skipped (sensitive): {stats['skipped_sensitive']}")
        if stats.get('skipped_too_deep', 0) > 0:
            print(f"Skipped (too deep): {stats['skipped_too_deep']}")
        print(f"Successfully processed: {stats['processed']}")
        print(f"Failed: {stats['failed']}")

        if stats['failed_files']:
            print(f"\nFailed files ({len(stats['failed_files'])}):")
            for file_path in stats['failed_files']:
                print(f"  - {file_path}")

        if dry_run and stats['processed'] > 0:
            print("\n" + "=" * 60)
            print("This was a DRY RUN - no files were actually modified.")
            print("Run without --dry-run to apply changes.")
            print("=" * 60)
