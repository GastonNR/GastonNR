"""Minimal FIGlet (.flf) renderer: horizontal smushing as figlet does it for fonts like slant.

Each letter is pushed left as far as every row allows (blanks on both sides), plus one more
column where the touching characters merge by the font's rules: equal characters, underscore
against | / \\ [ ] { } ( ) < >, hierarchy (| < /\\ < [] < {} < () < <>) and opposite pairs.
The output matches `figlet -f slant`.

Usage as a module: render(text, font_path) -> list of rows.
"""
import sys

UNDERSCORE_MATES = "|/\\[]{}()<>"
HIERARCHY = ["|", "/\\", "[]", "{}", "()", "<>"]
OPPOSITE = {"[]", "][", "{}", "}{", "()", ")("}


def load_font(path):
    lines = open(path, encoding="latin-1").read().split("\n")
    header = lines[0].split()
    hardblank = header[0][-1]
    height, comment_lines = int(header[1]), int(header[5])
    glyphs = {}
    i = 1 + comment_lines
    for code in range(32, 127):
        rows = lines[i:i + height]
        end = rows[0].rstrip()[-1]
        glyphs[chr(code)] = [r.rstrip().rstrip(end) for r in rows]
        i += height
    return glyphs, hardblank, height


def smush(a, b, hardblank):
    """Character resulting from overlapping `a` (left) and `b` (right), or None if they can't merge."""
    if a == " ":
        return b
    if b == " ":
        return a
    if hardblank in (a, b):
        return None
    if a == b:
        return a
    if a == "_" and b in UNDERSCORE_MATES:
        return b
    if b == "_" and a in UNDERSCORE_MATES:
        return a
    ca = next((i for i, c in enumerate(HIERARCHY) if a in c), None)
    cb = next((i for i, c in enumerate(HIERARCHY) if b in c), None)
    if ca is not None and cb is not None and ca != cb:
        return b if ca < cb else a
    if a + b in OPPOSITE:
        return "|"
    return None


def overlap(out, glyph, hardblank):
    """How many columns `glyph` can overlap the end of `out` (figlet's smushamt)."""
    amount = len(glyph[0])
    for o, g in zip(out, glyph):
        left = o.rstrip(" ")
        right_blanks = len(g) - len(g.lstrip(" "))
        amt = len(o) - len(left) + right_blanks
        if not left or right_blanks == len(g) or smush(left[-1], g[right_blanks], hardblank) is not None:
            amt += 1
        amount = min(amount, amt)
    return amount


def render(text, path):
    glyphs, hardblank, height = load_font(path)
    out = [""] * height
    for ch in text:
        g = glyphs[ch]
        width = max(len(r) for r in g)
        g = [r.ljust(width) for r in g]
        shift = min(overlap(out, g, hardblank), min(len(o) for o in out)) if out[0] else 0
        merged = []
        for o, r in zip(out, g):
            start = len(o) - shift
            merged.append(o[:start] + "".join(smush(a, b, hardblank) or b for a, b in zip(o[start:], r[:shift])) + r[shift:])
        out = merged
    rows = [o.replace(hardblank, " ").rstrip() for o in out]
    while rows and not rows[0].strip():
        rows.pop(0)
    while rows and not rows[-1].strip():
        rows.pop()
    return rows


if __name__ == "__main__":
    for row in render(sys.argv[1], sys.argv[2]):
        print(row)
