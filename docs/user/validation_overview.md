# Understanding the steps of the validation process

## Syntax

The first step in the validation process looks at the uploaded file to confirm that
it is a valid STEP Physical File (SPF) in accordance with [ISO 10303-21](https://www.iso.org/standard/63141.html).

## Schema

Schema validation consists of two parts:

1. Schema Version
2. Schema Compliance

### Schema Version

This check confirms that the schema identifier is one of the following:

- `IFC2X3`
- `IFC4`,
- `IFC4X3_ADD2`

### Schema Compliance

The schema compliance checks that all `WHERE` rules in the EXPRESS schema have passed.
This check also flags any entity types that are not included in a given schema version.

For example: `IfcAlignment` entity is only valid for schema version `4X3_ADD2`,
so it is not valid as part of a file with schema version `IFC2X3`.

## Normative Checks

There are two categories of normative checks:

1. Implementer Agreements
2. Informal Propositions
3. Industry Practices

### Implementer Agreements

These are normative checks that have been ratified as official agreements amongst software implementers.

### Informal Propositions

These are normative checks that have not been ratified as implementer agreements,
but are still considered mandatory for a file to be considered valid.

### Industry Practices

These series of checks are different than the previous two in that they will only raise a warning and not be considered an error.

## bsDD Checks

These checks verify that all applicable buildingSMART Data Dictionary (bsDD) requirements are met.
