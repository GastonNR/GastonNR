"""Profile banner: an 80s green-phosphor terminal (SVG + SMIL) that shows, in one session,
the name in ASCII letters, `cat perfil.ts` and the contributions graph of the last year.

The contributions come from the public calendar (github.com/users/<user>/contributions), so a
daily GitHub Action can regenerate the banner. The animation restarts every LOOP seconds.

Usage: python3 scripts/make_banner.py <out_dir> [calendar.html]
Without calendar.html the page is downloaded.
"""
import re
import sys
import urllib.request
from datetime import date, timedelta
from html import escape, unescape
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from figlet_slant import render  # noqa: E402

USER = "GastonNR"
LOOP = 30
OUT_NAME = "banner.svg"
MONO = "'JetBrains Mono', 'SFMono-Regular', ui-monospace, Menlo, Consolas, 'DejaVu Sans Mono', monospace"

# Monochrome: syntax is shown with the intensity of the green, not with different colours
GREEN, DIM, BRIGHT, PALE = "#4dff85", "#1f9e4a", "#d4ffe0", "#9dffb5"
KW, KEY, STR, PUN = PALE, GREEN, BRIGHT, DIM

SUBTITLE = "Desarrollador de Software"
FILENAME = "perfil.ts"


def strs(items):
    parts = [("[", PUN)]
    for i, s in enumerate(items):
        parts.append((f'"{s}"', STR))
        if i < len(items) - 1:
            parts.append((", ", PUN))
    parts.append(("],", PUN))
    return parts


CODE = [
    [("const ", KW), ("desarrollador", GREEN), (" = {", PUN)],
    [("  nombre", KEY), (": ", PUN), ('"Gastón Nicolás Ruiz Ahumada"', STR), (",", PUN)],
    [("  rol", KEY), (": ", PUN), ('"Desarrollador Full Stack"', STR), (",", PUN)],
    [("  stack", KEY), (": ", PUN), *strs(["React", "TypeScript", "Spring Boot", "Node.js"])],
    [("  proyectos", KEY), (": ", PUN), *strs(["LeitnerApp", "Entrópica"])],
    [("  github", KEY), (": ", PUN), ('"GastonNR"', STR), (",", PUN)],
    [("};", PUN)],
]

# contributions grid: level 0..4 -> (glyph, color)
CELLS = [("·", "#1a6b3a"), ("░", "#2fbf5f"), ("▒", "#4dff85"), ("▓", "#8dffad"), ("█", "#d4ffe0")]
MONTHS = "ene feb mar abr may jun jul ago sep oct nov dic".split()
DAYS = {1: "lun", 3: "mié", 5: "vie"}
FLICKER = "0;.05;0;.03;0;0"  # opacity steps of the green flicker over the whole screen
GLYPH, SQUASH = 18, 0.5  # block glyphs are about twice as tall as wide: squash them into squares


TITLE_TEXT = "GASTONNR"


def slant_title(text=TITLE_TEXT):
    """Title in figlet's 'slant' style, like the Oh My Zsh logo."""
    return render(text, HERE / "fonts" / "slant.flf")


# ---------------------------------------------------------------- contributions data

def load_calendar(html):
    """{(row, col): (date, level, count)} from the contributions page."""
    counts = {}
    for for_id, label in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', html):
        m = re.match(r"(\d+) contribution", unescape(label))
        counts[for_id] = int(m.group(1)) if m else 0
    cells = {}
    for attrs in re.findall(r"<td[^>]*data-date[^>]*>", html):
        d = re.search(r'data-date="([\d-]+)"', attrs).group(1)
        cid = re.search(r'id="(contribution-day-component-(\d+)-(\d+))"', attrs)
        level = int(re.search(r'data-level="(\d)"', attrs).group(1))
        cells[(int(cid.group(2)), int(cid.group(3)))] = (date.fromisoformat(d), level, counts.get(cid.group(1), 0))
    return cells


def stats(cells):
    by_day = sorted((d, n) for d, _, n in cells.values())
    total = sum(n for _, n in by_day)
    active = sum(1 for _, n in by_day if n)
    longest = run = 0
    prev = None
    for d, n in by_day:  # the calendar has every day, but check for gaps anyway
        run = run + 1 if n and prev == d - timedelta(days=1) else (1 if n else 0)
        prev = d
        longest = max(longest, run)
    best = max(by_day, key=lambda x: x[1])
    return total, active, longest, best


def fmt_int(n):
    return f"{n:,}".replace(",", ".")


def fmt_date(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


# ---------------------------------------------------------------- SMIL helpers

def at(t):
    """Begin time relative to the start of the current loop iteration."""
    return f"loop.begin+{round(t, 3)}s"


RESET = 'begin="loop.begin"'  # resets fire at every loop start


def appear(begin):
    """Hidden at each loop start, visible from `begin` on."""
    return f'<set attributeName="opacity" to="0" {RESET}/><set attributeName="opacity" to="1" begin="{at(begin)}"/>'


def reveal_clip(uid, x, y, h, step, n, begin, dur):
    """clipPath whose width grows `step` px at a time, `n` times, from `begin` during `dur` seconds."""
    widths = ";".join(str(round(i * step, 2)) for i in range(n + 1))
    return (
        f'  <clipPath id="{uid}"><rect x="{x}" y="{y}" width="0" height="{h}">'
        f'<set attributeName="width" to="0" {RESET}/>'
        f'<animate attributeName="width" values="{widths}" calcMode="discrete" begin="{at(begin)}" dur="{dur}s" fill="freeze"/>'
        f"</rect></clipPath>\n"
    ), widths


class Terminal:
    size, cw = 15, 9  # font size and character width
    lx = 34           # left margin

    def __init__(self):
        self.out = []
        self.cursor = []  # animations of the shared block cursor
        self.uid = 0

    def typed(self, x, y, text, begin, speed, spans=None, fill=GREEN):
        """A line revealed one character at a time; the cursor follows it. Returns the end time."""
        self.uid += 1
        n, cw, size = len(text), self.cw, self.size
        dur = round(n * speed, 3)
        clip, widths = reveal_clip(f"c{self.uid}", x, y - size, size * 1.5, cw, n, begin, dur)
        self.out.append(clip)
        self.out.append(
            f'  <text x="{x}" y="{y}" font-size="{size}" fill="{fill}" textLength="{round(n * cw, 2)}" '
            f'lengthAdjust="spacingAndGlyphs" clip-path="url(#c{self.uid})" xml:space="preserve">'
            f'{spans if spans is not None else escape(text)}</text>\n')
        xs = ";".join(str(round(x + float(w), 2)) for w in widths.split(";"))
        self.cursor.append(
            f'<set attributeName="y" to="{y - size + 2}" begin="{at(begin)}" fill="freeze"/>'
            f'<animate attributeName="x" values="{xs}" calcMode="discrete" begin="{at(begin)}" dur="{dur}s" fill="freeze"/>')
        return begin + dur

    def prompt(self, y, begin):
        self.out.append(f'  <text x="{self.lx}" y="{y}" font-size="{self.size}" fill="{GREEN}" opacity="0">${appear(begin)}</text>\n')

    def command(self, y, cmd, begin):
        self.prompt(y, begin)
        return self.typed(self.lx + 2 * self.cw, y, cmd, begin + 0.35, 0.06)

    def line(self, y, begin, content, size=None, fill=GREEN):
        """Output line that appears at once, like a program's output."""
        self.out.append(f'  <text x="{self.lx}" y="{y}" font-size="{size or self.size}" fill="{fill}" opacity="0" '
                        f'xml:space="preserve">{content}{appear(begin)}</text>\n')


# ---------------------------------------------------------------- banner

def build(cells):
    term = Terminal()
    size, cw, lx = term.size, term.cw, term.lx
    out = term.out
    title = slant_title()
    title_lh = 19
    t = 0.3

    # 1) title revealed column by column, subtitle typed below it
    title_y = 40
    cols = max(len(r) for r in title)
    dur = round(cols * 0.012, 3)
    clip, _ = reveal_clip("ctitle", lx, title_y - title_lh, len(title) * title_lh + 4, cw, cols, t, dur)
    out.append(clip)
    out.append(f'  <g font-size="{size}" fill="{BRIGHT}" clip-path="url(#ctitle)">\n')
    for i, row in enumerate(title):
        if row.strip():
            out.append(f'    <text x="{lx}" y="{title_y + i * title_lh}" textLength="{round(len(row) * cw, 2)}" '
                       f'lengthAdjust="spacingAndGlyphs">{escape(row).replace(" ", chr(0xa0))}</text>\n')
    out.append("  </g>\n")
    t += dur + 0.3
    y = title_y + (len(title) - 1) * title_lh + 36
    term.cursor.append(f'<set attributeName="opacity" to="1" begin="{at(t)}"/>')
    t = term.typed(lx, y, SUBTITLE, t, 0.045) + 0.6

    # 2) cat perfil.ts, typed line by line like an old serial terminal
    y += 46
    t = term.command(y, f"cat {FILENAME}", t) + 0.3
    y += 28
    for parts in CODE:
        text = "".join(p for p, _ in parts)
        spans = "".join(f'<tspan fill="{c}">{escape(p)}</tspan>' for p, c in parts)
        t = term.typed(lx, y, text, t, 0.03, spans=spans) + 0.12
        y += 24

    # 3) contributions graph of the last year, printed week by week
    total, active, longest, (best_day, best_n) = stats(cells)
    y += 26
    t = term.command(y, f"contrib --user {USER} --last-year", t + 0.4) + 0.5
    gcols = max(c for _, c in cells) + 1
    gx = lx + 5 * cw
    step_x, step_y = 15.6, 15
    months_y = y + 40
    grid_y = months_y + 24  # baseline of the first row
    out.append(f'  <g font-size="13" fill="{DIM}" opacity="0">{appear(t)}\n')
    last = -10
    for c in range(gcols):
        first = min((cells[(r, c)][0] for r in range(7) if (r, c) in cells), default=None)
        if first and first.day <= 7 and c - last >= 3:
            out.append(f'    <text x="{round(gx + c * step_x, 2)}" y="{months_y}">{MONTHS[first.month - 1]}</text>\n')
            last = c
    for r, name in DAYS.items():
        out.append(f'    <text x="{lx}" y="{grid_y + r * step_y}">{name}</text>\n')
    out.append("  </g>\n")

    def squashed_y(baseline):
        """Baseline in the squashed space, so the glyph's center lines up with text at `baseline`."""
        return round((baseline - 4.5) / SQUASH + GLYPH * 0.26, 2)

    wdur = round(gcols * 0.045, 3)
    clip, _ = reveal_clip("cgrid", gx - 4, grid_y - step_y, 7 * step_y + 6, step_x, gcols, t, wdur)
    out.append(clip)
    out.append(f'  <g clip-path="url(#cgrid)"><g font-size="{GLYPH}" transform="scale(1,{SQUASH})">\n')
    for r in range(7):
        spans = "".join(
            f'<tspan x="{round(gx + c * step_x, 2)}" fill="{CELLS[cells[(r, c)][1]][1]}">{CELLS[cells[(r, c)][1]][0]}</tspan>'
            for c in range(gcols) if (r, c) in cells)
        out.append(f'    <text y="{squashed_y(grid_y + r * step_y)}">{spans}</text>\n')
    out.append("  </g></g>\n")
    t += wdur + 0.4

    legend_y = grid_y + 6 * step_y + 34
    legend = "".join(f'<tspan x="{round(gx + (3 + i) * step_x, 2)}" fill="{color}">{glyph}</tspan>'
                     for i, (glyph, color) in enumerate(CELLS))
    out.append(f'  <g font-size="13" fill="{DIM}" opacity="0">{appear(t)}'
               f'<text x="{gx}" y="{legend_y}">menos</text>'
               f'<g transform="scale(1,{SQUASH})"><text y="{squashed_y(legend_y)}" font-size="{GLYPH}">{legend}</text></g>'
               f'<text x="{round(gx + 8.6 * step_x, 2)}" y="{legend_y}">más</text></g>\n')
    t += 0.35
    y = legend_y + 38
    term.line(y, t, f'<tspan fill="{BRIGHT}">{fmt_int(total)}</tspan> contribuciones en el último año · '
                    f'<tspan fill="{BRIGHT}">{active}</tspan> días activos')
    t += 0.2
    y += 24
    term.line(y, t, f'racha más larga: <tspan fill="{BRIGHT}">{longest}</tspan> días · mejor día: '
                    f'<tspan fill="{BRIGHT}">{best_n}</tspan> ({fmt_date(best_day)})')
    t += 0.4

    # 4) final prompt with a blinking block cursor
    y += 38
    term.prompt(y, t)
    term.cursor.append(
        f'<set attributeName="x" to="{lx + 2 * cw}" begin="{at(t)}"/><set attributeName="y" to="{y - size + 2}" begin="{at(t)}"/>'
        f'<animate attributeName="opacity" values="1;0" calcMode="discrete" dur="1s" begin="{at(t)}" repeatCount="indefinite"/>')
    out.append(f'  <rect x="0" y="0" width="{cw}" height="{size}" fill="{GREEN}" opacity="0">'
               f'<set attributeName="opacity" to="0" {RESET}/>{"".join(term.cursor)}</rect>\n')
    assert t < LOOP, f"the animation ({t:.1f} s) does not fit in {LOOP} s"

    W, H = 960, y + 30
    desc = (f"Una terminal de fósforo verde de los años 80 con {TITLE_TEXT} en letras ASCII, el subtítulo {SUBTITLE}, "
            f"el archivo {FILENAME} con el rol, el stack y los proyectos, y el gráfico de contribuciones del último año: "
            f"{fmt_int(total)} contribuciones, {active} días activos, racha más larga de {longest} días.")
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">\n'
        f'  <title id="t">Nicolás Ruiz · {SUBTITLE}</title>\n  <desc id="d">{escape(desc)}</desc>\n'
        '  <defs>\n'
        '    <filter id="glow" x="-5%" y="-20%" width="110%" height="140%"><feGaussianBlur stdDeviation="1.8" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>\n'
        '    <pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1.2" fill="#000" opacity=".45"/></pattern>\n'
        '    <radialGradient id="vignette" cx="50%" cy="50%" r="75%"><stop offset=".55" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#000" stop-opacity=".75"/></radialGradient>\n'
        '    <radialGradient id="screen" cx="50%" cy="45%" r="70%"><stop offset="0" stop-color="#020c06"/><stop offset="1" stop-color="#000000"/></radialGradient>\n'
        f'    <clipPath id="crt"><rect width="{W}" height="{H}" rx="12"/></clipPath>\n'
        '  </defs>\n'
        f'  <rect width="{W}" height="{H}" rx="12" fill="url(#screen)"/>\n'
        f'  <rect width="0" height="0"><animate id="loop" attributeName="x" values="0;0" dur="{LOOP}s" begin="0s;loop.end"/></rect>\n'
        '  <g clip-path="url(#crt)">\n'
        f'  <g font-family="{MONO}" filter="url(#glow)">\n'
    )
    # CRT effects on top of the text: scanlines, a faint flicker and the vignette
    tail = (
        "  </g>\n"
        f'  <rect width="{W}" height="{H}" fill="url(#scan)"/>\n'
        f'  <rect width="{W}" height="{H}" fill="{GREEN}" opacity="0"><animate attributeName="opacity" values="{FLICKER}" dur=".9s" repeatCount="indefinite"/></rect>\n'
        f'  <rect width="{W}" height="{H}" fill="url(#vignette)"/>\n'
        "  </g>\n"
        f'  <rect width="{W}" height="{H}" rx="12" fill="none" stroke="#1e293b" stroke-width="1.5"/>\n'
        "</svg>\n"
    )
    return head + "".join(out) + tail, (t, H, total, active, longest)


if __name__ == "__main__":
    out_dir = Path(sys.argv[1])
    if len(sys.argv) > 2:
        html = Path(sys.argv[2]).read_text()
    else:
        req = urllib.request.Request(f"https://github.com/users/{USER}/contributions",
                                     headers={"User-Agent": "profile-banner"})
        html = urllib.request.urlopen(req, timeout=30).read().decode()
    cells = load_calendar(html)
    # if GitHub changes the page format, fail instead of overwriting the banner with an empty graph
    if len(cells) < 300:
        sys.exit(f"Could not read the calendar: only {len(cells)} days found")
    svg, (t, H, total, active, longest) = build(cells)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / OUT_NAME).write_text(svg)
    print(f"{OUT_NAME}: animación de {t:.1f} s (ciclo de {LOOP} s), alto {H}px, {len(svg)} bytes · "
          f"{total} contribuciones, {active} días activos, racha de {longest}")
