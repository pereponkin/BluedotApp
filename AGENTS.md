# BlueDotApp Project Rules

## Tests

- Run the full suite from the repository root with `python -m pytest -q` when pytest is
  available in the active environment.
- For a focused file, append its path, for example `python -m pytest -q tests\test_panel.py`.
- The dependency-free fallback is `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.
