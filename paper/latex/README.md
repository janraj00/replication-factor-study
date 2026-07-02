# LaTeX paper

`main.tex` is a venue-neutral, two-column working paper. Author and affiliation
are intentionally left as placeholders near the top of the file.

Compile from this directory with:

```bash
latexmk -pdf -interaction=nonstopmode main.tex
```

The self-contained Tectonic engine is also supported:

```bash
tectonic -X compile main.tex
```

With a traditional TeX installation, the explicit sequence is:

```bash
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

The figures are loaded from `../figures/`. To adapt the paper to a venue,
replace the document class and page-layout settings while retaining the section
body and BibTeX database.
