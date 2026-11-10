"""
Representative syntax, schema, rule, header and signature reports as model data.

Shared by the typed report tests and the real Django server used by Playwright
to compare v1 React with the HTMX templates.
"""

HEADER_PASS = {
    "mvd": "Alignment-basedView",
    "name": "Header example2.ifc",
    "author": ["Evandro Alfieri"],
    "organization": ["buildingSMART Int."],
    "company_name": "Company",
    "application_name": "Application",
    "version": "26.0.0.0",
    "authorization": "none",
    "schema_identifier": "IFC4X3_ADD2",
    "originating_system": "Company - Application - 26.0.0.0",
    "preprocessor_version": "IFC Motor 1.0",
    "validation_errors": [],
}

IFC101 = {
    "feature": "IFC101 - Only official IFC versions allowed",
    "feature_version": 1,
    "severity": 1,
    "outcome_code": "X00040",
}

SCHEMA_PASSED = dict(type="SCHEMA", status="COMPLETED", status_reason="No IFC schema errors.",
                     outcomes=[dict(feature='{"type": "schema", "attribute": "SomeAttribute"}',
                                    severity=2, outcome_code="P00010")])

SCHEMA_SKIPPED = dict(type="SCHEMA", status="SKIPPED",
                      status_reason="Skipped due to fail in blocking tasks: SYNTAX", outcomes=[])

_SIGNATURE_PAYLOAD = "MIIGZQYJKoZIhvcNAQcCoIIGVjCCBlICAQExDTALBglghkgBZQMEAgEwCwYJKoZIhvcNAQcBoIID3TCCA9kwggHBAhQfhA1Gsyaylmk5LNR9teQdvZMp2zANBgkqhkiG9w0BAQsFADAmMQswCQYDVQQGEwJOTDEXMBUGA1UECgwOQWNtZSBJbmMuIHJvb3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDy4lyACmsdcF1F7COYIOHTDhamVwe0plQUWYXjyK+Hex1MqKFEtpS0GiQjM/RKSoSsgl/FJZYye0IUOJwpQlyhgs95IGb+zJ3/BmnF119x/ILK5iELplIpU9unH14NIyEviOyBKMCLa7aXsZkuxVVOApmJue3m7Ub9nUAbESWgyPHOSz+k2riwZGiHXoOw28Ug3m9UwdAHcsnex23h+RPkHltstTe2nZ244vV4YKWnDxa6XJnXpj2AzU5a5XGthmeIKxiBBYIENbmazbADh4fkCVSBw4KbRKMK+GnUAOvYi23VL8KmXInS8jIEHV/zPejFYsp8Vv3+SZHbVHL1SS1BAgMBAAEwDQYJKoZIhvcNAQELBQADggIBAGYBo6sgi+N1+oGpZDlyqpArY5S58rmiSfp8BFL+M7y2dXhMcBe30lXyBtjGMP0cKtpkThrS3AzZ7nz3cVdPcHLuEBE+lYyjqbnKPgMCOedNjqUFD46e93ycNqGTkdIQcF4ordrooPSsWbUtjQFiyP6lFxcUYDNfUpVXqSP1JlPSAGjcLLCvrPvtGlsfeBspM4ilfyA0W1RNMT82NMHP5nj6MDpGe9aWhQDwfNAkaKobIgenZfV0PuvC22OFCod1H0NMRcOqp/0QG860kFI4RUThrLEQdwVSl/IPytKfzM5qVet/Kow07yCpWZDW0neiXPJe/uvcasMNaC1Z1ovBLIeV7Rd9gRl/yS5lvSPfIYocIM10Fm+ZTatXTWOXO57wHx/7LRvKMZteSPlNAMqUbGRaL5h/NpdxP05Y5lFeMKNsDy6EDMmtCtIjCGLwL+iGbpxfnYd5TYKnLCSjhydz0jN2mIoyhYG/wA5+K8Pzt02wSQTYkr8/jUcjJbfvq+Wou5KGSk6NF1nI1XWAW2u2nslePXcscV73sZdGOH/pAjVl87b6KDLuH6qvWoRkl92pxy/Ui/+0lxWKzK6CLhuPlc1nmJvmKdU60YBX9F9t6Ako98NzT0mU3PtsMjFiarc4P12plWboNjNMn0cYxiHghjmhMZ7R0aEDbX69BG/Y9iukMYICTjCCAkoCAQEwPjAmMQswCQYDVQQGEwJOTDEXMBUGA1UECgwOQWNtZSBJbmMuIHJvb3QCFB+EDUazJrKWaTks1H215B29kynbMAsGCWCGSAFlAwQCAaCB5DAYBgkqhkiG9w0BCQMxCwYJKoZIhvcNAQcB"

SIGNATURE_CERT = {
    "issuer": "C=NL,O=Acme Inc. root",
    "subject": "C=NL,O=Acme Inc. end-entity",
    "signature_hash_algorithm_name": "sha256",
    "rsa_key_size": 2048,
    "not_valid_after": "2035-05-06 12:01:07+00:00",
    "not_valid_before": "2025-05-08 12:01:07+00:00",
    "fingerprint_hex": "3D:D2:DE:16:D8:8C:B6:C3:97:31:72:C0:55:5D:C6:74:A8:B2:B7:55:66:1E:BE:1A:A1:6C:5D:3E:7C:45:44:9F:A1",
    "payload": _SIGNATURE_PAYLOAD,
    "signature": "valid_known_cert",
}

def gherkin(feature: str, *, severity: int, version: int = 1, instance: str | None = None,
            expected=None, observed=None, outcome_code: str = "E00020") -> dict:
    return dict(feature=feature, feature_version=version, severity=severity, outcome_code=outcome_code,
                expected=expected, observed=observed, instance=instance)


CASES: list[dict] = [

    # ---------------------------------------------------------------- Case 1
    dict(name="case01-syntax-step", kind="syntax", public_id="r119954039",
         file_name="fail_double_semi.ifc", size=1172,
         model=dict(
             schema="IFC4", mvd="CoordinationView",
             status_syntax="i", status_header_syntax="v", status_header="i", status_prereq="v",
             header_validation={
                 "mvd": "CoordinationView", "name": "", "schema_identifier": "IFC4",
                 "originating_system": "IfcOpenShell-0.7.0", "preprocessor_version": "IfcOpenShell-0.7.0",
                 "validation_errors": ["originating_system", "company_name", "application_name", "description"],
             },
         ),
         instances=[],
         tasks=[
             dict(type="HEADER_SYNTAX", status="COMPLETED", status_reason="No IFC syntax error(s).",
                  outcomes=[dict(severity=2, outcome_code="P00010")]),
             dict(type="SYNTAX", status="COMPLETED",
                  status_reason="Found IFC syntax errors:\nOn line 27 column 66: Unexpected semicolon (';') ...",
                  outcomes=[dict(severity=4, outcome_code="E00001", observed=(
                      "On line 27 column 66:\n"
                      "Unexpected semicolon (';')\n"
                      "Expecting ENDSEC\n"
                      "00027 | #20=IFCPROJECT('2AyG2X0sb16Bjd4gQc07yZ',#5,'',$,$,$,$,(#11),#19);;\n"
                      "                                                                         ^"
                  ))]),
             dict(type="PREREQ", status="COMPLETED", status_reason="agg_status = Valid",
                  outcomes=[IFC101]),
             SCHEMA_SKIPPED,
         ]),

    # ---------------------------------------------------------------- Case 2
    dict(name="case02-syntax-duplicate-name", kind="syntax", public_id="r503400730",
         file_name="fail-duplicate-name.ifc", size=396,
         model=dict(
             schema="IFC4X3_ADD2", mvd="Alignment-basedView",
             status_syntax="i", status_header_syntax="v", status_header="v", status_prereq="v",
             header_validation=dict(HEADER_PASS, name="Header example2.ifc"),
         ),
         instances=[],
         tasks=[
             dict(type="HEADER_SYNTAX", status="COMPLETED", status_reason="No IFC syntax error(s).",
                  outcomes=[dict(severity=2, outcome_code="P00010")]),
             dict(type="SYNTAX", status="COMPLETED",
                  status_reason="Found IFC syntax errors:\nOn line 9: Duplicate instance name #1 ...",
                  outcomes=[dict(severity=4, outcome_code="E00001", observed=(
                      "On line 9:\n"
                      "Duplicate instance name #1\n"
                      "00009 | #1=IFCPERSON($,$,'',$,$,$,$,$);\n"
                      "        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
                  ))]),
             dict(type="PREREQ", status="COMPLETED", status_reason="agg_status = Valid", outcomes=[IFC101]),
             SCHEMA_SKIPPED,
         ]),

    # ---------------------------------------------------------------- Case 3
    dict(name="case03-schema-ifc101", kind="schema", public_id="r886847421",
         file_name="fail-ifc101-IFC4X3.ifc", size=1306,
         model=dict(
             schema="IFC4X3", mvd="ReferenceView",
             status_syntax="v", status_header="v", status_header_syntax="v", status_prereq="i",
             header_validation={
                 "mvd": "ReferenceView", "name": "fail-ifc101-IFC4X3.ifc",
                 "company_name": "IfcOpenShell contributors", "application_name": "IfcOpenShell",
                 "version": "v0.7.0+6c9e130ca", "schema_identifier": "IFC4X3",
                 "originating_system": "IfcOpenShell contributors - IfcOpenShell - v0.7.0+6c9e130ca",
                 "preprocessor_version": "", "validation_errors": ["description"],
             },
         ),
         instances=[],
         tasks=[
             dict(type="PREREQ", status="COMPLETED", status_reason="agg_status = Invalid",
                  outcomes=[gherkin("IFC101 - Only official IFC versions allowed", severity=4,
                                    expected={"oneOf": ["IFC2X3", "IFC4", "IFC4X3_ADD2"]},
                                    observed={"schema_identifier": "IFC4X3"})]),
             dict(type="SCHEMA", status="SKIPPED",
                  status_reason="Skipped due to fail in blocking tasks: PREREQ", outcomes=[]),
         ]),

    # ---------------------------------------------------------------- Case 4
    dict(name="case04-schema-attribute", kind="schema", public_id="r104761022",
         file_name="fail-selected-simple-type-as-literal.ifc", size=340,
         model=dict(
             schema="IFC2X3", mvd="DesignTransferView",
             status_syntax="v", status_header_syntax="v", status_header="v", status_prereq="v",
             header_validation={
                 "mvd": "DesignTransferView", "name": "qset.ifc", "authorization": "Nobody",
                 "schema_identifier": "IFC2X3", "originating_system": "Bonsai 0.8.1-alpha241113-d3333fe",
                 "preprocessor_version": "IfcOpenShell 0.0.0",
                 "validation_errors": ["originating_system", "company_name", "application_name", "description"],
             },
         ),
         instances=[dict(stepfile_id=1, ifc_type="IfcPropertySingleValue")],
         tasks=[
             dict(type="SCHEMA", status="COMPLETED", status_reason="No IFC schema errors.",
                  outcomes=[dict(feature='{"type": "schema", "attribute": "NominalValue"}',
                                 severity=4, outcome_code="E00002", instance=1, observed=(
                                     "With attribute:\n"
                                     "    <attribute NominalValue?: <select IfcValue: (<select IfcDerivedMeasureValue: "
                                     "(<type IfcAbsorbedDoseMeasure: <real>> | … | <type IfcWarpingMomentMeasure: <real>>)> "
                                     "| <select IfcMeasureValue: (…)> | <select IfcSimpleValue: (<type IfcBoolean: <boolean>> "
                                     "| <type IfcIdentifier: <string>> | <type IfcInteger: <integer>> | <type IfcLabel: <string>> "
                                     "| <type IfcLogical: <logical>> | <type IfcReal: <real>> | <type IfcText: <string>>)>)>>\n"
                                     "Value:\n"
                                     "    0.2\n"
                                     "Not valid\n"
                                 ))]),
         ]),

    # ---------------------------------------------------------------- Case 5
    dict(name="case05-schema-rule", kind="schema", public_id="r653740803",
         file_name="fail-axis2-anti-parallel-axes.ifc", size=420,
         model=dict(
             schema="IFC2X3", mvd="CoordinationView",
             status_syntax="v", status_header_syntax="v", status_header="i", status_prereq="v",
             header_validation={
                 "mvd": "CoordinationView", "name": "", "schema_identifier": "IFC2X3",
                 "originating_system": "IfcOpenShell", "preprocessor_version": "IfcOpenShell",
                 "validation_errors": ["originating_system", "company_name", "application_name", "description"],
             },
         ),
         instances=[dict(stepfile_id=4, ifc_type="IfcAxis2Placement3D")],
         tasks=[
             dict(type="SCHEMA", status="COMPLETED", status_reason="No IFC schema errors.",
                  outcomes=[dict(feature='{"type": "entity_rule", "attribute": "IfcAxis2Placement3D.WR4"}',
                                 severity=4, outcome_code="E00002", instance=4, observed=(
                                     "(not exists(axis) or not exists(refdirection) or IfcCrossProduct(axis, refdirection).Magnitude > 0.0)\n"
                                     "\nViolated by:\n"
                                     "    ((not True or not True or 0.0 > 0.0))\n"
                                     "     +  where True = exists(#2=IfcDirection((0.,0.,1.)))\n"
                                     "     +  and   True = exists(#3=IfcDirection((0.,0.,-1.)))\n"
                                     "     +  and   0.0 = #0=IfcVector(#2,0.).Magnitude\n"
                                     "     +    where #0=IfcVector(#2,0.) = IfcCrossProduct(#2=IfcDirection((0.,0.,1.)), #3=IfcDirection((0.,0.,-1.)))\n"
                                     "\nOn instance:\n"
                                     "    #4=IfcAxis2Placement3D(#1,#2,#3)\n"
                                 ))]),
             dict(type="PREREQ", status="COMPLETED", status_reason="agg_status = Valid", outcomes=[IFC101]),
         ]),

    # ---------------------------------------------------------------- Case 6
    dict(name="case06-normative", kind="normative", public_id="r721314331",
         file_name="fail-blt001-scenario02-door_type_own_operation_type.ifc", size=1510,
         model=dict(
             schema="IFC4X3_ADD2", mvd="ReferenceView",
             status_syntax="v", status_header_syntax="v", status_header="v", status_prereq="v",
             header_validation={
                 "mvd": "ReferenceView", "name": "fail-blt001-scenario02-door_type_own_operation_type.ifc",
                 "company_name": "IfcOpenShell contributors", "application_name": "IfcOpenShell",
                 "version": "v0.7.0+fa6bbf2d", "schema_identifier": "IFC4X3_ADD2",
                 "originating_system": "IfcOpenShell contributors - IfcOpenShell - v0.7.0+fa6bbf2d",
                 "preprocessor_version": "", "validation_errors": [],
             },
         ),
         instances=[dict(stepfile_id=22, ifc_type="IfcDoor"), dict(stepfile_id=21, ifc_type="IfcDoorType")],
         tasks=[
             dict(type="NORMATIVE_IA", status="COMPLETED", status_reason="agg_status = Invalid", outcomes=[
                 gherkin("BLT001 - Correct use of operation type attributes for doors", severity=4, instance=22,
                         expected={"schema_identifier": "empty"},
                         observed={"schema_identifier": "SLIDING_TO_RIGHT"}),
                 gherkin("SPS005 - Simultaneous spatial relationships", severity=4, version=2, instance=22,
                         expected="^Exactly^ 1 of the following relationships must be non-empty: 'Nests', 'Decomposes', "
                                  "'ContainedInStructure', 'AdheresToElement', 'VoidsElements'",
                         observed={"value": 0}),
                 gherkin("SPS007 - Spatial Containment", severity=4, version=6, instance=22,
                         expected="a *required* relationship .IfcRelContainedInSpatialStructure. to .IfcElement. "
                                  "from .IfcSpatialStructureElement."),
             ]),
         ]),

    # ---------------------------------------------------------------- Case 7
    dict(name="case07-industry", kind="industry", public_id="r420634185",
         file_name="fail-blt003-scenario01-IfcStair-aggregating-IfcBeam.ifc", size=1453,
         model=dict(
             schema="IFC4X3_ADD2", mvd="ReferenceView",
             status_syntax="v", status_header_syntax="v", status_header="v", status_prereq="v",
             header_validation=dict(HEADER_PASS, name="fail-blt003-scenario01-IfcStair-aggregating-IfcBeam.ifc"),
         ),
         instances=[dict(stepfile_id=21, ifc_type="IfcStair"),
                    dict(stepfile_id=11, ifc_type="IfcGeometricRepresentationContext")],
         tasks=[
             dict(type="INDUSTRY", status="COMPLETED", status_reason="agg_status = Warning", outcomes=[
                 gherkin("BLT003 - Stair decomposition", severity=3, version=2, instance=21,
                         expected={"oneOf": ["IfcRailing", "IfcSlab", "IfcStairFlight"],
                                   "context": "to be the whole that is decomposed by"},
                         observed={"instance": "IfcBeam(#22)"}),
                 gherkin("GEM052 - Correct geometric subcontexts", severity=3, version=2, instance=11,
                         expected={"schema_identifier": "not empty"},
                         observed={"schema_identifier": "empty"}),
             ]),
         ]),

    # ---------------------------------------------------------------- Case 8
    dict(name="case08-signatures-pass", kind="file", public_id="r804080876",
         file_name="pass_multiple_signatures.ifc", size=4971,
         model=dict(
             schema="IFC4", mvd="ReferenceView_V1.2",
             status_syntax="v", status_header_syntax="v", status_header="v", status_prereq="v",
             header_validation={
                 "mvd": "ReferenceView_V1.2", "name": "na_no_signature.ifc", "author": ["jdoe"],
                 "organization": ["Acme Inc."], "company_name": "Acme Inc.", "application_name": "MyFabTool",
                 "version": "2025.1", "authorization": "IFC4 model", "schema_identifier": "IFC4",
                 "preprocessor_version": "ABC rel. 0.1.2",
                 "originating_system": "Acme Inc. - MyFabTool - 2025.1", "validation_errors": [],
             },
         ),
         instances=[],
         tasks=[
             dict(type="DIGITAL_SIGNATURES", status="COMPLETED", status_reason="Digital signature check completed",
                  outcomes=[
                      dict(severity=2, outcome_code="P00010", observed=dict(SIGNATURE_CERT, start="383", end="2592")),
                      dict(severity=2, outcome_code="P00010", observed=dict(SIGNATURE_CERT, start="2592", end="4801")),
                  ]),
         ]),

    # ---------------------------------------------------------------- Case 9
    dict(name="case09-signatures-fail", kind="file", public_id="r187527567",
         file_name="fail_invalid_signature.ifc", size=2686,
         model=dict(
             schema="IFC4", mvd="ReferenceView_V1.2",
             status_syntax="v", status_header_syntax="v", status_header="v", status_prereq="v",
             header_validation={
                 "mvd": "ReferenceView_V1.2", "name": "na_no_signature.ifc", "author": ["jdoe"],
                 "organization": ["Acme Inc."], "company_name": "Acme Inc.", "application_name": "MyFabTool",
                 "version": "2025.1", "authorization": "IFC4 model", "schema_identifier": "IFC4",
                 "preprocessor_version": "ABC rel. 0.1.2",
                 "originating_system": "Acme Inc. - MyFabTool - 2025.1", "validation_errors": [],
             },
         ),
         instances=[],
         tasks=[
             dict(type="DIGITAL_SIGNATURES", status="COMPLETED", status_reason="Digital signature check completed",
                  outcomes=[dict(severity=4, outcome_code="E00020", observed={
                      "signature": "invalid", "start": "383", "end": "2592", "payload": _SIGNATURE_PAYLOAD,
                  })]),
         ]),

    # ---------------------------------------------------------------- Case 10
    dict(name="case10-header-pass", kind="file", public_id="r570974258",
         file_name="passing_header.ifc", size=1342,
         model=dict(
             schema="IFC4X3_ADD2", mvd="Alignment-basedView",
             status_syntax="v", status_header_syntax="v", status_header="v", status_prereq="v",
             header_validation=dict(HEADER_PASS),
         ),
         instances=[],
         tasks=[
             dict(type="HEADER", status="COMPLETED", status_reason="agg_status = Valid", outcomes=[]),
         ]),

    # ---------------------------------------------------------------- Case 11
    dict(name="case11-header-fail", kind="file", public_id="r954420949",
         file_name="blank_company_name.ifc", size=1337,
         model=dict(
             schema="IFC4X3_ADD2", mvd="Alignment-basedView",
             status_syntax="v", status_header_syntax="v", status_header="i", status_prereq="v",
             header_validation=dict(HEADER_PASS, company_name=" ",
                                    originating_system="  - Application - 26.0.0.0",
                                    validation_errors=["company_name"]),
         ),
         instances=[],
         tasks=[
             dict(type="HEADER", status="COMPLETED", status_reason="agg_status = Invalid", outcomes=[]),
         ]),

    # ---------------------------------------------------------------- Case 12
    dict(name="case12-many-errors", kind="schema", public_id="r337867640",
         file_name="fail-many-errors.ifc", size=976,
         model=dict(
             schema="IFC4X3_ADD2", mvd="Alignment-basedView",
             status_syntax="v", status_header_syntax="v", status_header="v", status_prereq="v",
             header_validation=dict(HEADER_PASS, name="Header example2.ifc"),
         ),
         instances=[dict(stepfile_id=i, ifc_type="IfcPerson") for i in range(1, 20)],
         tasks=[
             dict(type="SCHEMA", status="COMPLETED", status_reason="No IFC schema errors.",
                  outcomes=[dict(feature='{"type": "schema", "attribute": "GivenName"}', severity=4,
                                 outcome_code="E00002", instance=i,
                                 observed="With attribute:\n    <attribute GivenName?: <type IfcLabel: <string>>>\n"
                                          f"Value:\n    {i}\nNot valid\n")
                            for i in range(1, 20)]),
             dict(type="PREREQ", status="COMPLETED", status_reason="agg_status = Valid", outcomes=[IFC101]),
         ]),
]
