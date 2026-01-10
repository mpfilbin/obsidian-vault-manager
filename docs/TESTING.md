# Testing Guide for Library

Quick reference for testing the Library vault management tools.

## Quick Start

```bash
pip install -e ".[test]"
pytest                     # runs with config from pyproject.toml
pytest --cov=vault_manager --cov-report=term-missing --cov-report=html
```

## Test Organization

- **BDD Tests** (`tests/features/`) - Behavior-driven tests in Gherkin syntax
- **Unit Tests** (`tests/unit/`) - Traditional pytest unit tests
- **Fixtures** (`tests/conftest.py`) - Shared test fixtures and utilities

## Common Commands

```bash
pytest tests/unit/test_vault_utilities.py
pytest -m unit                # Only unit tests
pytest -m bdd                 # Only BDD tests
pytest --cov=vault_manager --cov-report=html
open htmlcov/index.html       # View coverage report
pytest --pdb                  # Drop into debugger on failure
pytest -x                     # Stop on first failure
pytest --lf                   # Run last failed tests
pytest -m "not slow"          # Skip slow tests
pytest --duration=10          # Show 10 slowest tests
```

## Writing Tests

### BDD Test (Gherkin)

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

### Unit Test

```python
import pytest

class TestMyFunction:
    def test_basic_behavior(self):
        result = my_function("input")
        assert result == "expected"

    def test_error_handling(self):
        with pytest.raises(ValueError):
            my_function(invalid_input)

    @pytest.mark.parametrize("input,expected", [
        ("a", "A"),
        ("b", "B"),
    ])
    def test_multiple_cases(self, input, expected):
        assert my_function(input) == expected
```

## Test Markers

Available markers (defined in `pyproject.toml`):
- `unit` - Unit tests
- `bdd` - BDD tests
- `requires_vault` - Needs real vault
- `requires_ai` - Needs AI API access

Apply markers to organize tests:

```python
@pytest.mark.unit
def test_tag_parsing():
    ...

@pytest.mark.requires_vault
def test_full_scan():
    ...
```

## Fixtures

Common fixtures from `conftest.py`:

```python
def test_with_temp_vault(temp_vault):
    """Use temporary vault."""
    note = temp_vault / "test.md"
    note.write_text("content")

def test_with_database(vault_database):
    """Use vault database."""
    conn = sqlite3.connect(vault_database)
    # ... test database operations

def test_with_populated_data(populated_database):
    """Use database with sample data."""
    # Database already has tags and files
```

## CI/CD Integration

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
          pytest --cov=Library --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Debugging Tips

1. **Use `--pdb`** - Drop into debugger on failure
2. **Use `-s`** - Show print statements
3. **Use `-k pattern`** - Run tests matching pattern
4. **Use `--lf`** - Re-run only failed tests
5. **Use `-vv --showlocals`** - Show all local variables

## Coverage

- Default HTML output goes to `htmlcov/` (set by `--cov-report=html`).
- Sources and omit rules are configured in `pyproject.toml` under `[tool.coverage.*]`.

## Best Practices

1. ✅ Test one thing per test
2. ✅ Use descriptive test names
3. ✅ Use fixtures for setup
4. ✅ Mock external dependencies
5. ✅ Test edge cases and errors
6. ✅ Keep tests fast
7. ✅ Make tests independent
8. ✅ Use appropriate markers

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-bdd documentation](https://pytest-bdd.readthedocs.io/)
- [Gherkin syntax reference](https://cucumber.io/docs/gherkin/reference/)
- **Detailed guide**: See `Library/tests/README.md`

## Configuration

- Pytest reads settings from `pyproject.toml` (`[tool.pytest.ini_options]`).
- No `pytest.ini` is required. Adjust markers, addopts, or testpaths there.

## Getting Help

```bash
# pytest help
pytest --help

# Available fixtures
pytest --fixtures

# Available markers
pytest --markers
```
