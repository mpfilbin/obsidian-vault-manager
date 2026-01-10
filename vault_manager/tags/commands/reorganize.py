#!/usr/bin/env python3
"""
Reorganize command - Suggest hierarchical reorganization of flat tags.

This command analyzes existing tags and suggests reorganization into hierarchical
structures (parent/child relationships using Obsidian's tag/subtag syntax).
"""

import json
import os
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from vault_manager.core.command import Command
from vault_manager.core.database import execute_query
from vault_manager.core.vault import get_vault_root


class ReorganizeCommand(Command):
    """Command to suggest hierarchical tag reorganization."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the reorganize command."""
        parser.add_argument(
            '--min-count',
            type=int,
            default=2,
            metavar='N',
            help='Minimum tag usage count to consider for reorganization (default: 2)'
        )
        parser.add_argument(
            '--output',
            metavar='FILE',
            default='tag-reorganization-report.md',
            help='Output markdown file (default: tag-reorganization-report.md)'
        )
        parser.add_argument(
            '--use-ai',
            action='store_true',
            help='Use AI (Claude) to suggest semantic relationships (requires ANTHROPIC_API_KEY)'
        )
        parser.add_argument(
            '--max-suggestions',
            type=int,
            default=50,
            metavar='N',
            help='Maximum number of reorganization suggestions (default: 50)'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the reorganize command to suggest tag hierarchy."""
        vault_root = get_vault_root()
        db_path = vault_root / 'vault.db'
        min_count = args.min_count
        output_file = args.output
        use_ai = args.use_ai
        max_suggestions = args.max_suggestions

        # Check if database exists
        if not db_path.exists():
            print("Error: vault.db not found. Run 'vault tags update' first.")
            sys.exit(1)

        print(f"\n{'='*60}")
        print(f"Tag Reorganization Analyzer")
        print(f"{'='*60}")
        print(f"Vault: {vault_root}")
        print(f"Minimum tag count: {min_count}")
        print(f"AI analysis: {'Enabled' if use_ai else 'Disabled (rule-based only)'}")
        print(f"Max suggestions: {max_suggestions}")
        print(f"{'='*60}\n")

        # Load tags from database
        print("Loading tags from database...")
        tags_data = self._load_tags(db_path, min_count)

        if len(tags_data) < 2:
            print(f"\nNot enough tags to analyze (found {len(tags_data)}).")
            print("Try lowering --min-count or run 'vault tags update' to refresh the database.")
            return

        print(f"Analyzing {len(tags_data)} tags...\n")

        # Separate hierarchical and flat tags
        hierarchical_tags, flat_tags = self._categorize_tags(tags_data)

        print(f"Found {len(hierarchical_tags)} hierarchical tags (with '/')")
        print(f"Found {len(flat_tags)} flat tags\n")

        # Extract existing parent tags from hierarchical structure
        existing_parents = self._extract_parent_tags(hierarchical_tags)
        print(f"Identified {len(existing_parents)} existing parent tags\n")

        # Generate suggestions
        if use_ai:
            print("Using AI to analyze semantic relationships...")
            suggestions = self._generate_ai_suggestions(
                flat_tags, existing_parents, tags_data, max_suggestions
            )
        else:
            print("Using rule-based analysis...")
            suggestions = self._generate_rule_based_suggestions(
                flat_tags, existing_parents, tags_data, max_suggestions
            )

        if not suggestions:
            print("No reorganization suggestions generated.")
            print("Try enabling AI analysis with --use-ai")
            return

        print(f"\nGenerated {len(suggestions)} reorganization suggestion(s)\n")

        # Display summary
        self._display_summary(suggestions, tags_data)

        # Generate report
        report_path = vault_root / output_file
        self._generate_report(
            report_path, suggestions, tags_data,
            hierarchical_tags, existing_parents, use_ai, min_count
        )
        print(f"\n✓ Report saved to: {report_path.name}")

    def _load_tags(self, db_path: Path, min_count: int) -> Dict[str, int]:
        """Load tags and their counts from the database."""
        results = execute_query("""
            SELECT tag, COUNT(*) as count
            FROM file_tags
            GROUP BY tag
            HAVING count >= ?
            ORDER BY count DESC
        """, (min_count,), db_path=db_path)

        return {tag: count for tag, count in results}

    def _categorize_tags(self, tags_data: Dict[str, int]) -> Tuple[List[str], List[str]]:
        """Separate hierarchical tags (with /) from flat tags."""
        hierarchical = []
        flat = []

        for tag in tags_data.keys():
            if '/' in tag:
                hierarchical.append(tag)
            else:
                flat.append(tag)

        return hierarchical, flat

    def _extract_parent_tags(self, hierarchical_tags: List[str]) -> Dict[str, List[str]]:
        """
        Extract parent tags and their children from hierarchical tags.

        Returns:
            Dict mapping parent tag to list of children
        """
        parents = {}

        for tag in hierarchical_tags:
            parts = tag.split('/')
            if len(parts) >= 2:
                parent = parts[0]
                if parent not in parents:
                    parents[parent] = []
                parents[parent].append(tag)

        return parents

    def _generate_rule_based_suggestions(
        self,
        flat_tags: List[str],
        existing_parents: Dict[str, List[str]],
        tags_data: Dict[str, int],
        max_suggestions: int
    ) -> List[Tuple[str, str, str, float]]:
        """
        Generate reorganization suggestions using rule-based analysis.

        Returns:
            List of (tag, suggested_parent, suggested_full_path, confidence) tuples
        """
        suggestions = []

        # Rule 1: Match flat tags with existing parent tags based on string similarity
        for tag in flat_tags:
            tag_lower = tag.lower()

            # Check if tag name contains or is contained by an existing parent
            for parent in existing_parents.keys():
                parent_lower = parent.lower()

                # Skip if tag and parent are too similar (likely duplicates)
                if tag_lower == parent_lower:
                    continue

                confidence = 0.0
                reason = ""

                # Tag contains parent (e.g., "software" in "software-development")
                if parent_lower in tag_lower and parent_lower != tag_lower:
                    confidence = 0.7
                    reason = f"tag contains parent keyword '{parent}'"
                # Parent contains tag (e.g., "design" in "design/principles")
                elif tag_lower in parent_lower:
                    confidence = 0.6
                    reason = f"parent contains tag keyword '{tag}'"
                # Word boundary match (e.g., "architecture" matches "software/architecture")
                elif self._has_word_overlap(tag, parent):
                    confidence = 0.5
                    reason = f"semantic overlap with '{parent}'"

                if confidence > 0:
                    suggested_path = f"{parent}/{tag}"
                    suggestions.append((tag, parent, suggested_path, confidence, reason))

        # Rule 2: Common domain patterns
        domain_patterns = {
            'software': ['development', 'engineering', 'coding', 'programming'],
            'architecture': ['distributed', 'microservices', 'patterns', 'scalability',
                            'performance', 'resiliency'],
            'security': ['owasp', 'authentication', 'encryption', 'vulnerabilities'],
            'computer-science': ['algorithms', 'data-structures', 'theory'],
            'design': ['patterns', 'principles', 'solid', 'oop', 'object-oriented'],
            'cloud': ['aws', 'azure', 'gcp', 'lambda', 'kubernetes'],
            'databases': ['sql', 'nosql', 'indexing', 'replication'],
        }

        for parent, keywords in domain_patterns.items():
            if parent in existing_parents or parent in tags_data:
                for tag in flat_tags:
                    tag_lower = tag.lower()
                    for keyword in keywords:
                        if keyword in tag_lower or tag_lower in keyword:
                            suggested_path = f"{parent}/{tag}"
                            # Avoid duplicate suggestions
                            if not any(s[0] == tag and s[1] == parent for s in suggestions):
                                suggestions.append((
                                    tag, parent, suggested_path, 0.8,
                                    f"domain pattern match: {parent} domain"
                                ))
                            break

        # Sort by confidence and limit
        suggestions.sort(key=lambda x: (x[3], tags_data.get(x[0], 0)), reverse=True)

        # Remove duplicates (keep highest confidence)
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            key = (suggestion[0], suggestion[1])  # (tag, parent)
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(suggestion)

        return unique_suggestions[:max_suggestions]

    def _has_word_overlap(self, tag1: str, tag2: str) -> bool:
        """Check if two tags share any significant words (>3 chars)."""
        words1 = set(w for w in tag1.lower().replace('-', ' ').split() if len(w) > 3)
        words2 = set(w for w in tag2.lower().replace('-', ' ').split() if len(w) > 3)
        return bool(words1 & words2)

    def _generate_ai_suggestions(
        self,
        flat_tags: List[str],
        existing_parents: Dict[str, List[str]],
        tags_data: Dict[str, int],
        max_suggestions: int
    ) -> List[Tuple[str, str, str, float, str]]:
        """
        Generate reorganization suggestions using AI analysis.

        Requires ANTHROPIC_API_KEY environment variable.

        Returns:
            List of (tag, suggested_parent, suggested_full_path, confidence, reason) tuples
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            print("\nError: anthropic package not installed.")
            print("Install with: pip install anthropic")
            print("Falling back to rule-based suggestions...\n")
            return self._generate_rule_based_suggestions(
                flat_tags, existing_parents, tags_data, max_suggestions
            )

        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("\nError: ANTHROPIC_API_KEY environment variable not set.")
            print("Falling back to rule-based suggestions...\n")
            return self._generate_rule_based_suggestions(
                flat_tags, existing_parents, tags_data, max_suggestions
            )

        client = Anthropic(api_key=api_key)

        # Prepare tag data for AI
        flat_tags_with_counts = [
            {"tag": tag, "count": tags_data[tag]}
            for tag in flat_tags
        ]
        existing_hierarchy = {
            parent: children
            for parent, children in existing_parents.items()
        }

        # Create prompt
        prompt = self._create_ai_prompt(
            flat_tags_with_counts, existing_hierarchy, max_suggestions
        )

        try:
            # Call Claude API
            print("Querying Claude API for semantic analysis...")
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse AI response
            suggestions = self._parse_ai_response(response.content[0].text)

            print(f"AI generated {len(suggestions)} suggestions")
            return suggestions[:max_suggestions]

        except Exception as e:
            print(f"\nError calling AI API: {e}")
            print("Falling back to rule-based suggestions...\n")
            return self._generate_rule_based_suggestions(
                flat_tags, existing_parents, tags_data, max_suggestions
            )

    def _create_ai_prompt(
        self,
        flat_tags: List[Dict],
        existing_hierarchy: Dict[str, List[str]],
        max_suggestions: int
    ) -> str:
        """Create the prompt for AI analysis."""
        return f"""You are analyzing an Obsidian vault's tag taxonomy to suggest hierarchical reorganization.

EXISTING HIERARCHICAL TAGS:
{json.dumps(existing_hierarchy, indent=2)}

FLAT TAGS TO REORGANIZE:
{json.dumps(flat_tags[:100], indent=2)}

TASK:
Analyze the flat tags and suggest which ones should be reorganized as children or grandchildren under existing parent tags or new parent tags. Consider:

1. Semantic relationships (e.g., "microservices" → "architecture/microservices")
2. Domain knowledge (software development, architecture, security, computer science, etc.)
3. Existing hierarchy patterns (maintain consistency)
4. Tag usage frequency (avoid reorganizing the most heavily used tags unless strongly justified)

RULES:
- Use Obsidian's tag/subtag syntax (e.g., "parent/child" or "parent/child/grandchild")
- Prefer organizing under existing parent tags when appropriate
- Suggest new parent tags only when there's a clear semantic grouping
- Provide a confidence score (0.0-1.0) and brief reason for each suggestion
- Maximum {max_suggestions} suggestions

OUTPUT FORMAT (JSON):
[
  {{
    "tag": "tag-name",
    "parent": "parent-tag-name",
    "suggested_path": "parent/tag-name",
    "confidence": 0.85,
    "reason": "Brief explanation"
  }}
]

Return ONLY the JSON array, no additional text."""

    def _parse_ai_response(self, response_text: str) -> List[Tuple[str, str, str, float, str]]:
        """Parse AI response into suggestion tuples."""
        try:
            # Extract JSON from response (handle potential markdown code blocks)
            response_text = response_text.strip()
            if response_text.startswith('```'):
                # Remove markdown code block markers
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])

            suggestions_json = json.loads(response_text)

            suggestions = []
            for item in suggestions_json:
                suggestions.append((
                    item['tag'],
                    item['parent'],
                    item['suggested_path'],
                    item['confidence'],
                    item['reason']
                ))

            return suggestions

        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse AI response as JSON: {e}")
            print("Response:", response_text[:200])
            return []

    def _display_summary(
        self,
        suggestions: List[Tuple[str, str, str, float, str]],
        tags_data: Dict[str, int]
    ) -> None:
        """Display summary of top suggestions."""
        print(f"{'='*60}")
        print("TOP REORGANIZATION SUGGESTIONS")
        print(f"{'='*60}\n")

        # Show top 10
        for i, (tag, parent, suggested_path, confidence, reason) in enumerate(suggestions[:10], 1):
            count = tags_data.get(tag, 0)
            print(f"{i}. {tag} ({count} files) → {suggested_path}")
            print(f"   Confidence: {confidence:.0%}")
            print(f"   Reason: {reason}")
            print(f"   Command: vault tags rename {tag} {suggested_path}")
            print()

        if len(suggestions) > 10:
            print(f"... and {len(suggestions) - 10} more suggestions in the report\n")

    def _generate_report(
        self,
        report_path: Path,
        suggestions: List[Tuple[str, str, str, float, str]],
        tags_data: Dict[str, int],
        hierarchical_tags: List[str],
        existing_parents: Dict[str, List[str]],
        use_ai: bool,
        min_count: int
    ) -> None:
        """Generate markdown report."""
        lines = []

        # Header
        lines.append("---")
        lines.append("tags:")
        lines.append("  - vault-management")
        lines.append("  - tag-reorganization")
        lines.append("---")
        lines.append("")
        lines.append("# Tag Reorganization Report")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Analysis method:** {'AI-powered (Claude)' if use_ai else 'Rule-based'}")
        lines.append(f"**Minimum tag count:** {min_count}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total reorganization suggestions:** {len(suggestions)}")
        lines.append(f"- **Existing hierarchical tags:** {len(hierarchical_tags)}")
        lines.append(f"- **Existing parent tags:** {len(existing_parents)}")
        lines.append("")

        # Current hierarchy
        if existing_parents:
            lines.append("## Current Tag Hierarchy")
            lines.append("")
            for parent in sorted(existing_parents.keys()):
                children = existing_parents[parent]
                lines.append(f"### {parent}")
                lines.append("")
                for child in sorted(children):
                    lines.append(f"- `{child}`")
                lines.append("")

        # Suggestions table
        lines.append("## Reorganization Suggestions")
        lines.append("")
        lines.append("| Tag | Files | Suggested Path | Confidence | Reason | Command |")
        lines.append("|-----|-------|----------------|------------|--------|---------|")

        for tag, parent, suggested_path, confidence, reason in suggestions:
            count = tags_data.get(tag, 0)
            command = f"`vault tags rename {tag} {suggested_path}`"
            lines.append(f"| `{tag}` | {count} | `{suggested_path}` | {confidence:.0%} | {reason} | {command} |")

        lines.append("")

        # Usage instructions
        lines.append("## How to Apply")
        lines.append("")
        lines.append("Review the suggestions above and apply them using the provided commands:")
        lines.append("")
        lines.append("```bash")
        lines.append("# Preview a reorganization (dry run)")
        if suggestions:
            example_tag = suggestions[0][0]
            example_path = suggestions[0][2]
            lines.append(f"vault tags rename {example_tag} {example_path} --dry-run")
        lines.append("")
        lines.append("# Apply a reorganization")
        if suggestions:
            lines.append(f"vault tags rename {example_tag} {example_path}")
        lines.append("```")
        lines.append("")
        lines.append("**Note:** Always use `--dry-run` first to preview changes before applying them.")
        lines.append("")

        # Write report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
