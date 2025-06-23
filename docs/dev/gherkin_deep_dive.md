# A deep dive into gherkin rule implementations

## Decorators

### `@gherkin_ifc`

This is used in place of `behave`'s default `@step_implementation` decorator
to provide additional capabilities related to context stacking and other concerns
related to tracking and evaluating instances in the IFC model.

### `@register_enum_type`

This is a small new decorator for registering enumeration types in a simpler way.

---
## Step handling

### `execute_step()`

Checks whether the current step being processed is a `Given` or `Then`.

### `handle_given()`

Handles a `Given` step.

### `handle_then()`

Handles a `Then` step.

---
## Context stacking

As steps are processed, they are captured in a persistent object of type `behave.runner.Context`.
This context object includes a hidden attribute `_stack` that is used to 'stack' information
and results for each step that is processed.

It can be helpful to monitor the content of the `instances` attribute of each item in the 
`context._stack` list.

---

## Feature Tags

Feature tags in Behave are used to categorize and control the execution of Gherkin-based test rules in the validation service. These tags are placed at the top of each `.feature` file and can be referenced through the command-line interface using the `--tags` option and are accessed through `context.tags` within the step implementation files.

### `@informal_propositions` and `@implementer-agreement`

These tags mark **normative IFC rules**, which result in either **passes** or **errors** in the validation service UI.

> **Note:** These tags are planned to be merged into a single tag: `@normative-rule`.

To run only these rules via command line:

> python3 -m behave --no-capture -v --tags=@informal-propositions --define input=/path/to/your.ifc

### `@industry-practice`

This tag indicates **best practice rules**. These result in **passing**, **warning**, or **not applicable** outcomes.

To execute these locally:
> python3 -m behave --no-capture -v --tags=@industry-practice --define input=/path/to/your.ifc

### `@disabled`

Rules marked with this tag are **disabled** and will not be executed by the validation service.

To explicitly **exclude** a rule, use the same --tags variable and a hyphen:
> python3 -m behave --no-capture -v --tags=@informal-propositions --tags=-@disabled --define input=/path/to/your.ifc



### `@AAA000`

This tag identifies the **functional part** (`AAA`) and the **rule number** (`000`). For example:

- The fourth rule in the georeferencing functional part (accounting for `@GRF000`) would be tagged as `@GRF003`.


### `@versionX`

This tag indicates the version of the `.feature` file.
The version number gets incremented whenever meaningful changes are made to the rule after its release.
A 'meaningul' change is one that could result in different outcomes for the same IFC model.

Minor changes such as fixing typos or adding control characters to a step implementation
are not considered a 'meaningful' change as they do not affect the end results of the validation process.


### `@no-activation`

This tag ensures that a passing result does not activate the functional part. Instead, it will be marked as not applicable.

For example, GRF003, which is a georeferencing rule, validates whether every IfcFacility is linked to an IfcCoordinateReferenceSystem. However, the presence of an IfcFacility does not necessarily imply that the file is intended to include georeferencing. Therefore, if georeferencing is not required, the rule should not trigger a "pass" status that marks that functional part green on the software certification scorecards.

By tagging the rule with @no-activation, no validation outcome with severity "Executed" and result "Passed" is recorded in the database, and the rule is not marked as passed. 

**This tag has no effect on error outcomes** — if the rule fails, the error is still raised and recorded as usual.
