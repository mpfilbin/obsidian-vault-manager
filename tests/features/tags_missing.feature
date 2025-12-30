Feature: Missing Tags Command
  As a vault maintainer
  I want to identify notes without tags
  So that I can ensure all notes are properly categorized

  Background:
    Given a test vault with markdown files

  Scenario: Find notes without tags in YAML frontmatter
    Given a note "test1.md" with no frontmatter
    And a note "test2.md" with frontmatter but no tags
    And a note "test3.md" with tags in frontmatter
    When I run the missing tags command
    Then the report should list "test1.md"
    And the report should list "test2.md"
    And the report should not list "test3.md"

  Scenario: Generate tagless notes report
    Given 5 notes without tags
    And 10 notes with tags
    When I run the missing tags command
    Then a report file "tagless-notes.md" should be created
    And the report should show "5" files without tags
    And the report should show "10" files with tags
    And the report should show "15" total files

  Scenario: Report includes wiki-links
    Given a note "Personal/Note.md" without tags
    When I run the missing tags command
    Then the report should contain wiki-link "[[Personal/Note]]"

  Scenario: Ignore files in .obsidian directory
    Given a note ".obsidian/config.md" without tags
    When I run the missing tags command
    Then the report should not list ".obsidian/config.md"

  Scenario: Handle empty vault
    Given an empty vault
    When I run the missing tags command
    Then the report should show "0" files without tags
    And the report should show "0" files with tags
    And the report should show "0" total files
