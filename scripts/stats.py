import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from html import escape

LOGIN = os.environ.get("GH_LOGIN", "Farhan-SE")
TOKEN = os.environ["GH_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets"

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    login
    createdAt
    pullRequests { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes { languages(first: 10) { edges { size node { name color } } } }
    }
  }
}
"""

THEMES = {
    "dark": {
        "bg": "#0d1117", "panel": "#161b22", "border": "#30363d",
        "text": "#e6edf3", "muted": "#8b949e", "accent": "#2b7fff",
        "ramp": ["#1c2230", "#0f3a7a", "#1858c4", "#2b7fff", "#7cb4ff"],
    },
    "light": {
        "bg": "#ffffff", "panel": "#f6f8fa", "border": "#d0d7de",
        "text": "#1f2328", "muted": "#59636e", "accent": "#1f6fe5",
        "ramp": ["#ebeff4", "#bcd6ff", "#7cb0ff", "#2b7fff", "#0b4fc2"],
    },
}


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(json.dumps(data["errors"]))
    return data["data"]["user"]


def summarize(user):
    cc = user["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        longest = max(longest, run)
    current = 0
    for i, d in enumerate(reversed(days)):
        if d["contributionCount"]:
            current += 1
        elif i == 0:
            continue
        else:
            break
    langs = Counter()
    colors = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]
            colors[e["node"]["name"]] = e["node"]["color"] or "#8b949e"
    total = sum(langs.values()) or 1
    top = [(n, s / total, colors[n]) for n, s in langs.most_common(5)]
    return {
        "name": user["name"] or user["login"],
        "login": user["login"],
        "total": cc["contributionCalendar"]["totalContributions"],
        "prs": user["pullRequests"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "active": sum(1 for d in days if d["contributionCount"]),
        "longest": longest,
        "current": current,
        "weeks": cc["contributionCalendar"]["weeks"],
        "langs": top,
    }


def level(count, peak):
    if count == 0:
        return 0
    q = count / peak
    return 1 if q <= 0.15 else 2 if q <= 0.35 else 3 if q <= 0.65 else 4


def render(s, t):
    W, H = 840, 410
    pad = 28
    peak = max((d["contributionCount"] for w in s["weeks"] for d in w["contributionDays"]), default=1) or 1
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")

    tiles = [
        ("Contributions", f"{s['total']:,}", "last 12 months"),
        ("Pull requests", f"{s['prs']:,}", "all time"),
        ("Active days", f"{s['active']}", "last 12 months"),
        ("Longest streak", f"{s['longest']}d", f"current {s['current']}d"),
        ("Repositories", f"{s['repos']}", "owned"),
    ]
    gap = 12
    tw = (W - 2 * pad - gap * (len(tiles) - 1)) / len(tiles)
    tile_svg = []
    for i, (label, value, sub) in enumerate(tiles):
        x = pad + i * (tw + gap)
        tile_svg.append(
            f'<g class="tile" style="animation-delay:{0.08 * i:.2f}s">'
            f'<rect x="{x:.1f}" y="78" width="{tw:.1f}" height="84" rx="10" fill="{t["panel"]}" stroke="{t["border"]}"/>'
            f'<text x="{x + 14:.1f}" y="100" class="label">{label}</text>'
            f'<text x="{x + 14:.1f}" y="134" class="value">{value}</text>'
            f'<text x="{x + 14:.1f}" y="152" class="sub">{sub}</text>'
            f"</g>"
        )

    cell, cgap = 11, 3
    grid_w = len(s["weeks"]) * (cell + cgap) - cgap
    gx = (W - grid_w) / 2
    gy = 230
    cells = []
    month_labels = []
    last_month = None
    for wi, w in enumerate(s["weeks"]):
        first = w["contributionDays"][0]["date"]
        m = first[5:7]
        if m != last_month and w["contributionDays"][0]["date"][8:10] <= "07":
            month_labels.append(
                f'<text x="{gx + wi * (cell + cgap):.1f}" y="{gy - 8}" class="sub">'
                f'{datetime.strptime(first, "%Y-%m-%d").strftime("%b")}</text>'
            )
            last_month = m
        for d in w["contributionDays"]:
            wd = datetime.strptime(d["date"], "%Y-%m-%d").isoweekday() % 7
            lv = level(d["contributionCount"], peak)
            cells.append(
                f'<rect class="c" style="animation-delay:{0.35 + wi * 0.018:.3f}s" '
                f'x="{gx + wi * (cell + cgap):.1f}" y="{gy + wd * (cell + cgap)}" width="{cell}" height="{cell}" rx="2.5" '
                f'fill="{t["ramp"][lv]}"><title>{d["date"]}: {d["contributionCount"]}</title></rect>'
            )

    ly = gy + 7 * (cell + cgap) + 26
    bar_w = W - 2 * pad
    bx = pad
    bars, legend = [], []
    lx = pad
    for i, (name, share, color) in enumerate(s["langs"]):
        w = bar_w * share
        bars.append(
            f'<rect class="bar" style="animation-delay:{1.3 + 0.1 * i:.2f}s" x="{bx:.1f}" y="{ly}" width="{max(w, 2):.1f}" height="8" fill="{color}"/>'
        )
        bx += w
        legend.append(
            f'<circle cx="{lx + 4}" cy="{ly + 26}" r="4" fill="{color}"/>'
            f'<text x="{lx + 13}" y="{ly + 30}" class="sub">{escape(name)} {share * 100:.1f}%</text>'
        )
        lx += 13 + len(f"{name} {share * 100:.1f}%") * 6.3 + 26

    ramp_legend = "".join(
        f'<rect x="{W - pad - 30 - (5 - i) * 14}" y="{gy - 44}" width="10" height="10" rx="2" fill="{c}"/>'
        for i, c in enumerate(t["ramp"])
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {escape(s['login'])}">
<title>GitHub stats for {escape(s['login'])}</title>
<style>
text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:{t["text"]}}}
.h{{font-size:20px;font-weight:700}}
.handle{{font-size:13px;fill:{t["muted"]}}}
.label{{font-size:12px;fill:{t["muted"]};font-weight:600}}
.value{{font-size:26px;font-weight:700}}
.sub{{font-size:11px;fill:{t["muted"]}}}
.accent{{fill:{t["accent"]}}}
.tile{{opacity:0;animation:up .5s cubic-bezier(.22,1,.36,1) forwards}}
.c{{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .35s cubic-bezier(.22,1,.36,1) forwards}}
.bar{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow .6s cubic-bezier(.22,1,.36,1) forwards}}
.pulse{{transform-box:fill-box;transform-origin:center;animation:pulse 2.4s ease-in-out infinite}}
@keyframes up{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{from{{opacity:0;transform:scale(.3)}}to{{opacity:1;transform:none}}}}
@keyframes grow{{to{{transform:scaleX(1)}}}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.35}}}}
@media (prefers-reduced-motion:reduce){{.tile,.c,.bar,.pulse{{animation:none;opacity:1;transform:none}}}}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{t["bg"]}" stroke="{t["border"]}"/>
<circle class="pulse accent" cx="{pad + 5}" cy="40" r="5"/>
<text x="{pad + 18}" y="47" class="h">{escape(s['name'])}</text>
<text x="{pad + 18 + len(s['name']) * 11 + 10}" y="47" class="handle">@{escape(s['login'])}</text>
<text x="{W - pad}" y="47" class="sub" text-anchor="end">updated {updated}</text>
{''.join(tile_svg)}
{''.join(month_labels)}
<text x="{pad}" y="{gy - 35}" class="label">Contribution activity</text>
<text x="{W - pad - 30 - 5 * 14 - 6}" y="{gy - 35}" class="sub" text-anchor="end">less</text>
{ramp_legend}
<text x="{W - pad}" y="{gy - 35}" class="sub" text-anchor="end">more</text>
{''.join(cells)}
<rect x="{pad}" y="{ly}" width="{bar_w}" height="8" rx="4" fill="{t["panel"]}"/>
<clipPath id="lb"><rect x="{pad}" y="{ly}" width="{bar_w}" height="8" rx="4"/></clipPath>
<g clip-path="url(#lb)">{''.join(bars)}</g>
{''.join(legend)}
</svg>
"""


def main():
    s = summarize(fetch())
    os.makedirs(OUT, exist_ok=True)
    for name, theme in THEMES.items():
        with open(os.path.join(OUT, f"stats-{name}.svg"), "w", encoding="utf-8") as f:
            f.write(render(s, theme))
    print(json.dumps({k: v for k, v in s.items() if k != "weeks"}))


if __name__ == "__main__":
    main()
