"""
Add command - AI-powered tag generation.

This module implements the add command which uses Claude API to generate
appropriate tags for markdown files.
"""

import os
import re
import sys
import textwrap
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from vault_manager.core.database import VaultDatabase
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.vault import iter_markdown_files

from ..common import extract_tags_from_frontmatter, is_valid_obsidian_tag
from . import Command

# Try to import anthropic for AI features
try:
    from anthropic import Anthropic

    HAS_ANTHROPIC = True
except ImportError:
    Anthropic = None
    HAS_ANTHROPIC = False


class AddCommand(Command):
    """Command to AI-generate and add tags to markdown files."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the add command."""
        parser.add_argument(
            "directory",
            help='Directory to process (relative to vault root, use "." for entire vault)',
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Preview changes without modifying files"
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing tags instead of skipping files with tags",
        )

    def execute(self, args: Namespace) -> None:
        """Execute the add command to AI-generate tags."""
        # Check for anthropic library
        if not HAS_ANTHROPIC:
            print("Error: anthropic library not installed")
            print("\nInstall it with:")
            print("  pip install anthropic")
            sys.exit(1)

        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY environment variable not set")
            print("\nSet it with:")
            print("  export ANTHROPIC_API_KEY='your-api-key'")
            sys.exit(1)

        # Get database instance
        db = VaultDatabase()
        vault_root = db.vault_root

        # Resolve directory path
        if args.directory == ".":
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

        # Check for database and build hierarchy
        has_database = db.exists()

        # Count tags in hierarchy if available
        hierarchy_info = "Not found - using default tag list"
        if has_database:
            hierarchy = self._build_tag_hierarchy_from_database(db, min_count=1)
            if hierarchy:
                tag_count = self._count_tags_in_hierarchy(hierarchy)
                hierarchy_info = f"Found - using complete tag taxonomy ({tag_count} tags)"
            else:
                hierarchy_info = "Found but empty - using default tag list"

        # Display header
        print("=" * 60)
        print("Add AI-Generated Tags to Markdown Files")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        print(
            f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}"
        )
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Overwrite: {'Yes' if args.overwrite else 'No (skip files with tags)'}")
        print(f"Tag database: {hierarchy_info}")
        print("Max recursion depth: 5 subdirectories")
        print("Ignored directories: .obsidian, .trash, Excalidraw")
        print("Ignored file types: .excalidraw.md")
        print("Privacy: Skipping notes with 'sensitive: true' in frontmatter")

        # Process directory
        with DryRunContext(args.dry_run) as ctx:
            self._process_directory(target_dir, vault_root, db, api_key, ctx, args.overwrite)

            # Print custom summary
            self._print_custom_summary(ctx)

            # Print standard dry-run summary
            print_dry_run_summary(ctx)

            if not args.dry_run and ctx.stats.files_processed > 0:
                print(
                    f"\nDone! Processed {ctx.stats.files_processed} file{'s' if ctx.stats.files_processed != 1 else ''}."
                )
            elif args.dry_run and ctx.stats.files_processed > 0:
                print(
                    f"\nDry run complete. {ctx.stats.files_processed} file{'s' if ctx.stats.files_processed != 1 else ''} would be processed."
                )
            else:
                print("\nNo files processed.")

    def _get_top_tags_from_database(self, db: VaultDatabase, limit: int = 10) -> List[str]:
        """
        Query the vault.db database for the most used tags (3NF: compute file_count).

        Args:
            db: VaultDatabase instance
            limit: Number of top tags to retrieve (default: 10)

        Returns:
            List of top tag names, or empty list if database doesn't exist
        """
        # If database doesn't exist, return empty list
        if not db.exists():
            return []

        try:
            # 3NF: Compute file_count from file_tags table
            with db:
                results = db.query(
                    """
                    SELECT ft.tag
                    FROM file_tags ft
                    GROUP BY ft.tag
                    ORDER BY COUNT(*) DESC, ft.tag ASC
                    LIMIT ?
                """,
                    (limit,),
                )

            return [tag for (tag,) in results]

        except Exception:
            # If there's any database error, return empty list
            return []

    def _build_tag_hierarchy_from_database(self, db: VaultDatabase, min_count: int = 2) -> Dict:
        """
        Build hierarchical tag structure from vault.db using slash notation.

        Parses nested tags (e.g., 'software-development/design-principles/solid')
        and builds a nested dictionary structure with usage counts.

        Args:
            db: VaultDatabase instance
            min_count: Minimum tag usage count to include (default: 2, filters rare tags)

        Returns:
            Nested dictionary representing tag hierarchy with counts
            Example: {'software-development': {'count': 54, 'children': {...}}}
        """
        if not db.exists():
            return {}

        try:
            # Get all tags with their counts
            with db:
                tags_with_counts = db.query(
                    """
                    SELECT ft.tag, COUNT(*) as count
                    FROM file_tags ft
                    GROUP BY ft.tag
                    HAVING count >= ?
                    ORDER BY count DESC, ft.tag ASC
                """,
                    (min_count,),
                )

            # Build hierarchy
            hierarchy = {}

            for tag, count in tags_with_counts:
                self._add_tag_to_hierarchy(hierarchy, tag, count)

            return hierarchy

        except Exception:
            # If there's any database error, return empty dict
            return {}

    def _add_tag_to_hierarchy(self, hierarchy: Dict, tag: str, count: int) -> None:
        """
        Add a tag (potentially nested with slashes) to the hierarchy.

        Args:
            hierarchy: The hierarchy dictionary to modify
            tag: Tag name (e.g., 'software-development/design-principles/solid')
            count: Usage count for this tag
        """
        parts = tag.split("/")
        current = hierarchy

        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {}

            # If this is the last part, set the count
            if i == len(parts) - 1:
                current[part]["count"] = count
            else:
                # Navigate to children, creating if needed
                if "children" not in current[part]:
                    current[part]["children"] = {}
                    # Initialize parent count if not set
                    if "count" not in current[part]:
                        current[part]["count"] = 0
                current = current[part]["children"]

    def _format_hierarchy_as_json(self, hierarchy: Dict, max_tokens: int = 400) -> str:
        """
        Format hierarchy as compact JSON string for LLM prompt.

        Iteratively prunes low-frequency tags until token budget is met.

        Args:
            hierarchy: Nested dictionary with tag hierarchy
            max_tokens: Maximum token budget (approximate)

        Returns:
            JSON string representation of hierarchy
        """
        import json

        # Try full hierarchy first (with indentation)
        full_json = json.dumps(hierarchy, indent=2, sort_keys=False)
        estimated_tokens = len(full_json) // 4  # Rough token estimate

        if estimated_tokens <= max_tokens:
            return full_json

        # Try compact format (no indentation)
        compact_json = json.dumps(hierarchy, separators=(",", ":"), sort_keys=False)
        estimated_tokens = len(compact_json) // 4

        if estimated_tokens <= max_tokens:
            return compact_json

        # Iteratively prune until we fit the budget
        # Try progressively higher thresholds: 5, 10, 15, 20
        for min_count in [5, 10, 15, 20, 30]:
            pruned = self._prune_hierarchy(hierarchy, min_count=min_count)

            if not pruned:  # If we pruned everything, use previous threshold
                break

            # Try compact format first for pruned hierarchy
            pruned_json = json.dumps(pruned, separators=(",", ":"), sort_keys=False)
            estimated_tokens = len(pruned_json) // 4

            if estimated_tokens <= max_tokens:
                # Use pretty format if it also fits
                pretty_json = json.dumps(pruned, indent=2, sort_keys=False)
                if len(pretty_json) // 4 <= max_tokens:
                    return pretty_json
                return pruned_json

        # Last resort: return most aggressive pruning with compact format
        final_pruned = self._prune_hierarchy(hierarchy, min_count=10)
        return json.dumps(final_pruned, separators=(",", ":"), sort_keys=False)

    def _prune_hierarchy(self, hierarchy: Dict, min_count: int) -> Dict:
        """
        Remove tags with count < min_count to reduce token usage.

        Args:
            hierarchy: Nested dictionary with tag hierarchy
            min_count: Minimum count threshold

        Returns:
            Pruned hierarchy dictionary
        """
        pruned = {}

        for tag, data in hierarchy.items():
            if isinstance(data, dict) and data.get("count", 0) >= min_count:
                pruned[tag] = {"count": data["count"]}

                if "children" in data:
                    pruned_children = self._prune_hierarchy(data["children"], min_count)
                    if pruned_children:
                        pruned[tag]["children"] = pruned_children

        return pruned

    def _count_tags_in_hierarchy(self, hierarchy: Dict) -> int:
        """
        Count total number of tags in hierarchy (including nested).

        Args:
            hierarchy: Nested dictionary with tag hierarchy

        Returns:
            Total count of tags
        """
        count = 0

        for tag, data in hierarchy.items():
            count += 1  # Count this tag

            if isinstance(data, dict) and "children" in data:
                count += self._count_tags_in_hierarchy(data["children"])

        return count

    def _extract_frontmatter_with_tags(
        self, content: str
    ) -> Tuple[Optional[str], str, Optional[List[str]]]:
        """
        Extract YAML frontmatter from markdown content and check for existing tags.

        Returns:
            Tuple of (frontmatter, body, existing_tags)
        """
        frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            return None, content, None

        frontmatter = match.group(1)
        body = content[match.end() :]

        # Check if tags already exist using the existing function
        existing_tags = extract_tags_from_frontmatter(content)
        return frontmatter, body, existing_tags if existing_tags else None

    def _generate_ai_tags(
        self, content: str, api_key: str, db: VaultDatabase
    ) -> Tuple[List[str], List[str]]:
        """
        Generate tags using Claude API with hierarchical tag structure.

        Args:
            content: Full markdown content (including frontmatter)
            api_key: Anthropic API key
            db: VaultDatabase instance

        Returns:
            Tuple of (valid_tags, filtered_tags)
            - valid_tags: List of valid tags that passed Obsidian validation
            - filtered_tags: List of invalid tags that were filtered out
        """
        client = Anthropic(api_key=api_key)

        # Build tag hierarchy from database (include ALL tags)
        hierarchy = self._build_tag_hierarchy_from_database(db, min_count=1)

        # Build the tags section of the prompt
        if hierarchy:
            # Use larger token budget to accommodate all tags (~2400 tokens for 366 tags)
            hierarchy_json = self._format_hierarchy_as_json(hierarchy, max_tokens=3000)
            tags_section = textwrap.dedent(
                f"""
                The vault uses a hierarchical tagging system. Here is the complete tag
                taxonomy in JSON format:

                {hierarchy_json}

                Tag Format Rules:
                1. Nested tags use SLASH notation: parent/child/grandchild
                   (e.g., "software-development/design-principles/solid")
                2. You can use tags at any level: leaf tags, parent tags, or full paths
                3. The "count" field shows usage frequency - prefer frequently-used tags
                4. ONLY use tags that exist in the hierarchy above - do NOT invent new tags

                Tag Selection Guidelines:
                - Prefer specific child tags over generic parent tags when appropriate
                - Use full slash paths for precision
                  (e.g., "software-architecture/distributed/microservices")
                - Choose 3-4 tags that accurately classify the note's content
                - Use kebab-case for all tag components

                Examples of VALID tag formats:
                - "software-development/design-principles/solid" (full path)
                - "security/owasp" (parent/child)
                - "software-architecture" (parent only)
                - "books" (standalone tag)
                """
            ).strip()
        else:
            # Fallback if database doesn't exist or has no tags
            tags_section = textwrap.dedent(
                """
                The vault uses a comprehensive tagging system. Common high-value tags
                include:
                - software-architecture, software-development, security, owasp,
                  computer-science
                - design-principles, solid, algorithms, databases, cloud, aws
                - mocs (Maps of Content), books, courses, tools, documentation

                Use kebab-case and prefer specific, established tags.
                """
            ).strip()

        prompt = textwrap.dedent(
            f"""
            Analyze this Obsidian markdown note and generate appropriate tags for it.

            {tags_section}

            CRITICAL - Obsidian Tag Validation Rules:
            - Tags must only contain: letters, numbers, underscore (_), hyphen (-), slash (/)
            - Tags must contain at least one letter or underscore (cannot be all numeric)
            - For nested tags, EACH component must follow these rules
            - Examples of INVALID tags: 2024, 1984, 123 (all numeric)
            - Examples of VALID nested tags: software-development/design-principles,
              security/owasp/mobile

            Return ONLY the tags as a comma-separated list, nothing else.
            Use slash notation for nested tags from the hierarchy.

            Example return format: software-architecture/distributed/microservices,
            design-principles/solid, security/owasp, books

            Note content:
            {content}
            """
        ).strip()

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse the response
        response = message.content[0].text.strip()
        tags = [tag.strip() for tag in response.split(",")]

        # Validate tags and filter out invalid ones
        valid_tags = []
        filtered_tags = []

        for tag in tags:
            # Validate nested tags - each component must be valid
            if self._is_valid_nested_tag(tag):
                valid_tags.append(tag)
            else:
                filtered_tags.append(tag)

        return valid_tags, filtered_tags

    def _is_valid_nested_tag(self, tag: str) -> bool:
        """
        Validate a potentially nested tag (with slashes).

        Each component separated by slashes must be a valid Obsidian tag.

        Args:
            tag: Tag to validate (e.g., "software-development/design-principles/solid")

        Returns:
            True if tag and all components are valid
        """
        if not tag:
            return False

        # Split by slash and validate each part
        parts = tag.split("/")

        for part in parts:
            if not is_valid_obsidian_tag(part):
                return False

        return True

    def _add_tags_to_frontmatter(self, frontmatter: str, tags: List[str]) -> str:
        """
        Add tags field to YAML frontmatter.

        Handles cases where:
        - tags property doesn't exist
        - tags property exists but is empty
        - tags property exists with values (when overwrite is used)

        Args:
            frontmatter: Existing frontmatter content
            tags: List of tags to add

        Returns:
            Updated frontmatter
        """
        import yaml

        # Parse frontmatter to check for existing tags property
        try:
            frontmatter_dict = yaml.safe_load(frontmatter) or {}

            # Remove existing 'tags' field if present (even if empty)
            # This prevents duplication when tags: exists but is empty
            if "tags" in frontmatter_dict:
                del frontmatter_dict["tags"]

            # Convert back to YAML
            frontmatter = yaml.dump(
                frontmatter_dict, default_flow_style=False, allow_unicode=True, sort_keys=False
            )
            frontmatter = frontmatter.rstrip("\n")
        except yaml.YAMLError:
            # If YAML parsing fails, proceed with simple append
            # This should rarely happen with valid frontmatter
            pass

        # Format tags as YAML list
        tags_yaml = "tags:\n" + "\n".join(f"  - {tag}" for tag in tags)

        # Add tags field at the end of frontmatter
        return f"{frontmatter}\n{tags_yaml}"

    def _update_file_with_tags(
        self, file_path: Path, tags: List[str], dry_run: bool = False
    ) -> bool:
        """
        Update a file with new tags in its frontmatter.

        Args:
            file_path: Path to markdown file
            tags: List of tags to add
            dry_run: If True, don't actually modify the file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read file content
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Extract frontmatter
            frontmatter, body, _ = self._extract_frontmatter_with_tags(content)

            if frontmatter is None:
                print(f"  Warning: No frontmatter found in {file_path}")
                return False

            # Add tags to frontmatter
            updated_frontmatter = self._add_tags_to_frontmatter(frontmatter, tags)

            # Reconstruct file
            updated_content = f"---\n{updated_frontmatter}\n---\n{body}"

            # Write back if not dry run
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)

            return True

        except Exception as e:
            print(f"  Error updating {file_path}: {e}")
            return False

    def _process_directory(
        self,
        directory: Path,
        vault_root: Path,
        db: VaultDatabase,
        api_key: str,
        ctx: DryRunContext,
        overwrite: bool = False,
        max_depth: int = 5,
    ) -> None:
        """
        Recursively process all markdown files in a directory.

        Args:
            directory: Directory to process
            vault_root: Root directory of the vault
            db: VaultDatabase instance
            api_key: Anthropic API key
            ctx: DryRunContext for tracking operations
            overwrite: If True, replace existing tags
            max_depth: Maximum depth to recurse into subdirectories (default: 5)
        """
        print(
            f"\n{'DRY RUN - ' if ctx.dry_run else ''}Processing markdown files (max depth: {max_depth})..."
        )

        # Note: iter_markdown_files uses rglob which traverses all depths
        # We'll need to manually check depth since there's no max_depth parameter
        # additional_ignores={'Excalidraw'} is handled by is_ignored_path_for_add logic
        for file_path in iter_markdown_files(
            directory, vault_root, additional_ignores={"Excalidraw"}, exclude_excalidraw=True
        ):
            # Calculate current depth relative to target directory
            try:
                relative_to_target = file_path.parent.relative_to(directory)
                current_depth = len(relative_to_target.parts)
            except ValueError:
                current_depth = 0

            # Skip if we've exceeded max depth
            if current_depth > max_depth:
                continue

            ctx.stats.increment("total_files")
            relative_path = file_path.relative_to(vault_root)

            try:
                # Read file
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # Check if note is marked as sensitive
                if FrontmatterManager.is_sensitive_note(content):
                    print(f"  Skipping (sensitive): {relative_path}")
                    ctx.stats.increment("skipped_sensitive")
                    continue

                # Extract frontmatter and check for existing tags
                frontmatter, body, existing_tags = self._extract_frontmatter_with_tags(content)

                if frontmatter is None:
                    print(f"  Skipping (no frontmatter): {relative_path}")
                    ctx.stats.increment("skipped_no_frontmatter")
                    continue

                if existing_tags and not overwrite:
                    print(f"  Skipping (has tags): {relative_path}")
                    ctx.stats.increment("skipped_has_tags")
                    continue

                # Generate tags
                print(
                    f"  {'Would generate' if ctx.dry_run else 'Generating'} tags: {relative_path}"
                )
                tags, filtered_tags = self._generate_ai_tags(content, api_key, db)

                # Track filtered tags
                if filtered_tags:
                    ctx.stats.increment("total_filtered_tags", len(filtered_tags))
                    ctx.stats.increment("files_with_filtered_tags")
                    print(f"    → Valid tags: {', '.join(tags)}")
                    print(f"    → Filtered (invalid): {', '.join(filtered_tags)}")
                else:
                    print(f"    → {', '.join(tags)}")

                # Update file
                if self._update_file_with_tags(file_path, tags, ctx.dry_run):
                    ctx.stats.increment("files_processed")
                    ctx.record_change(
                        file_path, f"Added {len(tags)} AI-generated tag(s)", tags=tags
                    )
                else:
                    ctx.stats.increment("files_failed")
                    ctx.stats.custom_stats.setdefault("failed_files", []).append(str(relative_path))

            except Exception as e:
                print(f"  Error processing {relative_path}: {e}")
                ctx.stats.increment("files_failed")
                ctx.stats.custom_stats.setdefault("failed_files", []).append(str(relative_path))

    def _print_custom_summary(self, ctx: DryRunContext) -> None:
        """Print custom summary of AI tag processing results."""
        print("\n" + "=" * 60)
        print("AI Tag Generation Details")
        print("=" * 60)
        print(f"Skipped (has tags): {ctx.stats.custom_stats.get('skipped_has_tags', 0)}")
        print(
            f"Skipped (no frontmatter): {ctx.stats.custom_stats.get('skipped_no_frontmatter', 0)}"
        )
        print(f"Skipped (sensitive): {ctx.stats.custom_stats.get('skipped_sensitive', 0)}")

        skipped_too_deep = ctx.stats.custom_stats.get("skipped_too_deep", 0)
        if skipped_too_deep > 0:
            print(f"Skipped (too deep): {skipped_too_deep}")

        # Report on filtered invalid tags
        total_filtered = ctx.stats.custom_stats.get("total_filtered_tags", 0)
        if total_filtered > 0:
            print("\nTag Validation:")
            print(
                f"Files with filtered tags: {ctx.stats.custom_stats.get('files_with_filtered_tags', 0)}"
            )
            print(f"Total invalid tags filtered: {total_filtered}")
            print("Note: Invalid tags were automatically removed (did not meet Obsidian rules)")

        failed_files = ctx.stats.custom_stats.get("failed_files", [])
        if failed_files:
            print(f"\nFailed files ({len(failed_files)}):")
            for file_path in failed_files:
                print(f"  - {file_path}")
