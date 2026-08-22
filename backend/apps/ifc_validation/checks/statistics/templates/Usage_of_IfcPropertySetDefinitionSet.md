# Usage of IfcPropertySetDefinitionSet

> SCOPE IFC4+

IFC4 introduced a mechanism by which the objectified relationship for property
set association obtained a select type between a single set and a set of sets.
This template selects the second category.

```text
concept {
    IfcRelDefinesByProperties:RelatingPropertyDefinition -> IfcPropertySetDefinitionSet
}
```
