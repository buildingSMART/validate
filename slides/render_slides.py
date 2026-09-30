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
import glob
import json
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
        save_figure(
            schema_bar_figure(payload),
            args.figures_dir, "01_model_counts",
        )
        frames.append(("Model counts per IFC schema", "01_model_counts", dataset_note(payload)))

    payload = load_payload(args.data_dir, "02_model_counts_over_5mb")
    if payload:
        save_figure(
            schema_bar_figure(payload),
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
