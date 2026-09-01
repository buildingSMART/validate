# Usage of transition curves - semantics

> SCOPE IFC4.3+

This is a template to uncover statistics on usage of the various kinds of (transition) curves and their usage context in alignment geometry. The check is on the business logic level.

```text
concept {
    IfcAlignment:IsNestedBy -> IfcRelNests_0:RelatingObject
    IfcRelNests_0:RelatedObjects -> IfcLinearElement
    IfcLinearElement:IsNestedBy -> IfcRelNests_1:RelatingObject
    IfcRelNests_1:RelatedObjects -> IfcAlignmentSegment_0

    IfcAlignmentSegment_0:DesignParameters -> IfcAlignmentHorizontalSegment
    IfcAlignmentSegment_0:DesignParameters -> IfcAlignmentVerticalSegment
    IfcAlignmentSegment_0:DesignParameters -> IfcAlignmentCantSegment

    IfcAlignmentHorizontalSegment:PredefinedType -> IfcAlignmentHorizontalSegmentTypeEnum
    IfcAlignmentHorizontalSegment:PredefinedType[binding="HorizontalType"]

    IfcAlignmentVerticalSegment:PredefinedType -> IfcAlignmentVerticalSegmentTypeEnum
    IfcAlignmentVerticalSegment:PredefinedType[binding="VerticalType"]

    IfcAlignmentCantSegment:PredefinedType -> IfcAlignmentCantSegmentTypeEnum
    IfcAlignmentCantSegment:PredefinedType[binding="CantType"]
}
```
