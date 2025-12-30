#!/usr/bin/env python3
"""
Similar command - Find similar tags that might be duplicates, typos, or consolidation candidates.

This command analyzes all tags in the vault and identifies pairs of similar tags
that could indicate typos, plurals, or opportunities for consolidation.
"""

import sqlite3
import sys
from argparse import ArgumentParser, Namespace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

from vault_manager.core.command import Command
from vault_manager.core.vault import get_vault_root


class SimilarCommand(Command):
    """Command to find similar tags for consolidation."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the similar command."""
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.8,
            metavar='RATIO',
            help='Similarity threshold 0.0-1.0 (default: 0.8, higher = more similar required)'
        )
        parser.add_argument(
            '--min-count',
            type=int,
            default=1,
            metavar='N',
            help='Minimum tag usage count to consider (default: 1, ignore rare tags with --min-count 2)'
        )
        parser.add_argument(
            '--output',
            metavar='FILE',
            help='Save report to markdown file (default: display only)'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the similar command to find similar tags."""
        vault_root = get_vault_root()
        db_path = vault_root / 'vault.db'
        threshold = args.threshold
        min_count = args.min_count
        output_file = args.output

        # Validate threshold
        if not 0.0 <= threshold <= 1.0:
            print("Error: Threshold must be between 0.0 and 1.0")
            sys.exit(1)

        # Check if database exists
        if not db_path.exists():
            print("Error: vault.db not found. Run 'vault tags update' first.")
            sys.exit(1)

        print(f"\n{'='*60}")
        print(f"Tag Similarity Finder")
        print(f"{'='*60}")
        print(f"Vault: {vault_root}")
        print(f"Similarity threshold: {threshold}")
        print(f"Minimum tag count: {min_count}")
        print(f"{'='*60}\n")

        # Load tags from database
        print("Loading tags from database...")
        tags_data = self._load_tags(db_path, min_count)

        if len(tags_data) < 2:
            print(f"\nNot enough tags to compare (found {len(tags_data)}).")
            print("Try lowering --min-count or run 'vault tags update' to refresh the database.")
            return

        print(f"Analyzing {len(tags_data)} tags...\n")

        # Find similar pairs
        similar_pairs = self._find_similar_pairs(tags_data, threshold)

        if not similar_pairs:
            print(f"No similar tags found above threshold {threshold}.")
            print("Try lowering the threshold with --threshold 0.7")
            return

        # Categorize and display results
        categorized = self._categorize_pairs(similar_pairs, tags_data)
        self._display_results(categorized, tags_data)

        # Generate report if requested
        if output_file:
            report_path = vault_root / output_file
            self._generate_report(report_path, categorized, tags_data, threshold, min_count)
            print(f"\n✓ Report saved to: {report_path.name}")

    def _load_tags(self, db_path: Path, min_count: int) -> Dict[str, int]:
        """
        Load tags and their counts from the database.

        Args:
            db_path: Path to vault.db
            min_count: Minimum usage count to include

        Returns:
            Dictionary mapping tag name to count
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query tags with counts
        cursor.execute("""
            SELECT tag, COUNT(*) as count
            FROM file_tags
            GROUP BY tag
            HAVING count >= ?
            ORDER BY tag
        """, (min_count,))

        tags_data = {tag: count for tag, count in cursor.fetchall()}
        conn.close()

        return tags_data

    def _find_similar_pairs(
        self,
        tags_data: Dict[str, int],
        threshold: float
    ) -> List[Tuple[str, str, float]]:
        """
        Find pairs of similar tags above the threshold.

        Args:
            tags_data: Dictionary of tag -> count
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            List of (tag1, tag2, similarity) tuples sorted by similarity descending
        """
        similar_pairs = []
        tags = list(tags_data.keys())

        # Compare each pair of tags
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                tag1, tag2 = tags[i], tags[j]
                similarity = self._calculate_similarity(tag1, tag2)

                if similarity >= threshold:
                    similar_pairs.append((tag1, tag2, similarity))

        # Sort by similarity descending
        similar_pairs.sort(key=lambda x: x[2], reverse=True)

        return similar_pairs

    def _calculate_similarity(self, tag1: str, tag2: str) -> float:
        """
        Calculate similarity ratio between two tags.

        Args:
            tag1: First tag
            tag2: Second tag

        Returns:
            Similarity ratio (0.0-1.0)
        """
        return SequenceMatcher(None, tag1, tag2).ratio()

    def _categorize_pairs(
        self,
        similar_pairs: List[Tuple[str, str, float]],
        tags_data: Dict[str, int]
    ) -> Dict[str, List[Tuple[str, str, float]]]:
        """
        Categorize similar pairs by type.

        Args:
            similar_pairs: List of (tag1, tag2, similarity) tuples
            tags_data: Tag counts

        Returns:
            Dictionary categorizing pairs
        """
        categorized = {
            'case_only': [],      # Only differ in case
            'likely_typo': [],    # High similarity, likely typo
            'plural': [],         # Likely singular/plural
            'similar': []         # Generally similar
        }

        for tag1, tag2, similarity in similar_pairs:
            # Case difference only
            if tag1.lower() == tag2.lower():
                categorized['case_only'].append((tag1, tag2, similarity))
            # Very high similarity - likely typo
            elif similarity >= 0.92:
                categorized['likely_typo'].append((tag1, tag2, similarity))
            # Check for plural pattern
            elif self._is_plural_pair(tag1, tag2):
                categorized['plural'].append((tag1, tag2, similarity))
            # Generally similar
            else:
                categorized['similar'].append((tag1, tag2, similarity))

        return categorized

    def _is_plural_pair(self, tag1: str, tag2: str) -> bool:
        """
        Check if tags are likely singular/plural variants.

        Args:
            tag1: First tag
            tag2: Second tag

        Returns:
            True if likely plural pair
        """
        # Simple heuristic: one ends with 's' and removing it matches the other
        if tag1.endswith('s') and tag1[:-1] == tag2:
            return True
        if tag2.endswith('s') and tag2[:-1] == tag1:
            return True

        # Check for -es plural
        if tag1.endswith('es') and tag1[:-2] == tag2:
            return True
        if tag2.endswith('es') and tag2[:-2] == tag1:
            return True

        return False

    def _display_results(
        self,
        categorized: Dict[str, List[Tuple[str, str, float]]],
        tags_data: Dict[str, int]
    ) -> None:
        """Display categorized results to console."""
        total_pairs = sum(len(pairs) for pairs in categorized.values())

        print(f"Found {total_pairs} similar tag pair(s)\n")

        # Case differences
        if categorized['case_only']:
            print(f"{'='*60}")
            print(f"CASE DIFFERENCES ({len(categorized['case_only'])})")
            print(f"{'='*60}")
            print("Tags that differ only in casing:\n")

            for tag1, tag2, similarity in categorized['case_only']:
                count1, count2 = tags_data[tag1], tags_data[tag2]
                print(f"  • {tag1} ({count1} files) ↔ {tag2} ({count2} files)")
                print(f"    Similarity: {similarity:.2%}")
                # Suggest keeping the more common one
                keep, rename = (tag1, tag2) if count1 >= count2 else (tag2, tag1)
                print(f"    → vault tags rename {rename} {keep}")
                print()

        # Likely typos
        if categorized['likely_typo']:
            print(f"{'='*60}")
            print(f"LIKELY TYPOS ({len(categorized['likely_typo'])})")
            print(f"{'='*60}")
            print("Very similar tags - possible typos:\n")

            for tag1, tag2, similarity in categorized['likely_typo']:
                count1, count2 = tags_data[tag1], tags_data[tag2]
                print(f"  • {tag1} ({count1} files) ↔ {tag2} ({count2} files)")
                print(f"    Similarity: {similarity:.2%}")
                # Suggest keeping the more common one
                keep, rename = (tag1, tag2) if count1 >= count2 else (tag2, tag1)
                print(f"    → vault tags rename {rename} {keep}")
                print()

        # Plurals
        if categorized['plural']:
            print(f"{'='*60}")
            print(f"SINGULAR/PLURAL ({len(categorized['plural'])})")
            print(f"{'='*60}")
            print("Tags that appear to be singular/plural variants:\n")

            for tag1, tag2, similarity in categorized['plural']:
                count1, count2 = tags_data[tag1], tags_data[tag2]
                print(f"  • {tag1} ({count1} files) ↔ {tag2} ({count2} files)")
                print(f"    Similarity: {similarity:.2%}")
                # Suggest keeping the more common one
                keep, rename = (tag1, tag2) if count1 >= count2 else (tag2, tag1)
                print(f"    → vault tags rename {rename} {keep}")
                print()

        # Similar
        if categorized['similar']:
            print(f"{'='*60}")
            print(f"SIMILAR TAGS ({len(categorized['similar'])})")
            print(f"{'='*60}")
            print("Tags with high similarity - consider consolidating:\n")

            for tag1, tag2, similarity in categorized['similar']:
                count1, count2 = tags_data[tag1], tags_data[tag2]
                print(f"  • {tag1} ({count1} files) ↔ {tag2} ({count2} files)")
                print(f"    Similarity: {similarity:.2%}")
                # Suggest keeping the more common one
                keep, rename = (tag1, tag2) if count1 >= count2 else (tag2, tag1)
                print(f"    → vault tags rename {rename} {keep}")
                print()

        print(f"{'='*60}")
        print(f"\nTip: Review suggestions and use 'vault tags rename --dry-run' to preview changes")

    def _generate_report(
        self,
        report_path: Path,
        categorized: Dict[str, List[Tuple[str, str, float]]],
        tags_data: Dict[str, int],
        threshold: float,
        min_count: int
    ) -> None:
        """Generate markdown report."""
        from datetime import datetime

        lines = []

        # Header
        lines.append("---")
        lines.append("tags:")
        lines.append("  - vault-management")
        lines.append("  - tag-similarity")
        lines.append("---")
        lines.append("")
        lines.append("# Tag Similarity Report")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Threshold:** {threshold}")
        lines.append(f"**Minimum count:** {min_count}")
        lines.append("")

        # Summary
        total_pairs = sum(len(pairs) for pairs in categorized.values())
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total similar pairs:** {total_pairs}")
        lines.append(f"- **Case differences:** {len(categorized['case_only'])}")
        lines.append(f"- **Likely typos:** {len(categorized['likely_typo'])}")
        lines.append(f"- **Singular/plural:** {len(categorized['plural'])}")
        lines.append(f"- **Similar tags:** {len(categorized['similar'])}")
        lines.append("")

        # Details for each category
        categories = [
            ('case_only', 'Case Differences', 'Tags that differ only in casing'),
            ('likely_typo', 'Likely Typos', 'Very similar tags - possible typos'),
            ('plural', 'Singular/Plural', 'Singular and plural variants'),
            ('similar', 'Similar Tags', 'Tags with high similarity')
        ]

        for category_key, title, description in categories:
            if categorized[category_key]:
                lines.append(f"## {title}")
                lines.append("")
                lines.append(description)
                lines.append("")
                lines.append("| Tag 1 | Files | Tag 2 | Files | Similarity | Suggested Action |")
                lines.append("|-------|-------|-------|-------|------------|------------------|")

                for tag1, tag2, similarity in categorized[category_key]:
                    count1, count2 = tags_data[tag1], tags_data[tag2]
                    keep, rename = (tag1, tag2) if count1 >= count2 else (tag2, tag1)
                    suggestion = f"`vault tags rename {rename} {keep}`"
                    lines.append(f"| `{tag1}` | {count1} | `{tag2}` | {count2} | {similarity:.2%} | {suggestion} |")

                lines.append("")

        # Write report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
