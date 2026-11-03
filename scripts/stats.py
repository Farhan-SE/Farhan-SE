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
      nodes { languages(first: 10) { edges { size node { name color } } } }
    }
  }
}
"""

THEMES = {
    "dark": {
        "bg": "#0d1117", "panel": "#161b22", "border": "#30363d",
        "text": "#e6edf3", "muted": "#8b949e",
    },
    "light": {
        "bg": "#ffffff", "panel": "#f6f8fa", "border": "#d0d7de",
        "text": "#1f2328", "muted": "#59636e",
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
        "longest": longest,
        "current": current,
        "langs": top,
    }


def render(s, t):
    W, H = 840, 244
    pad = 32
    now = datetime.now(timezone.utc)
    updated = f"{now.day} {now:%b %Y}"
    unit = lambda n, one, many: one if n == 1 else many

    stats = [
        ("CONTRIBUTIONS", f"{s['total']:,}", "", "in the last 12 months"),
        ("PULL REQUESTS", f"{s['prs']:,}", "", "opened, all time"),
        ("LONGEST STREAK", f"{s['longest']}", unit(s["longest"], " day", " days"), f"current streak {s['current']} {unit(s['current'], 'day', 'days')}"),
    ]
    cw = (W - 2 * pad) / len(stats)
    cols = []
    for i, (label, value, suffix, sub) in enumerate(stats):
        x = pad + i * cw + (24 if i else 0)
        divider = f'<line x1="{pad + i * cw:.1f}" y1="92" x2="{pad + i * cw:.1f}" y2="160" stroke="{t["border"]}"/>' if i else ""
        tail = f'<tspan class="unit">{suffix}</tspan>' if suffix else ""
        cols.append(
            f'{divider}<g class="col" style="animation-delay:{0.08 * i:.2f}s">'
            f'<text x="{x:.1f}" y="104" class="label">{label}</text>'
            f'<text x="{x:.1f}" y="142" class="value">{value}{tail}</text>'
            f'<text x="{x:.1f}" y="162" class="sub">{sub}</text>'
            f"</g>"
        )

    ly = 196
    bar_w = W - 2 * pad
    seg_gap = 3
    usable = bar_w - seg_gap * (len(s["langs"]) - 1)
    bx = pad
    bars, legend = [], []
    lx = pad
    for i, (name, share, color) in enumerate(s["langs"]):
        w = max(usable * share, 4)
        bars.append(
            f'<rect class="bar" style="animation-delay:{0.3 + 0.08 * i:.2f}s" x="{bx:.1f}" y="{ly}" width="{w:.1f}" height="6" rx="3" fill="{color}"/>'
        )
        bx += w + seg_gap
        pct = f"{share * 100:.1f}%"
        legend.append(
            f'<rect x="{lx}" y="{ly + 20}" width="8" height="8" rx="2" fill="{color}"/>'
            f'<text x="{lx + 14}" y="{ly + 28}" class="lang">{escape(name)} <tspan class="pct">{pct}</tspan></text>'
        )
        lx += 14 + len(f"{name} {pct}") * 6.6 + 24

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {escape(s['login'])}">
<title>GitHub stats for {escape(s['login'])}</title>
<style>
text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:{t["text"]};font-variant-numeric:tabular-nums}}
.h{{font-size:18px;font-weight:650}}
.handle{{font-size:13px;font-weight:400;fill:{t["muted"]}}}
.label{{font-size:10.5px;fill:{t["muted"]};font-weight:600;letter-spacing:.09em}}
.value{{font-size:34px;font-weight:700;letter-spacing:-.02em}}
.unit{{font-size:15px;font-weight:600;fill:{t["muted"]};letter-spacing:0}}
.sub{{font-size:12px;fill:{t["muted"]}}}
.lang{{font-size:12px;fill:{t["text"]}}}
.pct{{fill:{t["muted"]}}}
.col{{opacity:0;animation:up .55s cubic-bezier(.22,1,.36,1) forwards}}
.bar{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow .7s cubic-bezier(.22,1,.36,1) forwards}}
@keyframes up{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
@keyframes grow{{to{{transform:scaleX(1)}}}}
@media (prefers-reduced-motion:reduce){{.col,.bar{{animation:none;opacity:1;transform:none}}}}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>
<text x="{pad}" y="46" class="h">{escape(s['name'])}<tspan class="handle" dx="10">@{escape(s['login'])}</tspan></text>
<text x="{W - pad}" y="46" class="sub" text-anchor="end">Updated {updated}</text>
<line x1="{pad}" y1="70" x2="{W - pad}" y2="70" stroke="{t["border"]}"/>
{''.join(cols)}
{''.join(bars)}
{''.join(legend)}
</svg>
"""


def main():
    s = summarize(fetch())
    os.makedirs(OUT, exist_ok=True)
    for name, theme in THEMES.items():
        with open(os.path.join(OUT, f"stats-{name}.svg"), "w", encoding="utf-8") as f:
            f.write(render(s, theme))
    print(json.dumps(s))


if __name__ == "__main__":
    main()
