"""Generate the contributions graph for the GitHub profile, as an 80s green-phosphor terminal (SVG + SMIL).

It reads the public contribution calendar (github.com/users/<user>/contributions), draws the
53x7 grid with block characters (· ░ ▒ ▓ █), prints it week by week and adds a few stats.
The animation restarts every LOOP seconds, like the banners.

Usage: python3 make_contrib.py <out_dir> [calendar.html]
Without calendar.html the page is downloaded. It only has public contributions (plus private
ones if "Private contributions" is enabled on the profile).
"""
import re
import sys
import urllib.request
from datetime import date, timedelta
from html import escape, unescape
from pathlib import Path

USER = "GastonNR"
LOOP = 30
MONO = "'JetBrains Mono', 'SFMono-Regular', ui-monospace, Menlo, Consolas, 'DejaVu Sans Mono', monospace"
GREEN, DIM, BRIGHT = "#4dff85", "#1f9e4a", "#d4ffe0"
# level 0..4 -> (glyph, color)
CELLS = [("·", "#1a6b3a"), ("░", "#2fbf5f"), ("▒", "#4dff85"), ("▓", "#8dffad"), ("█", "#d4ffe0")]
MONTHS = "ene feb mar abr may jun jul ago sep oct nov dic".split()
DAYS = {1: "lun", 3: "mié", 5: "vie"}
GLYPH, SQUASH = 18, 0.5  # grid glyph size and vertical squash


def at(t):
    return f"loop.begin+{round(t, 3)}s"


RESET = 'begin="loop.begin"'


def appear(begin):
    return f'<set attributeName="opacity" to="0" {RESET}/><set attributeName="opacity" to="1" begin="{at(begin)}"/>'


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


def build(cells):
    cols = max(c for _, c in cells) + 1
    total, active, longest, (best_day, best_n) = stats(cells)

    size, cw = 15, 9
    lx = 34
    gx = lx + 5 * cw          # grid start, after the day labels
    step_x, step_y = 15.6, 15
    cmd_y = 40
    months_y = cmd_y + 40
    grid_y = months_y + 24    # baseline of the first row
    legend_y = grid_y + 6 * step_y + 34
    total_y = legend_y + 38
    streak_y = total_y + 24
    final_y = streak_y + 38
    W, H = 960, final_y + 30
    grid_w = round(cols * step_x, 2)

    out = []
    t = 0.3
    # 1) the command, typed
    cmd = f"contrib --user {USER} --last-year"
    out.append(f'  <text x="{lx}" y="{cmd_y}" font-size="{size}" fill="{GREEN}" opacity="0">${appear(t)}</text>\n')
    t += 0.35
    n = len(cmd)
    widths = ";".join(str(round(i * cw, 2)) for i in range(n + 1))
    dur = round(n * 0.06, 3)
    cx = lx + 2 * cw
    out.append(
        f'  <clipPath id="ccmd"><rect x="{cx}" y="{cmd_y - size}" width="0" height="{size * 1.5}">'
        f'<set attributeName="width" to="0" {RESET}/>'
        f'<animate attributeName="width" values="{widths}" calcMode="discrete" begin="{at(t)}" dur="{dur}s" fill="freeze"/></rect></clipPath>\n'
        f'  <text x="{cx}" y="{cmd_y}" font-size="{size}" fill="{GREEN}" textLength="{n * cw}" lengthAdjust="spacingAndGlyphs" '
        f'clip-path="url(#ccmd)" xml:space="preserve">{escape(cmd)}</text>\n')
    xs = ";".join(str(round(cx + float(w), 2)) for w in widths.split(";"))
    cursor = [f'<set attributeName="opacity" to="1" begin="{at(t)}"/>'
              f'<set attributeName="y" to="{cmd_y - size + 2}" begin="{at(t)}"/>'
              f'<animate attributeName="x" values="{xs}" calcMode="discrete" begin="{at(t)}" dur="{dur}s" fill="freeze"/>'
              f'<set attributeName="opacity" to="0" begin="{at(t + dur + 0.25)}"/>']
    t += dur + 0.5

    # 2) month labels, day labels and grid, printed week by week
    out.append(f'  <g opacity="0">{appear(t)}\n')
    last = -10
    for c in range(cols):
        first = min((cells[(r, c)][0] for r in range(7) if (r, c) in cells), default=None)
        if first and first.day <= 7 and c - last >= 3:
            out.append(f'    <text x="{round(gx + c * step_x, 2)}" y="{months_y}" font-size="13" fill="{DIM}">{MONTHS[first.month - 1]}</text>\n')
            last = c
    for r, name in DAYS.items():
        out.append(f'    <text x="{lx}" y="{round(grid_y + r * step_y, 2)}" font-size="13" fill="{DIM}">{name}</text>\n')
    out.append("  </g>\n")

    wdur = round(cols * 0.045, 3)
    widths = ";".join(str(round(i * step_x, 2)) for i in range(cols + 1))
    out.append(
        f'  <clipPath id="cgrid"><rect x="{gx - 4}" y="{grid_y - step_y}" width="0" height="{7 * step_y + 6}">'
        f'<set attributeName="width" to="0" {RESET}/>'
        f'<animate attributeName="width" values="{widths}" calcMode="discrete" begin="{at(t)}" dur="{wdur}s" fill="freeze"/></rect></clipPath>\n'
        # block glyphs are about twice as tall as wide: squash them vertically so each day is a square
        f'  <g clip-path="url(#cgrid)"><g font-size="{GLYPH}" transform="scale(1,{SQUASH})">\n')
    for r in range(7):
        spans = []
        for c in range(cols):
            if (r, c) not in cells:
                continue
            d, level, count = cells[(r, c)]
            glyph, color = CELLS[level]
            spans.append(f'<tspan x="{round(gx + c * step_x, 2)}" fill="{color}">{glyph}</tspan>')
        # baseline in the squashed space, so the glyph's center lines up with the day label
        y = ((grid_y + r * step_y - 4.5) / SQUASH) + GLYPH * 0.26
        out.append(f'    <text y="{round(y, 2)}">{"".join(spans)}</text>\n')
    out.append("  </g></g>\n")
    t += wdur + 0.4

    # 3) legend and stats, printed line by line like command output
    ly = round(((legend_y - 4.5) / SQUASH) + GLYPH * 0.26, 2)
    legend = "".join(f'<tspan x="{round(gx + (3 + i) * step_x, 2)}" fill="{color}">{glyph}</tspan>'
                     for i, (glyph, color) in enumerate(CELLS))
    out.append(f'  <g opacity="0">{appear(t)}'
               f'<text x="{gx}" y="{legend_y}" font-size="13" fill="{DIM}">menos</text>'
               f'<g transform="scale(1,{SQUASH})"><text y="{ly}" font-size="{GLYPH}">{legend}</text></g>'
               f'<text x="{round(gx + 8.6 * step_x, 2)}" y="{legend_y}" font-size="13" fill="{DIM}">más</text></g>\n')
    t += 0.35
    out.append(f'  <text x="{lx}" y="{total_y}" font-size="{size}" fill="{GREEN}" opacity="0" xml:space="preserve">'
               f'<tspan fill="{BRIGHT}">{fmt_int(total)}</tspan> contribuciones en el último año · '
               f'<tspan fill="{BRIGHT}">{active}</tspan> días activos{appear(t)}</text>\n')
    t += 0.2
    out.append(f'  <text x="{lx}" y="{streak_y}" font-size="{size}" fill="{GREEN}" opacity="0" xml:space="preserve">'
               f'racha más larga: <tspan fill="{BRIGHT}">{longest}</tspan> días · mejor día: '
               f'<tspan fill="{BRIGHT}">{best_n}</tspan> ({fmt_date(best_day)}){appear(t)}</text>\n')
    t += 0.4

    # 4) final prompt with a blinking block cursor
    out.append(f'  <text x="{lx}" y="{final_y}" font-size="{size}" fill="{GREEN}" opacity="0">${appear(t)}</text>\n')
    cursor.append(f'<set attributeName="x" to="{lx + 2 * cw}" begin="{at(t)}"/><set attributeName="y" to="{final_y - size + 2}" begin="{at(t)}"/>'
                  f'<animate attributeName="opacity" values="1;0" calcMode="discrete" dur="1s" begin="{at(t)}" repeatCount="indefinite"/>')
    out.append(f'  <rect x="0" y="0" width="{cw}" height="{size}" fill="{GREEN}" opacity="0">'
               f'<set attributeName="opacity" to="0" {RESET}/>{"".join(cursor)}</rect>\n')
    assert t < LOOP

    desc = (f"Gráfico de contribuciones de {USER} en una terminal de fósforo verde: {fmt_int(total)} contribuciones "
            f"en el último año, {active} días activos, racha más larga de {longest} días.")
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">\n'
        f'  <title id="t">Contribuciones de {USER}</title>\n  <desc id="d">{escape(desc)}</desc>\n'
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
    tail = (
        "  </g>\n"
        f'  <rect width="{W}" height="{H}" fill="url(#scan)"/>\n'
        f'  <rect width="{W}" height="{H}" fill="{GREEN}" opacity="0"><animate attributeName="opacity" values="0;.025;0;.015;0;0" dur=".9s" repeatCount="indefinite"/></rect>\n'
        f'  <rect width="{W}" height="{H}" fill="url(#vignette)"/>\n'
        "  </g>\n"
        f'  <rect width="{W}" height="{H}" rx="12" fill="none" stroke="#1e293b" stroke-width="1.5"/>\n'
        "</svg>\n"
    )
    return head + "".join(out) + tail, (total, active, longest, best_n, best_day, H)


if __name__ == "__main__":
    out_dir = Path(sys.argv[1])
    if len(sys.argv) > 2:
        html = Path(sys.argv[2]).read_text()
    else:
        req = urllib.request.Request(f"https://github.com/users/{USER}/contributions",
                                     headers={"User-Agent": "contrib-banner"})
        html = urllib.request.urlopen(req, timeout=30).read().decode()
    cells = load_calendar(html)
    # if GitHub changes the page format, fail instead of overwriting the graph with an empty one
    if len(cells) < 300:
        sys.exit(f"Could not read the calendar: only {len(cells)} days found")
    svg, (total, active, longest, best_n, best_day, H) = build(cells)
    (out_dir / "contrib-retro.svg").write_text(svg)
    print(f"contrib-retro.svg: alto {H}px, {len(svg)} bytes · total {total}, días activos {active}, "
          f"racha {longest}, mejor día {best_n} ({best_day})")
