import sys
from pathlib import Path

import ifcopenshell
from ifcopenshell.mvd import template


TEMPLATES_DIR = Path(__file__).parent / "templates"


def available_template_names(templates_dir=TEMPLATES_DIR):
    return tuple(
        markdown.name for markdown in sorted(Path(templates_dir).glob("*.md"))
    )


def json_value(value):
    if isinstance(value, ifcopenshell.entity_instance):
        return value.is_a()
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def extract_template_statistics(
    file_or_path,
    templates_dir=TEMPLATES_DIR,
    template_names=None,
):
    model = (
        file_or_path
        if isinstance(file_or_path, ifcopenshell.file)
        else ifcopenshell.open(file_or_path)
    )
    results = []

    selected_template_names = (
        None if template_names is None else set(template_names)
    )
    for markdown in sorted(Path(templates_dir).glob("*.md")):
        if (
            selected_template_names is not None
            and markdown.name not in selected_template_names
        ):
            continue
        concept = template.from_graphviz(markdown.read_text(encoding="utf-8"))
        try:
            focus_instances = model.by_type(concept.entity)
        except RuntimeError:
            focus_instances = ()

        for focus in focus_instances:
            rows = concept.extract(focus)
            for row in rows:
                graph = {
                    concept.binding_for(key) or key.attribute: json_value(value)
                    for key, value in row.items()
                }
                results.append({
                    "template": markdown.name,
                    "focus_step_id": focus.id(),
                    "focus_ifc_type": focus.is_a(),
                    "graph": graph,
                })

    return results


if __name__ == "__main__":
    for result in extract_template_statistics(sys.argv[1]):
        print(result)
