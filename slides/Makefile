.PHONY: all fetch figures pdf clean

PYTHON ?= python3

all: figures pdf

# Pull the JSON query results from the deployed service (see fetch.sh for
# HOST / SSHUSER / KEY overrides).
fetch:
	./fetch.sh

# Render data/*.json into figures/ and generated_frames.tex.
figures:
	$(PYTHON) render_slides.py

# Compile the deck (needs a LaTeX distribution with beamer, e.g. texlive).
pdf: figures
	pdflatex -interaction=nonstopmode -halt-on-error slides.tex
	pdflatex -interaction=nonstopmode -halt-on-error slides.tex

clean:
	rm -rf figures generated_frames.tex
	rm -f slides.aux slides.log slides.nav slides.out slides.snm slides.toc
