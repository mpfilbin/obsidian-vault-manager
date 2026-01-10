# Testing Guide

This directory contains comprehensive tests for the vault management tools using pytest and pytest-bdd.

## Quick Start

```bash
# Install test dependencies
pip install -e ".[test]"

# Run all tests with coverage
pytest
pytest --cov=vault_manager --cov-report=term-missing --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── features/                # BDD feature files (Gherkin syntax)
│   ├── tags_missing.feature
│   ├── tags_query.feature
│   └── index_broken_links.feature
├── step_defs/              # BDD step definitions
│   └── test_tags_missing_steps.py
├── unit/                   # Traditional unit tests
│   └── test_frontmatter_parsing.py
├── scripts/                # Helper scripts for testing
└── README.md               # This file
```

## Installation

Install test dependencies:

```bash
# Install with test dependencies only
pip install -e ".[test]"

# Or install with all development dependencies (includes AI features and tests)
pip install -e ".[dev]"
```

## Running Tests

### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run with detailed output (show locals on failure)
pytest -vv --showlocals

# Stop on first failure
pytest -x
```

### Run Specific Test Types

```bash
# Run specific test file
pytest tests/unit/test_vault_utilities.py

# Run only BDD tests
pytest -m bdd

# Run only unit tests
pytest -m unit

# Run tests for specific domain
pytest -m tags              # Tag management tests
pytest -m images            # Image management tests
pytest -m properties        # Properties management tests
pytest -m index             # Index management tests

# Skip slow tests
pytest -m "not slow"

# Run last failed tests
pytest --lf

# Run failed tests first
pytest --ff
```

### Coverage Reporting

```bash
# Run tests with coverage
pytest --cov=vault_manager --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=vault_manager --cov-report=html

# View HTML report (opens in browser)
open htmlcov/index.html

# Show slowest tests
pytest --duration=10
```

## Test Categories and Markers

Tests are organized using pytest markers (defined in `pyproject.toml`):

- **`@pytest.mark.unit`** - Unit tests for individual functions/classes
- **`@pytest.mark.integration`** - Integration tests for command workflows
- **`@pytest.mark.bdd`** - BDD tests using pytest-bdd
- **`@pytest.mark.tags`** - Tests for tag management commands
- **`@pytest.mark.images`** - Tests for image management commands
- **`@pytest.mark.properties`** - Tests for properties management commands
- **`@pytest.mark.index`** - Tests for index management commands
- **`@pytest.mark.slow`** - Tests that take significant time
- **`@pytest.mark.requires_vault`** - Tests requiring a real vault structure
- **`@pytest.mark.requires_ai`** - Tests requiring AI API access

Apply markers to organize tests:

```python
@pytest.mark.unit
def test_tag_parsing():
    ...

@pytest.mark.requires_vault
def test_full_scan():
    ...
```

## Writing BDD Tests

### 1. Create a Feature File

Feature files use Gherkin syntax and are stored in `features/`:

```gherkin
Feature: Command Name
  As a user
  I want to do something
  So that I can achieve a goal

  Scenario: Specific test case
    Given some initial context
    When I perform an action
    Then I expect a result
```

### 2. Implement Step Definitions

Step definitions are Python functions that implement the steps:

```python
from pytest_bdd import scenarios, given, when, then, parsers

# Load scenarios from feature file
scenarios('../features/my_feature.feature')

@given('some initial context')
def initial_context(context):
    # Setup code
    pass

@when('I perform an action')
def perform_action(context):
    # Action code
    pass

@then('I expect a result')
def expect_result(context):
    # Assertion code
    assert something
```

### 3. Use Parsers for Dynamic Steps

```python
@given(parsers.parse('a note "{filename}" with tags'))
def note_with_tags(context, filename):
    # filename is extracted from the step text
    pass

@then(parsers.parse('the report should show "{count:d}" files'))
def check_count(context, count):
    # count is automatically converted to int
    pass
```

### BDD Example from docs/TESTING.md

**Feature File** (`features/my_feature.feature`):
```gherkin
Feature: My Feature
  Scenario: Test something
    Given some context
    When I do something
    Then I expect a result
```

**Step Definitions** (`step_defs/test_my_feature_steps.py`):
```python
from pytest_bdd import scenarios, given, when, then

scenarios('../features/my_feature.feature')

@given('some context')
def setup_context(context):
    context['data'] = "test"

@when('I do something')
def perform_action(context):
    context['result'] = process(context['data'])

@then('I expect a result')
def check_result(context):
    assert context['result'] == "expected"
```

## Writing Unit Tests

Unit tests use standard pytest syntax:

```python
import pytest
from vault_manager.module import function

class TestFeature:
    """Group related tests in a class."""

    def test_specific_behavior(self):
        """Test a specific behavior."""
        result = function(input_data)
        assert result == expected_value

    def test_error_handling(self):
        """Test error conditions."""
        with pytest.raises(ValueError):
            function(invalid_input)

@pytest.mark.parametrize("input,expected", [
    ("foo", "FOO"),
    ("bar", "BAR"),
])
def test_with_parameters(input, expected):
    """Test with multiple input/output pairs."""
    assert function(input) == expected
```

## Common Fixtures

The `conftest.py` file provides shared fixtures:

- **`temp_vault`** - Temporary vault directory for testing
- **`vault_with_notes`** - Vault with sample markdown notes
- **`vault_database`** - Empty vault.db database
- **`populated_database`** - Database with sample tag data
- **`mock_vault_root`** - Mocks get_vault_root() to use temp vault
- **`mock_database_path`** - Mocks get_database_path() to use temp database
- **`sample_frontmatter`** - Sample YAML frontmatter strings

### Using Fixtures

```python
def test_with_temp_vault(temp_vault):
    """Test using temporary vault."""
    # temp_vault is a Path object
    note = temp_vault / "test.md"
    note.write_text("# Test")
    assert note.exists()

def test_with_database(vault_database):
    """Test using vault database."""
    conn = sqlite3.connect(vault_database)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tags")
    count = cursor.fetchone()[0]
    assert count > 0

def test_with_populated_data(populated_database):
    """Test using database with sample data."""
    # Database already has tags and files
    pass
```

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests
2. **Use Fixtures**: Leverage fixtures for common setup to keep tests DRY
3. **Descriptive Names**: Test names should clearly describe what they test
4. **One Assertion Per Test**: Focus each test on a single behavior
5. **Use Markers**: Tag tests appropriately for easy filtering
6. **Mock External Dependencies**: Use mocks for file I/O, databases, API calls
7. **Test Edge Cases**: Include tests for error conditions and boundary values

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[test]"

      - name: Run tests
        run: |
          pytest --cov=vault_manager --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Debugging Tests

```bash
# Run tests with Python debugger
pytest --pdb

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Show locals on failure
pytest -vv --showlocals

# Run last failed tests only
pytest --lf

# Run failed tests first, then others
pytest --ff

# Run tests matching a pattern
pytest -k pattern
```

## Writing New Tests

When adding new functionality:

1. **Write BDD feature first** - Define expected behavior in Gherkin
2. **Implement step definitions** - Make the feature executable
3. **Run and watch it fail** - Confirm test detects missing functionality
4. **Implement the feature** - Add the actual code
5. **Run and watch it pass** - Confirm feature works
6. **Add unit tests** - Test edge cases and internal functions
7. **Refactor with confidence** - Tests ensure nothing breaks

## Test Coverage Goals

- **Overall coverage**: Aim for >80%
- **Core utilities**: Aim for >90%
- **Command implementations**: Aim for >75%
- **Edge cases**: All known error conditions should be tested

## Configuration

- Pytest reads settings from `pyproject.toml` (`[tool.pytest.ini_options]`).
- No `pytest.ini` is required. Adjust markers, addopts, or testpaths there.
- Coverage configuration is in `pyproject.toml` under `[tool.coverage.*]`.

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-bdd documentation](https://pytest-bdd.readthedocs.io/)
- [Gherkin syntax reference](https://cucumber.io/docs/gherkin/reference/)

## Getting Help

```bash
# pytest help
pytest --help

# Available fixtures
pytest --fixtures

# Available markers
pytest --markers
```
