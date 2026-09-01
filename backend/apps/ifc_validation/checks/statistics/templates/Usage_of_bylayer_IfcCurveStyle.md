# Usage of 'by layer' IfcCurveStyle

> SCOPE IFC2X3+

There has been a bug in the IfcOpenShell rule execution that caused spaces within string literals of express rules to get dropped. Therefore IfcCurveStyle_WR11 execution was wrong. This template uncovers whether this pattern is present in vendor-created uploads, informing us whether it is safe to update the validation service logic.

```text
concept {
    IfcCurveStyle:CurveWidth -> IfcDescriptiveMeasure
    IfcDescriptiveMeasure -> constraint_0
    constraint_0[label="=by layer"]
}
```
