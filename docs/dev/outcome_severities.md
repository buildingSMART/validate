# Outcome Severities

Note: This documentation was developed in Nov 2024 based on the codebase at version 0.6.8.

## Overview - Database model enumerations

Severities are an enumeration of possible values for the severity of a
[Validation Outcome](https://github.com/buildingSMART/ifc-validation-data-model/blob/main/models.py#L978).

| String Value   | Integer Enumeration Value |
|----------------|---------------------------|
| EXECUTED       | 1                         |
| PASSED         | 2                         |
| WARNING        | 3                         |
| ERROR          | 4                         |
| NOT_APPLICABLE | 0                         |

## Severity Usage

### Schema Check

Schema checks are always applicable and therefore the only possible enumeration values are `PASSED` and `ERROR`.
[Passing outcomes for schema checks are stored to the database](https://github.com/buildingSMART/validate/blob/8f04bcc6d1f400240485a33b2c81e2f7d0edbeab/backend/apps/ifc_validation/tasks.py#L607).

### Syntax Check

Syntax checks are also always applicable and therefore the only possible enumeration values are `PASSED` and `ERROR`.
[Passing outcomes for syntax checks are stored to the database](https://github.com/buildingSMART/validate/blob/8f04bcc6d1f400240485a33b2c81e2f7d0edbeab/backend/apps/ifc_validation/tasks.py#L607).

### Gherkin Rules (Normative Rules and Industry Best Practices)

These rules are generally processed in similar fashion.
Unlike syntax and schema checks, a gherkin rule may or may not be applicable to a given model depending on the schema
and content of the model.
For example, alignment rules are only applicable to models with schema `IFC4X3_ADD2` as those entities were not part of
the
`IFC2X3` or `IFC4` schema versions.

Therefore, both sets of validation checks can potentially also return outcomes with severity of `NOT_APPLICABLE`.

#### Normative Rules

Normative rules enforce requirements from implementer agreements and informal propositions.
Therefore, the potential outcomes are:

- `NOT_APPLICABLE`
- `ERROR`
- `PASSED`

#### Industry Best Practices

Industry Best Practice checks enforce items that are not required,
but rather represent the preferred or most idiomatic way of implementing the IFC standard.

Therefore, the potential outcomes are:

- `NOT_APPLICABLE`
- `WARNING`
- `PASSED`

#### Gherkin Rule processing

Currently there are no individual instance outcomes from gherkin rules stored with severity=`PASSED`.
The initial idea was to pass them to the DB but it was quickly flooded with outcomes of this severity
and is currently [commented out](https://github.com/buildingSMART/ifc-gherkin-rules/blob/b363041433f252fc1b9e043ee3aac0bd6fcfad3d/features/steps/validation_handling.py#L254-L268).

_(potentially remove the following paragraph to avoid confusion...)_

When processing gherkin rules (*.feature files) with `behave`, Severity=`PASSED` is used only for `Given` statements.
A `PASSED` outcome is added to the temporary outcomes when the conditions of a `Given` statement are met.

The entire processing loop is as follows:

1. Severity=`NOT_APPLICABLE` is applied to all entity instances
2. The `Given` statements are executed
3. If there is *at least one* entity instance that meets the requirement of *ALL* `Given` statements,
   the rule is considered to be "activated" and severity=`EXECUTED` is applied to these instance(s).
   This is an 'all or nothing' situation where all `Given` statements must be "activated" in order for the rule
   to be considered "activated".
4. Those instance(s) are then tested against the `Then` statements.
5. Severity=`ERROR` is applied to each instance that fails a requirement of a `Then` statement.

If there is at least one instance with an `ERROR` outcome then an aggregated status for the rule is returned as follows:

- Severity=`ERROR` for normative rules (implementer agreements and informal propositions)
- Severity=`WARNING` for industry best practices.

This status is used to colour the "block" for each rule in the validation report.

## Outcome display and reporting

### Individual rules (Normative and Industry Best Practices)

Outcomes are always reported in the web UI based on aggregated status of all instances
activated by a given rule.

| Aggregated Value of `Severity` for a rule | Display colour | Label reported in `Severity` column |
|-------------------------------------------|----------------|-------------------------------------|
| `NOT_APPLICABLE`                          | grey           | 'N/A'                               |
| `EXECUTED`                                | green          | 'Applicable'                        |
| `PASSED`                                  | (not used)     |                                     |
| `WARNING`                                 | yellow         | 'Warning'                           |
| `ERROR`                                   | red            | 'Error'                             |

Display colour is determined by the
[statusToColor](https://github.com/buildingSMART/validate/blob/development/frontend/src/mappings.js#L1)
mapping function.

Display label is determined by the 
[statusToLabel](https://github.com/buildingSMART/validate/blob/development/frontend/src/mappings.js#L10)
mapping function.

### Overall status

A single overall status for each type of check (syntax, schema, normative rules, best practices)
is displayed on the Validation Service dashboard for each model.

The overall status of each
[ValidationTask](https://github.com/buildingSMART/ifc-validation-data-model/blob/main/models.py#L778)
is captured in a different data structure of
[Model.Status](https://github.com/buildingSMART/ifc-validation-data-model/blob/main/models.py#L324)
with the following possible enumeration values:

| Value of `Model.Status` | Display colour | Symbol                                                                       |
|-------------------------|----------------|------------------------------------------------------------------------------|
| `VALID`                 | green          | CheckCircleIcon                                                              |
| `INVALID`               | red            | WarningIcon                                                                  |
| `NOT_VALIDATED`         | grey           | HourglassBottomIcon                                                          |
| `WARNING`               | yellow         | ErrorIcon                                                                    |
| `NOT_APPLICABLE`        | grey           | BrowserNotSupportedIcon (technically possible but doesn't occur in practice) |

The options for overall status of each category of ValidationTask are as follows:

- Syntax and Schema
  - `VALID`
  - `INVALID`

- Normative Rules
  - `VALID`
  - `INVALID`
  - `NOT_APPLICABLE`

- Best Practices
  - `VALID`
  - `WARNING`
  - `NOT_APPLICABLE`

The overall status of a normative rule ValidationTask is determined by
[taking the highest severity](https://github.com/buildingSMART/ifc-validation-data-model/blob/f32164ab762fc695690d380e12e87c815b641912/models.py#L948)
of outcomes for all the rules contained in that task.

