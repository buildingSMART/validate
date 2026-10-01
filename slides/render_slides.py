#!/usr/bin/env python3
"""Render matplotlib figures and LaTeX beamer frames from statistics query exports.

Reads the JSON documents produced by the admin statistics page ("Return JSON
instead of the table" checkbox) or the ``manage.py statistics_query`` management
command from ``data/``, writes figures (PDF + PNG) into ``figures/`` and emits
``generated_frames.tex`` for ``slides.tex``.

Only matplotlib (and LaTeX for the PDF step) is required; this tool is external
to the Django application on purpose.

Text is set in Bitstream Charter: the XCharter fonts are picked up from an
installed font family, from a TeX distribution (kpsewhich, or the Windows side
of WSL), or explicitly via --font-file; otherwise DejaVu Serif is used.
"""

import argparse
import csv
import glob
import json
import math
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as font_manager
import matplotlib.pyplot as plt

SCHEMAS = ("IFC2X3", "IFC4", "IFC4X3_ADD2")
SCHEMA_COLORS = {"IFC2X3": "#4C72B0", "IFC4": "#DD8452", "IFC4X3_ADD2": "#55A868"}
TOP_ENTITY_BARS = 50

RESOURCE_ROOT = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "apps"
    / "ifc_validation"
    / "checks"
    / "ifc_gherkin_rules"
    / "features"
    / "resources"
)
# schema bucket -> (pset_definitions.csv resource directory, ifcopenshell schema)
SCHEMA_SOURCES = {
    "IFC2X3": ("IFC2X3", "ifc2x3"),
    "IFC4": ("IFC4", "ifc4"),
    "IFC4X3_ADD2": ("IFC4X3", "ifc4x3"),
}
COVERAGE_SCHEMA = "IFC4X3_ADD2"
NAMES_COLUMNS = 2
NAMES_PER_COLUMN = 29
NAMES_PER_FRAME = NAMES_COLUMNS * NAMES_PER_COLUMN

# per-model IfcSIUnit counts (one spec per schema: entity filters need one schema)
SI_UNIT_QUERIES = (
    ("IFC2X3", "06_si_units_ifc2x3"),
    ("IFC4", "07_si_units_ifc4"),
    ("IFC4X3_ADD2", "08_si_units_ifc4x3"),
)

CHARTER_FAMILY_CANDIDATES = ("XCharter", "Charter", "Bitstream Charter")
CHARTER_TEX_FONT_FILES = (
    "XCharter-Roman.otf",
    "XCharter-Bold.otf",
    "XCharter-Italic.otf",
    "XCharter-BoldItalic.otf",
)
# XCharter ships with TeX distributions; from WSL the Windows side is mounted.
WINDOWS_FONT_GLOBS = (
    "/mnt/c/Users/*/AppData/Local/Programs/MiKTeX/fonts/opentype/public/xcharter",
    "/mnt/c/texlive/*/texmf-dist/fonts/opentype/public/xcharter",
)

FRAME_TEMPLATE = """\
\\begin{{frame}}{{{title}}}
  \\includegraphics[width=\\textwidth,height={height}\\textheight,keepaspectratio]{{figures/{figure}.pdf}}
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


def note_lines(*lines):
    return "".join(
        f"  \\begin{{center}}\\scriptsize {line}\\end{{center}}\n"
        for line in lines if line
    )


def dataset_note(payload, extra=""):
    considered = payload.get("models_considered")
    return note_lines(
        f"Models considered: {format_integer(considered)}"
        if considered is not None else "",
        extra,
    )


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


def latex_name(name):
    """Escape a name and allow line breaks after underscores."""
    return latex_escape(name).replace("\\_", "\\allowbreak\\_")


def kpsewhich_charter_fonts():
    """Ask a TeX installation (MiKTeX/TeX Live) where the XCharter fonts are."""
    kpsewhich = shutil.which("kpsewhich")
    if not kpsewhich:
        return []
    fonts = []
    for filename in CHARTER_TEX_FONT_FILES:
        result = subprocess.run(
            [kpsewhich, filename], capture_output=True, text=True,
        )
        path = Path(result.stdout.strip())
        if path.is_file():
            fonts.append(path)
    return fonts


def windows_charter_fonts():
    """Look for the Windows-side XCharter fonts through the WSL mount."""
    fonts = []
    for pattern in WINDOWS_FONT_GLOBS:
        for directory in glob.glob(pattern):
            for filename in CHARTER_TEX_FONT_FILES:
                path = Path(directory) / filename
                if path.is_file():
                    fonts.append(path)
    return fonts


def configure_matplotlib_text(font_files):
    """Use Bitstream Charter for plain text, falling back to DejaVu Serif."""
    font_files = list(font_files)
    family = None
    if not font_files:
        installed = {font.name for font in font_manager.fontManager.ttflist}
        family = next(
            (name for name in CHARTER_FAMILY_CANDIDATES if name in installed),
            None,
        )
        if family is None:
            font_files = kpsewhich_charter_fonts() or windows_charter_fonts()
    if font_files:
        for path in font_files:
            font_manager.fontManager.addfont(str(path))
        family = font_manager.FontProperties(fname=str(font_files[0])).get_name()
        print(f"using font family {family!r} from {font_files[0]}")
        plt.rcParams.update({
            "font.family": family,
            "font.serif": [family, "DejaVu Serif"],
        })
    else:
        print(
            "warning: Bitstream Charter not found; install XCharter or pass "
            "--font-file. Falling back to DejaVu Serif.",
        )
        plt.rcParams.update({
            "font.family": "serif",
            "font.serif": ["DejaVu Serif"],
        })
    plt.rcParams["axes.unicode_minus"] = False


def save_figure(figure, figures_dir, name):
    figures_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(figures_dir / f"{name}.pdf", bbox_inches="tight")
    figure.savefig(figures_dir / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(figure)
    print(f"wrote {figures_dir / name}.pdf / .png")


def schema_bar_figure(payload):
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
        axis.set_xscale("log")
        axis.set_title(f"{schema} - top {len(top)} entities")
        axis.set_xlabel("Entity count (log scale)")
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
    axis.legend()
    axis.spines[["top", "right"]].set_visible(False)
    axis.margins(y=0.15)
    return figure


def observed_names(payload):
    """Collect the distinct names per schema bucket from grouped query rows."""
    observed = {schema: set() for schema in SCHEMAS}
    for schema, name, _count in payload["rows"]:
        schema = normalize_schema(schema)
        if schema in observed and name:
            observed[schema].add(name)
    return observed


def declared_entity_names():
    """Instantiable (non-abstract) entity names per schema, from ifcopenshell."""
    import ifcopenshell

    return {
        schema: {
            entity.name()
            for entity in ifcopenshell.schema_by_name(schema_id).entities()
            if not entity.is_abstract()
        }
        for schema, (_resource, schema_id) in SCHEMA_SOURCES.items()
    }


def declared_pset_names(schema):
    """Predefined property-set names from the gherkin feature resources."""
    resource = SCHEMA_SOURCES[schema][0]
    csv_path = RESOURCE_ROOT / resource / "pset_definitions.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        return {
            row["Name"]
            for row in csv.DictReader(csv_file)
            if row.get("Name")
        }


def coverage_statistics(observed, declared):
    """Percentage of declared names instantiated at least once, per schema."""
    return {
        schema: (
            100.0 * len(observed[schema] & declared[schema]) / len(declared[schema]),
            len(observed[schema] & declared[schema]),
            len(declared[schema]),
        )
        for schema in SCHEMAS
        if declared.get(schema)
    }


def coverage_bar_figure(stats, ylabel):
    schemas = [schema for schema in SCHEMAS if schema in stats]
    values = [stats[schema][0] for schema in schemas]
    labels = [
        f"{stats[schema][0]:.1f}%"
        f" ({format_integer(stats[schema][1])}/{format_integer(stats[schema][2])})"
        for schema in schemas
    ]

    figure, axis = plt.subplots(figsize=(9, 4.6))
    bars = axis.bar(schemas, values, color=[SCHEMA_COLORS[schema] for schema in schemas])
    axis.bar_label(bars, labels=labels, padding=3, fontsize=9)
    axis.set_ylabel(ylabel)
    axis.spines[["top", "right"]].set_visible(False)
    axis.margins(y=0.2)
    return figure


def si_unit_violin_figure(samples):
    """Horizontal violins: x = IfcSIUnit instances per model, thickness = models."""
    schemas = [
        schema for schema in SCHEMAS
        if len(samples.get(schema, ())) > 1
    ]
    log_samples = [
        [math.log10(value) for value in samples[schema]]
        for schema in schemas
    ]

    figure, axis = plt.subplots(figsize=(9, 4.6))
    parts = axis.violinplot(
        log_samples, vert=False, showmedians=True, showextrema=False,
    )
    for body, schema in zip(parts["bodies"], schemas):
        body.set_facecolor(SCHEMA_COLORS[schema])
        body.set_edgecolor(SCHEMA_COLORS[schema])
        body.set_alpha(0.55)
    if "cmedians" in parts:
        parts["cmedians"].set_color("black")

    axis.set_yticks(range(1, len(schemas) + 1))
    axis.set_yticklabels(schemas)
    low = math.floor(min(min(values) for values in log_samples))
    high = math.floor(max(max(values) for values in log_samples))
    ticks = list(range(low, high + 1))
    axis.set_xticks(ticks)
    axis.set_xticklabels([format_integer(10 ** tick) for tick in ticks])
    axis.set_xlabel("IfcSIUnit instances per model (log scale)")
    axis.spines[["top", "right"]].set_visible(False)
    return figure


def names_frames(title, names, note):
    """Text frames listing names in columns, paginated to fit the slide."""
    frames = []
    chunks = [
        names[index:index + NAMES_PER_FRAME]
        for index in range(0, len(names), NAMES_PER_FRAME)
    ] or [[]]
    for index, chunk in enumerate(chunks, start=1):
        suffix = f" ({index}/{len(chunks)})" if len(chunks) > 1 else ""
        columns = [
            chunk[column * NAMES_PER_COLUMN:(column + 1) * NAMES_PER_COLUMN]
            for column in range(NAMES_COLUMNS)
        ]
        columns = [column for column in columns if column]
        body = ["  \\begin{columns}[t]"]
        for column in columns:
            body.append(f"    \\begin{{column}}{{{0.98 / len(columns):.2f}\\textwidth}}")
            body.append("      \\raggedright")
            body.append("\\\\\n".join(latex_name(name) for name in column))
            body.append("    \\end{column}")
        body.append("  \\end{columns}")
        frames.append("\n".join([
            f"\\begin{{frame}}{{{latex_escape(title)}{suffix}}}",
            "  \\fontsize{5.5}{6.5}\\selectfont",
            *body,
            note.rstrip("\n"),
            "\\end{frame}",
        ]))
    return frames


def figure_frame(title, figure, note):
    # every extra caption line costs roughly this much of the frame height
    lines = max(1, note.count("\n"))
    height = max(0.50, 0.82 - 0.07 * (lines - 1))
    return FRAME_TEMPLATE.format(
        title=latex_escape(title),
        figure=figure,
        note=note,
        height=f"{height:.2f}",
    )


def write_frames(path, blocks):
    path.write_text(
        "% Generated by render_slides.py - do not edit by hand.\n\n"
        + "\n".join(blocks),
    )
    print(f"wrote {path} ({len(blocks)} frames)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=base / "data")
    parser.add_argument("--figures-dir", type=Path, default=base / "figures")
    parser.add_argument("--frames", type=Path, default=base / "generated_frames.tex")
    parser.add_argument(
        "--font-file",
        type=Path,
        action="append",
        default=[],
        help="Bitstream Charter font file (TTF/OTF) to register; repeatable.",
    )
    args = parser.parse_args()

    configure_matplotlib_text(args.font_file)
    frames = []

    payload = load_payload(args.data_dir, "01_model_counts")
    if payload:
        save_figure(schema_bar_figure(payload), args.figures_dir, "01_model_counts")
        frames.append(figure_frame(
            "Model counts per IFC schema",
            "01_model_counts",
            dataset_note(payload),
        ))

    payload = load_payload(args.data_dir, "02_model_counts_over_5mb")
    if payload:
        save_figure(schema_bar_figure(payload), args.figures_dir, "02_model_counts_over_5mb")
        frames.append(figure_frame(
            "Model counts per IFC schema (files larger than 5 MB)",
            "02_model_counts_over_5mb",
            dataset_note(payload),
        ))

    entity_payload = load_payload(args.data_dir, "03_entity_counts")
    if entity_payload:
        save_figure(entity_bars_figure(entity_payload), args.figures_dir, "03_entity_counts")
        frames.append(figure_frame(
            f"Top {TOP_ENTITY_BARS} entity counts per IFC schema",
            "03_entity_counts",
            dataset_note(entity_payload),
        ))

    si_unit_payloads = {}
    for schema, name in SI_UNIT_QUERIES:
        payload = load_payload(args.data_dir, name)
        if payload:
            si_unit_payloads[schema] = payload
    if si_unit_payloads:
        save_figure(
            si_unit_violin_figure({
                schema: [row[2] for row in payload["rows"]]
                for schema, payload in si_unit_payloads.items()
            }),
            args.figures_dir, "07_si_units",
        )
        frames.append(figure_frame(
            "Number of IfcSIUnit per model",
            "07_si_units",
            note_lines(*[
                f"{latex_escape(schema)}: {format_integer(len(payload['rows']))} of "
                f"{format_integer(payload['models_considered'])} models contain IfcSIUnit"
                for schema, payload in si_unit_payloads.items()
            ]),
        ))

    payload = load_payload(args.data_dir, "04_pset_counts")
    if payload:
        save_figure(pset_mix_figure(payload), args.figures_dir, "04_pset_counts")
        frames.append(figure_frame(
            "Predefined vs custom property sets per IFC schema",
            "04_pset_counts",
            dataset_note(payload),
        ))

    pset_payload = load_payload(args.data_dir, "05_pset_names")
    try:
        declared_psets = {schema: declared_pset_names(schema) for schema in SCHEMAS}
    except OSError as error:
        declared_psets = None
        print(f"warning: cannot read the pset definition resources ({error})")
    if pset_payload and declared_psets:
        observed = observed_names(pset_payload)
        save_figure(
            coverage_bar_figure(
                coverage_statistics(observed, declared_psets),
                "Predefined property sets instantiated (%)",
            ),
            args.figures_dir, "05_pset_coverage",
        )
        frames.append(figure_frame(
            "Share of predefined property sets instantiated at least once",
            "05_pset_coverage",
            dataset_note(pset_payload),
        ))
        missing = sorted(declared_psets[COVERAGE_SCHEMA] - observed[COVERAGE_SCHEMA])
        print(
            f"{COVERAGE_SCHEMA}: {len(missing)} of "
            f"{len(declared_psets[COVERAGE_SCHEMA])} predefined property sets never instantiated",
        )
        frames.extend(names_frames(
            f"Property sets never instantiated ({COVERAGE_SCHEMA})",
            missing,
            dataset_note(
                pset_payload,
                f"{latex_escape(COVERAGE_SCHEMA)}: {format_integer(len(missing))} of "
                f"{format_integer(len(declared_psets[COVERAGE_SCHEMA]))} predefined "
                "property sets never instantiated",
            ),
        ))

    if entity_payload:
        try:
            declared_entities = declared_entity_names()
        except (ImportError, RuntimeError) as error:
            declared_entities = None
            print(f"warning: cannot load IFC schemas via ifcopenshell ({error})")
        if declared_entities:
            observed = observed_names(entity_payload)
            save_figure(
                coverage_bar_figure(
                    coverage_statistics(observed, declared_entities),
                    "Concrete entity types instantiated (%)",
                ),
                args.figures_dir, "06_entity_coverage",
            )
            frames.append(figure_frame(
                "Share of concrete entity types instantiated at least once",
                "06_entity_coverage",
                dataset_note(entity_payload),
            ))
            missing = sorted(declared_entities[COVERAGE_SCHEMA] - observed[COVERAGE_SCHEMA])
            print(
                f"{COVERAGE_SCHEMA}: {len(missing)} of "
                f"{len(declared_entities[COVERAGE_SCHEMA])} concrete entity types never instantiated",
            )
            frames.extend(names_frames(
                f"Concrete entity types never instantiated ({COVERAGE_SCHEMA})",
                missing,
                dataset_note(
                    entity_payload,
                    f"{latex_escape(COVERAGE_SCHEMA)}: {format_integer(len(missing))} of "
                    f"{format_integer(len(declared_entities[COVERAGE_SCHEMA]))} concrete "
                    "entity types never instantiated",
                ),
            ))

    write_frames(args.frames, frames)


if __name__ == "__main__":
    main()
