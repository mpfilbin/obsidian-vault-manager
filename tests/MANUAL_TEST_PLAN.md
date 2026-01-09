# Manual Test Plan for DryRunContext Refactoring

This test plan validates that the refactored commands maintain correct behavior with no regressions.

## Test Environment Setup

### Prerequisites
1. Backup your test vault before running these tests
2. Ensure you have a test vault with:
   - At least 10 markdown files with frontmatter
   - Files with various tags (mixed case, duplicates, etc.)
   - Some files with existing summaries
   - Some files with related notes already set
3. Set `ANTHROPIC_API_KEY` environment variable for AI tests
4. Ensure the vault database is built: `vault index build`

### Test Data Setup
Create a test directory structure:
```
test-vault/
├── .obsidian/
├── notes/
│   ├── note1.md (tags: [Foo, bar])
│   ├── note2.md (tags: [FOO, baz])
│   ├── note3.md (tags: [foo, Bar, BAZ])
│   ├── note4.md (no tags)
│   ├── note5.md (tags: [old-tag])
│   └── sensitive.md (tags: [test], sensitive: true)
└── docs/
    ├── doc1.md (tags: [documentation])
    └── doc2.md (has summary already)
```

---

## Test Suite 1: Tags Purge Command

### Test 1.1: Dry-run Mode Preview
**Command:** `vault tags purge foo --dry-run`

**Expected Results:**
- ✅ Output shows "DRY RUN (preview only)" mode
- ✅ Lists files that would be modified
- ✅ Shows tag removal count
- ✅ Displays dry-run summary statistics
- ✅ NO files are actually modified (verify with `git status` or file inspection)
- ✅ NO database rebuild triggered

**Verification:**
```bash
# Before running command, note file content
cat notes/note1.md
# Run command
vault tags purge foo --dry-run
# After command, verify file unchanged
cat notes/note1.md
# Check git status shows no modifications
git status
```

### Test 1.2: Live Mode Execution
**Command:** `vault tags purge foo`

**Expected Results:**
- ✅ Output shows "LIVE MODE"
- ✅ Prompts for confirmation (if interactive)
- ✅ Actually removes 'foo' tags from files
- ✅ Shows progress: "Removed from notes/note1.md"
- ✅ Database rebuild triggered automatically
- ✅ Statistics show correct counts

**Verification:**
```bash
# Run command
vault tags purge foo
# Verify tags removed from files
grep -r "tags:" notes/
# Verify database updated
vault tags query "SELECT * FROM tags WHERE tag_name = 'foo'"
```

### Test 1.3: Multiple Tags Purge
**Command:** `vault tags purge foo bar baz --dry-run`

**Expected Results:**
- ✅ Preview shows all three tags would be removed
- ✅ Correct file counts for each tag
- ✅ No modifications in dry-run mode

### Test 1.4: No-Rebuild Flag
**Command:** `vault tags purge foo --no-rebuild`

**Expected Results:**
- ✅ Tags removed from files
- ✅ NO database rebuild triggered
- ✅ Message indicates database not rebuilt
- ✅ Manual rebuild needed: `vault index build`

**Verification:**
```bash
vault tags purge test-tag --no-rebuild
# Database should still have old data
vault tags query "SELECT * FROM tags WHERE tag_name = 'test-tag'"
# Manually rebuild
vault index build
# Now tag should be gone
vault tags query "SELECT * FROM tags WHERE tag_name = 'test-tag'"
```

---

## Test Suite 2: Tags Rename Command

### Test 2.1: Simple Rename Dry-run
**Command:** `vault tags rename old-tag new-tag --dry-run`

**Expected Results:**
- ✅ Shows "DRY RUN (preview only)" mode
- ✅ Lists files that would be affected
- ✅ Shows "old-tag → new-tag" transformation
- ✅ NO files modified
- ✅ Statistics show file counts

**Verification:**
```bash
vault tags rename old-tag new-tag --dry-run
grep -r "old-tag" notes/  # Should still exist
grep -r "new-tag" notes/  # Should not exist yet
```

### Test 2.2: Live Mode Rename
**Command:** `vault tags rename old-tag new-tag`

**Expected Results:**
- ✅ Shows "LIVE MODE"
- ✅ Actually renames tags in files
- ✅ Database rebuild triggered
- ✅ Old tag no longer exists in vault
- ✅ New tag exists with correct file counts

**Verification:**
```bash
vault tags rename old-tag new-tag
grep -r "old-tag" notes/  # Should return nothing
grep -r "new-tag" notes/  # Should find renamed tags
vault tags query "SELECT * FROM tags WHERE tag_name = 'new-tag'"
```

### Test 2.3: Conflict Handling
**Setup:** Create file with `tags: [foo]` and another with `tags: [bar]`
**Command:** `vault tags rename foo bar`

**Expected Results:**
- ✅ Detects conflict (bar already exists)
- ✅ Shows warning about merging tags
- ✅ Prompts for confirmation
- ✅ After rename, files have both tags merged
- ✅ No duplicate tags in any file

**Verification:**
```bash
# Setup
echo -e "---\ntags: [foo]\n---\nTest" > notes/test1.md
echo -e "---\ntags: [bar]\n---\nTest" > notes/test2.md
# Run rename
vault tags rename foo bar
# Check result - test1.md should now have bar
grep "tags:" notes/test1.md  # Should show: tags: [bar]
```

### Test 2.4: Case-Only Rename
**Command:** `vault tags rename foo FOO --dry-run`

**Expected Results:**
- ✅ Recognizes case-only change
- ✅ Shows files that would be updated
- ✅ Works correctly in both dry-run and live mode

---

## Test Suite 3: Tags Clean Normalize Command

### Test 3.1: Normalize Dry-run
**Setup:** Files with mixed-case tags: `Foo`, `BAR`, `BaZ`
**Command:** `vault tags clean normalize . --dry-run`

**Expected Results:**
- ✅ Shows "DRY RUN (preview only)" mode
- ✅ Scans all files for non-lowercase tags
- ✅ Shows case changes: "Foo → foo", "BAR → bar"
- ✅ Shows file counts affected
- ✅ NO files modified

**Verification:**
```bash
# Before
grep -r "tags:" notes/ | head -5
vault tags clean normalize . --dry-run
# After - should be unchanged
grep -r "tags:" notes/ | head -5
```

### Test 3.2: Normalize Live Mode with Confirmation
**Command:** `vault tags clean normalize .`

**Expected Results:**
- ✅ Shows "LIVE MODE"
- ✅ Scans and shows preview
- ✅ Prompts: "Proceed with normalization? (y/n):"
- ✅ Shows most common changes
- ✅ After confirmation, normalizes all tags
- ✅ Database rebuild triggered
- ✅ All tags now lowercase

**Verification:**
```bash
vault tags clean normalize .
# Answer 'y' to confirmation
# Verify all tags lowercase
grep -r "tags:" notes/ | grep -v "\[.*[a-z].*\]"  # Should return nothing
vault tags query "SELECT DISTINCT tag_name FROM tags"  # All lowercase
```

### Test 3.3: Already Normalized Vault
**Setup:** Ensure all tags are already lowercase
**Command:** `vault tags clean normalize . --dry-run`

**Expected Results:**
- ✅ Message: "All tags are already lowercase."
- ✅ No files to modify shown
- ✅ Early exit without processing

### Test 3.4: Two-Phase Confirmation
**Command:** `vault tags clean normalize .`

**Expected Results:**
- ✅ Phase 1: Scans files, shows preview
- ✅ Shows confirmation prompt with statistics
- ✅ If 'n', cancels without modifications
- ✅ If 'y', Phase 2: Actually normalizes files
- ✅ Database rebuilt after confirmation

**Verification:**
```bash
# First run - answer 'n'
vault tags clean normalize .
# Answer 'n' - should cancel
git status  # No changes
# Second run - answer 'y'
vault tags clean normalize .
# Answer 'y' - should normalize
git status  # Should show modified files
```

---

## Test Suite 4: Tags Add Command (AI)

### Test 4.1: Dry-run AI Tag Generation
**Prerequisites:** `ANTHROPIC_API_KEY` set
**Command:** `vault tags add notes --dry-run --overwrite`

**Expected Results:**
- ✅ Shows "DRY RUN (preview only)" mode
- ✅ Scans notes directory
- ✅ Shows: "Would generate tags for: notes/note.md"
- ✅ Displays AI-suggested tags for each file
- ✅ NO files modified
- ✅ NO API calls if file already has tags (unless --overwrite)
- ✅ Statistics show files processed

**Verification:**
```bash
vault tags add notes --dry-run
# Check files unchanged
git status
# Note suggested tags in output
```

### Test 4.2: Live Mode AI Tag Generation
**Command:** `vault tags add notes --max-files 2`

**Expected Results:**
- ✅ Shows "MODIFY FILES" mode
- ✅ Processes only 2 files (due to --max-files)
- ✅ Makes actual API calls to Anthropic
- ✅ Adds generated tags to frontmatter
- ✅ Shows progress for each file
- ✅ Files actually modified
- ✅ NO database rebuild (add command doesn't modify structure)

**Verification:**
```bash
# Note original content
cat notes/note4.md
# Run command
vault tags add notes --max-files 2
# Verify tags added
cat notes/note4.md  # Should have new tags
git diff notes/note4.md
```

### Test 4.3: Sensitive Note Skipping
**Setup:** File with `sensitive: true` in frontmatter
**Command:** `vault tags add notes`

**Expected Results:**
- ✅ Detects sensitive flag
- ✅ Shows: "Skipping (sensitive): notes/sensitive.md"
- ✅ Sensitive file not processed
- ✅ Statistics track skipped sensitive files
- ✅ Other files processed normally

**Verification:**
```bash
# Create sensitive note
cat > notes/sensitive.md << 'EOF'
---
tags: []
sensitive: true
---
Private content
EOF
# Run command
vault tags add notes --dry-run
# Should see skip message
```

### Test 4.4: Overwrite vs Skip Existing
**Setup:** Files with and without existing tags

**Command 1:** `vault tags add notes --dry-run`
**Expected:** Skips files with existing tags

**Command 2:** `vault tags add notes --dry-run --overwrite`
**Expected:** Processes all files, even those with tags

**Verification:**
```bash
# Without overwrite
vault tags add notes --dry-run | grep -c "Skipping (has tags)"
# With overwrite
vault tags add notes --dry-run --overwrite | grep -c "Would generate tags"
```

### Test 4.5: Missing API Key
**Setup:** Unset `ANTHROPIC_API_KEY`
**Command:** `unset ANTHROPIC_API_KEY && vault tags add notes`

**Expected Results:**
- ✅ Error message: "ANTHROPIC_API_KEY environment variable not set"
- ✅ Shows help text on how to set it
- ✅ Exits with error code
- ✅ No files processed

---

## Test Suite 5: Properties Relate Command (AI)

### Test 5.1: Dry-run Relation Finding
**Prerequisites:** `ANTHROPIC_API_KEY` set
**Command:** `vault properties enrich related notes --dry-run`

**Expected Results:**
- ✅ Shows "DRY RUN (preview only)" mode
- ✅ Analyzes notes for similarity
- ✅ Shows: "Would add related notes to: notes/note1.md"
- ✅ Displays suggested related notes
- ✅ Shows similarity scores/reasoning
- ✅ NO files modified
- ✅ Statistics show notes analyzed

**Verification:**
```bash
vault properties enrich related notes --dry-run
git status  # No changes
```

### Test 5.2: Live Mode Relation Adding
**Command:** `vault properties enrich related notes --max-relations 3`

**Expected Results:**
- ✅ Shows "MODIFY FILES" mode
- ✅ Analyzes note relationships
- ✅ Adds 'related' field to frontmatter
- ✅ Limits to 3 related notes per file
- ✅ Files actually modified
- ✅ Progress shown for each file

**Verification:**
```bash
# Before
grep -r "related:" notes/
# Run command
vault properties enrich related notes --max-relations 3
# After - should have related fields
grep -r "related:" notes/
cat notes/note1.md  # Check related field added
```

### Test 5.3: Overwrite Existing Relations
**Setup:** File already has `related: [...]` field
**Command 1:** `vault properties enrich related notes`
**Expected:** Skips file with existing relations

**Command 2:** `vault properties enrich related notes --overwrite`
**Expected:** Replaces existing relations

**Verification:**
```bash
# Setup file with existing related
echo -e "---\ntags: [test]\nrelated: [old-note]\n---\nContent" > notes/test-relate.md
# Without overwrite - should skip
vault properties enrich related notes --dry-run | grep test-relate
# With overwrite - should process
vault properties enrich related notes --dry-run --overwrite | grep test-relate
```

### Test 5.4: Similarity Algorithm Validation
**Setup:** Notes with clear relationships:
- notes/python.md (about Python)
- notes/flask.md (about Flask framework)
- notes/java.md (about Java)

**Command:** `vault properties enrich related notes --dry-run`

**Expected Results:**
- ✅ python.md should be related to flask.md (shared topic)
- ✅ python.md should NOT be highly related to java.md
- ✅ Similarity scores make logical sense
- ✅ Hybrid algorithm considers tags, links, folders, keywords

---

## Test Suite 6: Properties Summarize Command (AI)

### Test 6.1: Dry-run Summary Generation
**Prerequisites:** `ANTHROPIC_API_KEY` set
**Command:** `vault properties enrich summaries notes --dry-run`

**Expected Results:**
- ✅ Shows "DRY RUN (preview only)" mode
- ✅ Scans notes directory
- ✅ Shows: "Would generate summary: notes/note.md"
- ✅ Displays AI-generated summary preview
- ✅ Summary is 2-4 sentences
- ✅ NO files modified
- ✅ Statistics show files processed

**Verification:**
```bash
vault properties enrich summaries notes --dry-run
git status  # No changes
# Review suggested summaries in output
```

### Test 6.2: Live Mode Summary Generation
**Command:** `vault properties enrich summaries notes`

**Expected Results:**
- ✅ Shows "MODIFY FILES" mode
- ✅ Makes API calls to Anthropic
- ✅ Generates 2-4 sentence summaries
- ✅ Adds 'summary' field to frontmatter
- ✅ Files actually modified
- ✅ Shows progress per file

**Verification:**
```bash
# Before
grep -r "summary:" notes/
# Run command
vault properties enrich summaries notes
# After
grep -r "summary:" notes/
cat notes/note1.md  # Should have summary field
```

### Test 6.3: Skip Files with Summaries
**Setup:** File with existing `summary: "..."`
**Command:** `vault properties enrich summaries notes`

**Expected Results:**
- ✅ Shows: "Skipping (has summary): notes/doc2.md"
- ✅ Does not process file
- ✅ Statistics track skipped files
- ✅ Other files without summaries processed

**Verification:**
```bash
vault properties enrich summaries notes --dry-run | grep -c "Skipping (has summary)"
```

### Test 6.4: Overwrite Existing Summaries
**Command:** `vault properties enrich summaries notes --overwrite`

**Expected Results:**
- ✅ Processes ALL files, even with existing summaries
- ✅ Replaces old summaries with new ones
- ✅ No skip messages for files with summaries

### Test 6.5: Sensitive Note Skipping
**Setup:** File with `sensitive: true`
**Command:** `vault properties enrich summaries notes`

**Expected Results:**
- ✅ Shows: "Skipping (sensitive): notes/sensitive.md"
- ✅ Sensitive file not sent to API
- ✅ Privacy preserved

### Test 6.6: Summary Quality Validation
**Command:** `vault properties enrich summaries notes`

**Expected Results:**
- ✅ Summaries are 2-4 sentences
- ✅ Summaries capture main concepts
- ✅ NO markdown formatting (no bold, italic, code, links)
- ✅ Plain text only
- ✅ Professional, clear language

**Verification:**
```bash
vault properties enrich summaries notes
# Check summary field content
cat notes/note1.md
# Verify no markdown: no **, __, `, [], etc.
grep "summary:" notes/*.md | grep -E "(\*\*|__|`|\[|\])"  # Should return nothing
```

### Test 6.7: Max Depth Recursion
**Setup:** Nested directory structure 6+ levels deep
**Command:** `vault properties enrich summaries notes`

**Expected Results:**
- ✅ Processes files up to 5 subdirectory levels
- ✅ Skips files deeper than 5 levels
- ✅ Shows ignored directories in output

---

## Cross-Cutting Tests

### Test 7.1: Directory Validation
**Command:** `vault tags purge foo --directory invalid/path`

**Expected Results:**
- ✅ Error: "Directory not found: invalid/path"
- ✅ Shows absolute path it was looking for
- ✅ Exits with error code
- ✅ No processing attempted

### Test 7.2: Entire Vault Processing
**Command:** `vault tags clean normalize .`

**Expected Results:**
- ✅ Processes all markdown files in vault
- ✅ Respects default ignores (.obsidian, .trash, .backup)
- ✅ Shows progress for all files
- ✅ Statistics accurate for entire vault

### Test 7.3: Statistics Accuracy
For each command, verify:
- ✅ `total_files` matches actual file count
- ✅ `files_modified` is accurate
- ✅ `files_processed` is accurate
- ✅ `files_failed` shows actual failures
- ✅ Custom stats (skipped_sensitive, etc.) are correct

### Test 7.4: Error Handling
**Setup:** Create invalid YAML frontmatter
```markdown
---
tags: [foo
invalid yaml
---
```

**Command:** Run any command on this file

**Expected Results:**
- ✅ Error caught gracefully
- ✅ Shows: "Error processing notes/bad.md: ..."
- ✅ Statistics track failed file
- ✅ Other files continue processing
- ✅ No crash or stack trace

### Test 7.5: No Frontmatter Handling
**Setup:** File without frontmatter
**Command:** Run any tags/properties command

**Expected Results:**
- ✅ Shows: "Skipping (no frontmatter): notes/no-fm.md"
- ✅ Statistics track skipped files
- ✅ Other files processed normally

---

## Regression Checks

### Pre-Refactoring Behavior Validation

For each command, verify behavior matches pre-refactoring:

1. **Output Format**
   - ✅ Header banners match (=== lines)
   - ✅ Progress messages consistent
   - ✅ Summary format unchanged
   - ✅ Error messages clear and helpful

2. **File Modifications**
   - ✅ Frontmatter format preserved (quoting, indentation)
   - ✅ Line endings preserved
   - ✅ Body content untouched
   - ✅ File permissions unchanged

3. **Database Interactions**
   - ✅ Rebuilds triggered when expected
   - ✅ --no-rebuild flag works
   - ✅ Database queries return correct results
   - ✅ Tag/property counts accurate

4. **Interactive Prompts**
   - ✅ Confirmation prompts appear when expected
   - ✅ User input respected (y/n)
   - ✅ Cancellation works without side effects

5. **Performance**
   - ✅ No significant slowdown
   - ✅ Large vaults process efficiently
   - ✅ Memory usage reasonable

---

## Sign-Off Checklist

After completing all tests above:

- [ ] All dry-run commands preview correctly without modifications
- [ ] All live mode commands modify files as expected
- [ ] Database rebuilds trigger correctly (except add command)
- [ ] --no-rebuild flag works for all applicable commands
- [ ] Statistics tracking is accurate across all commands
- [ ] Sensitive notes are properly skipped by AI commands
- [ ] Error handling is graceful (no crashes)
- [ ] Confirmation prompts work correctly
- [ ] AI commands require API key and fail gracefully without it
- [ ] Output formatting is consistent and helpful
- [ ] No unexpected side effects observed
- [ ] Git status shows expected file changes only

---

## Quick Smoke Test Script

For rapid validation, run this sequence:

```bash
#!/bin/bash
# Quick smoke test for refactored commands

VAULT_PATH="path/to/test/vault"
cd "$VAULT_PATH"

echo "=== Smoke Test: DryRunContext Refactoring ==="

# 1. Tags purge dry-run
echo -e "\n[1/12] Tags purge dry-run..."
vault tags purge test-tag --dry-run || echo "FAIL"

# 2. Tags purge live
echo -e "\n[2/12] Tags purge live..."
vault tags purge test-tag --no-rebuild || echo "FAIL"

# 3. Tags rename dry-run
echo -e "\n[3/12] Tags rename dry-run..."
vault tags rename old new --dry-run || echo "FAIL"

# 4. Tags rename live
echo -e "\n[4/12] Tags rename live..."
vault tags rename old new --no-rebuild || echo "FAIL"

# 5. Tags normalize dry-run
echo -e "\n[5/12] Tags normalize dry-run..."
vault tags clean normalize . --dry-run || echo "FAIL"

# 6. Tags normalize live (skip confirmation in script)
echo -e "\n[6/12] Tags normalize live..."
echo "n" | vault tags clean normalize . || echo "FAIL"

# 7. Tags add dry-run
echo -e "\n[7/12] Tags add dry-run..."
vault tags add notes --dry-run --max-files 1 || echo "FAIL"

# 8. Tags add live
echo -e "\n[8/12] Tags add live..."
vault tags add notes --max-files 1 || echo "FAIL"

# 9. Properties relate dry-run
echo -e "\n[9/12] Properties relate dry-run..."
vault properties enrich related notes --dry-run || echo "FAIL"

# 10. Properties relate live
echo -e "\n[10/12] Properties relate live..."
vault properties enrich related notes --max-relations 2 || echo "FAIL"

# 11. Properties summarize dry-run
echo -e "\n[11/12] Properties summarize dry-run..."
vault properties enrich summaries notes --dry-run || echo "FAIL"

# 12. Properties summarize live
echo -e "\n[12/12] Properties summarize live..."
vault properties enrich summaries notes || echo "FAIL"

echo -e "\n=== Smoke Test Complete ==="
echo "Review output above for any FAIL messages"
```

---

## Notes

- **Backup First:** Always test on a backup or test vault
- **API Costs:** AI commands (add, relate, summarize) use Anthropic API and incur costs
- **Time:** Full test plan takes 30-45 minutes; smoke test takes 5-10 minutes
- **Git:** Use git to track changes and reset between tests
- **Documentation:** Update this plan if new edge cases are discovered
