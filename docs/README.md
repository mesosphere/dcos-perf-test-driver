
# `dcos-perf-test-driver` Documentation

This folder contains the sphinx sources needed in order to generate the documentation. To generate the `html` pages yourself do:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make html
```

If you want to generate the PDF documentation, instead of `make html` use `make pdflatex` (you must have a valid LaTeX installation in your system).
