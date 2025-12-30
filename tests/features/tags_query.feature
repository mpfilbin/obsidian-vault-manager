Feature: Tags Query Command
  As a vault maintainer
  I want to query tag statistics and information
  So that I can understand tag usage patterns

  Background:
    Given a vault database with tag data

  Scenario: Query tag statistics
    Given the database has 100 tags
    And 50 files with tags
    When I run "vault tags query --stats"
    Then the output should show "100" unique tags
    And the output should show tag distribution statistics

  Scenario: Query most used tags
    Given tags with usage counts:
      | tag                   | count |
      | software-architecture | 45    |
      | software-development  | 38    |
      | security              | 25    |
      | design-principles     | 20    |
    When I run "vault tags query --most-used 3"
    Then the output should list "software-architecture" first
    And the output should list "software-development" second
    And the output should list "security" third
    And the output should not list "design-principles"

  Scenario: Query files with specific tags
    Given files tagged with "software-architecture" and "design-principles":
      | file                |
      | SOLID Principles.md |
      | Clean Code.md       |
    When I run "vault tags query --files-with software-architecture design-principles"
    Then the output should list "SOLID Principles.md"
    And the output should list "Clean Code.md"

  Scenario: Query with custom SQL
    Given a populated tag database
    When I run "vault tags query --sql 'SELECT COUNT(*) FROM tags'"
    Then the output should show query results

  Scenario: Handle missing database
    Given no vault database exists
    When I run "vault tags query --stats"
    Then the command should fail with error "Database not found"
