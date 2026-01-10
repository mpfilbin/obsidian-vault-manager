---
applyTo: 'tests/unit/**.py'
description: 'Instructions for following unit testing best practices'
---
# Guidance for Writing Unit Tests

1. Write Clear and Concise Tests: Ensure each test checks one particular case or behavior and should pass or fail for only one reason.
2. Use Descriptive Names: Test names should describe what they are testing and the expected outcome.
3. Each test should exercise a single code path - branches in logic should be exercised by different tests. 
4. Use comments in test files sparingly - only add comments to clarify intention, otherwise the test should convey the intention themselves.
5. Maintain Independence: Tests should be independent of each other. Avoid shared state and ensure tests can run in any order.
6. Follow Arrange, Act, Assert (AAA) Pattern: Arrange - Set up the test data and environment, Act - Execute the functionality being tested. Assert - Verify that the outcome is as expected.    
