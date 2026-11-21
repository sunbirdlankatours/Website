#!/usr/bin/env python3
"""Builds the Sunbird Lanka Tours website from the files in content/ and static/.

    python build.py

The finished site is written to the _site folder. GitHub runs this automatically
every time you save a change (see .github/workflows/publish.yml), so you normally
never need to run it yourself. Needs only Python 3.8+ (no extra packages).
"""
import datetime
import hashlib
import html
import json
import os
import re
import shutil
from urllib.parse import quote

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, "content")
STATIC = os.path.join(ROOT, "static")
OUT = os.path.join(ROOT, "_site")

esc = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731


# =============================================================== reading files
def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [l.rstrip("\n") for l in f]


def unquote_val(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def read_settings(path):
    out = {}
    for l in read_lines(path):
        if not l.strip() or l.lstrip().startswith("#") or ":" not in l:
            continue
        k, v = l.split(":", 1)
        out[k.strip()] = unquote_val(v)
    return out


def read_rows(path):
    """Pipe-separated rows:  a | b | c"""
    rows = []
    for l in read_lines(path):
        if not l.strip() or l.lstrip().startswith("#"):
            continue
        rows.append([c.strip() for c in l.split("|")])
    return rows


def split_row(s):
    return [c.strip() for c in s.split("|")]


def read_menu(path):
    items = []
    for l in read_lines(path):
        if not l.strip() or l.lstrip().startswith("#") or "|" not in l:
            continue
        label, link, note = ([c.strip() for c in l.split("|", 2)] + [""])[:3]
        item = {"label": label, "link": link, "note": note, "children": []}
        if l.startswith(" ") and items:
            items[-1]["children"].append(item)
        else:
            items.append(item)
    return items


def read_md(path):
    """Markdown file with a --- front matter --- block (simple YAML: key: value and lists)."""
    text = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    meta, body = {}, text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        head, body = text[4:end], text[end + 4:].lstrip("\n")
        key = None
        for l in head.split("\n"):
            if not l.strip() or l.lstrip().startswith("#"):
                continue
            m = re.match(r"^\s+-\s+(.*)$", l)
            if m and key:
                if not isinstance(meta.get(key), list):
                    meta[key] = []
                meta[key].append(unquote_val(m.group(1)))
                continue
            if ":" in l:
                k, v = l.split(":", 1)
                key = k.strip()
                v = unquote_val(v)
                meta[key] = int(v) if re.fullmatch(r"-?\d+", v) else (v if v != "" else [])
    return meta, body


# =============================================================== markdown
RX_IMG = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)')
RX_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)(\{([^}]*)\})?")


def inline(t):
    t = html.escape(t, quote=False)

    def img(m):
        alt, src, title = m.group(1), m.group(2), m.group(3)
        return '<img src="%s" alt="%s" loading="lazy">' % (src, esc(alt or title or ""))

    def link(m):
        text, url, cls = m.group(1), m.group(2), m.group(4)
        attrs = ""
        if cls:
            classes = " ".join(c.lstrip(".") for c in cls.split() if c.startswith("."))
            attrs = ' class="%s"' % classes
        if re.match(r"^https?://", url) and "sunbirdtours.lk" not in url:
            attrs += ' target="_blank" rel="noopener"'
        return '<a href="%s"%s>%s</a>' % (url, attrs, text)

    t = RX_IMG.sub(img, t)
    t = RX_LINK.sub(link, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?![\*\w])", r"<em>\1</em>", t)
    return t


def gallery(par):
    figs = []
    for m in RX_IMG.finditer(par):
        alt, src, title = m.group(1), m.group(2), m.group(3)
        cap = "<figcaption>%s</figcaption>" % esc(title) if title else ""
        figs.append('<figure><img src="%s" alt="%s" loading="lazy">%s</figure>' % (src, esc(alt or title or ""), cap))
    cls = "gallery n%d" % min(len(figs), 4) + (" captions" if "figcaption" in "".join(figs) else "")
    return '<div class="%s">%s</div>' % (cls, "".join(figs))


def markdown(text, shortcode=None):
    """Small Markdown converter: headings, paragraphs, lists, images, links,
    bold/italic, ::: section blocks, ~ kicker lines and {{shortcodes}}."""
    out, par, lst = [], [], None
    sections = 0

    def flush_par():
        if par:
            p = " ".join(par).strip()
            if p and re.fullmatch(r"(\s*" + RX_IMG.pattern + r"\s*)+", p):
                out.append(gallery(p))
            elif p:
                out.append("<p>%s</p>" % inline(p))
            par.clear()

    def flush_list():
        nonlocal lst
        if lst:
            tag, items = lst
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(i) for i in items), tag))
            lst = None

    for raw in text.split("\n"):
        line = raw.rstrip()
        s = line.strip()
        if not s:
            flush_par(); flush_list(); continue
        m = re.match(r"^:::\s*(.*)$", s)
        if m:
            flush_par(); flush_list()
            if m.group(1):
                sections += 1
                out.append('<section class="band %s"><div class="wrap">' % esc(m.group(1)))
            else:
                out.append("</div></section>")
            continue
        m = re.fullmatch(r"\{\{\s*([\w:-]+)\s*\}\}", s)
        if m and shortcode:
            flush_par(); flush_list()
            out.append(shortcode(m.group(1)))
            continue
        if s.startswith("<") and re.match(r"^</?[a-zA-Z]", s):
            flush_par(); flush_list(); out.append(s); continue
        m = re.match(r"^(#{1,6})\s+(.*?)(?:\s*\{#([\w-]+)\})?$", s)
        if m:
            flush_par(); flush_list()
            n = len(m.group(1))
            hid = ' id="%s"' % m.group(3) if m.group(3) else ""
            out.append("<h%d%s>%s</h%d>" % (n, hid, inline(m.group(2)), n))
            continue
        if s.startswith("~ "):
            flush_par(); flush_list()
            out.append('<p class="kicker">%s</p>' % inline(s[2:]))
            continue
        if s in ("---", "***"):
            flush_par(); flush_list(); out.append("<hr>"); continue
        m = re.match(r"^([-*]|\d+\.)\s+(.*)$", s)
        if m and not s.startswith("**"):
            flush_par()
            tag = "ol" if m.group(1)[0].isdigit() else "ul"
            if lst and lst[0] != tag:
                flush_list()
            if not lst:
                lst = (tag, [])
            lst[1].append(m.group(2))
            continue
        if s.startswith("> "):
            flush_par(); flush_list(); out.append("<blockquote><p>%s</p></blockquote>" % inline(s[2:])); continue
        flush_list()
        par.append(s)
    flush_par(); flush_list()
    body = "\n".join(out)
    return body, sections


def wrap_band(body, sections):
    return body if sections else '<section class="band"><div class="wrap">%s</div></section>' % body


REGION_ORDER = ["Cultural Triangle", "Hill country", "South & west coast", "Wildlife parks", "North & east"]
# "More …" heading over the other places in the same region, on a destination page
MORE_IN = {"Cultural Triangle": "More in the Cultural Triangle", "Hill country": "More in the hill country",
           "South & west coast": "More along the coast", "Wildlife parks": "More wildlife parks",
           "North & east": "More in the north and east"}


def tour_days(t):
    """A tour's length in days, from its duration ("10 days", "1 day"); 0 when it has none."""
    m = re.search(r"\d+", str(t.get("duration", "")))
    return int(m.group(0)) if m else 0


def month_runs(code, ch="G"):
    """The months marked `ch` in a 12-letter season code as short ranges: "Jan – Mar", "Dec – Apr", "All year"."""
    if not code or ch not in code:
        return ""
    if code == ch * 12:
        return "All year"
    runs = []
    for i in range(12):
        if code[i] == ch and code[i - 1] != ch:
            j = i
            while code[(j + 1) % 12] == ch:
                j = (j + 1) % 12
            runs.append(MONTHS[i][:3] if i == j else "%s – %s" % (MONTHS[i][:3], MONTHS[j][:3]))
    return ", ".join(runs)


def tour_themes(t):
    """The category file names a tour lists under "themes:" (a list, or one comma-separated line)."""
    v = t.get("themes") or []
    return [s.strip() for s in (v.split(",") if isinstance(v, str) else v) if s.strip()]


def tour_stops(t):
    """The places a tour stops at, in order and once each, from its day headings
    ("### Day 2 · Colombo → Anuradhapura · The sacred city"). Day tours have none."""
    stops = []
    for h in re.findall(r"^###\s+(.*)$", t.get("body", ""), flags=re.M):
        parts = h.split(" · ")
        if len(parts) > 2:
            for p in parts[1].split("→"):
                p = p.strip()
                if p and p not in stops:
                    stops.append(p)
    return stops


# =============================================================== weather (monsoon dial, month question)
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def parse_months(text, where=""):
    """'Dec-Apr, Jul' -> {11, 0, 1, 2, 3, 6}: month numbers, January = 0. A range may run past December."""
    short = [m[:3].lower() for m in MONTHS]
    out = set()
    for part in str(text or "").replace("–", "-").split(","):
        part = part.strip()
        if not part:
            continue
        ends = [e.strip()[:3].lower() for e in part.split("-", 1)]
        if any(e not in short for e in ends):
            print("Warning: %s has a month I can't read: %s" % (where, part))
            continue
        m, last = short.index(ends[0]), short.index(ends[-1])
        out.add(m)
        while m != last:
            m = (m + 1) % 12
            out.add(m)
    return out


def season_code(best, mixed, where=""):
    """12 letters, January first: G = best time, M = mixed weather, R = rainy / off-season."""
    b, m = parse_months(best, where), parse_months(mixed, where)
    return "".join("G" if i in b else "M" if i in m else "R" for i in range(12))


# =============================================================== site data
class Site:
    def __init__(self):
        self.s = read_settings(os.path.join(CONTENT, "settings.txt"))
        self.menu = read_menu(os.path.join(CONTENT, "menu.txt"))
        self.tours = self.load_dir("tours")
        self.places = self.load_dir("destinations")
        self.posts = sorted(self.load_dir("posts"), key=lambda p: p["date"], reverse=True)
        self.pages = self.load_dir("pages")
        self.testimonials = read_rows(os.path.join(CONTENT, "testimonials.txt"))
        self.partners = read_rows(os.path.join(CONTENT, "partners.txt"))
        self.vehicles = read_rows(os.path.join(CONTENT, "vehicles.txt"))
        self.redirects = [[c.strip() for c in l.split("->")] for l in read_lines(os.path.join(CONTENT, "redirects.txt"))
                          if "->" in l and not l.lstrip().startswith("#")]
        for t in self.tours:
            t.setdefault("url", "/%s/" % t["slug"])
        self.tours.sort(key=lambda t: (t.get("order", 99), t["title"]))
        # tour categories (content/categories); a tour joins one by listing its file name under "themes:"
        self.cats = sorted(self.load_dir("categories"), key=lambda c: (c.get("order", 99), c.get("name", "")))
        for c in self.cats:
            c.setdefault("url", "/tours/%s/" % c["slug"])
        self.cat_by_slug = {c["slug"]: c for c in self.cats}
        for t in self.tours:
            for s in tour_themes(t):
                if s not in self.cat_by_slug:
                    print("Warning: %s lists a theme with no category file: %s" % (t["slug"], s))
        # weather: regions and "what's on" from the page that lists weather_regions (best-time-to-visit.md);
        # each tour's best and mixed months from its own file
        self.weather = None
        # the district map of Sri Lanka (content/data/sri-lanka-map.json: made from geoBoundaries / OpenStreetMap data)
        mp = os.path.join(CONTENT, "data", "sri-lanka-map.json")
        self.map = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else None
        wp = next((p for p in self.pages if p.get("weather_regions")), None)
        if wp:
            regions, district_region = [], {}
            for n, row in enumerate(wp["weather_regions"]):
                name, places, best, mixed, dists = (split_row(row) + [""] * 5)[:5]
                regions.append({"name": name, "places": places, "code": season_code(best, mixed, "weather region " + name)})
                for dist in (x.strip() for x in dists.split(",")):
                    if dist:
                        district_region[dist] = n
            events = (list(wp.get("weather_events") or []) + [""] * 12)[:12]
            self.weather = {"url": wp["url"], "regions": regions, "events": events, "district_region": district_region}
            if self.map:
                names = {d["name"] for d in self.map["districts"]}
                for dist in sorted(set(district_region) - names):
                    print("Warning: best-time-to-visit.md names a district the map doesn't have: %s" % dist)
                for dist in sorted(names - set(district_region)):
                    print("Warning: district %s isn't in any weather region (best-time-to-visit.md)" % dist)
        for t in self.tours:
            if t.get("best_months"):
                t["season"] = season_code(t.get("best_months"), t.get("mixed_months"), t["slug"])
        self.places.sort(key=lambda p: (p.get("order", 99), p.get("name", "")))
        # destinations: one page each at /destinations/<file name>/. "map" is "latitude, longitude" (the pin on the
        # island), "district" picks the weather (its weather region in best-time-to-visit.md), "region" groups them
        for p in self.places:
            p.setdefault("url", "/destinations/%s/" % p["slug"])
            ll = [float(x) for x in str(p.get("map", "")).split(",") if x.strip()]
            p["ll"] = ll if len(ll) == 2 else None
            r = self.weather["district_region"].get(p.get("district")) if self.weather else None
            p["season"] = self.weather["regions"][r]["code"] if r is not None else None
            if self.weather and p.get("district") and r is None:
                print("Warning: %s names a district with no weather region: %s" % (p["slug"], p["district"]))
            # the name as itineraries write it ("Wilpattu", not "Wilpattu National Park")
            p["short"] = re.sub(r"\s+National Park$", "", p.get("name", ""))
        self.ver = self.asset_version()
        self.year = datetime.date.today().year

    def load_dir(self, name):
        items = []
        d = os.path.join(CONTENT, name)
        for f in sorted(os.listdir(d)):
            if f.endswith(".md"):
                meta, body = read_md(os.path.join(d, f))
                meta["slug"] = f[:-3]
                meta["body"] = body
                items.append(meta)
        return items

    def asset_version(self):
        h = hashlib.md5()
        for f in ("css/site.css", "js/site.js"):
            p = os.path.join(STATIC, f)
            if os.path.exists(p):
                h.update(open(p, "rb").read())
        return h.hexdigest()[:8]


# =============================================================== components
# Runs first thing on every page. When the visitor has just clicked a category on the home page's tour
# wheel, that page stored the photo and word it ended on; this puts the same full-screen picture up straight
# away, so the new page opens on it and site.js can then fade it away (no jump between pages).
ARRIVE_SCRIPT = (
    '<script>(function(){try{var t=JSON.parse(sessionStorage.getItem("sbTrip")||"null");'
    'sessionStorage.removeItem("sbTrip");if(!t||Date.now()-t.t>8000)return;'
    'document.documentElement.classList.add("arriving");'
    'var o=document.createElement("div");o.className="pt pt-in"+(t.kind?" pt-"+t.kind:"");o.setAttribute("aria-hidden","true");'
    'if(t.img){var i=new Image();i.alt="";i.src=t.img;o.appendChild(i)}'
    'var s=document.createElement("div");s.className="pt-shade";o.appendChild(s);'
    'var p=document.createElement("p");p.className="pt-word";'
    'var a=document.createElement("small");a.textContent=t.lead||"";'
    'var e=document.createElement("em");e.textContent=t.word||"";'
    'p.appendChild(a);p.appendChild(e);o.appendChild(p);document.body.appendChild(o)}catch(x){}})();</script>')


ICON = {
    "pin": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Z"/><circle cx="12" cy="10" r="2.6"/></svg>',
    "clock": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    "phone": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>',
    "mail": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
    "whatsapp": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20l1.3-4A8 8 0 1 1 8 18.7Z"/><path d="M9 9.5c.3 2.3 2.2 4.2 4.5 4.5l1-1.3 2 .8v1.3a1 1 0 0 1-1 1A7 7 0 0 1 8.2 9a1 1 0 0 1 1-1h1.3l.8 2Z"/></svg>',
    "calendar": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>',
    "compass": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5Z"/></svg>',
    "users": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/></svg>',
    "arrow": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "sun": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    "chevron-up": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 15 6-6 6 6"/></svg>',
    "chevron-down": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>',
    "facebook": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v7h4v-7h3l1-4h-4V8Z"/></svg>',
    "instagram": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".8"/></svg>',
    "tripadvisor": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="7" cy="13" r="3.5"/><circle cx="17" cy="13" r="3.5"/><path d="M3 8.5h18M7 13h.01M17 13h.01M12 7l-2 3M12 7l2 3"/></svg>',
}


class Builder:
    def __init__(self, site):
        self.site = site
        self.s = site.s
        self.pages_written = []

    # ---------------------------------------------------------- helpers
    def tour_type(self, t):
        return "Day tour" if t.get("category") == "wildlife" else "Bespoke tour"

    def tours_in(self, cat_slug):
        """Tours in a category; tours that list it first under themes: (their main category) come first."""
        tours = [t for t in self.site.tours if cat_slug in tour_themes(t)]
        return sorted(tours, key=lambda t: tour_themes(t).index(cat_slug))

    def category_index(self, skip=None, kicker="", title="", text="", links="", hid=None):
        """Tour categories as an editorial index: numbered serif names in a list, with one large photo beside
        it that changes to the category you point at (site.js). On phones each row shows a small photo instead.
        Used at the top of /tours/ and as 'Other tour categories' on each category page."""
        cats = [c for c in self.site.cats if c["slug"] != skip]
        if not cats:
            return ""
        rows, photos = [], []
        for i, c in enumerate(cats):
            n = len(self.tours_in(c["slug"]))
            focus = ' style="object-position:%s"' % esc(c["focus"]) if c.get("focus") else ""
            rows.append(
                '<li><a class="ci-row{on}" href="{url}" data-i="{i}" data-line="{line}">'
                '<span class="ci-num">{num:02d}</span><img class="ci-thumb" src="{img}" alt="" loading="lazy"{focus}>'
                '<span class="ci-name">{name}</span><span class="ci-line">{line}</span>'
                '<span class="ci-meta">{n} tour{s}{arrow}</span></a></li>'.format(
                    on=" on" if i == 0 else "", url=c["url"], i=i, line=esc(c.get("tagline")), num=i + 1,
                    img=esc(c.get("image")), focus=focus, name=esc(c.get("name")), n=n, s="" if n == 1 else "s",
                    arrow=ICON["arrow"]))
            photos.append('<img src="%s" alt="" loading="lazy" decoding="async"%s%s>'
                          % (esc(c.get("image")), ' class="on"' if i == 0 else "", focus))
        return (
            '<div class="cat-index"><div class="ci-side">'
            '{kicker}<h2 class="ci-title"{hid}>{title}</h2>{text}'
            '<ol class="ci-list">{rows}</ol>'
            # phones: a thin progress line and "01 / 07" under the swipeable cards (site.js keeps it up to date)
            '<div class="ci-progress" aria-hidden="true"><span class="ci-bar"><i style="width:{first}%"></i></span>'
            '<span class="ci-count">01 / {total:02d}</span></div>{links}</div>'
            '<figure class="ci-photo" aria-hidden="true"><div class="ci-frame">{photos}</div>'
            '<figcaption class="ci-cap">{cap}</figcaption></figure></div>'
        ).format(kicker='<p class="ci-kicker">%s</p>' % esc(kicker) if kicker else "",
                 hid=' id="%s"' % hid if hid else "", title=esc(title),
                 text='<p class="ci-text">%s</p>' % esc(text) if text else "", rows="".join(rows),
                 links='<p class="ci-links">%s</p>' % links if links else "", photos="".join(photos),
                 cap=esc(cats[0].get("tagline")), first=round(100 / len(cats), 2), total=len(cats))

    def card_tour(self, t):
        """A tour as a photo tile: its length and main category, its name and its route sit on the photo
        (site.css .tile). Pointing at it, the photo slowly zooms and the route slides up. data-season
        (12 letters, January first) lets the month bar on category pages sort and tag the tiles."""
        stops = tour_stops(t)
        if stops:
            route = " · ".join(stops[:5]) + (" …" if len(stops) > 5 else "")
        else:   # day tours: their tagline instead
            route = (t.get("tagline") or "").replace(" • ", " · ")
        themes = tour_themes(t)
        cat = self.site.cat_by_slug.get(themes[0]) if themes else None
        kick = " · ".join(x for x in ("Day trip" if tour_days(t) == 1 else t.get("duration", ""),
                                      cat.get("name") if cat else "") if x)
        return (
            '<article class="card tour-card tile"{season}><a href="{url}" class="card-link">'
            '<div class="card-img"><img src="{img}" alt="" loading="lazy" decoding="async"></div>'
            '<div class="tile-body"><p class="tile-kick">{kick}</p><h3 class="tile-t">{title}</h3>'
            '{route}<span class="tile-go">View tour{arrow}</span></div></a></article>'
        ).format(url=t["url"], img=esc(t.get("image")), kick=esc(kick), title=esc(t["title"]), arrow=ICON["arrow"],
                 route=('<div class="tile-more"><p class="tile-route">%s<span>%s</span></p></div>' % (ICON["pin"], esc(route))
                        if route else ""),
                 season=' data-season="%s"' % t["season"] if t.get("season") else "")

    def tour_grid(self, which):
        tours = self.site.tours
        if which in ("bespoke", "wildlife"):
            tours = [t for t in tours if t.get("category") == which]
        elif which in self.site.cat_by_slug:
            tours = self.tours_in(which)
        elif which == "featured":
            # home page: the first tour is a wide feature tile, and when the tiles would leave a gap at the end,
            # one more tile leads to all the tours
            slugs = self.current.get("featured_tours") or []
            by = {t["slug"]: t for t in tours}
            tours = [by[s] for s in slugs if s in by]
            n = len(self.site.tours)
            more = ('<a class="tile-all" href="/tours/"><span class="tile-all-n">%d</span>'
                    '<span class="tile-all-t">See all %d tours</span><span class="tile-all-s">Every one private and tailor-made</span>'
                    '<span class="tile-all-go" aria-hidden="true">%s</span></a>' % (n, n, ICON["arrow"])
                    if len(tours) % 2 == 0 else "")
            return '<div class="grid tiles feature">%s%s</div>' % ("".join(self.card_tour(t) for t in tours), more)
        return '<div class="grid cards3 tiles"%s>%s</div>' % (' id="tours-%s"' % which if which in ("bespoke", "wildlife") else "",
                                                              "".join(self.card_tour(t) for t in tours))

    def tour_finder(self):
        """{{tour-finder}}: the whole of /tours/ in one place. A sentence with four blanks ("We're ___, travelling in
        ___ for ___, and we'd love ___.") is filled in one quick question at a time, and every tour sits in one
        numbered list under it. Each answer re-sorts the list (site.js): the tours that fit rise to the top with
        ticks saying why; the rest drop under "Possible with a few changes" (every tour can be changed). A big
        photo beside the list shows the tour you point at, and a small month strip on each row shows its best
        months. "Plan this trip" carries the sentence to the contact form. Without JavaScript the list keeps the
        usual tour order. The trip words are the categories' "word" (as on the home page wheel)."""
        tours = self.site.tours
        words_of = lambda t: [self.site.cat_by_slug[s].get("word") for s in tour_themes(t) if s in self.site.cat_by_slug]
        cap = lambda w: w[:1].upper() + w[1:]
        data = {"words": [c.get("word") for c in self.site.cats if c.get("word")], "months": MONTHS,
                "tours": [[t["title"], t["url"], t.get("image", ""), tour_days(t), t.get("duration", ""), words_of(t),
                           t.get("season", ""), t.get("summary", "")] for t in tours],
                # each trip word's photo (its category's), for the pills and behind the full-screen sentence
                "photos": {c["word"]: [c.get("image", ""), c.get("focus", "")] for c in self.site.cats if c.get("word")}}
        rows, day_anchor = [], False
        for i, t in enumerate(tours):
            rid = ""
            if tour_days(t) == 1 and not day_anchor:   # the old "Day tours" link (/tours/#wildlife) lands here
                rid, day_anchor = ' id="wildlife"', True
            rows.append(
                '<li class="tl-row" data-i="{i}"{rid}><a class="tl-link" href="{url}">'
                '<span class="tl-n">{n:02d}</span><img class="tl-thumb" src="{img}" alt="" loading="lazy">'
                '<span class="tl-main"><span class="tl-t">{title}</span>'
                '<span class="tl-why"><span>{dur}</span>{words}</span></span>'
                '<span class="tl-ms" aria-hidden="true">{strip}</span>'
                '<span class="tl-go" aria-hidden="true">{arrow}</span></a></li>'.format(
                    i=i, rid=rid, url=t["url"], n=i + 1, img=esc(t.get("image")), title=esc(t["title"]),
                    dur=esc("Day trip" if tour_days(t) == 1 else t.get("duration", "")),
                    words="".join("<span>%s</span>" % esc(cap(w)) for w in words_of(t)),
                    strip="".join('<i class="%s"></i>' % c for c in t.get("season", "")), arrow=ICON["arrow"]))
        # the blanks are spans acting as buttons (not <button>s), so a long answer wraps with the sentence
        blank = '<span class="tf-b empty" role="button" tabindex="0" data-q="{q}" aria-label="{label}">{ph}</span>'
        # testing switch in settings.txt: the full-screen sentence every time, starting empty
        test = str(self.s.get("tour_finder_test", "")).strip().lower() in ("yes", "true", "on", "1")
        first = tours[0]
        return (
            '<div class="tf" data-tf{fresh}>'
            # the first time on this page in a visit, the sentence fills the screen by itself, over blurred trip
            # photos, before any tour shows (site.js lifts it away on "Show my tours"). This runs before the page
            # is drawn, so the list never flashes up first. The old "Day tours" link (#wildlife) goes straight to
            # the list; if site.js doesn't arrive, the normal page comes back after a few seconds.
            # With "tour_finder_test: yes" in settings.txt it shows every time, with no answers remembered.
            '<script>(function(){{try{{if(location.hash==="#wildlife"||({seen}sessionStorage.getItem("sbTf")))return;'
            'var h=document.documentElement;h.classList.add("tf-intro","tf-dark");'
            '"scrollRestoration" in history&&(history.scrollRestoration="manual");'
            'setTimeout(function(){{if(!window.sbTfReady)h.classList.remove("tf-intro","tf-dark")}},6000)}}catch(e){{}}}})();</script>'
            '<div class="tf-bg" aria-hidden="true"></div>'
            '<div class="tf-top" id="find">'
            '<p class="ci-kicker">Find your tour</p>'
            '<p class="tf-say" aria-live="polite"><span class="tf-me">We’re</span> {b0}, travelling in {b1} for {b2}, '
            'and <span class="tf-we">we’d</span> love {b3}.</p>'
            '<div class="tf-ask"><div class="tf-ask-head"><p class="tf-q">Who’s coming?</p><p class="tf-step">1 of 4</p></div>'
            '<div class="tf-chips" role="group" aria-label="Answers"></div>'
            '<p class="tf-tools"><button type="button" class="tf-skip">Skip this one</button>'
            '<button type="button" class="tf-reset" hidden>Start again</button>'
            '<button type="button" class="btn gold tf-show">Show all {n} tours{arrow}</button>'
            '<a class="btn gold tf-go" href="/contact-us/#plan">Plan this trip{arrow}</a></p></div>'
            '</div>'
            '<div class="tl" id="bespoke">'
            '<aside class="tl-side" aria-hidden="true"><figure class="tl-photo"><div class="tl-frame">'
            '<img class="on" src="{img0}" alt=""><img src="{img0}" alt=""></div>'
            '<figcaption><span class="tl-cap-t">{t0}</span><span class="tl-cap-s">{s0}</span></figcaption></figure></aside>'
            '<div class="tl-col">'
            '<div class="tl-head"><p class="tf-count" aria-live="polite">All {n} tours</p>'
            '<p class="mstrip-key tl-key"><span class="G">Best months</span><span class="M">Mixed</span><span class="R">Rainy</span></p></div>'
            '<ol class="tl-list">{rows}<li class="tl-sep" hidden>Possible with a few changes</li></ol>'
            '<div class="tl-end"><p class="tl-end-say">Not quite it? Every trip we plan is made for the people going.</p>'
            '<a class="btn gold tf-go" href="/contact-us/#plan">Send us your sentence{arrow}</a></div>'
            '<p class="tl-cats">Read about each kind of trip: {cats}</p>'
            '</div></div>'
            '<script type="application/json" class="tf-data">{data}</script></div>'
        ).format(fresh=' data-fresh' if test else "", seen="false&&" if test else "",
                 b0=blank.format(q=0, label="Who’s coming", ph="who?"),
                 b1=blank.format(q=1, label="When you’re travelling", ph="when?"),
                 b2=blank.format(q=2, label="How long you have", ph="how long?"),
                 b3=blank.format(q=3, label="What you’d love", ph="what?"),
                 arrow=ICON["arrow"], img0=esc(first.get("image")), t0=esc(first["title"]), s0=esc(first.get("summary", "")),
                 n=len(tours), rows="".join(rows),
                 cats=" · ".join('<a href="%s">%s</a>' % (c["url"], esc(c["name"])) for c in self.site.cats),
                 data=json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))

    def place_cards(self, which):
        places = self.site.places
        if which == "featured":
            slugs = self.current.get("featured_places") or []
            by = {p["slug"]: p for p in places}
            places = [by[s] for s in slugs if s in by]
            return '<div class="grid cards4">%s</div>' % "".join(self.place_card(p) for p in places)
        # all places on /destinations/: the island with a pin for each on one side (big screens), and the places
        # grouped by region beside it. Pointing at a place lights up its pin (site.js).
        groups = []
        for region in self.regions():
            ps = [p for p in places if p.get("region") == region]
            codes = {p["season"] for p in ps}
            best = month_runs(codes.pop()) if len(codes) == 1 and None not in codes else ""
            groups.append(
                '<section class="di-region" id="{id}"><header class="di-head"><h3 class="di-name">{name}</h3>'
                '<p class="di-meta">{n} place{s}{best}</p></header><div class="di-cards">{cards}</div></section>'.format(
                    id=re.sub(r"[^a-z]+", "-", region.lower()).strip("-"), name=esc(region), n=len(ps),
                    s="" if len(ps) == 1 else "s", best=('<span>%sBest %s</span>' % (ICON["sun"], best)) if best else "",
                    cards="".join(self.place_card(p) for p in ps)))
        return ('<div class="dest-index"><div class="di-map">%s</div><div class="di-regions">%s</div></div>'
                % (self.isle(), "".join(groups)))

    def regions(self):
        """Destination regions (content/destinations: "region"), roughly the way a first trip travels round the
        island: the ancient cities, the hills, the coast, the parks, then the north and east. A new region
        name goes at the end."""
        out = []
        for p in self.site.places:
            if p.get("region") and p["region"] not in out:
                out.append(p["region"])
        return sorted(out, key=lambda r: REGION_ORDER.index(r) if r in REGION_ORDER else len(REGION_ORDER))

    def place_card(self, p):
        return ('<a class="place-card" href="{url}" data-slug="{slug}"><img src="{img}" alt="" loading="lazy">'
                '<span class="pc-text"><strong>{name}</strong><small>{tag}</small></span></a>').format(
                    url=p["url"], slug=p["slug"], img=esc(p.get("image")), name=esc(p.get("name")), tag=esc(p.get("tagline", "")))

    def pin_xy(self, ll):
        """Latitude/longitude -> position on the island map, as percentages of its width and height."""
        mp = self.site.map
        pr = mp["projection"]
        return ((ll[1] - pr["lon0"]) * pr["cos"] * pr["scale"] / mp["width"] * 100,
                (pr["lat1"] - ll[0]) * pr["scale"] / mp["height"] * 100)

    def isle(self, here=None):
        """The island of Sri Lanka (an image written by build_places) with a pin for every destination.
        On a destination page (here=that place) only its own pin is named; the others are small dots."""
        if not self.site.map:
            return ""
        pins = []
        for p in self.site.places:
            if not p["ll"]:
                continue
            x, y = self.pin_xy(p["ll"])
            where = 'style="left:%.2f%%;top:%.2f%%"' % (x, y)
            if here is None:
                pins.append('<a class="isle-pin" href="%s" %s data-slug="%s"><span>%s</span></a>' % (p["url"], where, p["slug"], esc(p["name"])))
            elif p is here:
                pins.append('<span class="isle-pin here" %s><span>%s</span></span>' % (where, esc(p["name"])))
            else:
                pins.append('<span class="isle-dot" %s></span>' % where)
        return ('<figure class="isle%s"%s><img src="/img/sri-lanka.svg" alt="" width="%d" height="%d">%s</figure>'
                % ("" if here is None else " small", ' aria-hidden="true"' if here is not None else ' aria-label="Map of Sri Lanka"',
                   self.site.map["width"], self.site.map["height"], "".join(pins)))

    def place_match(self, p, text):
        return re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(p["short"]), text, flags=re.I) is not None

    def place_tours(self, p):
        """Tours that stop at place p: a day heading names it ("Day 4 · Kandy → Ella · …"); for tours without
        day headings (the day tours), the name is in the title. Most days there first."""
        found = []
        for t in self.site.tours:
            heads = [h.split(" · ") for h in re.findall(r"^###\s+(.*)$", t["body"], flags=re.M)]
            places = [h[1] for h in heads if len(h) > 2]
            days = sum(1 for w in places if self.place_match(p, w))
            if days or (not places and self.place_match(p, t["title"])):
                found.append((-days, t.get("order", 99), t))
        return [t for _, _, t in sorted(found, key=lambda f: f[:2])]

    def month_strip(self, code):
        names = {"G": "best", "M": "mixed", "R": "rainy"}
        return ('<div class="mstrip" role="img" aria-label="Weather through the year: best %s">%s</div>'
                '<p class="mstrip-key"><span class="G">Best</span><span class="M">Mixed</span><span class="R">Rainy</span></p>') % (
            esc(month_runs(code)), "".join('<span class="%s" title="%s: %s">%s</span>' % (c, MONTHS[i], names[c], MONTHS[i][0])
                                         for i, c in enumerate(code)))

    def card_post(self, p):
        return (
            '<article class="card post-card"><a class="card-link" href="{url}"><div class="card-img"><img src="{img}" alt="" loading="lazy"></div>'
            '<div class="card-body"><p class="card-type">{date}{cat}</p><h3>{title}</h3><p>{summary}</p><span class="more">Read more {arrow}</span></div></a></article>'
        ).format(url=esc(p["url"]), img=esc(p.get("image")), date=self.nice_date(p["date"]),
                 cat=(" · " + esc(p["category"])) if p.get("category") else "", title=esc(p["title"]),
                 summary=esc(p.get("summary", "")), arrow=ICON["arrow"])

    def post_cards(self, which):
        posts = self.site.posts[:3] if which == "latest" else self.site.posts
        return '<div class="grid cards3">%s</div>' % "".join(self.card_post(p) for p in posts)

    @staticmethod
    def nice_date(d):
        try:
            return datetime.date.fromisoformat(d).strftime("%d %B %Y").lstrip("0")
        except ValueError:
            return d

    def slider(self):
        slides = []
        for n, row in enumerate(self.current.get("slides") or []):
            c = split_row(row) + ["", "", "", "", ""]
            h = "h1" if n == 0 else "h2"
            slides.append(
                '<div class="slide{act}" style="background-image:url(\'{img}\')"><div class="wrap">'
                '<p class="kicker">{k}</p><{h}>{t}</{h}><p class="slide-btns"><a class="btn gold" href="{link}">{btn}</a>'
                '<a class="btn ghost" href="/contact-us/#plan">Plan My Trip</a></p></div></div>'.format(
                    act=" active" if n == 0 else "", img=esc(c[0]), k=esc(c[1]), h=h, t=esc(c[2]), btn=esc(c[3]), link=esc(c[4])))
        dots = "".join('<button type="button" aria-label="Slide %d"%s></button>' % (i + 1, ' class="active"' if i == 0 else "")
                       for i in range(len(slides)))
        return '<section class="slider" aria-label="Highlights">%s<div class="dots">%s</div></section>' % ("".join(slides), dots)

    def home_hero(self):
        """The big first screen on the home page (settings live in content/pages/home.md)."""
        p = self.current

        def parts(key, n):
            return (split_row(p.get(key) or "") + [""] * n)[:n]

        first, accent, last = parts("hero_title", 3)
        btn_text, btn_link = parts("hero_button", 2)
        title = "".join(('<span>%s</span>' % esc(first) if first else "",
                         ' <em>%s</em>' % esc(accent) if accent else "",
                         ' <span>%s</span>' % esc(last) if last else ""))
        facts = "".join('<li><strong>%s</strong>%s</li>' % tuple(esc(x) for x in (split_row(r) + [""])[:2])
                        for r in (p.get("hero_facts") or []))
        place = p.get("hero_place")
        foot = ""
        if facts or place:
            foot = '<div class="hh-foot">%s%s</div>' % (
                '<ul class="hh-facts">%s</ul>' % facts if facts else "",
                '<p class="hh-place">%s%s</p>' % (ICON["pin"], esc(place)) if place else "")
        wa = self.s.get("whatsapp")
        return (
            '<section class="hero-home" aria-label="Welcome">'
            '<picture>{wide_src}<img class="hh-photo" src="{img}" alt="{alt}" style="--focus:{focus};--focus-wide:{focus_wide}" fetchpriority="high" decoding="async"></picture>'
            '<div class="hh-shade"></div>'
            '<div class="wrap hh-inner">'
            '<p class="hh-kicker">{kicker}</p>'
            '<h1 class="hh-title">{title}</h1>'
            '<p class="hh-text">{text}</p>'
            '<p class="hh-btns"><a class="btn gold" href="{link}">{btn}{arrow}</a>{wa}</p>'
            '{foot}'
            '</div>'
            '</section>'
        ).format(
            img=esc(p.get("hero_photo_phone") or p.get("image")),
            wide_src=('<source media="(min-width: 761px)" srcset="%s">' % esc(p.get("image"))) if p.get("hero_photo_phone") else "",
            alt=esc(p.get("hero_photo_alt")), focus=esc(p.get("hero_focus") or "50% 50%"),
            focus_wide=esc(p.get("hero_focus_wide") or p.get("hero_focus") or "50% 50%"),
            kicker=esc(p.get("hero_kicker")), title=title,
            text=esc(p.get("hero_text")), link=esc(btn_link or "/contact-us/#plan"), btn=esc(btn_text or "Plan your trip"),
            arrow=ICON["arrow"],
            wa=('<a class="btn ghost" href="https://wa.me/%s" target="_blank" rel="noopener">%sWhatsApp us</a>'
                % (esc(wa), ICON["whatsapp"])) if wa else "",
            foot=foot,
        )

    # ---------------------------------------------------------- weather: month question, monsoon dial, month guide
    # (the facts live in content/pages/best-time-to-visit.md and in each tour's best_months / mixed_months)
    def weather_data(self):
        """The weather facts as JSON for site.js: month names, regions, what's on, and each tour's months."""
        w = self.site.weather
        data = {"months": MONTHS, "guide": w["url"], "events": w["events"],
                "regions": [[r["name"], r["places"], r["code"]] for r in w["regions"]],
                "tours": [[t["title"], t["url"], t["season"]] for t in self.site.tours if t.get("season")]}
        return '<script type="application/json" id="sb-weather">%s</script>' % (
            json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))

    @staticmethod
    def month_buttons(cls, pressed=False):
        return "".join('<button type="button" class="%s" data-m="%d" aria-label="%s"%s>%s</button>'
                       % (cls, i, m, ' aria-pressed="false"' if pressed else "", m[:3]) for i, m in enumerate(MONTHS))

    def tours_for(self, m, limit):
        """Tours at their best in month m (multi-day tours first, as in the tour order)."""
        return [t for t in self.site.tours if t.get("season") and t["season"][m] == "G"][:limit]

    def sunny_line(self, m):
        sunny = [r["name"] for r in self.site.weather["regions"] if r["code"][m] == "G"]
        return "Sunniest: " + ", ".join(sunny) if sunny else "Showers almost everywhere"

    def month_bar(self):
        """Slim 'When are you travelling?' bar above a category's tours: a month puts the tours that suit it first."""
        if not self.site.weather:
            return ""
        return (
            '<div class="month-bar" data-grid="#cat-tours">'
            '<div class="mb-head"><p class="mb-ask">When are you travelling?</p>'
            '<a class="mb-guide" href="{url}">Month-by-month guide{arrow}</a></div>'
            '<div class="mb-months" role="group" aria-label="Travel month">'
            '<button type="button" class="mb-m" data-m="-1" aria-pressed="true">Any month</button>{months}</div>'
            '<p class="mb-note" aria-live="polite">Pick your month and we will put the tours that suit it first.</p></div>'
        ).format(url=self.site.weather["url"], arrow=ICON["arrow"], months=self.month_buttons("mb-m", pressed=True))

    def month_ask(self, c):
        """Full-screen 'When are you travelling?' on the category's own photo. site.js opens it only when the visitor
        has just clicked through from another page of this site and hasn't picked a month yet - never for someone
        arriving straight from Google (search engines penalise pages that open with a pop-up)."""
        if not self.site.weather:
            return ""
        focus = ' style="object-position:%s"' % esc(c["focus"]) if c.get("focus") else ""
        return (
            '<div class="month-ask" role="dialog" aria-modal="true" aria-labelledby="ma-title" hidden>'
            '<img class="ma-photo" src="{img}" alt=""{focus}><div class="ma-shade"></div>'
            '<div class="ma-box"><p class="ma-kicker">{name}</p>'
            '<h2 class="ma-title" id="ma-title">When are you <em>travelling?</em></h2>'
            '<p class="ma-text">Sri Lanka has two monsoons, so one side of the island is always sunny. '
            'Pick your month and we will put the tours that suit it first.</p>'
            '<div class="ma-months">{months}</div>'
            '<p class="ma-foot"><button type="button" class="ma-skip">Not sure yet</button></p></div></div>'
        ).format(img=esc(c.get("image")), focus=focus, name=esc(c.get("name")), months=self.month_buttons("ma-m"))

    def dial_info(self, m):
        """The changing part of the panel beside the monsoon map for month m (site.js redraws it the same way)."""
        w, labels = self.site.weather, {"G": "Sunny", "M": "Mixed", "R": "Rainy"}
        regions = "".join('<li><span class="dr-name">{n}<small>{p}</small></span><span class="dr-st {c}">{l}</span></li>'.format(
            n=esc(r["name"]), p=esc(r["places"]), c=r["code"][m], l=labels[r["code"][m]]) for r in w["regions"])
        tours = " · ".join('<a href="%s">%s</a>' % (t["url"], esc(t["title"])) for t in self.tours_for(m, 6))
        guide = "" if self.current.get("url") == w["url"] else w["url"]   # on the guide page itself, just jump down
        return (
            '<ul class="dial-regions">{regions}</ul>'
            '<p class="dial-k">What’s on</p><p class="dial-on">{on}</p>'
            '<p class="dial-k">Tours at their best</p><p class="dial-tours">{tours}</p>'
            '<a class="dial-more" href="{guide}#{id}">Read the {name} guide{arrow}</a>'
        ).format(regions=regions, on=esc(w["events"][m]), tours=tours or "Ask us: we will plan around the weather.",
                 guide=guide, id=MONTHS[m].lower(), name=MONTHS[m], arrow=ICON["arrow"])

    def island_map(self, m):
        """Sri Lanka's 25 districts as an SVG, each coloured by its weather region's month m (G sunny, M mixed,
        R rainy), with the province borders drawn over them and rain falling only over the rainy districts."""
        mp, w = self.site.map, self.site.weather
        if not mp:
            return ""
        paths, rainy = [], []
        for dist in mp["districts"]:
            r = w["district_region"].get(dist["name"])
            s = w["regions"][r]["code"][m] if r is not None else "M"
            pid = "dm-" + re.sub(r"[^a-z]+", "-", dist["name"].lower()).strip("-")
            if s == "R":
                rainy.append(pid)
            paths.append('<path class="dm-d {s}" id="{id}" data-r="{r}" data-name="{n}" data-prov="{p}" d="{d}">'
                         '<title>{n} District, {p} Province</title></path>'.format(
                             s=s, id=pid, r="" if r is None else r, n=esc(dist["name"]), p=esc(dist["province"]), d=dist["d"]))
        # rain: raindrops - small rings that open and fade at scattered spots, like drops landing on water. They
        # cover the whole island but only show inside the rainy districts (the clip). Positions and start times
        # are spread out evenly with the golden ratio, so they look random but are the same on every build.
        W, H, GOLD = mp["width"], mp["height"], 0.6180339887
        drops = []
        for k in range(70):
            x = (k * GOLD % 1) * (W - 30) + 15
            y = ((k + 0.5) / 70) * (H - 30) + 15
            drops.append('<circle class="dm-drop" cx="%.0f" cy="%.0f" r="%d" style="animation-delay:%.2fs"/>'
                         % (x, y, 20 + (k * 7) % 11, (k * GOLD * 2.8) % 2.8))
        return (
            '<svg class="dial-map" viewBox="0 0 {w} {h}" role="img" aria-label="Map of Sri Lanka’s 25 districts and 9 '
            'provinces, coloured by the weather in the chosen month">'
            '<defs><clipPath id="dm-rain-clip">{uses}</clipPath></defs>'
            '<g class="dm-districts">{paths}</g>'
            '<g class="dm-rain" clip-path="url(#dm-rain-clip)">{drops}</g>'
            '<path class="dm-prov" d="{prov}"/></svg>'
        ).format(w=W, h=int(H), uses="".join('<use href="#%s"/>' % u for u in rainy), paths="".join(paths),
                 drops="".join(drops), prov=mp["province_lines"])

    def monsoon_dial(self):
        """{{monsoon-dial}}: the map of Sri Lanka inside a ring of the twelve months. A small sun travels round the
        ring to the chosen month, the districts turn sunny, mixed or rainy, and the panel beside it shows what's on
        and the tours at their best. Opens on January; site.js turns it to the visitor's month (or this month)."""
        if not self.site.weather:
            return ""
        months = "".join(
            '<button type="button" class="dial-m{on}" style="--i:{i}" data-m="{i}" aria-label="{n}" aria-pressed="{p}">{s}</button>'.format(
                on=" on" if i == 0 else "", i=i, n=n, p="true" if i == 0 else "false", s=n[:3]) for i, n in enumerate(MONTHS))
        credit = self.site.map.get("credit") if self.site.map else ""
        return (
            '<div class="dial-wrap" data-dial>'
            '<div class="dial" role="group" aria-label="Choose a month"><span class="dial-ring" aria-hidden="true"></span>'
            '<span class="dial-sun" aria-hidden="true"><i></i></span>{months}{map}<p class="dial-tip" hidden></p></div>'
            '<div class="dial-info" aria-live="polite"><p class="dial-name">{name}</p><p class="dial-sum">{sum}</p>'
            '<p class="dial-legend"><span class="G">Sunny</span><span class="M">Mixed</span><span class="R">Rainy</span></p>'
            '<div class="dial-detail">{info}</div></div></div>'
            '{credit}{data}'
        ).format(months=months, map=self.island_map(0), name=MONTHS[0], sum=esc(self.sunny_line(0)), info=self.dial_info(0),
                 credit='<p class="map-credit">%s</p>' % esc(credit) if credit else "", data=self.weather_data())

    def island_dial(self):
        """{{island-dial}} on the home page: the monsoon map in its own section. Scrolling with a mouse or
        trackpad over the map turns the months (site.js); on phones you tap them.
        Its words are in content/pages/home.md (dial_kicker, dial_title, dial_text, dial_text_phone)."""
        if not self.site.weather:
            return ""
        p = self.current
        return (
            '<section class="island-dial" aria-labelledby="id-title"><div class="id-stick"><div class="wrap">'
            '<div class="id-head"><p class="ci-kicker">{kicker}</p><h2 id="id-title">{title}</h2>'
            '<p class="id-text"><span class="id-desk">{text}</span><span class="id-phone">{phone}</span></p></div>'
            '{dial}</div></div></section>'
        ).format(kicker=esc(p.get("dial_kicker") or "When to go"), title=esc(p.get("dial_title") or "There is always a sunny side"),
                 text=esc(p.get("dial_text") or ""), phone=esc(p.get("dial_text_phone") or p.get("dial_text") or ""),
                 dial=self.monsoon_dial())

    def ella_ride(self):
        """{{ella-ride}} on the home page: a wide train window onto the hill country line. The sky, the mountains,
        the tea hills and the trackside drift past on their own, each at its own speed (site.css .er-*), and the
        invitation to ride the whole way, scroll by scroll, on /ella-train/ (static/ella-train/) sits on the view
        itself. The pictures are the ride's own; site.js loads them once the section is near and lets them move
        only while it is on screen.
        Its words are in content/pages/home.md (ride_kicker, ride_title, ride_text, ride_time)."""
        p = self.current
        base = 0.7   # how fast the trackside passes, in window heights a second; the rest move slower, as in the ride
        layers = (   # name, picture, width, height, top and height (in window heights), speed (share of the trackside's)
            ("sky", "sky.webp", 2400, 1018, -0.06, 1.12, 0.012),
            ("far", "far.webp", 2400, 1018, -0.07, 1.08, 0.06),
            ("mid", "mid-home.webp", 1933, 820, 0.27, 0.96, 0.24),
            # the trackside starts above the window, so its trees and poles run off the top edge instead of ending in view
            ("near", "near-blur.webp", 1600, 679, -0.1, 1.14, 1),
        )
        view = []
        for name, src, w, h, top, hgt, k in layers:
            # four copies end to end, every other one mirrored so the joins match; sliding the strip half its
            # length brings it back to where it started
            secs = 2 * hgt * w / h / (base * k)
            imgs = "".join('<img data-src="/ella-train/img/%s" alt="" width="%d" height="%d"%s>'
                           % (src, w, h, ' class="flip"' if i % 2 else "") for i in range(4))
            view.append('<div class="er-l er-%s" style="top:%.1f%%;height:%.1f%%"><div class="er-s" style="--d:%.1fs">%s</div></div>'
                        % (name, top * 100, hgt * 100, secs, imgs))
        stations = (("Kandy", .02), ("Hatton", .19), ("Nanu Oya", .38), ("Pattipola", .53), ("Haputale", .79), ("Ella", .965))
        route = "".join('<li style="left:%.1f%%">%s</li>' % ((at - .02) / (.965 - .02) * 100, esc(n)) for n, at in stations)
        return (
            '<section class="band ella-ride" aria-labelledby="er-title"><div class="wrap">'
            '<div class="er-win"><div class="er-scene" aria-hidden="true">{view}</div><span class="er-glass"></span>'
            '<div class="er-text"><p class="kicker">{kicker}</p><h2 id="er-title">{title}</h2><p>{text}</p>'
            '<p class="er-btns"><a class="btn gold" href="/ella-train/">Ride the train</a>'
            '<a class="btn ghost" href="/destinations/ella/">Explore Ella</a></p></div>'
            '<span class="er-chip">{time}</span></div>'
            '<div class="er-route" aria-hidden="true"><span class="er-track"><i class="er-loco"></i></span><ol>{route}</ol></div>'
            '</div></section>'
        ).format(kicker=esc(p.get("ride_kicker") or "The hill country line"),
                 title=inline(p.get("ride_title") or "Take the train to *Ella*"),
                 text=esc(p.get("ride_text") or ""), time=esc(p.get("ride_time") or "Kandy → Ella"),
                 view="".join(view), route=route)

    def month_guide(self):
        """{{month-guide}}: the year planner. The weather regions are rows and the twelve months columns side by side,
        each square gold (best), sand (mixed) or blue (rainy), so the good seasons read as bands of colour. Under it,
        the chosen month in detail: where to go, what's on and the tours at their best. All twelve months are in
        the page (what search engines read, and what shows without JavaScript); site.js shows one at a time and
        slides a frame to the chosen column. Each month keeps its own address (#january ...)."""
        w = self.site.weather
        if not w:
            return ""
        labels = {"G": "Best", "M": "Mixed", "R": "Rainy"}
        head = "".join('<button type="button" class="yp-m" data-m="{i}" aria-label="{n}" aria-pressed="false">{a}<span>{b}</span></button>'.format(
            i=i, n=n, a=n[0], b=n[1:3]) for i, n in enumerate(MONTHS))
        rows = "".join(
            '<p class="yp-region"><strong>{name}</strong><small>{places}</small></p>{cells}'.format(
                name=esc(r["name"]), places=esc(r["places"]), cells="".join(
                    '<span class="yp-c {c}" data-m="{i}" title="{name} in {n}: {l}"></span>'.format(
                        c=c, i=i, name=esc(r["name"]), n=MONTHS[i], l=labels[c].lower()) for i, c in enumerate(r["code"])))
            for r in w["regions"])
        months = []
        for m, name in enumerate(MONTHS):
            order = sorted(w["regions"], key=lambda r: "GMR".index(r["code"][m]))
            wx = "".join('<li><span class="ypm-dot {c}"></span><span class="ypm-r">{n}</span><span class="ypm-s">{l}</span></li>'.format(
                c=r["code"][m], n=esc(r["name"]), l=labels[r["code"][m]]) for r in order)
            tours = self.tours_for(m, 4)
            tl = "".join(
                '<li><a href="{url}"><img src="{img}" alt="" loading="lazy"><span><strong>{t}</strong><small>{d}</small></span></a></li>'.format(
                    url=t["url"], img=esc(t.get("image")), t=esc(t["title"]), d=esc(t.get("duration", ""))) for t in tours)
            months.append(
                '<article class="yp-month" id="{id}" data-m="{m}">'
                '<header class="ypm-head"><p class="ypm-n">{num:02d} / 12</p><h3>Sri Lanka in {name}</h3></header>'
                '<div class="ypm-cols"><div><p class="ci-kicker">The weather</p><ul class="ypm-wx">{wx}</ul></div>'
                '<div><p class="ci-kicker">What’s on</p><ul class="ypm-on">{on}</ul></div>'
                '<div><p class="ci-kicker">Tours at their best</p>{tours}</div></div></article>'.format(
                    id=name.lower(), m=m, num=m + 1, name=name, wx=wx,
                    on="".join("<li>%s</li>" % esc(e.strip()) for e in w["events"][m].split(" · ") if e.strip()),
                    tours=('<ul class="ypm-tours">%s</ul>' % tl) if tl else
                          '<p class="ypm-none">Ask us: we will plan a trip around the weather.</p>'))
        return (
            '<div class="yp" data-yp>'
            '<div class="yp-grid" role="group" aria-label="The weather in each region, month by month">'
            '<span class="yp-corner" aria-hidden="true"></span>{head}{rows}<span class="yp-frame" aria-hidden="true"></span></div>'
            '<p class="mstrip-key yp-key"><span class="G">Best</span><span class="M">Mixed</span><span class="R">Rainy</span></p>'
            '<div class="yp-detail"><div class="ypm-nav"><button type="button" class="ypm-prev" aria-label="Previous month">{arrow}</button>'
            '<button type="button" class="ypm-next" aria-label="Next month">{arrow}</button></div>'
            '<div class="yp-months">{months}</div></div></div>'
        ).format(head=head, rows=rows, months="".join(months), arrow=ICON["arrow"])

    def categories(self):
        cards = []
        for row in self.current.get("categories") or []:
            img, name, link = (split_row(row) + ["", "", ""])[:3]
            cards.append('<a class="cat-card" href="%s"><img src="%s" alt="" loading="lazy"><span>%s</span></a>' % (esc(link), esc(img), esc(name)))
        return '<div class="grid cats">%s</div>' % "".join(cards)

    def trip_wheel(self):
        """'I want a trip full of ___' with a turning wheel of words (settings in content/pages/home.md)."""
        p = self.current
        rows = [(split_row(r) + [""] * 5)[:5] for r in (p.get("trip_wheel") or [])]
        if not rows:
            return ""
        lead = p.get("wheel_text") or "I want a trip full of"
        photos, words = [], []
        for n, (word, img, line, link, focus) in enumerate(rows):
            # start place on the ring (the script keeps it up to date): 0 = the chosen word, -1/1 its neighbours…
            r = n if n <= len(rows) / 2 else n - len(rows)
            slot = max(-3, min(3, r))
            # only the first photo loads with the page; the script loads the others as the wheel turns
            photos.append('<img %s="%s" alt="" decoding="async"%s%s>' % (
                "src" if n == 0 else "data-src", esc(img), ' class="on" loading="lazy"' if n == 0 else "",
                ' style="object-position:%s"' % esc(focus) if focus else ""))
            words.append('<a class="tw-word%s" href="%s" data-line="%s" style="--k:%d;--s:%s"><span>%s</span></a>' % (
                " on" if n == 0 else "", esc(link), esc(line), slot, "1" if r == 0 else (".78" if abs(r) == 1 else ".62"),
                esc(word)))
        first = rows[0]
        return (
            '<section class="trip-wheel" aria-label="Tour categories">'
            '<div class="tw-photos" aria-hidden="true">{photos}</div><div class="tw-shade"></div>'
            '<div class="wrap tw-inner">'
            '<p class="tw-kicker">{kicker}</p>'
            '<div class="tw-row"><p class="tw-lead">{lead}</p>'
            '<div class="tw-wheel" tabindex="0" aria-label="Choose a kind of trip. Use the arrow keys to turn the wheel.">'
            '<span class="tw-ring" aria-hidden="true"></span><div class="tw-rot">{words}</div></div>'
            '<div class="tw-turn"><button type="button" class="tw-prev" aria-label="Previous">{up}</button>'
            '<small><span class="tw-hint-touch">Swipe to change</span><span class="tw-hint-mouse">Scroll to change</span></small><button type="button" class="tw-next" aria-label="Next">{down}</button></div></div>'
            '<p class="tw-line" aria-live="polite"><span>{line}</span></p>'
            '<p class="tw-btns"><a class="btn gold tw-go" href="{link}"><span>Show me <em>{word}</em></span>{arrow}</a>'
            '<a class="btn ghost tw-mix" href="/tours/#find">Want it all? Mix your own</a></p>'
            '</div></section>'
        ).format(photos="".join(photos), kicker=esc(p.get("wheel_kicker") or "Tour categories"), lead=esc(lead),
                 words="".join(words), up=ICON["chevron-up"], down=ICON["chevron-down"], line=esc(first[2]),
                 link=esc(first[3]), word=esc(first[0]), arrow=ICON["arrow"], all=esc(p.get("wheel_all_link") or "/tours/"))

    # Sri Lanka's coastline, clockwise from Point Pedro: (longitude, latitude) of a few dozen coastal places.
    # Rough on purpose: it is drawn as a soft dotted outline, not used for navigation.
    SL_COAST = [(80.23, 9.83), (80.43, 9.60), (80.55, 9.45), (80.82, 9.27), (80.95, 8.98), (81.23, 8.57),
                (81.43, 8.25), (81.56, 7.93), (81.70, 7.72), (81.82, 7.41), (81.85, 6.87), (81.70, 6.55),
                (81.33, 6.22), (81.12, 6.12), (80.80, 6.02), (80.59, 5.92), (80.22, 6.03), (80.10, 6.14),
                (80.00, 6.42), (79.96, 6.58), (79.85, 6.93), (79.84, 7.21), (79.79, 7.58), (79.73, 8.20),
                (79.87, 8.50), (79.93, 8.85), (80.03, 9.02), (80.11, 9.42), (80.01, 9.62), (79.86, 9.74),
                (80.05, 9.81)]

    def island(self):
        """Dotted outline of Sri Lanka with a route drawn between stops (stops are in content/pages/home.md
        under island_route: "name | longitude | latitude"). The home page script draws the route as you scroll."""
        def xy(lon, lat):  # 1 degree = 100 units; close enough to true shape this near the equator
            return (float(lon) - 79.62) * 100, (9.9 - float(lat)) * 100

        pts = [xy(*p) for p in self.SL_COAST]
        n = len(pts)
        # smooth closed curve through the points (Catmull-Rom turned into Bezier curves)
        d = "M%.1f %.1f" % pts[0]
        for i in range(n):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            d += " C%.1f %.1f %.1f %.1f %.1f %.1f" % (c1 + c2 + p2)
        stops = []
        for row in self.current.get("island_route") or []:
            name, lon, lat = (split_row(row) + ["", "", ""])[:3]
            try:
                stops.append((name, float(lon)) + xy(lon, lat))
            except ValueError:
                continue
        legs, marks = [], []
        for i, (a, b) in enumerate(zip(stops, stops[1:])):
            (ax, ay), (bx, by) = a[2:], b[2:]
            dx, dy = bx - ax, by - ay
            bend = 0.22 * (1 if i % 2 == 0 else -1)  # alternate sides so the line looks hand-drawn
            cx, cy = (ax + bx) / 2 - dy * bend, (ay + by) / 2 + dx * bend
            legs.append('<path class="is-leg" pathLength="1" d="M%.1f %.1f Q%.1f %.1f %.1f %.1f"/>' % (ax, ay, cx, cy, bx, by))
        for name, lon, x, y in stops:
            left = lon < 80.3  # west-coast stops get their name on the sea side
            marks.append('<g class="is-stop" transform="translate(%.1f %.1f)"><circle r="3.4"/><text x="%d" y="2.6"%s>%s</text></g>'
                         % (x, y, -7 if left else 7, ' text-anchor="end"' if left else "", esc(name)))
        label = "Map of Sri Lanka with a route through %s" % ", ".join(s[0] for s in stops)
        return ('<svg class="island" viewBox="-4 -4 244 414" role="img" aria-label="%s"><path class="is-coast" d="%s"/>%s%s</svg>'
                % (esc(label), d, "".join(legs), "".join(marks)))

    # ---------------------------------------------------------- About us: a journey in chapters
    def about_open(self, p):
        """The first screen of the About page (layout "about"): one line that inks in word by word over a slowly
        drifting photo (site.js). Words between *stars* in open_line are set in italics; a | starts a new line."""
        words, k = [], 0
        for part in re.split(r"(\*[^*]+\*)", p.get("open_line") or p["title"]):
            em = part.startswith("*") and part.endswith("*")
            for w in part.strip("*").split():
                if w == "|":
                    words.append("<br>")
                    continue
                words.append('<span class="ab-w%s" style="--i:%d">%s</span>' % (" em" if em else "", k, esc(w)))
                k += 1
        return (
            '<section class="ab-open"><div class="ab-open-bg" aria-hidden="true"><img src="{img}" alt=""></div>'
            '<div class="wrap"><p class="ci-kicker">{kicker}</p><h1 class="ab-say">{words}</h1>{note}</div>'
            '<a class="ab-down" href="#who" aria-label="Read on"><span></span></a></section>'
        ).format(img=esc(p.get("image")), kicker=esc(p.get("open_kicker") or "About us"), words=" ".join(words),
                 note=('<p class="ab-note">%s</p>' % esc(p["open_note"])) if p.get("open_note") else "")

    def about_since(self):
        """{{about-since}}: a huge outline year (front matter "since") that drifts behind the chapter, and the
        numbers from the home page's stats, which count up when they come into view (site.js)."""
        items = []
        for r in self.site.pages_by_url["/"].get("stats") or []:
            val, label = (split_row(r) + [""])[:2]
            m = re.match(r"^(\D*)(\d+)(.*)$", val)
            # "02+" keeps its leading zero while it counts; "1500+" doesn't get one
            pad = len(m.group(2)) if m and m.group(2).startswith("0") else 0
            data = (' data-to="%s" data-pad="%d" data-pre="%s" data-suf="%s"' % (int(m.group(2)), pad, esc(m.group(1)), esc(m.group(3)))
                    if m else "")
            items.append('<li><strong%s>%s</strong><span>%s</span></li>' % (data, esc(val), esc(label)))
        year = self.current.get("since") or ""
        return ('<div class="ab-since">%s<ul class="ab-stats">%s</ul></div>'
                % (('<span class="ab-year" aria-hidden="true">%s</span>' % esc(year)) if year else "", "".join(items)))

    def about_chapters(self, body):
        """Tidy the About chapters: "**Title** — text" list items lose the dash (the title sits on its own line),
        and in "How we plan" the heading and button are gathered beside the list, where they stay in view."""
        body = re.sub(r"(<li><strong>[^<]+</strong>)\s+—\s+", r"\1 ", body)

        def side(m):
            inner = m.group(2)
            lists = re.findall(r"<ul>.*?</ul>", inner, flags=re.S)
            rest = re.sub(r"<ul>.*?</ul>", "", inner, flags=re.S)
            return m.group(1) + '<div class="ab-side">%s</div>%s</div></section>' % (rest.strip(), "".join(lists))
        return re.sub(r'(<section class="[^"]*\bchapter plan"><div class="wrap">)(.*?)</div></section>', side, body, flags=re.S)

    def stats(self):
        rows = self.site.pages_by_url["/"].get("stats") or []
        items = "".join('<div><strong>%s</strong><span>%s</span></div>' % tuple(esc(x) for x in (split_row(r) + [""])[:2])
                        for r in rows)
        return '<section class="stats"><div class="wrap">%s</div></section>' % items

    def events(self):
        cards = []
        for row in self.current.get("events") or []:
            img, title, place = (split_row(row) + ["", "", ""])[:3]
            cards.append('<div class="event" style="background-image:url(\'%s\')"><span><strong>%s</strong>%s %s</span></div>'
                         % (esc(img), esc(title), ICON["pin"], esc(place)))
        return '<div class="grid events">%s</div>' % "".join(cards)

    def testimonials(self):
        cards = []
        for row in self.site.testimonials:
            name, quote_, photo = (row + ["", "", ""])[:3]
            pic = '<img src="%s" alt="" loading="lazy">' % esc(photo) if photo else '<span class="avatar">%s</span>' % esc(name[:1].upper())
            cards.append('<figure class="quote"><blockquote>“%s”</blockquote><figcaption>%s<span><strong>%s</strong>Traveller</span></figcaption></figure>'
                         % (esc(quote_), pic, esc(name)))
        ta = ('<p class="center"><a class="btn outline" href="%s" target="_blank" rel="noopener">Read our reviews on TripAdvisor</a></p>'
              % esc(self.s.get("tripadvisor"))) if self.s.get("tripadvisor") else ""
        return '<div class="quotes">%s</div>%s' % ("".join(cards), ta)

    def partners(self):
        logos = []
        for row in self.site.partners:
            name, logo, link = (row + ["", "", ""])[:3]
            img = '<img src="%s" alt="%s" loading="lazy">' % (esc(logo), esc(name))
            logos.append('<a href="%s" target="_blank" rel="noopener">%s</a>' % (esc(link), img) if link else "<span>%s</span>" % img)
        return '<div class="partners">%s</div>' % "".join(logos)

    def vehicles(self):
        cards = []
        for row in self.site.vehicles:
            name, model, seats, drive, price = (row + ["", "", "", "", ""])[:5]
            cards.append(
                '<div class="vehicle"><h3>{n}</h3><dl><dt>Model</dt><dd>{m}</dd><dt>Seats</dt><dd>{s}</dd><dt>Type</dt><dd>{d}</dd></dl>{p}'
                '<a class="btn gold small" href="/contact-us/#plan">Book now</a></div>'.format(
                    n=esc(name), m=esc(model), s=esc(seats), d=esc(drive), p=('<p class="price">%s</p>' % esc(price)) if price else ""))
        return '<div class="grid vehicles">%s</div>' % "".join(cards)

    def contact_cards(self):
        s = self.s
        return (
            '<div class="grid contact-cards">'
            '<div class="ccard">{pin}<h3>Our address</h3><p>{company}<br>{addr}</p></div>'
            '<div class="ccard">{phone}<h3>Phone & WhatsApp</h3><p><a href="tel:{pl}">{p}</a><br><a href="tel:{pl2}">{p2}</a><br>'
            '<a href="https://wa.me/{wa}" target="_blank" rel="noopener">Chat on WhatsApp</a></p></div>'
            '<div class="ccard">{mail}<h3>Email</h3><p><a href="mailto:{e}">{e}</a><br><a href="mailto:{e2}">{e2}</a></p><p class="muted">Open {hours}</p></div>'
            '</div>'
        ).format(pin=ICON["pin"], phone=ICON["phone"], mail=ICON["mail"], company=esc(s.get("company")), addr=esc(s.get("address")),
                 pl=esc(s.get("phone_link")), p=esc(s.get("phone")), pl2=esc(s.get("phone2_link")), p2=esc(s.get("phone2")),
                 wa=esc(s.get("whatsapp")), e=esc(s.get("email")), e2=esc(s.get("email2")), hours=esc(s.get("hours")))

    def form(self, tour=None):
        opts = ['<option value="">Not sure yet – help me plan</option>']
        for t in self.site.tours:
            sel = " selected" if tour and t["slug"] == tour["slug"] else ""
            opts.append('<option%s>%s</option>' % (sel, esc(t["title"])))
        opts += ["<option>MICE / corporate event</option>", "<option>Vehicle hire</option>", "<option>Accommodation only</option>"]
        subject = "Tour enquiry: %s" % tour["title"] if tour else "Trip plan request"
        return (
            '<form class="plan-form" data-subject="{subject}" novalidate>'
            '<div class="fgrid">'
            '<label>Your name*<input name="name" required autocomplete="name"></label>'
            '<label>Email*<input type="email" name="email" required autocomplete="email"></label>'
            '<label>Phone / WhatsApp<input type="tel" name="phone" autocomplete="tel"></label>'
            '<label>Country<input name="country" autocomplete="country-name"></label>'
            '<label>Arrival date<input type="date" name="arrival_date"></label>'
            '<label>Number of days<input type="number" name="days" min="1" max="60" inputmode="numeric"></label>'
            '<label>Adults<input type="number" name="adults" min="1" max="99" value="2" inputmode="numeric"></label>'
            '<label>Children<input type="number" name="children" min="0" max="99" value="0" inputmode="numeric"></label>'
            '<label class="wide">I’m interested in<select name="tour">{opts}</select></label>'
            '<label class="wide">Tell us about your trip*<textarea name="message" rows="5" required placeholder="Places you’d like to see, travel style, budget, special requests…"></textarea></label>'
            '<input type="checkbox" name="botcheck" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">'
            '</div><p class="form-actions"><button class="btn gold" type="submit">Send my request</button>'
            '<span class="form-note">We reply within 24 hours. Prefer WhatsApp? <a href="https://wa.me/{wa}" target="_blank" rel="noopener">Message us</a></span></p>'
            '<p class="form-status" role="status" aria-live="polite"></p></form>'
        ).format(subject=esc(subject), opts="".join(opts), wa=esc(self.s.get("whatsapp")))

    def shortcode(self, name):
        kind, _, arg = name.partition(":")
        return {
            "slider": lambda: self.slider(),
            "hero": lambda: self.home_hero(),
            "categories": lambda: self.categories(),
            "monsoon-dial": lambda: self.monsoon_dial(),
            "island-dial": lambda: self.island_dial(),
            "ella-ride": lambda: self.ella_ride(),
            "month-guide": lambda: self.month_guide(),
            "trip-wheel": lambda: self.trip_wheel(),
            "island": lambda: self.island(),
            "tours": lambda: self.tour_grid(arg or "all"),
            "tour-finder": lambda: self.tour_finder(),
            "about-since": lambda: self.about_since(),
            "places": lambda: self.place_cards(arg or "all"),
            "posts": lambda: self.post_cards(arg or "all"),
            "stats": lambda: self.stats(),
            "events": lambda: self.events(),
            "testimonials": lambda: self.testimonials(),
            "partners": lambda: self.partners(),
            "vehicles": lambda: self.vehicles(),
            "contact-cards": lambda: self.contact_cards(),
            "form": lambda: self.form(),
        }.get(kind, lambda: "<!-- unknown block %s -->" % esc(name))()

    # ---------------------------------------------------------- layout
    def nav(self):
        items = []
        for it in self.site.menu:
            if it["children"]:
                sub = "".join('<li><a href="%s"><span class="sub-t">%s</span>%s</a></li>' % (
                    esc(c["link"]), esc(c["label"]), '<span class="sub-d">%s</span>' % esc(c["note"]) if c["note"] else "")
                    for c in it["children"])
                items.append('<li class="has-sub"><a href="%s">%s</a><button class="sub-toggle" type="button" aria-label="Open %s menu" aria-expanded="false"></button><ul>%s</ul></li>'
                             % (esc(it["link"]), esc(it["label"]), esc(it["label"]), sub))
            else:
                items.append('<li><a href="%s">%s</a></li>' % (esc(it["link"]), esc(it["label"])))
        return "<ul>%s</ul>" % "".join(items)

    def footer(self):
        s = self.s
        tours = "".join('<li><a href="%s">%s</a></li>' % (t["url"], esc(t["title"])) for t in self.site.tours if t.get("category") == "bespoke")
        social = "".join('<a href="%s" target="_blank" rel="noopener" aria-label="%s">%s</a>' % (esc(s[k]), k.title(), ICON[k])
                         for k in ("facebook", "instagram", "tripadvisor") if s.get(k))
        return (
            '<footer class="site-footer"><div class="wrap fcols">'
            '<div class="fabout"><img src="/img/logo-white.png" alt="{name}" width="190" loading="lazy"><p>{ft}</p><p class="social">{social}</p></div>'
            '<div><h3>Explore</h3><ul><li><a href="/tours/">All tours</a></li><li><a href="/tours/#wildlife">Day tours</a></li><li><a href="/destinations/">Destinations</a></li>'
            + ('<li><a href="%s">Best time to visit</a></li>' % self.site.weather["url"] if self.site.weather else "") +
            '<li><a href="/mice/">MICE</a></li><li><a href="/transport-and-stays/">Vehicle hire & stays</a></li><li><a href="/about-us/">About us</a></li>'
            '<li><a href="/blog/">Blog</a></li><li><a href="/contact-us/">Contact us</a></li><li><a href="/booking-terms-conditions/">Booking terms</a></li>'
            '<li><a href="/cookie-policy/">Cookie policy</a></li></ul></div>'
            '<div><h3>Tours</h3><ul>{tours}</ul></div>'
            '<div><h3>Get in touch</h3><ul class="fcontact"><li>{phone}<a href="tel:{pl}">{p}</a></li><li>{phone}<a href="tel:{pl2}">{p2}</a></li>'
            '<li>{mail}<a href="mailto:{e}">{e}</a></li><li>{mail}<a href="mailto:{e2}">{e2}</a></li><li>{pin}<span>{addr}</span></li></ul></div>'
            '</div><div class="fbottom"><div class="wrap">© {year} {company}. All rights reserved.</div></div></footer>'
        ).format(name=esc(s.get("site_name")), ft=esc(s.get("footer_text")), social=social, tours=tours,
                 phone=ICON["phone"], mail=ICON["mail"], pin=ICON["pin"], pl=esc(s.get("phone_link")), p=esc(s.get("phone")),
                 pl2=esc(s.get("phone2_link")), p2=esc(s.get("phone2")), e=esc(s.get("email")), e2=esc(s.get("email2")),
                 addr=esc(s.get("address")), year=self.site.year, company=esc(s.get("company")))

    def hero(self, title, tagline=None, image=None, crumbs=None, facts=None, focus=None):
        style = ' style="background-image:url(\'%s\')%s"' % (esc(image), ";background-position:%s" % esc(focus) if focus else "") if image else ""
        trail = ""
        if crumbs:
            trail = '<nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a>%s</nav>' % "".join(
                ' <span>›</span> <a href="%s">%s</a>' % (u, esc(t)) if u else ' <span>›</span> <span>%s</span>' % esc(t) for t, u in crumbs)
        return '<section class="page-hero%s"%s><div class="wrap">%s<h1>%s</h1>%s%s</div></section>' % (
            "" if image else " plain", style, '<p class="kicker">%s</p>' % esc(tagline) if tagline else "", esc(title), facts or "", trail)

    def page(self, url, title, body, description="", image=None, layout="page", noindex=False):
        s = self.s
        full_title = title if s.get("site_name", "") in title else "%s – %s" % (title, s.get("site_name"))
        og_img = (s.get("url") + image) if image and image.startswith("/") else (s.get("url") + "/img/logo.png")
        langs = [l.strip() for l in s.get("languages", "en").split(",") if l.strip()]
        gt = s.get("google_tag")
        tawk = s.get("tawk_chat")
        cfg = {"key": s.get("web3forms_key", ""), "email": s.get("email", ""), "whatsapp": s.get("whatsapp", "")}
        doc = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
{noindex}<meta property="og:type" content="website">
<meta property="og:site_name" content="{site}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{ogimg}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.png" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@600;700;800&family=Instrument+Serif:ital@0;1&display=swap">
<link rel="stylesheet" href="/css/site.css?v={ver}">
{gtag}</head>
<body class="layout-{layout}">
{arrive}
<a class="skip" href="#main">Skip to content</a>
<div class="topbar"><div class="wrap">
<span class="tb-item">{pin}{addr}</span><span class="tb-item tb-hours">{clock}{hours}</span>
<span class="tb-right"><span class="gtranslate_wrapper"></span><a class="tb-item" href="https://wa.me/{wa}" target="_blank" rel="noopener">{waicon}{phone}</a></span>
</div></div>
<header class="site-header"><div class="wrap">
<a class="logo" href="/"><img class="logo-dark" src="/img/logo.png" alt="{site}" width="170" height="64"><img class="logo-light" src="/img/logo-white.png" alt="{site}" width="170" height="64"></a>
<nav id="nav" class="nav" aria-label="Main">{nav}<a class="btn gold nav-cta" href="/contact-us/#plan">Plan my trip</a></nav>
<a class="btn gold header-cta" href="/contact-us/#plan">Plan my trip</a>
<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav"><span class="bars"></span><span class="sr">Menu</span></button>
</div></header>
<main id="main">
{body}
</main>
{footer}
<script>window.SB={cfg};</script>
{motion}<script src="/js/site.js?v={ver}" defer></script>
<script>window.gtranslateSettings={{"default_language":"en","languages":{langs},"wrapper_selector":".gtranslate_wrapper","flag_style":"2d"}};</script>
<script src="https://cdn.gtranslate.net/widgets/latest/dropdown.js" defer></script>
{tawk}</body>
</html>
""".format(
            title=esc(full_title), desc=esc(description or s.get("description")), canon=esc(s.get("url", "") + quote(url, safe="/#")),
            noindex='<meta name="robots" content="noindex">\n' if noindex else "", site=esc(s.get("site_name")), ogimg=esc(og_img),
            ver=self.site.ver, layout=layout, pin=ICON["pin"], clock=ICON["clock"], waicon=ICON["whatsapp"],
            addr=esc(s.get("address")), hours=esc(s.get("hours")), wa=esc(s.get("whatsapp")), phone=esc(s.get("phone")),
            nav=self.nav(), body=body, footer=self.footer(), arrive=ARRIVE_SCRIPT,
            # smooth-scrolling library for the home page motion (see site.js)
            motion=('<script src="https://cdn.jsdelivr.net/npm/lenis@1.1.13/dist/lenis.min.js" defer></script>\n'
                    if layout == "home" else ""), cfg=json.dumps(cfg), langs=json.dumps(langs),
            gtag=('<script async src="https://www.googletagmanager.com/gtag/js?id={g}"></script>\n'
                  '<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag("js",new Date());gtag("config","{g}");</script>\n').format(g=esc(gt)) if gt else "",
            tawk=('<script>var Tawk_API=Tawk_API||{{}},Tawk_LoadStart=new Date();(function(){{var s=document.createElement("script");'
                  's.async=true;s.src="https://embed.tawk.to/{t}";s.charset="UTF-8";s.setAttribute("crossorigin","*");document.body.appendChild(s);}})();</script>\n').format(t=esc(tawk)) if tawk else "",
        )
        self.write(url, doc)
        if not noindex:
            self.pages_written.append(url)

    def write(self, url, doc):
        if url.endswith(".html"):
            path = os.path.join(OUT, url.lstrip("/"))
        else:
            path = os.path.join(OUT, *[p for p in url.split("/") if p], "index.html")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)

    # ---------------------------------------------------------- page types
    def build_pages(self):
        self.site.pages_by_url = {p["url"]: p for p in self.site.pages}
        for p in self.site.pages:
            self.current = p
            body, sections = markdown(p["body"], self.shortcode)
            body = wrap_band(body, sections)
            if p.get("layout") == "about":
                body = self.about_open(p) + self.about_chapters(body)
            elif p.get("layout") not in ("home", "plain"):
                body = self.hero(p["title"], p.get("tagline"), p.get("image"), crumbs=[(p["title"], None)]) + body
            self.page(p["url"], p["title"], body, p.get("description"), p.get("image"), p.get("layout", "page"),
                      noindex=bool(p.get("noindex")))

    def day_by_day(self, html_):
        """A tour's "## Itinerary" as its own band: one fold-out row per day, and on wide screens a photo
        beside them that follows the day you are on. Day headings read "Day N · Place · Title"; the place
        can be a route ("Kandy → Ella") or left out ("Day N · Title")."""
        lead, h3, rest = html_.partition("<h3>")
        days = re.findall(r"<h3>(.*?)</h3>(.*?)(?=<h3>|\Z)", h3 + rest, flags=re.S)
        rows, stops, pics, caps = [], [], [], []
        for head, text in days:
            parts = [p.strip() for p in head.split(" · ")]
            label, title = parts[0], parts[-1]
            places = [p.strip() for p in parts[1].split("→")] if len(parts) > 2 else []
            m = re.search(r"\d+", label)
            num = m.group(0) if m else str(len(rows) + 1)
            imgs = re.findall(r'<img src="([^"]+)" alt="([^"]*)"', text)
            text = re.sub(r'<div class="gallery[^"]*">.*?</div>', "", text, flags=re.S).strip()   # photos are shown apart
            # the day's places that have a destination page get a link under the day's text
            dests = []
            for w in places:
                for d in self.site.places:
                    if d not in dests and self.place_match(d, w):
                        dests.append(d)
            if dests:
                text += '<p class="day-go">%s</p>' % "".join(
                    '<a href="%s">About %s%s</a>' % (d["url"], esc(d["short"]), ICON["arrow"]) for d in dests)
            for p in places:
                if p not in [s for s, _ in stops] and p.lower() != "airport":
                    stops.append((p, num))
            pics.append(imgs)
            caps.append((label, " → ".join(places)))
            where = ('<span class="day-where">%s%s</span>' % (ICON["pin"], ('<i aria-hidden="true">%s</i>' % ICON["arrow"]).join(
                '<span>%s</span>' % p for p in places))) if places else ""
            rows.append(
                '<details class="day" id="day-{n}"{data}><summary>'
                '<span class="day-stop" aria-hidden="true"></span>'
                '<span class="day-head"><span class="day-meta"><span class="day-n">{label}</span>{where}</span>'
                '<h3 class="day-title">{title}</h3></span>'
                '<span class="day-plus" aria-hidden="true"></span></summary>'
                '<div class="day-body"><div class="day-in"><div class="day-text">{text}</div>{pics}</div></div></details>'.format(
                    n=num, label=label, where=where, title=title, text=text,
                    data=(' data-where="%s"' % " → ".join(places) if places else ""),   # already escaped by markdown()
                    pics=('<div class="day-pics">%s</div>' % "".join(
                        '<span class="day-pic"><img src="%s" alt="%s" loading="lazy"></span>' % (src, alt)
                        for src, alt in imgs[:2])) if imgs else ""))
        # the photo window beside the days (wide screens): one slide per day, its first photo (a day without
        # one repeats the last). site.js slides them up through the window as you scroll, with parallax.
        slides, last = [], next((p[0][0] for p in pics if p), "")
        for i, p in enumerate(pics):
            last = p[0][0] if p else last
            slides.append('<span class="dbd-slide"><img %s="%s" alt=""></span>' % ("src" if i == 0 else "data-src", last))
        side = ('<div class="dbd-side" aria-hidden="true"><div class="dbd-window">{slides}'
                '<p class="dbd-cap"><span class="dbd-cap-n">{n}</span><span class="dbd-cap-w">{w}</span></p>'
                '<p class="dbd-count"><span class="dbd-count-n">01</span> / {total:02d}</p></div></div>').format(
                    slides="".join(slides), n=caps[0][0] if caps else "", w=caps[0][1] if caps else "",
                    total=int((re.findall(r"\d+", caps[-1][0]) or [len(days)])[-1]) if caps else 0)   # "Days 14–15" -> 15
        first = last
        route = ('<p class="dbd-route">%s</p>' % "".join(
            '<a href="#day-%s">%s</a>' % (n, p) for p, n in stops)) if len(stops) > 1 else ""
        return (
            '<section class="band dbd" id="itinerary"><div class="wrap">'
            '<div class="dbd-top"><div class="dbd-say"><p class="kicker">The itinerary</p><h2>Day by day</h2></div>'
            '<div class="dbd-tools">{route}{lead}<button type="button" class="dbd-all" aria-pressed="false">'
            '<span class="day-plus" aria-hidden="true"></span><span class="dbd-all-t">Open every day</span></button></div></div>'
            '<div class="dbd-grid{solo}">{side}<div class="dbd-days">{rows}</div></div>'
            '</div></section>').format(route=route, lead=lead.strip(), side=side if first else "",
                                       solo="" if first else " solo", rows="".join(rows))

    def faq_details(self, body):
        # FAQ -> collapsible questions
        def faq(m):
            qa = re.findall(r"<h3>(.*?)</h3>\s*(.*?)(?=<h3>|\Z)", m.group(2), flags=re.S)
            return m.group(1) + '<div class="faq">%s</div>' % "".join(
                "<details><summary>%s</summary><div>%s</div></details>" % (q, a) for q, a in qa)
        body = re.sub(r"(<h2>FAQ</h2>)(.*?)(?=<h2>|\Z)", faq, body, flags=re.S)
        return body

    def build_tours(self):
        for t in self.site.tours:
            self.current = t
            body, _ = markdown(t["body"])
            body = self.faq_details(body)
            facts = '<p class="facts"><span>%s%s</span><span>%s%s</span><span>%sTailor-made</span></p>' % (
                ICON["calendar"], esc(t.get("duration", "")), ICON["compass"], self.tour_type(t), ICON["users"])
            cats = [self.site.cat_by_slug[s] for s in tour_themes(t) if s in self.site.cat_by_slug]
            # breadcrumb goes through the tour's first category, when it has one
            crumbs = [("Tours", "/tours/")] + ([(cats[0]["name"], cats[0]["url"])] if cats else []) + [(t["title"], None)]
            wa_text = quote("Hi Sunbird, I'm interested in the %s." % t["title"])
            aside = (
                '<aside class="tour-aside"><div class="box"><p class="kicker">Interested?</p><h3>{title}</h3>'
                '<ul class="facts-list"><li>{cal}{dur}</li><li>{comp}{typ}</li>{best}</ul>{cats}'
                '<a class="btn gold block" href="#enquire">Enquire about this tour</a>'
                '<a class="btn outline block" href="https://wa.me/{wa}?text={txt}" target="_blank" rel="noopener">{waicon}Ask on WhatsApp</a>'
                '<p class="muted small">Every tour can be changed to suit your dates, budget and interests.</p></div></aside>'
            ).format(title=esc(t["title"]), cal=ICON["calendar"], dur=esc(t.get("duration")), comp=ICON["compass"],
                     typ=self.tour_type(t), wa=esc(self.s.get("whatsapp")), txt=wa_text, waicon=ICON["whatsapp"],
                     best=('<li>%sBest %s</li>' % (ICON["sun"], esc(str(t["best_months"]).replace("-", " – ")))) if t.get("best_months") else "",
                     cats=('<p class="tour-cats">%s</p>' % "".join('<a href="%s">%s</a>' % (c["url"], esc(c["name"])) for c in cats)) if cats else "")
            # "You may also like": tours sharing the most categories with this one, then same-type tours to fill up
            mine = set(tour_themes(t))
            main = tour_themes(t)[0] if mine else None
            others = [r for r in self.site.tours if r["slug"] != t["slug"]]
            # most shared categories first; on a tie, tours sharing this tour's main category, then the same kind
            # (day tours suggest day tours)
            shared = sorted((r for r in others if mine & set(tour_themes(r))),
                            key=lambda r: (-len(mine & set(tour_themes(r))), main not in tour_themes(r),
                                           r.get("category") != t.get("category")))
            related = (shared + [r for r in others if r not in shared and r.get("category") == t.get("category")])[:3]
            # the itinerary gets a band of its own between the intro (with the enquiry box) and the rest
            it = re.search(r"<h2>Itinerary</h2>(.*?)(?=<h2>|\Z)", body, flags=re.S)
            intro, days, rest = (body[:it.start()], self.day_by_day(it.group(1)), body[it.end():]) if it else (body, "", "")
            html_ = (self.hero(t["title"], t.get("tagline"), t.get("image"), crumbs=crumbs, facts=facts)
                     + '<section class="band"><div class="wrap tour-layout"><article class="prose">%s</article>%s</div></section>' % (intro, aside)
                     + days
                     + ('<section class="band tour-rest"><div class="wrap tour-layout"><article class="prose">%s</article></div></section>' % rest
                        if rest.strip() else "")
                     + '<section class="band mist" id="enquire"><div class="wrap"><p class="kicker">Plan this trip</p><h2>Enquire about the %s</h2>%s</div></section>' % (esc(t["title"]), self.form(t))
                     + '<section class="band"><div class="wrap"><p class="kicker">You may also like</p><h2>More tours</h2><div class="grid cards3 tiles">%s</div></div></section>'
                     % "".join(self.card_tour(r) for r in related))
            self.page(t["url"], t["title"], html_, t.get("summary"), t.get("image"), "tour")

    def build_categories(self):
        """One page per tour category at /tours/<file name>/: intro text, its tours, then the other categories."""
        for c in self.site.cats:
            self.current = c
            intro, _ = markdown(c["body"])
            tours = self.tours_in(c["slug"])
            facts = '<p class="facts"><span>%s%d tour%s</span><span>%sPrivate and tailor-made</span></p>' % (
                ICON["compass"], len(tours), "" if len(tours) == 1 else "s", ICON["users"])
            html_ = (self.hero(c["title"], c.get("tagline"), c.get("image"), crumbs=[("Tours", "/tours/"), (c["name"], None)], facts=facts,
                               focus=c.get("focus"))
                     + '<section class="band"><div class="wrap"><div class="cat-intro">%s</div>%s'
                       '<div class="grid cards3 tiles" id="cat-tours">%s</div></div></section>' % (
                         intro, self.month_bar(), "".join(self.card_tour(t) for t in tours))
                     + self.month_ask(c) + (self.weather_data() if self.site.weather else "")
                     + '<section class="band mist"><div class="wrap">%s</div></section>' % self.category_index(
                         skip=c["slug"], kicker="More ways to travel", title="Other tour categories",
                         links='<a class="btn gold" href="/contact-us/#plan">Plan my trip%s</a>'
                               '<a class="ci-more" href="/tours/">See all tours</a>' % ICON["arrow"]))
            self.page(c["url"], c["title"], html_, c.get("description"), c.get("image"), "page")

    def build_places(self):
        """One page per destination at /destinations/<file name>/, made from the parts of its file: the opening
        text, **Hidden gems** (a list), **Top attractions** (photos), and the "**Best time to visit:**",
        "**Where to stay:**" ... lines. The photos are small portraits, so the page is laid out around tall
        pictures (none of them is stretched across the screen)."""
        mp = self.site.map
        if mp:
            os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
            with open(os.path.join(OUT, "img", "sri-lanka.svg"), "w", encoding="utf-8") as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"><g fill="#d3e4ec" stroke="#f6fafc" '
                        'stroke-width="1.4" stroke-linejoin="round">{d}</g></svg>'.format(
                            w=mp["width"], h=int(mp["height"]), d="".join('<path d="%s"/>' % x["d"] for x in mp["districts"])))
        for p in self.site.places:
            self.current = p
            html_, _ = markdown(p["body"])
            # the parts
            gems_html = re.search(r"<p><strong>Hidden gems</strong></p>\s*<ul>(.*?)</ul>", html_, flags=re.S)
            gems = re.findall(r"<li>(.*?)</li>", gems_html.group(1), flags=re.S) if gems_html else []
            photos = [(src, re.sub(r"[:\s]+$", "", cap)) for src, cap in
                      re.findall(r'<figure><img src="([^"]+)"[^>]*><figcaption>(.*?)</figcaption></figure>', html_)]
            info = dict(re.findall(r"<p><strong>([^<]+?):</strong>\s*(.*?)</p>", html_, flags=re.S))
            intro = html_
            for rx in (r"<p><strong>Hidden gems</strong></p>\s*<ul>.*?</ul>", r"<p><strong>Top attractions</strong></p>",
                       r'<div class="gallery[^"]*">.*?</div>', r"<p><strong>[^<]+?:</strong>.*?</p>"):
                intro = re.sub(rx, "", intro, flags=re.S)
            # a short plain line just before the gems ("Ella's best-kept secrets await beyond the trails.") leads them
            paras = re.findall(r"<p>.*?</p>", intro, flags=re.S)
            lead = ""
            if paras and "<" not in paras[-1][3:-4] and len(paras[-1]) < 120:
                lead = paras[-1][3:-4]
                intro = intro.replace(paras[-1], "")
            tours = self.place_tours(p)
            same = [q for q in self.site.places if q.get("region") == p.get("region") and q is not p]
            best = month_runs(p["season"]) if p["season"] else ""
            name = esc(p["name"])

            # 1. opening: the name beside three tall photos
            stack = [p.get("image")] + [s for s, _ in photos if s != p.get("image")]
            hero = (
                '<section class="dest-hero"><div class="wrap dh-grid"><div class="dh-text">'
                '<nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> <span>›</span> <a href="/destinations/">Destinations</a>'
                ' <span>›</span> <span>{name}</span></nav>'
                '<p class="ci-kicker">{region}</p><h1>{name}</h1><p class="dh-tag">{tag}</p>'
                '<p class="dh-facts">{best}{count}</p>'
                '<p class="dh-btns"><a class="btn gold" href="/contact-us/#plan">Plan a trip with {name}{arrow}</a>{see}</p></div>'
                '<div class="dh-photos" aria-hidden="true">{stack}</div></div></section>'
            ).format(name=name, region=esc(p.get("region", "Sri Lanka")), tag=esc(p.get("tagline", "")),
                     best=('<span>%sBest %s</span>' % (ICON["sun"], best)) if best else "",
                     count=('<span>%s%d tour%s stop%s here</span>' % (ICON["compass"], len(tours), "" if len(tours) == 1 else "s",
                                                                      "s" if len(tours) == 1 else "")) if tours else "",
                     arrow=ICON["arrow"], see='<a class="ci-more" href="#tours">See the tours</a>' if tours else "",
                     stack="".join('<span class="dh-ph"><img src="%s" alt=""%s></span>' % (esc(s), "" if i == 0 else ' loading="lazy"')
                                   for i, s in enumerate(stack[:3])))

            # 2. the opening text, with where it is and when to go beside it
            glance = (
                '<aside class="dest-glance">{map}<div class="dg-when"><p class="ci-kicker">When to go</p>{strip}'
                '<p class="dg-note">{note}</p></div></aside>'
            ).format(map=self.isle(p), strip=self.month_strip(p["season"]) if p["season"] else "",
                     note=info.get("Best time to visit", ""))
            body = '<section class="band dest-intro"><div class="wrap di-grid"><div class="prose">%s</div>%s</div></section>' % (intro.strip(), glance)

            # 3. top attractions: a row of tall photos you slide through
            if photos:
                body += (
                    '<section class="band dest-sights"><div class="wrap"><div class="ds-head"><div>'
                    '<p class="ci-kicker">Top attractions</p><h2>What to see in {name}</h2></div>'
                    '<div class="ds-nav"><button type="button" class="ds-prev" aria-label="Previous photos">{arrow}</button>'
                    '<button type="button" class="ds-next" aria-label="Next photos">{arrow}</button></div></div>'
                    '<ol class="ds-list">{items}</ol><div class="ds-bar" aria-hidden="true"><i></i></div></div></section>'
                ).format(name=name, arrow=ICON["arrow"], items="".join(
                    '<li><figure><span class="ds-ph"><img src="{src}" alt="{cap}" loading="lazy"></span>'
                    '<figcaption><span class="ds-n">{n:02d}</span>{cap}</figcaption></figure></li>'.format(src=esc(s), cap=c, n=i + 1)
                    for i, (s, c) in enumerate(photos)))

            # 4. hidden gems: a numbered list ("Name – what it is")
            if gems:
                rows = []
                for i, g in enumerate(gems):
                    head, rest = (re.split(r"\s+[–-]\s+", g, maxsplit=1) + [""])[:2]
                    rows.append('<li><span class="dg-n">{n:02d}</span><span class="dg-t{solo}">{h}</span>{r}</li>'.format(
                        n=i + 1, solo="" if rest else " solo", h=head.strip(), r=('<span class="dg-d">%s</span>' % rest.strip()) if rest else ""))
                body += (
                    '<section class="band dest-gems"><div class="wrap dgm-grid"><div class="dgm-say">'
                    '<p class="ci-kicker">Off the beaten track</p><h2>Hidden gems</h2>{lead}</div>'
                    '<ol class="dgm-list">{rows}</ol></div></section>'
                ).format(lead='<p>%s</p>' % lead if lead else "", rows="".join(rows))

            # 5. good to know: where to stay, eat and shop
            cols = []
            for key, label in (("Where to stay", "Where to stay"), ("Where to eat", "Where to eat"), ("Where to shop", "Where to shop")):
                v = info.get(key, "").strip()
                if not v:
                    continue
                if " · " in v:   # a list of hotels
                    v = '<ul class="dk-list">%s</ul>' % "".join("<li>%s</li>" % re.sub(r"\.{2,}$|…$", "", x).strip() for x in v.split(" · "))
                else:
                    v = "<p>%s</p>" % v
                cols.append('<div class="dk-col"><p class="ci-kicker">%s</p>%s</div>' % (label, v))
            if cols:
                body += ('<section class="band dest-know"><div class="wrap"><h2 class="dk-title">Good to know</h2>'
                         '<div class="dk-grid">%s</div></div></section>' % "".join(cols))

            # 6. tours that stop here
            if tours:
                body += ('<section class="band mist dest-tours" id="tours"><div class="wrap"><div class="dt-head"><p class="ci-kicker">Tours</p>'
                         '<h2>Tours that visit {name}</h2><p class="dt-text">Every tour is private and can be changed: '
                         'more nights here, fewer somewhere else.</p></div><div class="grid cards3 tiles">{cards}</div></div></section>'
                         ).format(name=name, cards="".join(self.card_tour(t) for t in tours))
            else:
                body += ('<section class="band mist dest-tours" id="tours"><div class="wrap"><div class="dt-head"><p class="ci-kicker">Tours</p>'
                         '<h2>Add {name} to your trip</h2><p class="dt-text">None of our set tours stops here yet. Tell us '
                         'you’d like to go and we’ll plan the days around it.</p>'
                         '<p class="dt-btns"><a class="btn gold" href="/contact-us/#plan">Plan my trip{arrow}</a></p></div></div></section>'
                         ).format(name=name, arrow=ICON["arrow"])

            # 7. more places in the same region
            if same:
                body += (
                    '<section class="band dest-more"><div class="wrap"><div class="ds-head"><div>'
                    '<p class="ci-kicker">Nearby</p><h2>{title}</h2></div>'
                    '<a class="ci-more" href="/destinations/">All destinations</a></div>'
                    '<div class="dm-cards">{cards}</div></div></section>'
                ).format(title=esc(MORE_IN.get(p.get("region"), "More in %s" % p.get("region"))),
                         cards="".join(self.place_card(q) for q in same[:4]))
            first = re.search(r"<p>(.*?)</p>", intro, flags=re.S)
            desc = re.sub(r"<[^>]+>", "", first.group(1)) if first else p.get("tagline", "")
            desc = desc if len(desc) <= 155 else desc[:155].rsplit(" ", 1)[0] + "…"
            self.page(p["url"], "%s, Sri Lanka" % p["name"], hero + body, desc, p.get("image"), "place")

    def build_posts(self):
        for n, p in enumerate(self.site.posts):
            self.current = p
            body, _ = markdown(p["body"])
            meta = '<p class="facts"><span>%s%s</span>%s</p>' % (ICON["calendar"], self.nice_date(p["date"]),
                                                                ('<span>%s</span>' % esc(p["category"])) if p.get("category") else "")
            others = [o for o in self.site.posts if o is not p][:3]
            html_ = (self.hero(p["title"], None, p.get("image"), crumbs=[("Blog", "/blog/"), (p["title"], None)], facts=meta)
                     + '<section class="band"><div class="wrap narrow"><article class="prose">%s</article>'
                       '<p class="post-cta"><a class="btn gold" href="/contact-us/#plan">Plan your Sri Lanka trip</a> <a class="btn outline" href="/blog/">All articles</a></p></div></section>' % body
                     + '<section class="band mist"><div class="wrap"><h2>More articles</h2><div class="grid cards3">%s</div></div></section>'
                     % "".join(self.card_post(o) for o in others))
            self.page(p["url"], p["title"], html_, p.get("summary"), p.get("image"), "post")

    def build_redirects(self):
        n = 0
        for old, new in self.site.redirects:
            if not old.startswith("/") or old.rstrip("/") == "":
                continue
            path = os.path.join(OUT, *[p for p in old.split("/") if p], "index.html")
            if os.path.exists(path):
                continue  # a real page lives here
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Moved</title>'
                        '<meta name="robots" content="noindex"><link rel="canonical" href="{abs}">'
                        '<meta http-equiv="refresh" content="0; url={new}"><script>location.replace({js})</script>'
                        '</head><body><p>This page has moved: <a href="{new}">{new}</a></p></body></html>'.format(
                            abs=esc(self.s.get("url", "") + new), new=esc(new), js=json.dumps(new)))
            n += 1
        return n

    def build_extras(self):
        site_url = self.s.get("url", "")
        urls = sorted(set(self.pages_written))
        with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for u in urls:
                f.write("  <url><loc>%s%s</loc></url>\n" % (esc(site_url), esc(quote(u, safe="/"))))
            f.write("</urlset>\n")
        with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
            f.write("User-agent: *\nAllow: /\nDisallow: /admin/\n\nSitemap: %s/sitemap.xml\n" % site_url)
        with open(os.path.join(OUT, "CNAME"), "w", encoding="utf-8") as f:
            f.write(re.sub(r"^https?://", "", site_url).strip("/") + "\n")
        open(os.path.join(OUT, ".nojekyll"), "w").close()
        return len(urls)


def apply_base_path(base):
    """Prefix every site-relative link with `base` (for example "/SunBird") so the site also
    works from a sub-folder such as username.github.io/SunBird/. GitHub fills this in
    automatically (see publish.yml). With the real domain it is empty and nothing changes."""
    base = "/" + base.strip("/") if base.strip("/") else ""
    if not base:
        return 0
    rules_html = [
        re.compile(r'(\s(?:href|src|srcset|action|poster)=")/(?!/)'),
        re.compile(r'(http-equiv="refresh" content="\d+;\s*url=)/(?!/)'),
        re.compile(r'(location\.replace\(")/(?!/)'),
    ]
    css_url = re.compile(r"""(url\(\s*['"]?)/(?!/)""")
    changed = 0
    for folder, _, files in os.walk(OUT):
        for name in files:
            if not name.endswith((".html", ".css")):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            new = css_url.sub(lambda m: m.group(1) + base + "/", text)
            if name.endswith(".html"):
                for rx in rules_html:
                    new = rx.sub(lambda m: m.group(1) + base + "/", new)
            if new != text:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
                changed += 1
    return changed


def main():
    # empty the output folder (keeping the folder itself, so a preview server can stay open)
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):
        p = os.path.join(OUT, name)
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)
    shutil.copytree(STATIC, OUT, dirs_exist_ok=True)
    site = Site()
    b = Builder(site)
    b.build_pages()
    b.build_tours()
    b.build_categories()
    b.build_places()
    b.build_posts()
    n_red = b.build_redirects()
    n = b.build_extras()
    # the admin panel (/admin/) saves to this GitHub repository when it runs on the live site
    if os.path.isdir(os.path.join(OUT, "admin")):
        with open(os.path.join(OUT, "admin", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"mode": "github", "repo": site.s.get("admin_repo", ""),
                       "branch": site.s.get("admin_branch", "main") or "main"}, f)
    print("Built %d pages, %d tours, %d posts, %d redirects -> %s" % (n, len(site.tours), len(site.posts), n_red, OUT))
    base = os.environ.get("SITE_BASE_PATH", "")
    if apply_base_path(base):
        print("Links adjusted to work from the sub-folder %s" % base)


if __name__ == "__main__":
    main()
