# Validation Steps

## Serial steps

1. Syntax Validation

```shell
python3 apps/ifc_validation/checks/step_file_parser/main.py --json filename 
```

2. Parse Info

```python

import ifcopenshell

...

try:
    ifcopenshell.open(filename)
    # all OK
except ifcopenshell.Error as err:
    print(f'Error: {err}')

```

3. Prerequisites

```shell
python3 apps/ifc_validation/checks/check_gherkin.py --file-name file_name --task-id id --rule-type CRITICAL (--verbose)
```

## Parallel steps

4. Schema Validation

```shell
python3 -m ifcopenshell.validate --json --rules --fields filename 
```

5. bSDD Validation

```shell
python3 apps/ifc_validation/checks/check_bsdd.py --file-name file_name --task-id id (--verbose)
```

6. Normative Rules - Implementer Agreements (IA)

```shell
python3 apps/ifc_validation/checks/check_gherkin.py --file-name file_name --task-id id --rule-type IMPLEMENTER_AGREEMENT (--verbose)
```

7. Normative Rules - Informal Proposition (IP)

```shell
python3 apps/ifc_validation/checks/check_gherkin.py --file-name file_name --task-id id --rule-type INFORMAL_PROPOSITION (--verbose)
```

8. Industry Practices

```shell
python3 apps/ifc_validation/checks/check_gherkin.py --file-name file_name --task-id id --rule-type INDUSTRY_PRACTICE (--verbose)
```
