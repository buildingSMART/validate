from ..datamodel.ui import FAQ, LandingPage, Resource, ValidationLayer, WorkflowStep


def landing_page(max_size_mb: int) -> LandingPage:
    return LandingPage(
        layers=(
            ValidationLayer("STEP Syntax", "Confirms the uploaded file is a valid STEP Physical File (SPF) in accordance with ISO 10303-21."),
            ValidationLayer("IFC Schema", "Checks against the referenced IFC schema version, including formal propositions and EXPRESS-encoded functions."),
            ValidationLayer("Normative Rules", "Validates implementer agreements and informal propositions defined in the IFC specification."),
            ValidationLayer("Industry Practices", "Non-normative checks against common practices and sensible defaults used across the industry."),
        ),
        steps=(WorkflowStep("01", "Upload", f"Upload your .ifc file ({max_size_mb}mb max)"),
               WorkflowStep("02", "Validate", "Automated checks run against the IFC standard"),
               WorkflowStep("03", "Review", "Get a detailed conformity report with errors and warnings")),
        faqs=(
            FAQ("Is the Validation Service free?", "Yes. The service is free and provided by buildingSMART international to improve interoperability of IFC."),
            FAQ("Do I need an account?", "Yes. An account is required for progress notifications and to gather statistics on authoring tools; developer accounts are excluded from these statistics."),
            FAQ("Does it include geometric visualisation?", "The emphasis is on the four validation layers outlined above, while there are rules that relate to geometry there is no geometric visualization of the model or coordination features."),
            FAQ("What IFC schema versions are supported?", "The supported schemas are IFC2X3, IFC4 and IFC 4.3 (IFC4X3_ADD2)"),
        ),
        resources=(
            Resource("buildingSMART", "About buildingSMART", "In-depth information on everything we do at buildingSMART.org", "https://buildingsmart.org"),
            Resource("Docs", "User Guide & Documentation", "Step-by-step guide and technical reference", "https://buildingsmart.github.io/validate/index.html"),
            Resource("GitHub", "Source Code on GitHub", "Open-source repository - run it on your own infrastructure", "https://github.com/buildingSMART/validate"),
            Resource("Forum", "Community Forum", "Updates, discussions, and feedback", "https://forums.buildingsmart.org/"),
        ),
    )
