# BasisCurves of IfcPointByDistanceExpression

> SCOPE IFC4.3+

Per the schema IfcPointByDistanceExpression.BasisCurve is of type IfcCurve
which includes a broad range of subtypes, most of which do not make sense in
the context of linear referencing.

```
concept {
    IfcPointByDistanceExpression:BasisCurve -> IfcCurve
    IfcPointByDistanceExpression:BasisCurve[binding="BasisCurve"]
}
```
