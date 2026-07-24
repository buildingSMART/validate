# Reference Information

Reference information is primarily aimed at software vendors and solutions providers that wish to implement the IFC standard.
Typically, this audience is interested in software certification as well.

## Digital Application Authentication

```{include} ./digital-app-auth/purpose.md
:heading-offset: 1
:relative-images:
```

```{include} ./digital-app-auth/implementation.md
:heading-offset: 1
:relative-images:
```

```{include} ./digital-app-auth/user-interface.md
:heading-offset: 1
:relative-images:
```

## Allowlisting

IFC schema definitions occasionally include typos or other minor incorrections.
For example, if a vendor has implemented IFC export capabilities using the correct spelling,
the strict checking of the Validation Service will return an error because there is not an exact match with the schema definition.

For this reason, an allowlist capability has been built in to the platform so that
implementers are not unfairly penalized for an error that originates in the schema definition,
not their implementation.

This capability runs as a post-processing step after the validation process has completed.
For validation outcomes returning more than 10 instances, the allowlisting is only applied to the first 10.
This is considered acceptable as it can only ever result in a false positive (green result displayed on the scoreboard)
and never a false negative (unfair red result displayed on the scoreboard).

## Additional Information for Normative Rules

Occasionally, the Validation Service team will receive inquiries regarding a specific rule that requires
a detailed explanation above and beyond existing documentation in the IFC specification and Validation Service documentation.
The responses to these inquiries are provided here for the benefit of the entire community.

```{include} ./normative-rules/ALB021.md
:heading-offset: 1
:relative-images:
```

```{include} ./normative-rules/ALS016.md
:heading-offset: 1
:relative-images:
```

```{include} ./normative-rules/BRP003.md
:heading-offset: 1
:relative-images:
```
