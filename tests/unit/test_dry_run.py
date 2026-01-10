"""
Unit tests for vault_manager.core.dry_run module.

Tests cover:
- OperationStats tracking and incrementing
- DryRunContext context manager behavior
- Change recording
- Summary printing
- Edge cases and error handling
"""

from pathlib import Path

from vault_manager.core.dry_run import (
    OperationStats,
    DryRunContext,
    print_dry_run_summary,
    print_operation_summary
)


class TestOperationStats:
    """Test OperationStats dataclass."""

    def test_default_initialization(self):
        """Test that stats initialize to zero."""
        stats = OperationStats()

        assert stats.total_files == 0
        assert stats.files_processed == 0
        assert stats.files_modified == 0
        assert stats.files_skipped == 0
        assert stats.files_failed == 0
        assert stats.custom_stats == {}

    def test_custom_initialization(self):
        """Test initialization with custom values."""
        stats = OperationStats(
            total_files=100,
            files_processed=50,
            files_modified=25,
            files_skipped=10,
            files_failed=5
        )

        assert stats.total_files == 100
        assert stats.files_processed == 50
        assert stats.files_modified == 25
        assert stats.files_skipped == 10
        assert stats.files_failed == 5

    def test_increment_standard_stat(self):
        """Test incrementing standard statistics."""
        stats = OperationStats()

        stats.increment('files_processed')
        assert stats.files_processed == 1

        stats.increment('files_processed', 5)
        assert stats.files_processed == 6

        stats.increment('files_modified', 3)
        assert stats.files_modified == 3

    def test_increment_custom_stat(self):
        """Test incrementing custom statistics."""
        stats = OperationStats()

        stats.increment('tags_added')
        assert stats.custom_stats['tags_added'] == 1

        stats.increment('tags_added', 10)
        assert stats.custom_stats['tags_added'] == 11

        stats.increment('properties_removed', 5)
        assert stats.custom_stats['properties_removed'] == 5

    def test_increment_mixed_stats(self):
        """Test incrementing both standard and custom stats."""
        stats = OperationStats()

        stats.increment('files_processed')
        stats.increment('files_modified', 2)
        stats.increment('tags_added', 5)
        stats.increment('links_fixed', 3)

        assert stats.files_processed == 1
        assert stats.files_modified == 2
        assert stats.custom_stats['tags_added'] == 5
        assert stats.custom_stats['links_fixed'] == 3

    def test_to_dict_empty(self):
        """Test converting empty stats to dict."""
        stats = OperationStats()
        result = stats.to_dict()

        assert result == {
            'total_files': 0,
            'files_processed': 0,
            'files_modified': 0,
            'files_skipped': 0,
            'files_failed': 0
        }

    def test_to_dict_with_values(self):
        """Test converting stats with values to dict."""
        stats = OperationStats(
            total_files=100,
            files_processed=50,
            files_modified=25
        )
        stats.increment('tags_added', 10)
        stats.increment('properties_removed', 5)

        result = stats.to_dict()

        assert result['total_files'] == 100
        assert result['files_processed'] == 50
        assert result['files_modified'] == 25
        assert result['files_skipped'] == 0
        assert result['files_failed'] == 0
        assert result['tags_added'] == 10
        assert result['properties_removed'] == 5

    def test_to_dict_immutability(self):
        """Test that to_dict returns a new dict (not a reference)."""
        stats = OperationStats(total_files=10)
        dict1 = stats.to_dict()
        dict1['total_files'] = 999

        # Original stats should be unchanged
        assert stats.total_files == 10

        # New dict call should return original value
        dict2 = stats.to_dict()
        assert dict2['total_files'] == 10


class TestDryRunContext:
    """Test DryRunContext context manager."""

    def test_initialization_dry_run_true(self):
        """Test initialization in dry-run mode."""
        ctx = DryRunContext(dry_run=True)

        assert ctx.dry_run is True
        assert isinstance(ctx.stats, OperationStats)
        assert ctx.changes == []

    def test_initialization_dry_run_false(self):
        """Test initialization in live mode."""
        ctx = DryRunContext(dry_run=False)

        assert ctx.dry_run is False
        assert isinstance(ctx.stats, OperationStats)
        assert ctx.changes == []

    def test_context_manager_enter_exit(self):
        """Test context manager protocol."""
        with DryRunContext(dry_run=True) as ctx:
            assert isinstance(ctx, DryRunContext)
            assert ctx.dry_run is True

        # Context should exit cleanly

    def test_record_change_basic(self):
        """Test recording a basic change."""
        ctx = DryRunContext(dry_run=True)
        file_path = Path('test.md')

        ctx.record_change(file_path, 'Added tags')

        assert len(ctx.changes) == 1
        assert ctx.changes[0]['file'] == 'test.md'
        assert ctx.changes[0]['description'] == 'Added tags'

    def test_record_change_with_details(self):
        """Test recording a change with additional details."""
        ctx = DryRunContext(dry_run=True)
        file_path = Path('notes/test.md')

        ctx.record_change(
            file_path,
            'Added tags',
            tags=['foo', 'bar'],
            count=2
        )

        assert len(ctx.changes) == 1
        change = ctx.changes[0]
        assert change['file'] == 'notes/test.md'
        assert change['description'] == 'Added tags'
        assert change['tags'] == ['foo', 'bar']
        assert change['count'] == 2

    def test_record_multiple_changes(self):
        """Test recording multiple changes."""
        ctx = DryRunContext(dry_run=True)

        ctx.record_change(Path('file1.md'), 'Change 1', detail='a')
        ctx.record_change(Path('file2.md'), 'Change 2', detail='b')
        ctx.record_change(Path('file3.md'), 'Change 3', detail='c')

        assert len(ctx.changes) == 3
        assert ctx.changes[0]['file'] == 'file1.md'
        assert ctx.changes[1]['file'] == 'file2.md'
        assert ctx.changes[2]['file'] == 'file3.md'

    def test_would_modify_dry_run_true(self):
        """Test would_modify in dry-run mode."""
        ctx = DryRunContext(dry_run=True)

        result = ctx.would_modify(Path('test.md'))

        assert result is False

    def test_would_modify_dry_run_false(self):
        """Test would_modify in live mode."""
        ctx = DryRunContext(dry_run=False)

        result = ctx.would_modify(Path('test.md'))

        assert result is True

    def test_stats_tracking_in_context(self):
        """Test that stats can be updated within context."""
        with DryRunContext(dry_run=True) as ctx:
            ctx.stats.increment('total_files', 10)
            ctx.stats.increment('files_modified', 5)
            ctx.stats.increment('tags_added', 15)

        assert ctx.stats.total_files == 10
        assert ctx.stats.files_modified == 5
        assert ctx.stats.custom_stats['tags_added'] == 15

    def test_changes_persist_after_context(self):
        """Test that changes are accessible after context exits."""
        ctx = DryRunContext(dry_run=True)

        with ctx:
            ctx.record_change(Path('test.md'), 'Change 1')
            ctx.record_change(Path('test2.md'), 'Change 2')

        # Changes should persist
        assert len(ctx.changes) == 2
        assert ctx.changes[0]['description'] == 'Change 1'
        assert ctx.changes[1]['description'] == 'Change 2'

    def test_realistic_workflow_dry_run(self):
        """Test a realistic workflow in dry-run mode."""
        files = [Path(f'file{i}.md') for i in range(5)]

        with DryRunContext(dry_run=True) as ctx:
            ctx.stats.increment('total_files', len(files))

            for file in files:
                # Simulate processing
                if file.name in ['file0.md', 'file2.md', 'file4.md']:
                    ctx.record_change(file, 'Added tags', tags=['foo'])
                    ctx.stats.increment('files_modified')
                else:
                    ctx.stats.increment('files_skipped')

        assert ctx.stats.total_files == 5
        assert ctx.stats.files_modified == 3
        assert ctx.stats.files_skipped == 2
        assert len(ctx.changes) == 3

    def test_realistic_workflow_live(self):
        """Test a realistic workflow in live mode."""
        files = [Path(f'file{i}.md') for i in range(3)]

        with DryRunContext(dry_run=False) as ctx:
            ctx.stats.increment('total_files', len(files))

            for file in files:
                # In live mode, would_modify returns True
                if ctx.would_modify(file):
                    ctx.record_change(file, 'Modified')
                    ctx.stats.increment('files_modified')

        assert ctx.stats.total_files == 3
        assert ctx.stats.files_modified == 3
        assert len(ctx.changes) == 3


class TestPrintFunctions:
    """Test summary printing functions."""

    def test_print_dry_run_summary_basic(self, capsys):
        """Test basic dry-run summary printing."""
        ctx = DryRunContext(dry_run=True)
        ctx.stats.total_files = 10
        ctx.stats.files_modified = 5

        print_dry_run_summary(ctx)

        captured = capsys.readouterr()
        output = captured.out

        assert 'DRY RUN SUMMARY' in output
        assert 'Total files scanned:  10' in output
        assert 'Files that would be modified: 5' in output
        assert '⚠ This was a DRY RUN' in output
        assert 'Run without --dry-run to apply changes' in output

    def test_print_dry_run_summary_live_mode(self, capsys):
        """Test summary printing in live mode."""
        ctx = DryRunContext(dry_run=False)
        ctx.stats.total_files = 10
        ctx.stats.files_modified = 5

        print_dry_run_summary(ctx)

        captured = capsys.readouterr()
        output = captured.out

        assert 'SUMMARY' in output
        assert 'DRY RUN SUMMARY' not in output
        assert 'Total files scanned:  10' in output
        assert 'Files modified:       5' in output
        assert '⚠ This was a DRY RUN' not in output

    def test_print_dry_run_summary_with_skipped(self, capsys):
        """Test summary with skipped files."""
        ctx = DryRunContext(dry_run=True)
        ctx.stats.total_files = 20
        ctx.stats.files_modified = 5
        ctx.stats.files_skipped = 10

        print_dry_run_summary(ctx)

        captured = capsys.readouterr()
        output = captured.out

        assert 'Total files scanned:  20' in output
        assert 'Files that would be modified: 5' in output
        assert 'Files skipped:        10' in output

    def test_print_dry_run_summary_with_failures(self, capsys):
        """Test summary with failed files."""
        ctx = DryRunContext(dry_run=True)
        ctx.stats.total_files = 20
        ctx.stats.files_modified = 5
        ctx.stats.files_failed = 3

        print_dry_run_summary(ctx)

        captured = capsys.readouterr()
        output = captured.out

        assert 'Total files scanned:  20' in output
        assert 'Files that would be modified: 5' in output
        assert 'Files failed:         3' in output

    def test_print_dry_run_summary_with_custom_stats(self, capsys):
        """Test summary with custom statistics."""
        ctx = DryRunContext(dry_run=True)
        ctx.stats.total_files = 10
        ctx.stats.files_modified = 5
        ctx.stats.increment('tags_added', 15)
        ctx.stats.increment('properties_removed', 8)

        print_dry_run_summary(ctx)

        captured = capsys.readouterr()
        output = captured.out

        assert 'Total files scanned:  10' in output
        assert 'Files that would be modified: 5' in output
        assert 'Tags Added: 15' in output
        assert 'Properties Removed: 8' in output

    def test_print_dry_run_summary_with_additional_info(self, capsys):
        """Test summary with additional information."""
        ctx = DryRunContext(dry_run=True)
        ctx.stats.total_files = 10
        ctx.stats.files_modified = 5

        print_dry_run_summary(ctx, additional_info='Custom message here')

        captured = capsys.readouterr()
        output = captured.out

        assert 'Total files scanned:  10' in output
        assert 'Custom message here' in output

    def test_print_operation_summary_backward_compatibility(self, capsys):
        """Test legacy print_operation_summary function."""
        stats = OperationStats(
            total_files=10,
            files_modified=5
        )

        print_operation_summary(stats, dry_run=True)

        captured = capsys.readouterr()
        output = captured.out

        assert 'DRY RUN SUMMARY' in output
        assert 'Total files scanned:  10' in output
        assert 'Files that would be modified: 5' in output

    def test_print_operation_summary_with_additional_info(self, capsys):
        """Test legacy function with additional info."""
        stats = OperationStats(total_files=10)

        print_operation_summary(
            stats,
            dry_run=False,
            additional_info='Test message'
        )

        captured = capsys.readouterr()
        output = captured.out

        assert 'SUMMARY' in output
        assert 'Total files scanned:  10' in output
        assert 'Test message' in output


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_tag_purge_workflow(self):
        """Simulate a tag purge command workflow."""
        files_to_process = [
            Path('notes/file1.md'),
            Path('notes/file2.md'),
            Path('notes/file3.md')
        ]

        # Dry-run first
        with DryRunContext(dry_run=True) as ctx:
            ctx.stats.increment('total_files', len(files_to_process))

            for file in files_to_process:
                # Simulate finding tag to remove
                ctx.record_change(file, 'Removed tag', tag='obsolete')
                ctx.stats.increment('files_modified')
                ctx.stats.increment('tags_removed')

        assert ctx.stats.total_files == 3
        assert ctx.stats.files_modified == 3
        assert ctx.stats.custom_stats['tags_removed'] == 3
        assert len(ctx.changes) == 3

    def test_property_set_workflow(self):
        """Simulate a property set command workflow."""
        files = [
            Path('file1.md'),
            Path('file2.md'),
            Path('file3.md')
        ]

        with DryRunContext(dry_run=False) as ctx:
            ctx.stats.increment('total_files', len(files))

            for file in files:
                if ctx.would_modify(file):
                    ctx.record_change(
                        file,
                        'Set property',
                        property='status',
                        value='draft'
                    )
                    ctx.stats.increment('files_modified')
                    ctx.stats.increment('properties_set')

        assert ctx.stats.total_files == 3
        assert ctx.stats.files_modified == 3
        assert ctx.stats.custom_stats['properties_set'] == 3

    def test_mixed_results_workflow(self):
        """Simulate a workflow with mixed results."""
        files = [
            ('file1.md', 'success'),
            ('file2.md', 'skip'),
            ('file3.md', 'success'),
            ('file4.md', 'fail'),
            ('file5.md', 'success')
        ]

        with DryRunContext(dry_run=True) as ctx:
            ctx.stats.increment('total_files', len(files))

            for filename, result in files:
                file = Path(filename)
                ctx.stats.increment('files_processed')

                if result == 'success':
                    ctx.record_change(file, 'Modified')
                    ctx.stats.increment('files_modified')
                elif result == 'skip':
                    ctx.stats.increment('files_skipped')
                elif result == 'fail':
                    ctx.stats.increment('files_failed')

        assert ctx.stats.total_files == 5
        assert ctx.stats.files_processed == 5
        assert ctx.stats.files_modified == 3
        assert ctx.stats.files_skipped == 1
        assert ctx.stats.files_failed == 1
        assert len(ctx.changes) == 3
