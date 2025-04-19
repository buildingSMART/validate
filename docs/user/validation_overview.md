# Understanding the validation process

Given an IFC file, the Validation Service provides a judgement of conformity
against the IFC standard - including schema and specification

## STEP Syntax

The first step in the validation process looks at the uploaded file to confirm that
it is a valid STEP Physical File (SPF) in accordance with [ISO 10303-21](https://www.iso.org/standard/63141.html).

## IFC Schema

Schema validation consists of two parts:

1. Schema Version
2. Schema Compliance

### Schema Version

This check confirms that the schema identifier is one of the following:

- `IFC2X3`
- `IFC4`
- `IFC4X3_ADD2`

### Schema Compliance

The schema compliance checks the following aspects that are defined in the EXPRESS schema:

 - Entity attributes are correctly populated, correct number of attributes and correct type and cardinalities in case of aggregates
 - Inverse attributes are correctly populated and with the correct cardinalities
 - Entity-scoped `WHERE` rules
 - Global rules

This check also flags any entity types that are not included in a given schema version, or the instantiation of abstract entities.

For example: `IfcAlignment` entity is only valid for schema version `IFC4X3_ADD2`,
so it is not valid as part of a file with schema version `IFC2X3`.

## Normative Checks

There are two categories of normative checks:

1. Implementer Agreements
2. Informal Propositions

### Implementer Agreements

These are normative checks that have been ratified as official agreements amongst software implementers.

### Informal Propositions

These are normative checks that have not been ratified as implementer agreements,
but are still considered mandatory for a file to be considered valid.

## Additional, Non-normative Checks

### Industry Practices

This step involves checking the IFC file against common practices and sensible defaults.
None of these checks render the IFC file invalid.
Therefore, any issues identified result in warnings rather than errors.

### buildingSMART Data Dictionary (bSDD) Compliance

```{note}
bSDD Checks are temporarily disabled as of v0.6.6.
```

