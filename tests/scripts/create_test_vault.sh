#!/bin/bash
# create_test_vault.sh
# Creates a test vault for validating DryRunContext refactoring

set -e  # Exit on error

# Configuration
DEFAULT_VAULT_PATH="$HOME/Documents/Test Vault"
VAULT_PATH="${1:-$DEFAULT_VAULT_PATH}"

echo "=========================================="
echo "Creating Test Vault for Manual Testing"
echo "=========================================="
echo "Vault path: $VAULT_PATH"
echo ""

# Confirm or exit
read -p "This will create/overwrite the vault at the above path. Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Clean and create vault directory
rm -rf "$VAULT_PATH"
mkdir -p "$VAULT_PATH"

# Create Obsidian config directory
mkdir -p "$VAULT_PATH/.obsidian"
cat > "$VAULT_PATH/.obsidian/app.json" << 'EOF'
{
  "alwaysUpdateLinks": true,
  "newLinkFormat": "shortest",
  "useMarkdownLinks": false
}
EOF

# Create main directories
mkdir -p "$VAULT_PATH/notes"
mkdir -p "$VAULT_PATH/docs"
mkdir -p "$VAULT_PATH/projects"
mkdir -p "$VAULT_PATH/archive"

# Create nested directory structure for depth testing
mkdir -p "$VAULT_PATH/deep/level1/level2/level3/level4/level5/level6"

echo "✓ Created directory structure"

# ============================================================================
# Test Suite 1: Tags Purge - Files with various tag configurations
# ============================================================================

cat > "$VAULT_PATH/notes/note1.md" << 'EOF'
---
tags: [Foo, bar, test-tag]
created: 2024-01-01
---

# Note 1

This is a test note with mixed-case tags.
It should be affected by purge, rename, and normalize operations.
EOF

cat > "$VAULT_PATH/notes/note2.md" << 'EOF'
---
tags: [FOO, baz, test-tag]
created: 2024-01-02
---

# Note 2

Another test note with uppercase FOO tag.
Links to [[note1]].
EOF

cat > "$VAULT_PATH/notes/note3.md" << 'EOF'
---
tags: [foo, Bar, BAZ]
created: 2024-01-03
---

# Note 3

This note has mixed case tags: foo, Bar, BAZ.
Should be normalized to lowercase.
EOF

# ============================================================================
# Test Suite 2: Tags Rename - Files with tags to rename
# ============================================================================

cat > "$VAULT_PATH/notes/note5.md" << 'EOF'
---
tags: [old-tag, other]
created: 2024-01-05
---

# Note 5

This note has the old-tag that should be renamed.
EOF

cat > "$VAULT_PATH/notes/note6.md" << 'EOF'
---
tags: [old-tag, another]
created: 2024-01-06
---

# Note 6

Another note with old-tag for rename testing.
EOF

# ============================================================================
# Test Suite 3: Tags Add - Files needing AI tag generation
# ============================================================================

cat > "$VAULT_PATH/notes/note4.md" << 'EOF'
---
tags: []
created: 2024-01-04
---

# Note 4 - Python Web Development

This note discusses building web applications with Python and Flask.
It covers routing, templates, database integration, and deployment strategies.
The Flask framework provides a lightweight approach to web development.
EOF

cat > "$VAULT_PATH/notes/no-tags.md" << 'EOF'
---
created: 2024-01-10
---

# Machine Learning Basics

An introduction to machine learning concepts including supervised learning,
unsupervised learning, and neural networks. Covers common algorithms like
linear regression, decision trees, and k-means clustering.
EOF

cat > "$VAULT_PATH/notes/has-tags.md" << 'EOF'
---
tags: [existing, should-skip]
created: 2024-01-11
---

# Note with Existing Tags

This note already has tags and should be skipped unless --overwrite is used.
EOF

# ============================================================================
# Test Suite 4: Sensitive Notes
# ============================================================================

cat > "$VAULT_PATH/notes/sensitive.md" << 'EOF'
---
tags: [personal]
sensitive: true
created: 2024-01-07
---

# Sensitive Note

This note contains private information and should be skipped by AI commands.
It has the sensitive: true flag in frontmatter.
EOF

# ============================================================================
# Test Suite 5: Properties Summarize - Files needing summaries
# ============================================================================

cat > "$VAULT_PATH/docs/doc1.md" << 'EOF'
---
tags: [documentation]
created: 2024-01-08
---

# Documentation Standards

This document outlines the documentation standards for the project.
All code should be well-documented with clear docstrings.
README files should include installation instructions, usage examples,
and contribution guidelines. Use Markdown for all documentation files.
EOF

cat > "$VAULT_PATH/docs/doc2.md" << 'EOF'
---
tags: [documentation]
summary: "This document already has a summary and should be skipped by default."
created: 2024-01-09
---

# Existing Summary Document

This document already has a summary field in its frontmatter.
It should be skipped by the summarize command unless --overwrite is used.
EOF

# ============================================================================
# Test Suite 6: Properties Relate - Files with topical relationships
# ============================================================================

cat > "$VAULT_PATH/projects/python.md" << 'EOF'
---
tags: [python, programming, language]
created: 2024-01-15
---

# Python Programming Language

Python is a high-level, interpreted programming language known for its
readability and simplicity. It supports multiple programming paradigms
including object-oriented, functional, and procedural programming.

Key features:
- Dynamic typing
- Automatic memory management
- Extensive standard library
- Large ecosystem of third-party packages

Related: [[flask]], [[django]]
EOF

cat > "$VAULT_PATH/projects/flask.md" << 'EOF'
---
tags: [python, flask, web, framework]
created: 2024-01-16
---

# Flask Web Framework

Flask is a lightweight WSGI web application framework written in Python.
It's designed to be simple and easy to use, making it perfect for small
to medium web applications.

Features:
- Built-in development server
- RESTful request dispatching
- Jinja2 templating
- Support for unit testing

Based on [[python]]. Compare with [[django]].
EOF

cat > "$VAULT_PATH/projects/django.md" << 'EOF'
---
tags: [python, django, web, framework]
created: 2024-01-17
---

# Django Web Framework

Django is a high-level Python web framework that encourages rapid development
and clean, pragmatic design. It follows the model-template-view (MTV)
architectural pattern.

Features:
- ORM (Object-Relational Mapping)
- Admin interface
- Authentication system
- Template engine

Built on [[python]]. Alternative to [[flask]].
EOF

cat > "$VAULT_PATH/projects/java.md" << 'EOF'
---
tags: [java, programming, language]
created: 2024-01-18
---

# Java Programming Language

Java is a high-level, class-based, object-oriented programming language
designed to have as few implementation dependencies as possible.
It's widely used for enterprise applications.

Key features:
- Write once, run anywhere (WORA)
- Strongly typed
- Automatic garbage collection
- Rich API and libraries

Unrelated to [[python]] - different ecosystem.
EOF

cat > "$VAULT_PATH/projects/react.md" << 'EOF'
---
tags: [javascript, react, web, frontend]
created: 2024-01-19
---

# React JavaScript Library

React is a JavaScript library for building user interfaces.
It lets you create reusable UI components and manage application state
efficiently using a virtual DOM.

Features:
- Component-based architecture
- JSX syntax
- One-way data binding
- Large ecosystem
EOF

# ============================================================================
# Test Suite 7: Files with existing related field
# ============================================================================

cat > "$VAULT_PATH/projects/has-related.md" << 'EOF'
---
tags: [test]
related: [old-relation-1, old-relation-2]
created: 2024-01-20
---

# Note with Existing Relations

This note already has a related field and should be skipped unless --overwrite.
EOF

# ============================================================================
# Test Suite 8: Error Handling - Files with issues
# ============================================================================

cat > "$VAULT_PATH/notes/no-frontmatter.md" << 'EOF'
# Note Without Frontmatter

This note has no YAML frontmatter at all.
It should be skipped by commands that require frontmatter.
EOF

cat > "$VAULT_PATH/notes/invalid-yaml.md" << 'EOF'
---
tags: [foo
invalid yaml here
no closing bracket
---

# Invalid YAML

This note has malformed YAML frontmatter.
It should be caught gracefully with an error message.
EOF

cat > "$VAULT_PATH/notes/empty-frontmatter.md" << 'EOF'
---
---

# Empty Frontmatter

This note has empty frontmatter.
EOF

# ============================================================================
# Test Suite 9: Deep Directory Testing
# ============================================================================

cat > "$VAULT_PATH/deep/level1/note-depth1.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 1
EOF

cat > "$VAULT_PATH/deep/level1/level2/note-depth2.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 2
EOF

cat > "$VAULT_PATH/deep/level1/level2/level3/note-depth3.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 3
EOF

cat > "$VAULT_PATH/deep/level1/level2/level3/level4/note-depth4.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 4
EOF

cat > "$VAULT_PATH/deep/level1/level2/level3/level4/level5/note-depth5.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 5
EOF

cat > "$VAULT_PATH/deep/level1/level2/level3/level4/level5/level6/note-depth6.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 6 - Should be ignored by max_depth=5
EOF

# ============================================================================
# Test Suite 10: Archive with various patterns
# ============================================================================

cat > "$VAULT_PATH/archive/archived-note.md" << 'EOF'
---
tags: [archive, OLD-TAG]
created: 2023-12-01
---

# Archived Note

This is an old note that should still be processed by commands.
EOF

# ============================================================================
# Test Suite 11: Images and Links Testing
# ============================================================================

# Create images directory structure
mkdir -p "$VAULT_PATH/images"
mkdir -p "$VAULT_PATH/images/screenshots"
mkdir -p "$VAULT_PATH/images/diagrams"
mkdir -p "$VAULT_PATH/assets"

# Create dummy image files (1x1 PNG - valid minimal PNG)
# This is a base64-encoded 1x1 transparent PNG
PNG_DATA="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

# Referenced images (used in notes) - various formats
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/referenced-image.png"
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/screenshot.png"
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/photo.jpg"  # Actually PNG but named .jpg for testing
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/icon.gif"   # Actually PNG but named .gif for testing
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/assets/diagram.png"
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/screenshots/ui-screenshot.png"
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/diagrams/architecture.png"

# Orphaned images (NOT referenced anywhere) - should be found by `vault images find`
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/orphaned-image-1.png"
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/orphaned-image-2.png"
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/orphaned-photo.jpg"
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/images/screenshots/orphaned-screenshot.png"
echo "$PNG_DATA" | base64 -d > "$VAULT_PATH/assets/unused-asset.png"

# Create notes with valid image references - all formats
cat > "$VAULT_PATH/notes/with-valid-image.md" << 'EOF'
---
tags: [images, test]
created: 2024-01-25
---

# Note with Valid Image References

This note has valid image references in multiple formats.

## Markdown format
![Referenced Image](../images/referenced-image.png)
![Photo](../images/photo.jpg)

## Obsidian wiki-link format
![[referenced-image.png]]
![[screenshot.png]]
![[icon.gif]]

## Wiki-link with alt text
![[diagram.png|Diagram]]

## HTML format
<img src="../images/diagrams/architecture.png" alt="Architecture Diagram">

## Subdirectory references
![[ui-screenshot.png]]
EOF

# Create notes with broken image references - all formats
cat > "$VAULT_PATH/notes/with-broken-images.md" << 'EOF'
---
tags: [images, broken]
created: 2024-01-26
---

# Note with Broken Image References

This note references images that don't exist.

## Broken markdown references
![Missing Image](../images/does-not-exist.png)
![Missing Photo](../images/missing-photo.jpg)

## Broken wiki-links
![[missing-image.png]]
![[nonexistent.jpg|This file is missing]]
![[missing-screenshot.png]]

## Broken HTML reference
<img src="../images/not-found.gif" alt="Missing GIF">

## Broken subdirectory reference
![Missing](../images/screenshots/missing.png)

This should be detected by `vault images broken` command.
EOF

# Create note with mixed (valid and broken) images
cat > "$VAULT_PATH/notes/mixed-images.md" << 'EOF'
---
tags: [images]
created: 2024-01-27
---

# Note with Mixed Image References

Valid reference (PNG):
![[referenced-image.png]]

Broken reference:
![Missing](../images/404.png)

Valid again (JPG):
![[photo.jpg]]

Broken HTML:
<img src="../images/broken.gif">

Valid subdirectory:
![[ui-screenshot.png]]
EOF

# Create notes with broken wiki-links
cat > "$VAULT_PATH/notes/with-broken-links.md" << 'EOF'
---
tags: [links, broken]
created: 2024-01-28
---

# Note with Broken Wiki-Links

This note has several broken links to non-existent notes.

Link to missing note: [[this-note-does-not-exist]]
Another broken link: [[nonexistent-page]]
Link with display text: [[missing-note|Display Text]]

This should be detected by `vault index broken-links` command.
EOF

# Create notes with valid wiki-links
cat > "$VAULT_PATH/notes/with-valid-links.md" << 'EOF'
---
tags: [links, valid]
created: 2024-01-29
---

# Note with Valid Wiki-Links

This note has valid links to existing notes.

Link to note1: [[note1]]
Link to note2: [[note2]]
Link with custom text: [[note3|See Note 3]]

These links should resolve correctly.
EOF

# Create note with mixed (valid and broken) links
cat > "$VAULT_PATH/notes/mixed-links.md" << 'EOF'
---
tags: [links]
created: 2024-01-30
---

# Note with Mixed Links

Valid link: [[note1]]
Broken link: [[does-not-exist]]
Valid link: [[python]]
Broken link: [[missing-file]]

Mix of working and broken references.
EOF

# Create note for alt-text removal testing
cat > "$VAULT_PATH/notes/images-with-alt.md" << 'EOF'
---
tags: [images, alt-text]
created: 2024-01-31
---

# Images with Alt Text

These wiki-link images have alt text that can be removed:

![[referenced-image.png|This is alt text]]
![[diagram.png|Another alt text here]]
![[referenced-image.png|Remove this alt]]

Use `vault images remove-alt` to strip alt text.
EOF

# ============================================================================
# Test Suite 12: Property Validation and Normalization
# ============================================================================

# Create files with denormalized properties (should be removed)
cat > "$VAULT_PATH/notes/denormalized-properties.md" << 'EOF'
---
tags: [test]
author: John Doe
title: This is the title
description: A description of the note
created: 2024-01-01
published: 2024-01-15
summary: This should stay
source: https://example.com
---

# Denormalized Properties

This file has properties that should be removed by normalization:
- author (remove)
- title (remove)
- description (remove)
- created (remove)
- published (remove)

But these should stay:
- tags (keep)
- summary (keep)
- source (keep)
EOF

# Create file with url property (should be renamed to source)
cat > "$VAULT_PATH/notes/url-to-source.md" << 'EOF'
---
tags: [web, reference]
url: https://example.com/article
title: Article Title
author: Jane Smith
---

# URL to Source Rename

This file has a 'url' property that should be renamed to 'source'.
Also has 'title' and 'author' that should be removed.

After normalization:
- url → source (renamed)
- title → removed
- author → removed
- tags → kept
EOF

# Create file with url AND source (conflict scenario)
cat > "$VAULT_PATH/notes/url-source-conflict.md" << 'EOF'
---
tags: [conflict]
url: https://example.com/old
source: https://example.com/new
---

# URL and Source Conflict

This file has BOTH 'url' and 'source' properties.
The normalization should handle this conflict appropriately.
EOF

# Create file with duplicate property keys
cat > "$VAULT_PATH/notes/duplicate-properties.md" << 'EOF'
---
tags: [test]
author: First Author
tags: [duplicate, test2]
summary: First summary
author: Second Author
created: 2024-01-01
summary: Second summary
---

# Duplicate Properties

This file has duplicate property keys:
- tags appears twice
- author appears twice
- summary appears twice

The clean deduplicate command should fix this.
EOF

# Create file with multiple denormalized properties
cat > "$VAULT_PATH/docs/heavily-denormalized.md" << 'EOF'
---
tags: [documentation]
author: Documentation Team
title: Documentation Title
description: This is a description
created: 2024-01-01T10:00:00
published: 2024-01-15T14:30:00
modified: 2024-02-01T09:15:00
url: https://docs.example.com
category: Tutorial
status: Published
version: 1.0
---

# Heavily Denormalized Properties

This file has many denormalized properties that should be cleaned up.

Should be removed:
- author
- title
- description
- created
- published
- modified
- category
- status
- version

Should be renamed:
- url → source

Should stay:
- tags
EOF

# Create file with only valid properties (should not be modified)
cat > "$VAULT_PATH/docs/clean-properties.md" << 'EOF'
---
tags: [clean, valid]
summary: This is a clean file with only valid properties
source: https://example.com
related: [note1, note2]
---

# Clean Properties

This file has only valid properties and should NOT be modified:
- tags ✓
- summary ✓
- source ✓
- related ✓

No denormalized properties to remove.
EOF

# Create file with invalid YAML for validation testing
cat > "$VAULT_PATH/notes/invalid-yaml-properties.md" << 'EOF'
---
tags: [invalid
missing closing bracket
author: "Unclosed quote
summary: Valid summary
unquoted: special:characters:here
---

# Invalid YAML Properties

This file has invalid YAML that should be detected by validate command:
- tags: missing closing bracket
- author: unclosed quote
- unquoted: unescaped colons
EOF

# Create file with empty properties
cat > "$VAULT_PATH/notes/empty-properties.md" << 'EOF'
---
tags: []
author: ""
title:
summary:
source:
---

# Empty Properties

This file has empty properties:
- tags: empty array
- author: empty string
- title: null/undefined
- summary: null/undefined
- source: null/undefined

Some should be removed during normalization.
EOF

# Create file with nested/complex properties
cat > "$VAULT_PATH/notes/complex-properties.md" << 'EOF'
---
tags: [nested, complex]
metadata:
  author: Nested Author
  created: 2024-01-01
  title: Nested Title
custom:
  field1: value1
  field2: value2
summary: Valid summary
---

# Complex Properties

This file has nested properties.
The normalization should handle or preserve these appropriately.
EOF

# Create file with various property types for validation
cat > "$VAULT_PATH/docs/property-types.md" << 'EOF'
---
tags: [types, validation]
string_prop: "A string value"
number_prop: 42
boolean_prop: true
date_prop: 2024-01-01
array_prop: [item1, item2, item3]
null_prop: null
summary: Testing various property types
---

# Property Types

This file has various property types for validation testing:
- string
- number
- boolean
- date
- array
- null
EOF

# ============================================================================
# Test Suite 13: Invalid Tags
# ============================================================================

# Create files with invalid tags for testing `vault tags clean invalid`
cat > "$VAULT_PATH/notes/invalid-tags-numeric.md" << 'EOF'
---
tags: [2024, 123, valid-tag, 456]
created: 2024-02-10
---

# Invalid Tags - All Numeric

This file has invalid all-numeric tags: 2024, 123, 456
These should be detected and removed by `vault tags clean invalid`.
EOF

cat > "$VAULT_PATH/notes/invalid-tags-special-chars.md" << 'EOF'
---
tags: [tag@invalid, tag!, tag#hash, valid-tag, tag$pecial]
created: 2024-02-11
---

# Invalid Tags - Special Characters

This file has tags with special characters that are not allowed:
- tag@invalid (@ not allowed)
- tag! (! not allowed)
- tag#hash (# not allowed)
- tag$pecial ($ not allowed)

Only valid-tag should remain after cleaning.
EOF

cat > "$VAULT_PATH/notes/invalid-tags-spaces.md" << 'EOF'
---
tags: [tag with spaces, another bad tag, good-tag]
created: 2024-02-12
---

# Invalid Tags - Spaces

This file has tags with spaces in them:
- "tag with spaces"
- "another bad tag"

These are invalid in Obsidian and should be removed.
EOF

cat > "$VAULT_PATH/notes/invalid-tags-mixed.md" << 'EOF'
---
tags: [2024, valid-tag, tag@bad, 999, good_tag, tag!, nested/valid]
created: 2024-02-13
---

# Invalid Tags - Mixed Valid and Invalid

This file has a mix of valid and invalid tags:

Invalid:
- 2024 (all numeric)
- tag@bad (special char)
- 999 (all numeric)
- tag! (special char)

Valid:
- valid-tag
- good_tag
- nested/valid

After cleaning, only the valid tags should remain.
EOF

cat > "$VAULT_PATH/notes/invalid-tags-edge-cases.md" << 'EOF'
---
tags: [_underscore, -dash-only-, 42, y2024, tag&amp;, tag.dot]
created: 2024-02-14
---

# Invalid Tags - Edge Cases

Testing edge cases:
- _underscore (valid - starts with underscore)
- -dash-only- (valid - has dashes)
- 42 (invalid - all numeric)
- y2024 (valid - has letter)
- tag&amp; (invalid - special char)
- tag.dot (invalid - period not allowed)
EOF

cat > "$VAULT_PATH/docs/all-valid-tags.md" << 'EOF'
---
tags: [valid, another-valid, nested/tag, with_underscore, tag123, y2024]
created: 2024-02-15
---

# All Valid Tags

This file has only valid tags and should not be modified:
- valid
- another-valid
- nested/tag
- with_underscore
- tag123 (has letters and numbers)
- y2024 (starts with letter)
EOF

# ============================================================================
# Test Suite 13: Duplicate Files
# ============================================================================

# Create directory for duplicates testing
mkdir -p "$VAULT_PATH/duplicates"

# Create original file
cat > "$VAULT_PATH/notes/original-content.md" << 'EOF'
---
tags: [original]
created: 2024-02-01
---

# Original Content

This is the original file with unique content.
It has multiple paragraphs to create a distinct hash.

Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
EOF

# Create exact duplicate (same content, different name)
cat > "$VAULT_PATH/duplicates/duplicate-copy-1.md" << 'EOF'
---
tags: [original]
created: 2024-02-01
---

# Original Content

This is the original file with unique content.
It has multiple paragraphs to create a distinct hash.

Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
EOF

# Create another exact duplicate (different location)
cat > "$VAULT_PATH/archive/duplicate-copy-2.md" << 'EOF'
---
tags: [original]
created: 2024-02-01
---

# Original Content

This is the original file with unique content.
It has multiple paragraphs to create a distinct hash.

Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
EOF

# Create a different file (not a duplicate)
cat > "$VAULT_PATH/notes/unique-content.md" << 'EOF'
---
tags: [unique]
created: 2024-02-02
---

# Unique Content

This file has completely different content and should not be detected as a duplicate.
EOF

# ============================================================================
# Test Suite 13: Mangled Filenames
# ============================================================================

# Create files with underscores (should be spaces)
cat > "$VAULT_PATH/notes/File_With_Underscores.md" << 'EOF'
---
tags: [mangled]
created: 2024-02-03
---

# File With Underscores

This filename has underscores instead of spaces.
Should be detected by `vault index rename find`.
EOF

cat > "$VAULT_PATH/notes/Another_Mangled_File_Name.md" << 'EOF'
---
tags: [mangled]
created: 2024-02-04
---

# Another Mangled File Name

Another file with underscores that should be spaces.
EOF

cat > "$VAULT_PATH/projects/Python_Programming_Guide.md" << 'EOF'
---
tags: [python, mangled]
created: 2024-02-05
---

# Python Programming Guide

Filename should be "Python Programming Guide.md" not "Python_Programming_Guide.md".
EOF

# Create file with URL-encoding (percent-encoded spaces)
cat > "$VAULT_PATH/docs/File%20With%20Encoded%20Spaces.md" << 'EOF'
---
tags: [mangled, url-encoded]
created: 2024-02-06
---

# File With Encoded Spaces

This filename has %20 instead of spaces (URL-encoded).
Should be detected as mangled.
EOF

# Create file with mixed issues (underscores + special chars)
cat > "$VAULT_PATH/notes/Really_Bad_Filename_From_Web.md" << 'EOF'
---
tags: [mangled]
created: 2024-02-07
---

# Really Bad Filename From Web

This file was probably downloaded from the web and has mangled formatting.
EOF

# Create properly named files (should NOT be detected as mangled)
cat > "$VAULT_PATH/notes/Properly Named File.md" << 'EOF'
---
tags: [clean]
created: 2024-02-08
---

# Properly Named File

This filename is correctly formatted with spaces.
EOF

cat > "$VAULT_PATH/docs/Another Clean Filename.md" << 'EOF'
---
tags: [clean]
created: 2024-02-09
---

# Another Clean Filename

No underscores or encoding issues here.
EOF

echo "✓ Created test markdown files, images, duplicates, and mangled filenames"

# ============================================================================
# Create .gitignore for test vault
# ============================================================================

cat > "$VAULT_PATH/.gitignore" << 'EOF'
.obsidian/workspace*
.obsidian/cache
.trash/
vault.db
vault.db-*
EOF

# ============================================================================
# Build the vault database
# ============================================================================

echo ""
echo "Building vault database..."
cd "$VAULT_PATH"

# Check if vault command is available
if ! command -v vault &> /dev/null; then
    echo "⚠ Warning: 'vault' command not found."
    echo "   Please install vault-manager and run: vault index build"
    echo "   in the test vault directory."
else
    vault index build
    echo "✓ Built vault database"
fi

# ============================================================================
# Create README for test vault
# ============================================================================

cat > "$VAULT_PATH/README.md" << 'EOF'
# Test Vault for DryRunContext Refactoring

This vault was automatically generated for testing the refactored commands.

## Structure

- `notes/` - Test notes with various tag configurations
  - Mixed-case tags (Foo, BAR, baz)
  - Tags to purge (test-tag)
  - Tags to rename (old-tag)
  - Sensitive notes
  - Invalid YAML
  - No frontmatter
  - Broken/valid image references
  - Broken/valid wiki-links

- `docs/` - Documentation notes
  - Some with existing summaries
  - Some needing summaries

- `projects/` - Project notes with topical relationships
  - Python, Flask, Django (related topics)
  - Java (unrelated)
  - React (different domain)

- `archive/` - Archived notes

- `deep/` - Nested directories for depth testing (6 levels)

- `duplicates/` - Duplicate files for testing

- `images/` - Image files for testing
  - Referenced images (used in notes)
  - Orphaned images (not referenced anywhere)

- `assets/` - Additional image assets

## Test Data Summary

| File | Tags | Purpose |
|------|------|---------|
| notes/note1.md | Foo, bar, test-tag | Purge, rename, normalize |
| notes/note2.md | FOO, baz, test-tag | Purge, normalize |
| notes/note3.md | foo, Bar, BAZ | Normalize |
| notes/note4.md | [] | AI tag generation |
| notes/note5.md | old-tag, other | Rename |
| notes/note6.md | old-tag, another | Rename |
| notes/sensitive.md | personal | Sensitive flag test |
| notes/no-tags.md | (none) | AI tag generation |
| notes/has-tags.md | existing | Skip/overwrite test |
| notes/no-frontmatter.md | (none) | Error handling |
| notes/invalid-yaml.md | (invalid) | Error handling |
| docs/doc1.md | documentation | AI summary generation |
| docs/doc2.md | documentation | Has summary (skip) |
| projects/python.md | python, programming | Relate test |
| projects/flask.md | python, flask, web | Relate test |
| projects/django.md | python, django, web | Relate test |
| projects/java.md | java, programming | Relate test |
| projects/react.md | javascript, react | Relate test |
| projects/has-related.md | test | Has related (skip) |
| notes/with-valid-image.md | images, test | Valid image refs |
| notes/with-broken-images.md | images, broken | Broken image refs |
| notes/mixed-images.md | images | Mixed valid/broken images |
| notes/with-broken-links.md | links, broken | Broken wiki-links |
| notes/with-valid-links.md | links, valid | Valid wiki-links |
| notes/mixed-links.md | links | Mixed valid/broken links |
| notes/images-with-alt.md | images, alt-text | Alt text removal |
| notes/denormalized-properties.md | test | Properties to remove |
| notes/url-to-source.md | web, reference | url → source rename |
| notes/url-source-conflict.md | conflict | url + source conflict |
| notes/duplicate-properties.md | test, duplicate | Duplicate property keys |
| docs/heavily-denormalized.md | documentation | Many denormalized props |
| docs/clean-properties.md | clean, valid | Only valid properties |
| notes/invalid-yaml-properties.md | invalid | Invalid YAML structure |
| notes/empty-properties.md | [] | Empty property values |
| notes/complex-properties.md | nested, complex | Nested properties |
| docs/property-types.md | types, validation | Various property types |
| notes/invalid-tags-numeric.md | 2024, 123, valid-tag, 456 | Invalid all-numeric tags |
| notes/invalid-tags-special-chars.md | tag@invalid, tag!, etc. | Invalid special chars |
| notes/invalid-tags-spaces.md | tag with spaces, etc. | Invalid tags with spaces |
| notes/invalid-tags-mixed.md | mixed valid/invalid | Mixed valid and invalid |
| notes/invalid-tags-edge-cases.md | edge cases | Edge case testing |
| docs/all-valid-tags.md | all valid | Only valid tags |
| notes/original-content.md | original | Original file |
| duplicates/duplicate-copy-1.md | original | Duplicate of original |
| archive/duplicate-copy-2.md | original | Duplicate of original |
| notes/unique-content.md | unique | Unique content (not dup) |
| notes/File_With_Underscores.md | mangled | Mangled filename |
| notes/Another_Mangled_File_Name.md | mangled | Mangled filename |
| projects/Python_Programming_Guide.md | python, mangled | Mangled filename |
| docs/File%20With%20Encoded%20Spaces.md | mangled, url-encoded | URL-encoded filename |
| notes/Really_Bad_Filename_From_Web.md | mangled | Mangled filename |
| notes/Properly Named File.md | clean | Clean filename |
| docs/Another Clean Filename.md | clean | Clean filename |

## Images

| File | Referenced | Purpose |
|------|------------|---------|
| images/referenced-image.png | Yes | Referenced (PNG format) |
| images/screenshot.png | Yes | Referenced (PNG format) |
| images/photo.jpg | Yes | Referenced (JPG format) |
| images/icon.gif | Yes | Referenced (GIF format) |
| images/screenshots/ui-screenshot.png | Yes | Referenced (subdirectory) |
| images/diagrams/architecture.png | Yes | Referenced (HTML img tag) |
| assets/diagram.png | Yes | Referenced (assets dir) |
| images/orphaned-image-1.png | No | **Orphaned** (not referenced) |
| images/orphaned-image-2.png | No | **Orphaned** (not referenced) |
| images/orphaned-photo.jpg | No | **Orphaned** (JPG, not referenced) |
| images/screenshots/orphaned-screenshot.png | No | **Orphaned** (subdirectory) |
| assets/unused-asset.png | No | **Orphaned** (unused asset) |

**Image Reference Formats Tested:**
- ✅ Markdown: `![alt](path/image.png)`
- ✅ Wiki-link: `![[image.png]]`
- ✅ Wiki-link with alt: `![[image.png|alt text]]`
- ✅ HTML: `<img src="path/image.png">`
- ✅ Multiple file formats: PNG, JPG, GIF
- ✅ Subdirectory images: `images/screenshots/`, `images/diagrams/`

## Database

Run `vault index build` to create the initial database.

## Usage

Follow the MANUAL_TEST_PLAN.md in the main repository to test each command.
EOF

# ============================================================================
# Summary and next steps
# ============================================================================

echo ""
echo "=========================================="
echo "✓ Test Vault Created Successfully"
echo "=========================================="
echo "Location: $VAULT_PATH"
echo ""
echo "Files created:"
find "$VAULT_PATH" -name "*.md" | wc -l | xargs echo "  Markdown files:"
find "$VAULT_PATH" -name "*.png" | wc -l | xargs echo "  Image files:"
echo "  Total directories: $(find "$VAULT_PATH" -type d | wc -l | xargs)"
echo ""
echo "Next steps:"
echo "  1. cd $VAULT_PATH"
echo "  2. Review README.md for vault structure"
echo "  3. Follow MANUAL_TEST_PLAN.md to run tests"
echo ""
echo "Quick test commands:"
echo ""
echo "  # Tags domain"
echo "  vault tags purge test-tag --dry-run"
echo "  vault tags rename old-tag new-tag --dry-run"
echo "  vault tags clean normalize . --dry-run"
echo "  vault tags clean invalid . --dry-run"
echo "  vault tags add notes --dry-run --max-files 2"
echo ""
echo "  # Properties domain"
echo "  vault properties clean normalize . --dry-run"
echo "  vault properties clean deduplicate . --dry-run"
echo "  vault properties validate ."
echo "  vault properties repair . --dry-run"
echo "  vault properties enrich related projects --dry-run"
echo "  vault properties enrich summaries docs --dry-run"
echo ""
echo "  # Images domain"
echo "  vault images find ."
echo "  vault images broken ."
echo "  vault images remove-alt notes --dry-run"
echo ""
echo "  # Index domain"
echo "  vault index broken-links"
echo "  vault index duplicates find"
echo "  vault index rename find"
echo "  vault index build"
echo ""
echo "⚠ Note: AI commands require ANTHROPIC_API_KEY environment variable"
echo "=========================================="
