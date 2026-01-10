---
applyTo: 'tests/features/**.feature, '
description: 'description'
---
## Guidance for Behavior-Driven-Development (BDD) Tests

### For Writing Feature files (features/**.feature)
1. **Use Clear and Consistent Language**: Write in simple language that all stakeholders can understand. Avoid technical jargon.
2. **Structure Scenarios Properly**: Follow the Given-When-Then format. "Given" sets up the context, "When" states the action taken, and "Then" describes the expected outcome.
3. **Focus on Business Outcomes**: Scenarios should reflect business rules and objectives, not technical details.
4. **Be Specific**: Avoid ambiguity by being as specific as possible in your scenarios.
5. **Keep It Simple**: Each scenario should test a single piece of functionality to keep tests easy to read and maintain.
6. **Use Background Wisely**: Use the Background section to define the common setup steps shared across scenarios in a feature.
7. **Avoid Long Scenarios**: If a scenario gets too long, break it down into smaller, more focused scenarios.
8. **Make Scenarios Independent**: Each scenario should be self-contained and able to run independently.
9. **Names Matter**: Use descriptive names for your features, scenarios, and steps to make them understandable at a glance.
10. **Review and Refine**: Regularly review and update scenarios with feedback from team members to ensure relevance and accuracy.
11. **Modular**: Keep the specHere are some best practices for writing step definitions in BDD using Gherkin:

### For Writing Step Definitions (step_defs/*.py)
1. **Keep Steps Simple and Declarative**: Ensure that each step clearly describes the behavior without delving into implementation details.
2. **Use Consistent Naming Conventions**: Maintain consistent language and naming conventions across all steps to improve readability.
3. **Reuse Step Definitions**: Create reusable steps to avoid duplication. This helps maintain consistency and reduces maintenance effort.
4. **Ensure Steps are Independent**: Write steps that can be executed independently without relying on the order of execution. This increases flexibility and reliability in your tests.
5. **Match Steps Specifically**: Ensure that regular expressions used for step matching are specific enough to avoid accidental matches with unintended steps.
6. **Avoid Business Logic in Steps**: Keep the logic out of step definitions. Use these to call more detailed implementation code.
7. **Parameterize When Possible**: Use parameters in steps to handle multiple scenarios with similar steps, improving reuse and clarity.
8. **Use Comments and Doc Strings Wisely**: Add comments where necessary and use Doc Strings for handling large data inputs that don't fit well as a single line.
9. **Organize Step Definitions Logically**: Group related step definitions in the same file or module to keep the codebase organized and easy to navigate.
10. **Regularly Refactor**: Continuously review and refactor step definitions to simplify, remove redundancy, and improve clarity.
