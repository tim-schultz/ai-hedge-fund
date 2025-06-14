import nbformat

NOTEBOOK_PATH = 'src/selv/backtest.ipynb'
UNICODE_FIXES = [
    ('\u2011', '-'),  # non-breaking hyphen
    ('\u00d7', 'x'),  # multiplication sign
    ('\u2192', '->'),  # right arrow
]

def fix_unicode(text: str) -> str:
    for bad, good in UNICODE_FIXES:
        text = text.replace(bad, good)
    return text

def main():
    nb = nbformat.read(NOTEBOOK_PATH, as_version=4)
    changed = False
    for cell in nb.cells:
        if getattr(cell, 'cell_type', None) == 'code':
            if isinstance(cell.source, list):
                new_lines = []
                for line in cell.source:
                    new_line = fix_unicode(line)
                    if new_line != line:
                        changed = True
                    new_lines.append(new_line)
                cell.source = new_lines
            else:
                new = fix_unicode(cell.source)
                if new != cell.source:
                    changed = True
                cell.source = new
    if changed:
        nbformat.write(nb, NOTEBOOK_PATH)
        print(f"Fixed unicode issues in {NOTEBOOK_PATH}")
    else:
        print(f"No unicode issues found in {NOTEBOOK_PATH}")

if __name__ == "__main__":
    main()
