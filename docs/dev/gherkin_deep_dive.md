# A deep dive into gherkin rule implementations

## Decorators

### `@gherkin_ifc`

This is used in place of `behave`'s default `@step_implementation` decorator
to provide additional capabilities related to context stacking and other concerns
related to tracking and evaluating instances in the IFC model.

### `@register_enum_type`

This is a small new decorator for registering enumeration types in a simpler way.

## Step handling

### `execute_step()`

Checks whether the current step being processed is a `Given` or `Then`.

### `handle_given()`

Handles a `Given` step.

### `handle_then()`

Handles a `Then` step.

## Context stacking

As steps are processed, they are captured in a persistent object of type `behave.runner.Context`.
This context object includes a hidden attribute `_stack` that is used to 'stack' information
and results for each step that is processed.

It can be helpful to monitor the content of the `instances` attribute of each item in the 
`context._stack` list.
