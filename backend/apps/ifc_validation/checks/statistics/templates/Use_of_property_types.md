# Usage of property types

> SCOPE IFC2X3+

This is a template to uncover statistics on usage of the various kinds of properties within the context of a property set.

```text
concept {
    IfcPropertySet:Name -> IfcLabel
    IfcPropertySet:Name[binding="PropertySetName"]

    IfcPropertySet:HasProperties -> IfcProperty
    IfcPropertySet:HasProperties[binding="PropertyType"]
}
```
