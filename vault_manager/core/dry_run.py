"""
Dry-run infrastructure for standardized operation tracking and preview mode.

This module provides utilities for tracking operations and implementing consistent
dry-run behavior across all commands that modify files.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path


@dataclass
class OperationStats:
    """
    Track statistics for dry-run and live operations.

    Attributes:
        total_files: Total number of files scanned
        files_processed: Number of files processed
        files_modified: Number of files modified
        files_skipped: Number of files skipped
        files_failed: Number of files that failed to process
        custom_stats: Dictionary for command-specific statistics

    Examples:
        >>> stats = OperationStats()
        >>> stats.increment('files_processed')
        >>> stats.increment('tags_added', 5)
        >>> stats.to_dict()
        {'total_files': 0, 'files_processed': 1, 'files_modified': 0,
         'files_skipped': 0, 'files_failed': 0, 'tags_added': 5}
    """
    total_files: int = 0
    files_processed: int = 0
    files_modified: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    custom_stats: Dict[str, Any] = field(default_factory=dict)

    def increment(self, stat: str, amount: int = 1) -> None:
        """
        Increment a statistic by the given amount.

        Args:
            stat: Name of the statistic to increment
            amount: Amount to increment by (default: 1)

        Examples:
            >>> stats = OperationStats()
            >>> stats.increment('files_processed')
            >>> stats.files_processed
            1
            >>> stats.increment('custom_count', 5)
            >>> stats.custom_stats['custom_count']
            5
        """
        if hasattr(self, stat):
            setattr(self, stat, getattr(self, stat) + amount)
        else:
            self.custom_stats[stat] = self.custom_stats.get(stat, 0) + amount

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for reporting.

        Returns:
            Dictionary with all statistics

        Examples:
            >>> stats = OperationStats(total_files=10, files_modified=5)
            >>> d = stats.to_dict()
            >>> d['total_files']
            10
            >>> d['files_modified']
            5
        """
        return {
            'total_files': self.total_files,
            'files_processed': self.files_processed,
            'files_modified': self.files_modified,
            'files_skipped': self.files_skipped,
            'files_failed': self.files_failed,
            **self.custom_stats
        }


class DryRunContext:
    """
    Context manager for dry-run operations with change tracking.

    Provides standardized dry-run behavior and change recording for
    commands that modify files.

    Attributes:
        dry_run: Whether this is a dry-run (preview) mode
        stats: OperationStats object for tracking statistics
        changes: List of recorded changes

    Examples:
        >> with DryRunContext(dry_run=True) as ctx:
        ...     for file in files:
        ...         if should_modify:
        ...             ctx.record_change(file, "Added tags", tags=['foo', 'bar'])
        ...             ctx.stats.increment('files_modified')
        ...
        >> print(f"Would modify {ctx.stats.files_modified} files")
        >> for change in ctx.changes:
        ...     print(f"{change['file']}: {change['description']}")
    """

    def __init__(self, dry_run: bool):
        """
        Initialize the dry-run context.

        Args:
            dry_run: Whether this is a dry-run (preview) mode

        Examples:
            >>> ctx = DryRunContext(dry_run=True)
            >>> ctx.dry_run
            True
            >>> ctx.stats.total_files
            0
        """
        self.dry_run = dry_run
        self.stats = OperationStats()
        self.changes: List[Dict[str, Any]] = []

    def record_change(
        self,
        file_path: Path,
        description: str,
        **kwargs: Any
    ) -> None:
        """
        Record a change that would be or was made.

        Args:
            file_path: Path to file being modified
            description: Description of the change
            **kwargs: Additional change details (e.g., tags added, properties changed)

        Examples:
            >>> ctx = DryRunContext(dry_run=True)
            >>> ctx.record_change(Path('test.md'), 'Added tags', tags=['foo'])
            >>> ctx.changes[0]['file']
            'test.md'
            >>> ctx.changes[0]['description']
            'Added tags'
            >>> ctx.changes[0]['tags']
            ['foo']
        """
        self.changes.append({
            'file': str(file_path),
            'description': description,
            **kwargs
        })

    def would_modify(self, file_path: Path) -> bool:
        """
        Check if file would be modified (for conditional logic).

        In dry-run mode, returns False to prevent actual modifications.
        In live mode, returns True to allow modifications.

        Args:
            file_path: Path to file

        Returns:
            True if file would be modified, False otherwise

        Examples:
            >>> ctx = DryRunContext(dry_run=True)
            >>> ctx.would_modify(Path('test.md'))
            False
            >>> ctx = DryRunContext(dry_run=False)
            >>> ctx.would_modify(Path('test.md'))
            True
        """
        return not self.dry_run

    def __enter__(self) -> 'DryRunContext':
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the context manager."""
        return False


def print_dry_run_summary(
    ctx: DryRunContext,
    additional_info: Optional[str] = None
) -> None:
    """
    Print a standardized dry-run summary.

    Args:
        ctx: DryRunContext with statistics
        additional_info: Optional additional information to display

    Examples:
        >>> ctx = DryRunContext(dry_run=True)
        >>> ctx.stats.total_files = 10
        >>> ctx.stats.files_modified = 5
        >>> print_dry_run_summary(ctx)
        ========================================
        DRY RUN SUMMARY
        ========================================
        <BLANKLINE>
        Total files scanned:  10
        Files that would be modified: 5
        <BLANKLINE>
        ========================================
        ⚠ This was a DRY RUN - no files were modified
        Run without --dry-run to apply changes
        ========================================
    """
    print("\n" + "=" * 60)
    print("DRY RUN SUMMARY" if ctx.dry_run else "SUMMARY")
    print("=" * 60 + "\n")

    print(f"Total files scanned:  {ctx.stats.total_files}")
    print(f"Files processed:      {ctx.stats.files_processed}")

    if ctx.dry_run:
        print(f"Files that would be modified: {ctx.stats.files_modified}")
    else:
        print(f"Files modified:       {ctx.stats.files_modified}")

    if ctx.stats.files_skipped > 0:
        print(f"Files skipped:        {ctx.stats.files_skipped}")

    if ctx.stats.files_failed > 0:
        print(f"Files failed:         {ctx.stats.files_failed}")

    # Print custom statistics
    if ctx.stats.custom_stats:
        print()
        for key, value in ctx.stats.custom_stats.items():
            # Convert key from snake_case to Title Case
            display_key = key.replace('_', ' ').title()
            print(f"{display_key}: {value}")

    if additional_info:
        print(f"\n{additional_info}")

    if ctx.dry_run:
        print("\n" + "=" * 60)
        print("⚠ This was a DRY RUN - no files were modified")
        print("Run without --dry-run to apply changes")
        print("=" * 60)


def print_operation_summary(
    stats: OperationStats,
    dry_run: bool = False,
    additional_info: Optional[str] = None
) -> None:
    """
    Print a standardized operation summary (legacy function for backward compatibility).

    Args:
        stats: OperationStats object
        dry_run: Whether this was a dry-run
        additional_info: Optional additional information to display

    Examples:
        >>> stats = OperationStats(total_files=10, files_modified=5)
        >>> print_operation_summary(stats, dry_run=True)
        ========================================
        DRY RUN SUMMARY
        ========================================
        <BLANKLINE>
        Total files scanned:  10
        Files processed:      0
        Files that would be modified: 5
        <BLANKLINE>
        ========================================
        ⚠ This was a DRY RUN - no files were modified
        Run without --dry-run to apply changes
        ========================================
    """
    ctx = DryRunContext(dry_run)
    ctx.stats = stats
    print_dry_run_summary(ctx, additional_info)
