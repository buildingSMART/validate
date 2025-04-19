# Detailed Information for Normative Rules

Follow these steps to add a new rule to the Validation Service

| n. | Step                                                                                     | Responsible                 |
|----|------------------------------------------------------------------------------------------|-----------------------------|
| 1  | Create a new branch in the bSI ifc-gherkin-rules repository                              | bSI Validation Service team |
| 2  | In this branch, start developing the rule needed **following instructions below**        | rule developer              |
| 3  | Create a pull request to further test the rule(s) behavior using the sandbox environment | rule developer              |
| 4  | Assign a reviewer to the pull request when you think the rule is ready to be merged      | rule developer              |
| 5  | Review the pull request                                                                  | bSI Validation Service team |
| 6  | (optional) Fix the rule according to feedback from reviewer                              | rule developer              |
| 7  | Approve and merge the pull request                                                       | bSI Validation Service team |

## 1. Branch creation

In the buildingSMART [GitHub repository containing all rules](https://github.com/buildingSMART/ifc-gherkin-rules), create the branch that will be used to develop the new rule.

- Name the branch with the name of the new rule. Example: `GEM900` for a new rule in the geometry functional part
- Add 1 rule per branch, to facilitate review (1 rule = 1 `.feature` file)

## 2. Rule development

A rule is considered complete when it has:

- a Gherkin [**feature file**](21-write-feature-files-gherkin-rules-for-ifc)
- corresponding python implementation (aka, [**python steps**](22-write-python-steps))
- a set of [**unit test files**](23-write-unit-test-files)

Below are instructions for all these 3 components.

(21-write-feature-files-gherkin-rules-for-ifc)=
### 2.1) Write feature files (gherkin rules) for IFC

A feature file is a file, written using Gherkin syntax, describing the rule behavior.
In the branch just created, add a Gherkin feature file following these instructions.

**File format**: `.feature`

**Location**: https://github.com/buildingSMART/ifc-gherkin-rules/tree/main/features

#### Naming convention for feature files

- The file name is rule code_rule title
- The rule code is made of 3 digits capital letters (taken from the list of [Functional parts](./functional_parts.md)) + 3 digits number
- The rule code, and rule title, must be unique
- The rule title shall have no space and shall use `-` as separator

<details><summary>wrong</summary>

```
SPS001 - Basic-spatial-structure-for-buildings.feature
SPS001_Basic spatial structure for buildings.feature
SPS001 - Basic spatial structure for buildings.feature
```
</details>
<details><summary>right</summary>

```
SPS001_Basic-spatial-structure-for-buildings.feature
```
</details>

#### Mandatory content

`.feature` files:
- must include one and only one of these tags to classify the validation category:
    - `@critical`
    - `@implementer-agreement`
    - `@informal-proposition`
    - `@industry-practice` (warning; not a pass / fail)
- must include a 3-character alpha tag to the functional part. See [Functional parts](./functional_parts.md)
- must include a single tag indicating the version of the feature file as a 1-based integer
  - Example: `@version1` for initial version of a feature file
  - Example: `@version3` for the third version of a feature file
    - Minor changes such as fixing typos or re-wording the description do not increment the version
    - Any change to a **"Given"** or **"Then"** statement, or to a step implementation, requires the version number to be incremented by 1.
- must include one or more tags indicating the [error code](error-codes) to be raised
  - If all scenarios raise the same error, then this tag should be placed immediately above the **"Feature:"** line

    <details><summary>example</summary>

    ```
    @implementer-agreement
    @GRF
    @version1
    @E00050
    Feature: GRF001 - Identical....
    ```

    </details>

    - If some scenarios raise different error codes, then this tag should be placed immediately above each **"Scenario"
      ** line

    <details><summary>example</summary>

    ```
    @implementer-agreement
    @ALS
    @version1
    Feature: ALS005 - Alignment shape representation

    Background: ...

    @E00020
    Scenario: Agreement on ... representation - Value

    @E00010
    Scenario: Agreement on ... representation - Type
    ```
 
    </details>
  
- must include exactly 1 Feature
- the naming convention for the Feature is the following: rule code - rule title (the same used for the file name). For the rule title blank spaces must be used instead of `-` 

<details><summary>wrong</summary>

```
Feature: ALB001_Alignment Layout

Given ...
Then ...
```
```
@ALB
Feature: ALB001_Alignment-Layout

Given ...
Then ...
```
```
@ALB
Feature: ALB001 - Alignment-Layout

Given ...
Then ...
```

</details>
<details><summary>right</summary>

```
@ALB
Feature: ALB001 - Alignment Layout

Given ...
Then ...
```
</details>

 - must include **a description of the rule** that start with "The rule verifies that..." 

<details><summary>example</summary>

```
@implementer-agreement
@ALB
Feature: ALB003 - Allowed entities nested in Alignment
The rule verifies that an Alignment has a nesting relationship with its components (i.e., Horizontal, Vertical, Cant layouts) or with Referents (e.g., mileage markers). And not with any other entity.

  Scenario: Agreement on nested elements of IfcAlignment
  Given ...
  Then ...
```
</details>

#### Mandatory Given(s)
If the rule in the feature file applies only to specific IFC version(s) and/or View Definition(s), then the feature file (or each of its Scenarios, if it has more than one) must start with Given steps specifying the applicability of the following steps

<details><summary>examples</summary>

```
Given A model with Schema "IFC2X3"
Given A file with Model View Definition "CoordinationView"
```
```
Given A model with Schema "IFC2X3" or "IFC4"
Given A file with Model View Definition "CoordinationView" or "ReferenceView"
```
</details>

#### Optional content
`.feature` files:
- can include 1 or more Scenarios
- Scenario titles have no constraints
- can include the `@disabled` tag to temporarily remove them from processing

#### No spaces between steps

<details><summary>wrong</summary>

```
Given A model with Schema "IFC4.3"

Then Each IfcAlignmentHorizontal must be nested only by 1 IfcAlignment
Then Each IfcAlignmentVertical must be nested only by 1 IfcAlignment
Then Each IfcAlignmentCant must be nested only by 1 IfcAlignment
```
</details>
<details><summary>right</summary>

```
Given A model with Schema "IFC4.3"
Then Each IfcAlignmentHorizontal must be nested only by 1 IfcAlignment
Then Each IfcAlignmentVertical must be nested only by 1 IfcAlignment
Then Each IfcAlignmentCant must be nested only by 1 IfcAlignment
```
</details>

#### Watch out for extra blank spaces

<details><summary>wrong</summary>

```
Given A model with Schema "IFC4.3"
Then Each IfcAlignmentHorizontal must be nested only by 1 IfcAlignment
Then  Each IfcAlignmentVertical must be nested only by 1 IfcAlignment
Then  Each IfcAlignmentCant must be nested only by 1 IfcAlignment
```
</details>
<details><summary>right</summary>

```
Given A model with Schema "IFC4.3"
Then Each IfcAlignmentHorizontal must be nested only by 1 IfcAlignment
Then Each IfcAlignmentVertical must be nested only by 1 IfcAlignment
Then Each IfcAlignmentCant must be nested only by 1 IfcAlignment
```
</details>

#### Do not use punctuation at the end of the steps

<details><summary>wrong</summary>

```
Given A model with Schema "IFC4.3",
Then Each IfcAlignmentHorizontal must be nested only by 1 IfcAlignment;
Then Each IfcAlignmentVertical must be nested only by 1 IfcAlignment;
Then Each IfcAlignmentCant must be nested only by 1 IfcAlignment.
```
</details>
<details><summary>right</summary>

```
Given A model with Schema "IFC4.3"
Then Each IfcAlignmentHorizontal must be nested only by 1 IfcAlignment
Then Each IfcAlignmentVertical must be nested only by 1 IfcAlignment
Then Each IfcAlignmentCant must be nested only by 1 IfcAlignment
```
</details>

#### Be careful when typing parameters. They are case-sensitive!

<details><summary>wrong</summary>

```
Given A model with schema "IFC4.3",
```
</details>
<details><summary>right</summary>

```
Given A model with Schema "IFC4.3"
```
</details>

#### Must vs Shall
Use **must**, not **shall** to impose requirements.
[ALB001_Alignment-in-spatial-structure.feature](https://github.com/buildingSMART/ifc-gherkin-rules/blob/main/features/ALB002_Alignment-layout.feature)
"Shall" is ambiguous, also in the legal field the community is moving to a strong preference for “must” as the clearest way to express a requirement or obligation.

<details><summary>wrong</summary>

```
Given A model with Schema "IFC2X3"
Given A file with Model View Definition "CoordinationView"
Then There shall be exactly 1 IfcSite element(s)
```
</details>
<details><summary>right</summary>

```
Given A model with Schema "IFC2X3"
Given A file with Model View Definition "CoordinationView"
Then There must be exactly 1 IfcSite element(s)
```
</details>

#### Verbs for IFC relationships

When a rule requires a specific IFC relationship to exist, refer to the table below for the right verb to be used.

| IFC relationship       | Verb for rules        | Examples                                                           |
|------------------------|-----------------------|--------------------------------------------------------------------|
| IfcRelAggregates       | aggregate, aggregates | Then IfcSite must aggregate IfcBuilding                            |
| IfcRelNests            | nest, nests           | Then Each IfcAlignmentVertical nests a list of IfcAlignmentSegment |
| ...                    |                       |


#### Reference for schema versioning

Rules that are applicable only to specific schema versions must specify
the schema version with the initial `Given` statement.

For example, alignment entities were introduced in IFC4.3 and are not valid
in earlier schema versions.

```
Given A model with Schema "IFC4.3"
Given An IfcAlignment
Then ...
```

Multiple schema versions may be specified if applicable.

```
Given A model with Schema "IFC2X3" or "IFC4"
Given An IfcElement
Then ...
```

##### Valid (active, not withdrawn or retired) Schema Versions 

| Version | Formal Name   | Schema id   | Common Name |
|---------|---------------|-------------|-------------|
| 4.3.2.0 | IFC4.3 ADD2   | IFC4X3_ADD2 | IFC4.3      |
| 4.0.2.1 | IFC4 ADD2 TC1 | IFC4        | IFC4        |
| 2.3.0.1 | IFC2x3 TC1    | IFC2X3      | IFC2x3      |

(22-write-python-steps)=
### 2.2) Write python steps 

The python steps are the implementation (using python language) of the Gherkin grammar used in the feature files.
In the same branch used for the Gherkin rules, change or add python steps following these instructions.

**File format**: `.py`

**Location**: https://github.com/buildingSMART/ifc-gherkin-rules/tree/main/features/steps

#### Naming convention for python files

For the moment, all python steps are contained in [steps.py](https://github.com/buildingSMART/ifc-gherkin-rules/blob/main/features/steps/steps.py). Therefore, **you should not create a new python file, just expand the existing one.**

:construction: :construction: :construction:
*In the future, when this file grows, python steps may be splitted in more files - using a certain criteria (e.g., functional parts). When this will be the case, the instruction will be: locate the best .py file to host your steps and start adding your steps*

#### Steps parametrisation

When creating a new step, think about parametrisation and optimisation of the step for future uses.

#### Step re-use

Before creating a new step, check if something similar already exist.
Try to reuse existing steps.

#### Do not use "when" or "And" keywords

The "when" keyword must not be used.
The "And" keyword must not be used.
Instead, repeat the "Given" or "Then" as appropriate.

Allowed keywords are: `Given`, and `Then`.

#### Use of existing IfcOpenShell APIs

Try not to use existing functionality included in the `ifcopenshell.api` namespace.








(23-write-unit-test-files)=
### 2.3) Write unit test files 

Unit test files are atomic IFC files, created to develop a rule and test its behavior.
In the same branch used for the Gherkin rules, and python steps, create unit test files following these instructions. **IMPORTANT**: every rule developed must have a set of unit test files.

**File format**: `.ifc`

**Location**:[ifc-gherkin-rules/tree/main/test/files](https://github.com/buildingSMART/ifc-gherkin-rules/tree/main/test/files)

- in the test/files folder, create a subfolder using the rule code (E.g., ALB001)
- add the set of unit test files for that rule in this subfolder

#### Naming convention for unit test files

Unit test files must follow this naming convention:

`Expected result`-`rule code`-`rule scenario`-`short_informative_description`.ifc

Or in case where a rule has no scenarios:
`Expected result`-`rule code`-`short_informative_description`.ifc

<details><summary>Examples</summary>

```shell
pass-alb001-short_informative_description.ifc
fail-alb001-scenario01-short_informative_description.ifc
fail-alb001-short_informative_description.ifc
```

</details>


#### Content of the unit tests subfolder

The unit test subfolder must contain:

- all unit test files (.ifc)
- a README file (.md), listing the files and their expected behavior. Using the [template table](#table-template-for-unit-test-files) below
- where used, the script (.py) created to generate the unit test files 

#### Number of unit tests required

- Each rule developed must have a set of unit test files
- There must be at least 1 fully compliant unit test file
- Fail files must cover all scenarios of the rule

(table-template-for-unit-test-files)=
#### Table template for unit test files

Example table describing unit test expected results

| File name                                             | Expected result | Error log                                                                        | Description                                                                      |
|-------------------------------------------------------|-----------------|----------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| pass-alb002-alignment-layout                          | success         | n.a.                                                                             |                                                                                  |
| fail-alb002-scenario01-nested_attributes_IfcAlignment | fail            | The instance IfcAlignment is nesting two instances of IfcAlignmentHorizontal ... | Error is descriptive or exactly the error in pytest? If exactly, multiple row... |
| fail-alb002-scenario02-two_alignments                 | fail            | The following 2 instances were encountered: IfcAlignment #23, IfcAlignment #906  | For IfcAlignmentHorizontal, IfcAlignmentVertical and IfcAlignmentCant            |
| fail-alb002-scenario03-layout                   | fail            | The instance #906=IfcAlignment is nesting #907=IfcWall                           | Includes errors for scenario 2                                                   |
| fail-alb002-scenario04-alignment_segments             | fail            | The instance (s) #28=IfcAlignmentHorizontal is assigned to #906=IfcWall          | @todo IfcAlignmentVertical, IfcAlignmentCant. As well as empty list/typo's?      |



## 4. Assign a reviewer to the pull request
...
## 5. Review the pull request
...
## 6. (optional) Fix the rule according to feedback from reviewer
...
## 7. Approve and merge the pull request
...

## Appendix

(error-codes)=
### Error Codes

Error codes are used to classify and categorize outcomes from the validation service and are
implemented in [ifc-validation-data-model/main/models.py#L937](https://github.com/buildingSMART/ifc-validation-data-model/blob/main/models.py#L937).

| Error Code | Description                            |
|------------|----------------------------------------|
| P00010     | Passed                                 |
| N00010     | Not Applicable                         |
|            |                                        |
| E00001     | Syntax Error                           |
| E00002     | Schema Error                           |
| E00010     | Type Error                             |
| E00020     | Value Error                            |
| E00030     | Geometry Error                         |
| E00040     | Cardinality Error                      |
| E00050     | Duplicate Error                        |
| E00060     | Placement Error                        |
| E00070     | Units Error                            |
| E00080     | Quantity Error                         |
| E00090     | Enumerated Value Error                 |
| E00100     | Relationship Error                     |
| E00110     | Naming Error                           |
| E00120     | Reference Error                        |
| E00130     | Resource Error                         |
| E00140     | Deprecation Error                      |
| E00150     | Shape Representation Error             |
| E00160     | Instance Structure Error               |
|            |                                        |
| W00010     | Alignment Contains Business Logic Only |
| W00020     | Alignment Contains Geometry Only       |
| W00030     | Warning                                |
|            |                                        |
| X00040     | Executed                               |

#### Notes

`Not Applicable` refers to a rule that does not apply because of the schema version.
`Executed` refers to a rule that does apply because of schema version,
but the model does not contain any entities validated as part of a particular rule.

Both outcomes are reported as "N/A" in the validation service user interface.