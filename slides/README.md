# Statistics slides

Standalone tool (external to the Django app) that turns statistics-query JSON
exports from the Validation Service into a matplotlib + LaTeX beamer deck.

```
queries/   query specifications (input for manage.py statistics_query)
data/      fetched JSON results (produced by fetch.sh or downloaded by hand)
figures/   rendered PDF/PNG charts (gitignored build output)
```

## Requirements

- Python 3 with `matplotlib` (in the WSL dev env:
  `~/miniconda3/envs/validate/bin/python`).
- A LaTeX distribution with `beamer` for `make pdf`
  (e.g. `sudo apt install texlive-latex-recommended texlive-latex-extra`).

## Getting the JSON

Two equivalent ways to obtain a result document (`columns`, `rows`,
`models_considered`, `sql`):

1. Django admin -> Model statistics query builder -> check
   "Return JSON instead of the table" and run the query.
2. On the deployed host:
   `docker compose exec -T backend sh -c 'cd /app/backend && python manage.py statistics_query' < spec.json`

`make fetch` does option 2 for every file in `queries/` over SSH (see
`fetch.sh` for `HOST` / `SSHUSER` / `KEY` / `REMOTE_DIR` overrides) and stores
the results in `data/`.

## Building the deck

```sh
make            # figures + slides.pdf (needs pdflatex)
make figures    # only figures/ and generated_frames.tex
```

Charts currently included:

| # | Query spec | Chart |
|---|------------|-------|
| 1 | `queries/01_model_counts.json` | Model counts in IFC2X3, IFC4, IFC4X3\_ADD2 |
| 2 | `queries/02_model_counts_over_5mb.json` | Same for files larger than 5 MB |
| 3 | `queries/03_entity_counts.json` | Top 50 entity counts per schema |
| 4 | `queries/04_pset_counts.json` | Predefined vs custom property-set definitions per schema |

Note: query 3 fetches 300 rows (top 50 for up to three schemas); widen the
`limit` and `SCHEMAS` in `render_slides.py` when the corpus grows.

## Adding a chart

1. Add a query specification to `queries/` (the concept vocabulary is
   documented in `backend/apps/ifc_validation/statistics_query.md`; the admin
   UI example patterns show the JSON shape).
2. Add a figure function and a payload hook in `render_slides.py`; the matching
   beamer frame is appended to `generated_frames.tex` automatically.
