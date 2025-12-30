Feature: Broken Links Command
  As a vault maintainer
  I want to identify broken wiki-links
  So that I can fix or remove invalid references

  Background:
    Given a vault database with link data

  Scenario: Find broken wiki-links
    Given a note "source.md" with link "[[NonExistent]]"
    And no note exists at "NonExistent.md"
    When I run the broken-links command
    Then the report should list "[[NonExistent]]" as broken
    And the source should be "source.md"

  Scenario: Exclude self-references in report
    Given a note "broken-links.md" with broken links
    When I run the broken-links command
    Then the report should not include links from "broken-links.md"

  Scenario: Group broken links by source file
    Given a note "note1.md" with broken links:
      | link      |
      | [[Foo]]   |
      | [[Bar]]   |
    And a note "note2.md" with broken links:
      | link      |
      | [[Baz]]   |
    When I run the broken-links command
    Then the report should show "note1.md" with 2 broken links
    And the report should show "note2.md" with 1 broken link

  Scenario: Include line numbers for broken links
    Given a note with a broken link on line 15
    When I run the broken-links command
    Then the report should show line number "15"

  Scenario: Generate clickable wiki-links for source files
    Given a broken link in "Personal/Software Architecture/SOLID.md"
    When I run the broken-links command
    Then the report should contain "[[Personal/Software Architecture/SOLID]]"

  Scenario: Handle vault with no broken links
    Given all wiki-links resolve correctly
    When I run the broken-links command
    Then the report should show "0" broken links
    And the report should show "0" affected files
