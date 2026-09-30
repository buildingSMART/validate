#!/usr/bin/env python3
"""Render matplotlib figures and LaTeX beamer frames from statistics query exports.

Reads the JSON documents produced by the admin statistics page ("Return JSON
instead of the table" checkbox) or the ``manage.py statistics_query`` management
command from ``data/``, writes figures (PDF + PNG) into ``figures/`` and emits
``generated_frames.tex`` for ``slides.tex``.

Only matplotlib (and LaTeX for the PDF step) is required; this tool is external
to the Django application on purpose.
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCHEMAS = ("IFC2X3", "IFC4", "IFC4X3_ADD2")
SCHEMA_COLORS = {"IFC2X3": "#4C72B0", "IFC4": "#DD8452", "IFC4X3_ADD2": "#55A868"}
TOP_ENTITY_BARS = 50

FRAME_TEMPLATE = """\
\\begin{{frame}}{{{title}}}
  \\includegraphics[width=\\textwidth,height=0.82\\textheight,keepaspectratio]{{figures/{figure}.pdf}}
{note}\\end{{frame}}
"""


def load_payload(data_dir, name):
    path = data_dir / f"{name}.json"
    if not path.exists():
        print(f"skip: {path} not found")
        return None
    return json.loads(path.read_text())


def normalize_schema(schema):
    """Fold casing variants such as IFC4x3_ADD2 into the canonical spelling."""
    return schema.strip().upper() if isinstance(schema, str) else schema


def format_integer(value):
    return f"{round(value):,}"


def dataset_note(payload):
    considered = payload.get("models_considered")
    if considered is None:
        return ""
    return f"  \\begin{{center}}\\scriptsize Models considered: {format_integer(considered)}\\end{{center}}\n"


def latex_escape(text):
    for old, new in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    ):
        text = text.replace(old, new)
    return text


def save_figure(figure, figures_dir, name):
    figures_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(figures_dir / f"{name}.pdf", bbox_inches="tight")
    figure.savefig(figures_dir / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(figure)
    print(f"wrote {figures_dir / name}.pdf / .png")


def schema_bar_figure(payload, title):
    counts = {}
    for schema, count in payload["rows"]:
        schema = normalize_schema(schema)
        if schema in SCHEMAS:
            counts[schema] = counts.get(schema, 0) + count
    schemas = [schema for schema in SCHEMAS if schema in counts]
    values = [counts[schema] for schema in schemas]

    figure, axis = plt.subplots(figsize=(9, 4.6))
    bars = axis.bar(schemas, values, color=[SCHEMA_COLORS[schema] for schema in schemas])
    axis.bar_label(bars, labels=[format_integer(value) for value in values], padding=3)
    axis.set_ylabel("Models")
    axis.set_title(title)
    axis.spines[["top", "right"]].set_visible(False)
    axis.margins(y=0.15)
    return figure


def entity_bars_figure(payload):
    by_schema = {schema: [] for schema in SCHEMAS}
    for schema, entity, count in payload["rows"]:
        schema = normalize_schema(schema)
        if schema in by_schema:
            by_schema[schema].append((entity, count))
    schemas = [schema for schema in SCHEMAS if by_schema[schema]]

    figure, axes = plt.subplots(
        1, len(schemas), figsize=(5.4 * len(schemas), 12), squeeze=False,
    )
    for axis, schema in zip(axes[0], schemas):
        top = by_schema[schema][:TOP_ENTITY_BARS]
        entities = [entity for entity, _ in reversed(top)]
        counts = [count for _, count in reversed(top)]
        axis.barh(entities, counts, color=SCHEMA_COLORS[schema])
        axis.set_title(f"{schema} - top {len(top)} entities")
        axis.set_xlabel("Entity count")
        axis.tick_params(axis="y", labelsize=7)
        axis.spines[["top", "right"]].set_visible(False)
        axis.margins(x=0.15)
    figure.tight_layout()
    return figure


def pset_mix_figure(payload):
    totals = {}
    for schema, standardized, count in payload["rows"]:
        schema = normalize_schema(schema)
        if schema not in SCHEMAS:
            continue
        label = (
            "Predefined"
            if str(standardized).casefold() in {"standard", "standardized", "true"}
            else "Custom"
        )
        totals.setdefault(schema, {"Predefined": 0, "Custom": 0})[label] += count
    schemas = [schema for schema in SCHEMAS if schema in totals]

    width = 0.38
    figure, axis = plt.subplots(figsize=(9, 4.6))
    for offset, label, color in (
        (-width / 2, "Predefined", "#55A868"),
        (width / 2, "Custom", "#C44E52"),
    ):
        values = [totals[schema][label] for schema in schemas]
        bars = axis.bar(
            [index + offset for index in range(len(schemas))],
            values, width, label=label, color=color,
        )
        axis.bar_label(bars, labels=[format_integer(value) for value in values], padding=3, fontsize=8)
    axis.set_xticks(range(len(schemas)))
    axis.set_xticklabels(schemas)
    axis.set_ylabel("Property-set definitions")
    axis.set_title("Predefined vs custom property sets per schema")
    axis.legend()
    axis.spines[["top", "right"]].set_visible(False)
    axis.margins(y=0.15)
    return figure


def write_frames(path, frames):
    blocks = [
        "% Generated by render_slides.py - do not edit by hand.",
        "",
    ]
    for title, figure, note in frames:
        blocks.append(FRAME_TEMPLATE.format(
            title=latex_escape(title),
            figure=figure,
            note=note,
        ))
    path.write_text("\n".join(blocks))
    print(f"wrote {path} ({len(frames)} frames)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=base / "data")
    parser.add_argument("--figures-dir", type=Path, default=base / "figures")
    parser.add_argument("--frames", type=Path, default=base / "generated_frames.tex")
    args = parser.parse_args()

    frames = []

    payload = load_payload(args.data_dir, "01_model_counts")
    if payload:
        save_figure(
            schema_bar_figure(payload, "Model counts per IFC schema"),
            args.figures_dir, "01_model_counts",
        )
        frames.append(("Model counts per IFC schema", "01_model_counts", dataset_note(payload)))

    payload = load_payload(args.data_dir, "02_model_counts_over_5mb")
    if payload:
        save_figure(
            schema_bar_figure(payload, "Model counts per IFC schema (files larger than 5 MB)"),
            args.figures_dir, "02_model_counts_over_5mb",
        )
        frames.append((
            "Model counts per IFC schema (files larger than 5 MB)",
            "02_model_counts_over_5mb",
            dataset_note(payload),
        ))

    payload = load_payload(args.data_dir, "03_entity_counts")
    if payload:
        save_figure(entity_bars_figure(payload), args.figures_dir, "03_entity_counts")
        frames.append((
            f"Top {TOP_ENTITY_BARS} entity counts per IFC schema",
            "03_entity_counts",
            dataset_note(payload),
        ))

    payload = load_payload(args.data_dir, "04_pset_counts")
    if payload:
        save_figure(pset_mix_figure(payload), args.figures_dir, "04_pset_counts")
        frames.append((
            "Predefined vs custom property sets per IFC schema",
            "04_pset_counts",
            dataset_note(payload),
        ))

    write_frames(args.frames, frames)


if __name__ == "__main__":
    main()
