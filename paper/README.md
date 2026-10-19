# AICAP 2027 paper

This directory uses the official IEEE `IEEEtran` two-column conference format for **Aviation Innovation Conference for Asia Pacific (AICAP) 2027**.

## Submission requirements

According to the public call for papers (checked on 2026-10-16):

- Use the IEEE two-column conference paper format.
- The complete paper is limited to **8 pages**, including references, appendices, and any other supplementary content.
- Submit a PDF no larger than **6 MB** through EasyChair.
- The public instructions do not specify whether review is anonymous; check the latest submission-system requirements before submitting.

Submission deadline: 2026-10-30; acceptance notification: 2026-12-01; final manuscript deadline: 2026-12-15. The public page does not specify the deadline timezone.

Conference website: https://event.ntu.edu.sg/AICAP-2027

Call for papers and formatting requirements: https://easychair.org/cfp/AICAP-2027

Official IEEE templates: https://www.ieee.org/conferences/publishing/templates

## File structure

```text
paper/
  main.tex                       Main document
  .latexmkrc                     Local build configuration; outputs to build/
  build/                         Local generated files; not committed
  IEEEtran.cls                   Official IEEE document class
  IEEEtran.bst                   Official IEEE bibliography style
  macros.tex                     Project notation and draft notes
  references.bib                 BibTeX bibliography
  sections/
    abstract.tex                 Abstract
    introduction.tex             Introduction
    related_work.tex             Existing related-work text
    problem_formulation.tex      Problem formulation
    method.tex                   Method
    experiments.tex              Experiments
    discussion.tex               Discussion and limitations
    conclusion.tex               Conclusion
    appendix.tex                 Appendix
  figures/                       Figures
  tables/                        Tables
```

Sections are included through `\input` in `main.tex` and are not compiled separately. Existing related-work text is retained with IEEE numeric citations. Other sections still contain explicit writing placeholders; these do not represent completed experiments.

The current focus is historical scene-complexity quantification and validation using correlation dimension of trajectory-embedding point clouds. Do not describe forecasting or control capabilities that have not been implemented and evaluated as established results.

## Compilation

From `paper/`, run:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

The project `.latexmkrc` selects pdfLaTeX and writes the PDF and auxiliary files to `build/`. The output is `build/main.pdf`; keep generated files out of the source root.

To clean auxiliary files while keeping the PDF:

```bash
latexmk -c main.tex
```

On Overleaf, select `main.tex` as the main file and pdfLaTeX as the compiler. Alternatively, open `paper/` in Codex for built-in compilation and PDF preview.

`main.tex` uses `\documentclass[conference]{IEEEtran}` and `\bibliographystyle{IEEEtran}`. Use `\cite{key}` for citations, or `Lim et al.~\cite{key}` when naming authors in the sentence.

The class defaults to US Letter, 10 pt body text, and standard two-column layout; the recorded conference instructions do not specify another paper size. Follow any later conference-specific template. Do not reduce font size, margins, or line spacing to compress the paper. Appendices remain in two columns and count toward the page limit.

Set `\showdraftnotesfalse` in `macros.tex` to hide drafting prompts. Before submission, complete or remove all placeholders and confirm authors and affiliations.

## Style files and maintenance

`IEEEtran.cls` and `IEEEtran.bst` are unmodified IEEEtran 1.8b files supplied by TeX Live, retained for local and Overleaf compilation. Version and release information: https://ctan.org/pkg/ieeetran .

Bibliographic authors, titles, and publication details are stored in `references.bib`. Two instructor-provided papers whose formal publication details remain unverified are marked as manuscripts; update them when formal records become available.

Generated files in `build/` and an accidentally generated root `main.pdf` are excluded by `.gitignore`. PDF figure assets in `figures/` may be committed and must not be excluded along with the manuscript. Model, preprocessing, and training code are outside this directory and are unaffected by paper-layout changes.

## Draft status and maintenance conventions

- This is a draft. The abstract, experiments, discussion, conclusion, and other sections still contain `\draftnote` placeholders. Successful compilation does not mean the paper is complete.
- The organization pass does not change body text, bibliography entries, author placeholders, or experimental conclusions, and does not automatically import historical meeting material.
- Use the [evaluation report](../evaluation/report.md) for current synthetic-perturbation evidence and the [method note](../doc/trajectory-embedding-point-cloud-complexity.md) for the estimator implementation. Check each paper claim against its evidence during writing.
- `figures/` holds cited figures; `tables/` holds table sources included with `\input`. Both are currently empty, with `.gitkeep` preserving the planned structure.
- Retain local `IEEEtran.cls` and `IEEEtran.bst`; do not delete or manually modify third-party templates as redundant code.
- Submission information retains its original verification date, 2026-10-16. This organization and translation work did not recheck conference requirements.
