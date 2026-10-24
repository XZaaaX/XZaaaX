#!/usr/bin/env python3
"""Regenerate profile README sections from live GitHub data.

Stdlib only. Updates in place:
  sec-projects-gold.svg  - 4 project cards (name, desc, lang, stars, ring %)
  sec-stack-gold.svg     - top-3 language bars
  sec-stats-gold.svg     - stars / contributions / repos / followers
  sec-heatmap-gold.svg    - contribution grid levels + total text
Run locally or from .github/workflows/regen.yml (cron).
"""
import datetime
import html as htmllib
import json
import os
import re
import sys
import urllib.request

USER = "XZaaaX"
D = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "profile-readme-regen"}

# language colors (GitHub Linguist palette; first three keep legacy look)
LC = {
    "Jupyter Notebook": "#DA5B0B", "JavaScript": "#f1e05a", "Python": "#3572A5",
    "TypeScript": "#3178c6", "HTML": "#e34c26", "CSS": "#563d7c", "Java": "#b07219",
    "C": "#555555", "C++": "#f34b7d", "C#": "#178600", "Go": "#00ADD8",
    "Rust": "#dea584", "PHP": "#4F5D95", "Ruby": "#701516", "Swift": "#F05138",
    "Kotlin": "#A97BFF", "Dart": "#00B4AB", "Shell": "#89e051", "Vue": "#41b883",
    "R": "#198CE7", "Scala": "#c22d41", "Lua": "#000080", "Perl": "#0298c3",
}
# softer fills used for stars text + stack bars (legacy look)
SC = {"Jupyter Notebook": "#f47829", "JavaScript": "#f1e05a", "Python": "#5594c8"}


def get(url, binary=False):
    r = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(r, timeout=30).read()
    return data if binary else data.decode("utf-8", "replace")


def jget(url):
    return json.loads(get(url))


def esc(s):
    return htmllib.escape(s or "", quote=False)


def ago(iso):
    d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    days = (datetime.datetime.now(datetime.timezone.utc) - d).days
    if days < 1: return "today"
    if days < 30: return "%dd ago" % days
    if days < 365: return "%dmo ago" % (days // 30)
    return "%dy ago" % (days // 365)


def wrap2(text, n=47):
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= n:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][:n - 1] + "…"
    while len(lines) < 2:
        lines.append("")
    return lines


def fetch_readme(repo, branch="main"):
    """First prose line of README as fallback description."""
    raw = ""
    for b in (branch, "master"):
        try:
            raw = get("https://raw.githubusercontent.com/%s/%s/%s/README.md" % (USER, repo, b))
            break
        except Exception:
            continue
    if not raw:
        return ""
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!", "[!", "[<", "<", "|", "-", "*", "```", "[", "===")):
            continue
        line = re.sub(r"[#*_`>\[\]()]", "", line).strip()
        if len(line) > 12:
            return line
    return ""


def lang_color(name, soft=False):
    if soft and name in SC:
        return SC[name]
    return LC.get(name, "#8b949e")


def pick_repos(repos, n=4):
    pool = [r for r in repos if not r["fork"] and r["name"] != USER]
    with_lang = sorted([r for r in pool if r.get("language")],
                       key=lambda r: r["pushed_at"], reverse=True)
    rest = sorted([r for r in pool if not r.get("language")],
                  key=lambda r: r["pushed_at"], reverse=True)
    return (with_lang + rest)[:n]


def load_langs(repos):
    out = {}
    for r in repos:
        if r["fork"]:
            continue
        out[r["name"]] = jget("https://api.github.com/repos/%s/%s/languages" % (USER, r["name"]))
    return out


def contributions():
    page = get("https://github.com/users/%s/contributions" % USER)
    cells = {}
    total = 0
    for date, level in re.findall(r'data-date="([\d-]+)"[^>]*data-level="(\d)"', page):
        cells[date] = int(level)
    for tip in re.findall(r"<tool-tip[^>]*>([^<]+)</tool-tip>", page):
        m = re.match(r"(\d+) contribution", tip)
        if m:
            total += int(m.group(1))
    return cells, total


# ---------------------------------------------------------------- projects
def regen_projects(repos, langs_by_repo):
    p = os.path.join(D, "sec-projects-gold.svg")
    t = open(p, encoding="utf-8").read()
    sel = pick_repos(repos, 4)
    assert len(sel) == 4, "only %d repos" % len(sel)

    t = re.sub(r">\d+ projects<", ">%d projects<" % len(sel), t, count=1)

    blocks = []
    spans = [(m.start(), t.index("</a>", m.start()) + 4)
             for m in re.finditer(r"<a href=", t)]
    out, last = t, []
    for i, (s, e) in enumerate(reversed(spans)):
        r = sel[3 - i]
        block = t[s:e]
        block = regen_card(block, r, langs_by_repo.get(r["name"], {}))
        out = out[:s] + block + out[e:]
    open(p, "w", encoding="utf-8", newline="\n").write(out)
    print("projects ->", [r["name"] for r in sel])


def regen_card(b, r, langs):
    name = r["name"]
    desc = (r.get("description") or "").strip()
    if not desc:
        desc = fetch_readme(name)
    lines = wrap2(desc) if desc else ["No description provided.", ""]
    label = r.get("language") or "Other"
    total = sum(langs.values()) or 1
    ordered = sorted(langs.items(), key=lambda kv: -kv[1])
    pct1 = round(100 * ordered[0][1] / total) if ordered else 100
    c1 = lang_color(label)
    short = name if len(name) <= 25 else name[:24] + "…"
    stars = r["stargazers_count"]
    badge_w = int(round(len(label) * 5.7 + 22))
    badge_cx = 18 + badge_w // 2
    C = 157.08  # 2*pi*25

    # href + header name
    b = re.sub(r'<a href="[^"]+"', '<a href="https://github.com/%s/%s"' % (USER, name), b, count=1)
    b = re.sub(r'(•</tspan>) [^<]*(</text>)', r"\1 " + esc(name) + r"\2", b, count=1)
    # title
    b = re.sub(r'(y="58"[^>]*>)[^<]*(<tspan)', r"\g<1>" + esc(short) + r"\g<2>", b, count=1)
    # desc lines
    b = re.sub(
        r'<text x="18" y="79"[^>]*>[^<]*</text><text x="18" y="95"[^>]*>[^<]*</text>',
        '<text x="18" y="79" font-family="ui-monospace,\'SF Mono\',SFMono-Regular,Menlo,Consolas,monospace" font-size="11.5" fill="#8b949e">%s</text>'
        '<text x="18" y="95" font-family="ui-monospace,\'SF Mono\',SFMono-Regular,Menlo,Consolas,monospace" font-size="11.5" fill="#8b949e">%s</text>'
        % (esc(lines[0]), esc(lines[1])), b, count=1)
    # badge width + label + center
    b = re.sub(r'<rect x="18" y="112" width="\d+"',
               '<rect x="18" y="112" width="%d"' % badge_w, b, count=1)
    b = re.sub(r'<text x="\d+" y="124\.5" text-anchor="middle"([^>]*?fill=")[^"]+("[^>]*>)[^<]*(</text>)',
               lambda m: ('<text x="%d" y="124.5" text-anchor="middle"' % badge_cx)
               + m.group(1) + c1 + m.group(2) + esc(label) + m.group(3), b, count=1)
    # stars + updated
    b = re.sub(
        r'<text x="18" y="150"[^>]*>.*?</text>',
        '<text x="18" y="150" font-family="ui-monospace,\'SF Mono\',SFMono-Regular,Menlo,Consolas,monospace" font-size="11" fill="#8b949e">'
        '<tspan fill="%s">★</tspan> %d<tspan fill="#f5d78e" fill-opacity="0.7" dx="12">updated %s</tspan></text>'
        % (lang_color(label, soft=True), stars, ago(r["pushed_at"])), b, count=1)
    # percent text
    b = re.sub(r'(y="96" text-anchor="middle"[^>]*>)[^<]*(</text>)',
               r"\g<1>%d%%\g<2>" % pct1, b, count=1)
    # ring segments: replace every stroke-dasharray circle (keep bg circle)
    segs = []
    p1 = round(C * pct1 / 100, 2)
    segs.append((c1, p1, round(C - p1, 2), 0.0))
    if len(ordered) > 1:
        pct2 = round(100 * ordered[1][1] / total)
        if pct2 >= 1:
            p2 = round(C * pct2 / 100, 2)
            segs.append((lang_color(ordered[1][0]), p2, round(C - p2, 2), -p1))
    seg_tpl = ('<circle cx="348" cy="92" r="25" fill="none" stroke="%s" stroke-width="8" '
               'stroke-dasharray="%.2f %.2f" stroke-dashoffset="%.2f" transform="rotate(-90 348 92)" opacity="0">'
               '<animate attributeName="opacity" from="0" to="1" dur="0.01s" begin="0.55s" fill="freeze"/>'
               '<animate attributeName="stroke-dasharray" from="0 157.08" to="%.2f %.2f" dur="0.6s" begin="0.55s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.3 0 0.2 1"/></circle>')
    new_segs = "".join(seg_tpl % (c, a, bb, off, a, bb) for c, a, bb, off in segs)
    # remove existing seg circles (those with stroke-dasharray) and insert after bg circle
    b = re.sub(r'<circle cx="348" cy="92" r="25"[^>]*stroke-dasharray.*?</circle>', "", b)
    b = b.replace('<text x="348" y="96"', new_segs + '<text x="348" y="96"', 1)
    return b


# ---------------------------------------------------------------- stack
def regen_stack(repos, langs_by_repo):
    p = os.path.join(D, "sec-stack-gold.svg")
    t = open(p, encoding="utf-8").read()
    agg = {}
    for name, langs in langs_by_repo.items():
        for k, v in langs.items():
            agg[k] = agg.get(k, 0) + v
    total = sum(agg.values()) or 1
    top = sorted(agg.items(), key=lambda kv: -kv[1])[:3]
    pcts = [round(100 * v / total) for _, v in top]

    tpl = ('    <g class="aura-chip" style="animation-delay:{delay}ms">\n'
           '      <circle cx="54" cy="{cy}" r="5" fill="{c}"/>\n'
           '      <text x="72" y="{ty}" font-family="SpaceGrotesk,sans-serif" font-size="11.9" font-weight="800" fill="#ffffff">{label}</text>\n'
           '      <text x="306" y="{ty}" font-family="SpaceGrotesk,sans-serif" font-size="11" font-weight="850" fill="{c}" text-anchor="end">{pct}%</text>\n'
           '      <rect x="330" y="{by}" width="466" height="9" rx="4.5" fill="rgba(255,255,255,0.12)"/>\n'
           '      <rect class="aura-bar" x="330" y="{by}" width="{bw}" height="9" rx="4.5" fill="{c}" opacity="0.95"/>\n'
           '    </g>\n')
    ys = [(107, 112, 98), (139, 144, 130), (171, 176, 162)]
    chips = ""
    for i, ((lang, _), pct) in enumerate(zip(top, pcts)):
        cy, ty, by = ys[i]
        bw = max(19, round(466 * pct / 100))
        chips += tpl.format(delay=i * 100, cy=cy, ty=ty, by=by, bw=bw,
                            c=lang_color(lang, soft=True), label=esc(lang), pct=pct)

    s = t.index('<g class="aura-chip"')
    # end = last </g> of the third chip (before closing of root <g id=...>)
    root_close = t.rindex("</g>")  # root group close
    e = t.rindex("</g>", s, root_close) + 4
    out = t[:s] + chips + t[e:]
    # normalize trailing newline before root close
    out = re.sub(r"\n+</g>\s*</svg>", "\n  </g>\n</svg>", out)
    open(p, "w", encoding="utf-8", newline="\n").write(out)
    print("stack ->", [(k, p) for (k, _), p in zip(top, pcts)])


# ---------------------------------------------------------------- stats
def regen_stats(repos, total_contribs):
    p = os.path.join(D, "sec-stats-gold.svg")
    t = open(p, encoding="utf-8").read()
    stars = sum(r["stargazers_count"] for r in repos)
    nrepos = len([r for r in repos if not r["fork"]])
    followers = jget("https://api.github.com/users/%s" % USER)["followers"]
    vals = [stars, total_contribs, nrepos, followers]
    mx = max(vals) or 1

    xs = [56, 260, 464, 668]
    for x, v in zip(xs, vals):
        t = re.sub(r'(<text x="%d" y="166"[^>]*>)[^<]*(</text>)' % x,
                   r"\g<1>%d\g<2>" % v, t, count=1)
        bw = max(11, round(136 * v / mx))
        t = re.sub(r'(<rect class="aura-bar" x="%d" y="186" width=")\d+(")' % x,
                   r"\g<1>%d\g<2>" % bw, t, count=1)
    open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("stats -> stars=%d contribs=%d repos=%d followers=%d" % tuple(vals))


# ---------------------------------------------------------------- heatmap
LEVEL = {0: ("#e0a53a", 0.07), 1: ("#ffcd57", 0.34), 2: ("#ffcd57", 0.55),
         3: ("#ffcd57", 0.78), 4: ("#ffcd57", 1.00)}


def regen_heatmap(cells, total):
    p = os.path.join(D, "sec-heatmap-gold.svg")
    t = open(p, encoding="utf-8").read()

    def fix_cell(m):
        x, y, inner = float(m.group(1)), float(m.group(2)), m.group(3)
        col = int(round((x - 51.5) / 14))
        row = int(round((y - 105.5) / 14))
        date = (datetime.date(2025, 10, 19) + datetime.timedelta(days=col * 7 + row)).isoformat()
        lvl = cells.get(date, 0)
        fill, v = LEVEL[lvl]
        peak = round(min(1.0, v * 1.4), 2)
        inner = re.sub(r'fill="[^"]*"', 'fill="%s"' % fill, inner, count=1)
        inner = re.sub(r'values="0;[\d.]+;[\d.]+"',
                       'values="0;%.2f;%.2f"' % (peak, v), inner, count=1)
        return '<g transform="translate(%s,%s)">%s</g>' % (m.group(1), m.group(2), inner)

    t = re.sub(r'<g transform="translate\(([\d.]+),([\d.]+)\)">((?:(?!</g>).)*?)</g>',
               fix_cell, t, flags=re.S)
    t = re.sub(r">\d+ contributions in the last year<",
               ">%d contributions in the last year<" % total, t, count=1)
    open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("heatmap -> %d cells, %d contributions" % (len(cells), total))


def main():
    repos = jget("https://api.github.com/users/%s/repos?per_page=100" % USER)
    langs_by_repo = load_langs(repos)
    cells, total = contributions()
    regen_projects(repos, langs_by_repo)
    regen_stack(repos, langs_by_repo)
    regen_stats(repos, total)
    regen_heatmap(cells, total)
    # validate XML
    import xml.dom.minidom
    for f in ("sec-projects-gold.svg", "sec-stack-gold.svg",
              "sec-stats-gold.svg", "sec-heatmap-gold.svg"):
        xml.dom.minidom.parse(os.path.join(D, f))
    print("XML valid: 4/4")


if __name__ == "__main__":
    sys.exit(main())
