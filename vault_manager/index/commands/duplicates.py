"""
Duplicates command - Find and cleanup duplicate files.

This module implements the duplicates command which identifies files with
identical content (via SHA-256 hashing) and provides cleanup functionality.
"""

import re
import shutil
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict

from ...core.database import VaultDatabase
from ..common import format_file_size, get_file_extension_category
from . import Command


class DuplicatesCommand(Command):
    """Command to find and cleanup duplicate files."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the duplicates command."""
        subparsers = parser.add_subparsers(
            dest="subcommand", required=True, help="Duplicates sub-commands"
        )

        # Find subcommand
        subparsers.add_parser("find", help="Find duplicate files and generate report")

        # Cleanup subcommand
        subparsers.add_parser("cleanup", help="Move checked duplicates to .trash")

    def execute(self, args: Namespace) -> None:
        """Execute the duplicates command."""
        with VaultDatabase() as db:
            if args.subcommand == "find":
                self._find_duplicates(db)
            elif args.subcommand == "cleanup":
                self._cleanup_duplicates(db)

    def _find_duplicates(self, db: VaultDatabase) -> None:
        """Find and report duplicate files."""
        print("Finding duplicate files...")

        db.require_exists("index duplicates find")

        # Query duplicate groups from database using centralized utility
        rows = db.query("""
            SELECT f.content_hash, f.file_path, f.size_bytes
            FROM files f
            WHERE f.content_hash IN (
                SELECT content_hash
                FROM files
                WHERE content_hash IS NOT NULL
                GROUP BY content_hash
                HAVING COUNT(*) > 1
            )
            ORDER BY f.content_hash, f.file_path
        """)

        if not rows:
            print("\nNo duplicate files found!")
            print("Note: Duplicates are detected using SHA-256 content hashing.")
            print("Make sure the index was built with hashing enabled (without --no-hash flag).")
            return

        # Group by hash (3NF: compute extension from file_path)
        duplicate_groups = defaultdict(list)
        for hash_val, path, size in rows:
            ext = Path(path).suffix  # Compute extension from path
            duplicate_groups[hash_val].append({"path": path, "size": size, "ext": ext})

        print(f"Found {len(duplicate_groups)} duplicate groups")
        print(f"Total files affected: {sum(len(files) for files in duplicate_groups.values())}")

        # Generate report
        print("\nGenerating report...")
        report = self._generate_report(duplicate_groups, db)

        # Write to duplicates.md
        output_file = db.vault_root / "duplicates.md"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"✓ Report written to: {output_file}")
        print("\nNext steps:")
        print("1. Review duplicates.md")
        print("2. Check boxes next to files to remove")
        print("3. Run: vault index duplicates cleanup")

    def _get_reference_counts(self, db: VaultDatabase) -> Dict[str, int]:
        """Get incoming reference counts for all files from links table."""
        # Count incoming links for each file using centralized utility
        rows = db.query("""
            SELECT target_file, COUNT(*) as ref_count
            FROM links
            WHERE target_file IS NOT NULL
            GROUP BY target_file
        """)

        ref_counts = {row[0]: row[1] for row in rows}
        return ref_counts

    def _generate_report(self, duplicate_groups: Dict, db: VaultDatabase) -> str:
        """Generate markdown report grouped by file type."""
        # Get reference counts for all files
        ref_counts = self._get_reference_counts(db)

        # Group duplicates by extension
        by_extension = defaultdict(list)

        for hash_val, files in duplicate_groups.items():
            ext = files[0]["ext"]
            by_extension[ext].append((hash_val, files))

        # Build report header
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "---",
            "tags:",
            "  - vault-management",
            "  - duplicates",
            "  - files",
            "---",
            "",
            "# Duplicate Files",
            "",
            f"**Generated:** {now}",
            f"**Vault:** `{db.vault_root}`",
            "",
            "## Statistics",
            "",
        ]

        # Calculate statistics
        total_groups = len(duplicate_groups)
        total_files = sum(len(files) for files in duplicate_groups.values())
        total_size = sum(f["size"] for files in duplicate_groups.values() for f in files)
        waste_size = sum(
            sum(f["size"] for f in files[1:])  # All except first (which we keep)
            for files in duplicate_groups.values()
        )

        lines.extend(
            [
                f"- Duplicate groups: {total_groups}",
                f"- Files affected: {total_files}",
                f"- Total size: {format_file_size(total_size)}",
                f"- Space to reclaim: {format_file_size(waste_size)}",
                "",
                "## Duplicate Groups",
                "",
            ]
        )

        # Group by extension
        for ext in sorted(by_extension.keys()):
            ext_name = get_file_extension_category(ext).capitalize()
            lines.append(f"### {ext_name} Files ({ext})")
            lines.append("")

            for hash_val, files in by_extension[ext]:
                # Show truncated hash
                short_hash = hash_val[:12] if hash_val else "unknown"
                size_str = format_file_size(files[0]["size"])

                lines.append(
                    f"**Group** ({len(files)} copies, {size_str} each) - `{short_hash}...`"
                )
                lines.append("")
                lines.append(
                    "*First file is recommended to keep. Check boxes to mark files for deletion:*"
                )
                lines.append("")

                # First file: keep (no checkbox)
                first_refs = ref_counts.get(files[0]["path"], 0)
                ref_text = (
                    f" - **Referenced by {first_refs} file(s)**"
                    if first_refs > 0
                    else " - Not referenced"
                )
                lines.append(f"- **KEEP:** [[{files[0]['path']}]]{ref_text}")

                # Remaining files: checkboxes for removal
                for file_info in files[1:]:
                    file_refs = ref_counts.get(file_info["path"], 0)
                    ref_text = (
                        f" - Referenced by {file_refs} file(s)"
                        if file_refs > 0
                        else " - Not referenced"
                    )
                    lines.append(f"- [ ] [[{file_info['path']}]]{ref_text}")

                lines.append("")

        # Add instructions
        lines.extend(
            [
                "---",
                "",
                "## Instructions",
                "",
                "1. Review each duplicate group above",
                "2. Check `[ ]` boxes next to files you want to **REMOVE**",
                "3. The first file in each group is marked **KEEP** (recommended)",
                "4. Run: `vault index duplicates cleanup`",
                "5. Checked files will be moved to `.trash`",
                "",
                "---",
                "",
                "*Generated by `vault index duplicates find`*",
            ]
        )

        return "\n".join(lines) + "\n"

    def _cleanup_duplicates(self, db: VaultDatabase) -> None:
        """Move checked duplicates to .trash."""
        print("Cleaning up duplicates...")

        report_file = db.vault_root / "duplicates.md"

        if not report_file.exists():
            print(f"Error: duplicates.md not found at {report_file}")
            print("Run 'vault index duplicates find' first to generate the report.")
            return

        # Parse report for checked items
        with open(report_file, encoding="utf-8") as f:
            content = f.read()

        # Extract checked items: - [x] [[path]]
        pattern = r"^\s*- \[x\] \[\[([^\]]+)\]\]"
        checked_files = []

        for line in content.split("\n"):
            match = re.match(pattern, line)
            if match:
                checked_files.append(match.group(1))

        if not checked_files:
            print("No files checked for removal.")
            print("Please check boxes in duplicates.md next to files you want to remove.")
            return

        print(f"Found {len(checked_files)} files marked for removal")

        # Create .trash directory
        trash_dir = db.vault_root / ".trash"
        trash_dir.mkdir(exist_ok=True)

        # Move files
        moved_files = []
        failed_files = []

        for file_path in checked_files:
            source = db.vault_root / file_path

            if not source.exists():
                print(f"  Warning: File not found: {file_path}")
                failed_files.append(file_path)
                continue

            # Preserve directory structure in .trash
            relative_path = Path(file_path)
            target = trash_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)

            try:
                shutil.move(str(source), str(target))
                moved_files.append(file_path)
                print(f"  ✓ Moved: {file_path}")
            except Exception as e:
                failed_files.append(file_path)
                print(f"  ✗ Error moving {file_path}: {e}")

        # Update report (remove moved items)
        if moved_files:
            new_lines = []
            for line in content.split("\n"):
                # Skip checked lines that were successfully moved
                match = re.match(pattern, line)
                if match and match.group(1) in moved_files:
                    continue
                new_lines.append(line)

            with open(report_file, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))

        # Print summary
        print("\n" + "=" * 60)
        print("Cleanup Summary")
        print("=" * 60)
        print(f"Successfully moved: {len(moved_files)} files")
        print(f"Failed: {len(failed_files)} files")
        print(f"Trash location: {trash_dir}")

        if moved_files:
            # Calculate space reclaimed
            space_reclaimed = 0
            for file_path in moved_files:
                trash_file = trash_dir / file_path
                if trash_file.exists():
                    space_reclaimed += trash_file.stat().st_size

            print(f"Space reclaimed: {format_file_size(space_reclaimed)}")
            print("\nReport updated: duplicates.md")
