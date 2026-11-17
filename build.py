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
        label, link = [c.strip() for c in l.split("|", 1)]
        item = {"label": label, "link": link, "children": []}
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
        self.places.sort(key=lambda p: (p.get("order", 99), p.get("name", "")))
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
        return "Wildlife & day tour" if t.get("category") == "wildlife" else "Bespoke tour"

    def card_tour(self, t):
        return (
            '<article class="card tour-card"><a href="{url}" class="card-link">'
            '<div class="card-img"><img src="{img}" alt="" loading="lazy"><span class="chip">{dur}</span></div>'
            '<div class="card-body"><p class="card-type">{typ}</p><h3>{title}</h3><p>{summary}</p>'
            '<span class="more">View tour {arrow}</span></div></a></article>'
        ).format(url=t["url"], img=esc(t.get("image")), dur=esc(t.get("duration", "")), typ=self.tour_type(t),
                 title=esc(t["title"]), summary=esc(t.get("summary", "")), arrow=ICON["arrow"])

    def tour_grid(self, which):
        tours = self.site.tours
        if which in ("bespoke", "wildlife"):
            tours = [t for t in tours if t.get("category") == which]
        elif which == "featured":
            slugs = self.current.get("featured_tours") or []
            by = {t["slug"]: t for t in tours}
            tours = [by[s] for s in slugs if s in by]
        return '<div class="grid cards3">%s</div>' % "".join(self.card_tour(t) for t in tours)

    def place_cards(self, which):
        places = self.site.places
        if which == "featured":
            slugs = self.current.get("featured_places") or []
            by = {p["slug"]: p for p in places}
            places = [by[s] for s in slugs if s in by]
            return '<div class="grid cards4">%s</div>' % "".join(
                '<a class="place-card" href="/destinations/#{slug}"><img src="{img}" alt="" loading="lazy">'
                '<span class="pc-text"><strong>{name}</strong><small>{tag}</small></span></a>'.format(
                    slug=p["slug"], img=esc(p.get("image")), name=esc(p.get("name")), tag=esc(p.get("tagline", "")))
                for p in places)
        # all places, one after the other
        jump = '<nav class="jump" aria-label="Destinations">%s</nav>' % "".join(
            '<a href="#%s">%s</a>' % (p["slug"], esc(p.get("name"))) for p in places)
        items = []
        for p in places:
            body, _ = markdown(p["body"])
            items.append(
                '<article class="place" id="{slug}"><header><p class="kicker">{tag}</p><h2>{name}</h2></header>'
                '<div class="place-body">{body}</div><a class="top" href="#top-places">Back to all destinations ↑</a></article>'.format(
                    slug=p["slug"], tag=esc(p.get("tagline", "")), name=esc(p.get("name")), body=body))
        return '<div id="top-places"></div>' + jump + "".join(items)

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
                '<p class="kicker">{k}</p><{h}>{t}</{h}><p class="slide-btns"><a class="btn" href="{link}">{btn}</a>'
                '<a class="btn ghost" href="/contact-us/#plan">Plan My Trip</a></p></div></div>'.format(
                    act=" active" if n == 0 else "", img=esc(c[0]), k=esc(c[1]), h=h, t=esc(c[2]), btn=esc(c[3]), link=esc(c[4])))
        dots = "".join('<button type="button" aria-label="Slide %d"%s></button>' % (i + 1, ' class="active"' if i == 0 else "")
                       for i in range(len(slides)))
        return '<section class="slider" aria-label="Highlights">%s<div class="dots">%s</div></section>' % ("".join(slides), dots)

    # Gold sunbird used in the home hero. The wing is separate so it can flap.
    SUNBIRD_SVG = (
        '<svg viewBox="0 0 64 48" aria-hidden="true" focusable="false">'
        '<path class="b-tail" d="M22 31 L5 40 L8 43 L24 34 Z"/>'
        '<path class="b-body" d="M20 29 C20 21 29 16 37 17.5 C43 18.6 46.5 22.5 45.5 27 C44 33 35 36.5 27 35 C22.5 34.2 20 32 20 29 Z"/>'
        '<circle class="b-body" cx="43.5" cy="17.5" r="5.6"/>'
        '<path class="b-bill" d="M48.6 16.4 Q56.5 16.2 62 22.8"/>'
        '<circle class="b-eye" cx="45" cy="16.4" r="1.15"/>'
        '<path class="b-feet" d="M30 35.5 L29 41 M34 35 L34.5 41"/>'
        '<path class="b-wing" d="M30 26 C27 16 20 9 11 6 C16 14 21.5 22 31 28.5 Z"/>'
        '</svg>')

    def home_hero(self):
        """The big first screen on the home page (settings live in content/pages/home.md)."""
        p = self.current

        def parts(key, n):
            return (split_row(p.get(key) or "") + [""] * n)[:n]

        first, script, last = parts("hero_title", 3)
        btn_text, btn_link = parts("hero_button", 2)
        greet, greet_small = parts("hero_greeting", 2)
        facts = "".join('<li><strong>%s</strong>%s</li>' % tuple(esc(x) for x in (split_row(r) + [""])[:2])
                        for r in (p.get("hero_facts") or []))
        wa = self.s.get("whatsapp")
        return (
            '<section class="hero-home" aria-label="Welcome">'
            '<img class="hh-photo" src="{img}" alt="{alt}" style="--focus:{focus}" fetchpriority="high" decoding="async">'
            '<div class="hh-shade"></div>'
            '<div class="wrap hh-inner">'
            '<p class="hh-kicker">{kicker}</p>'
            '<h1 class="hh-title"><span>{first}</span> <em class="hh-script">{script}<svg class="hh-branch" viewBox="0 0 200 24" preserveAspectRatio="none" aria-hidden="true" focusable="false"><path d="M2 15 C 60 23, 132 21, 197 4"/></svg><span class="hh-bird">{bird}</span></em> <span>{last}</span></h1>'
            '<p class="hh-text">{text}</p>'
            '<p class="hh-btns"><a class="btn gold" href="{link}">{btn}{arrow}</a>{wa}</p>'
            '{facts}'
            '</div>'
            '{greet}'
            '<a class="hh-scroll" href="#start" aria-label="Scroll down"><span></span></a>'
            '</section><span id="start"></span>'
        ).format(
            img=esc(p.get("image")), alt=esc(p.get("hero_photo_alt")), focus=esc(p.get("hero_focus") or "50% 50%"),
            kicker=esc(p.get("hero_kicker")), first=esc(first), script=esc(script), last=esc(last), bird=self.SUNBIRD_SVG,
            text=esc(p.get("hero_text")), link=esc(btn_link or "/contact-us/#plan"), btn=esc(btn_text or "Plan your trip"),
            arrow=ICON["arrow"],
            wa=('<a class="btn ghost" href="https://wa.me/%s" target="_blank" rel="noopener">%sWhatsApp us</a>'
                % (esc(wa), ICON["whatsapp"])) if wa else "",
            facts=('<ul class="hh-facts">%s</ul>' % facts) if facts else "",
            greet=('<p class="hh-greet" aria-hidden="true"><span>%s</span><small>%s</small>'
                   '<svg viewBox="0 0 220 24"><path d="M4 16 C 50 4, 110 22, 216 8"/></svg></p>'
                   % (esc(greet), esc(greet_small))) if greet else "",
        )

    def categories(self):
        cards = []
        for row in self.current.get("categories") or []:
            img, name, link = (split_row(row) + ["", "", ""])[:3]
            cards.append('<a class="cat-card" href="%s"><img src="%s" alt="" loading="lazy"><span>%s</span></a>' % (esc(link), esc(img), esc(name)))
        return '<div class="grid cats">%s</div>' % "".join(cards)

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
                '<a class="btn small" href="/contact-us/#plan">Book now</a></div>'.format(
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
            '</div><p class="form-actions"><button class="btn" type="submit">Send my request</button>'
            '<span class="form-note">We reply within 24 hours. Prefer WhatsApp? <a href="https://wa.me/{wa}" target="_blank" rel="noopener">Message us</a></span></p>'
            '<p class="form-status" role="status" aria-live="polite"></p></form>'
        ).format(subject=esc(subject), opts="".join(opts), wa=esc(self.s.get("whatsapp")))

    def shortcode(self, name):
        kind, _, arg = name.partition(":")
        return {
            "slider": lambda: self.slider(),
            "hero": lambda: self.home_hero(),
            "categories": lambda: self.categories(),
            "tours": lambda: self.tour_grid(arg or "all"),
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
                sub = "".join('<li><a href="%s">%s</a></li>' % (esc(c["link"]), esc(c["label"])) for c in it["children"])
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
            '<div><h3>Explore</h3><ul><li><a href="/tours/">All tours</a></li><li><a href="/destinations/">Destinations</a></li>'
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

    def hero(self, title, tagline=None, image=None, crumbs=None, facts=None):
        style = ' style="background-image:url(\'%s\')"' % esc(image) if image else ""
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@600;700;800&family=Montez&family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Caveat:wght@700&display=swap">
<link rel="stylesheet" href="/css/site.css?v={ver}">
{gtag}</head>
<body class="layout-{layout}">
<a class="skip" href="#main">Skip to content</a>
<div class="topbar"><div class="wrap">
<span class="tb-item">{pin}{addr}</span><span class="tb-item tb-hours">{clock}{hours}</span>
<span class="tb-right"><span class="gtranslate_wrapper"></span><a class="tb-item" href="https://wa.me/{wa}" target="_blank" rel="noopener">{waicon}{phone}</a></span>
</div></div>
<header class="site-header"><div class="wrap">
<a class="logo" href="/"><img class="logo-dark" src="/img/logo.png" alt="{site}" width="170" height="64"><img class="logo-light" src="/img/logo-white.png" alt="{site}" width="170" height="64"></a>
<nav id="nav" class="nav" aria-label="Main">{nav}<a class="btn nav-cta" href="/contact-us/#plan">Request a Quote</a></nav>
<a class="btn header-cta" href="/contact-us/#plan">Request a Quote</a>
<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav"><span class="bars"></span><span class="sr">Menu</span></button>
</div></header>
<main id="main">
{body}
</main>
{footer}
<script>window.SB={cfg};</script>
<script src="/js/site.js?v={ver}" defer></script>
<script>window.gtranslateSettings={{"default_language":"en","languages":{langs},"wrapper_selector":".gtranslate_wrapper","flag_style":"2d"}};</script>
<script src="https://cdn.gtranslate.net/widgets/latest/dropdown.js" defer></script>
{tawk}</body>
</html>
""".format(
            title=esc(full_title), desc=esc(description or s.get("description")), canon=esc(s.get("url", "") + quote(url, safe="/#")),
            noindex='<meta name="robots" content="noindex">\n' if noindex else "", site=esc(s.get("site_name")), ogimg=esc(og_img),
            ver=self.site.ver, layout=layout, pin=ICON["pin"], clock=ICON["clock"], waicon=ICON["whatsapp"],
            addr=esc(s.get("address")), hours=esc(s.get("hours")), wa=esc(s.get("whatsapp")), phone=esc(s.get("phone")),
            nav=self.nav(), body=body, footer=self.footer(), cfg=json.dumps(cfg), langs=json.dumps(langs),
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
            if p.get("layout") != "home":
                body = self.hero(p["title"], p.get("tagline"), p.get("image"), crumbs=[(p["title"], None)]) + body
            self.page(p["url"], p["title"], body, p.get("description"), p.get("image"), p.get("layout", "page"),
                      noindex=bool(p.get("noindex")))

    def faq_and_itinerary(self, body):
        # Itinerary section -> timeline
        body = re.sub(r"(<h2>Itinerary</h2>)(.*?)(?=<h2>|\Z)", lambda m: m.group(1) + '<div class="itinerary">%s</div>' % m.group(2), body, flags=re.S)
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
            body = self.faq_and_itinerary(body)
            facts = '<p class="facts"><span>%s%s</span><span>%s%s</span><span>%sTailor-made</span></p>' % (
                ICON["calendar"], esc(t.get("duration", "")), ICON["compass"], self.tour_type(t), ICON["users"])
            listing = "/tours/#%s" % t.get("category", "bespoke")
            wa_text = quote("Hi Sunbird, I'm interested in the %s." % t["title"])
            aside = (
                '<aside class="tour-aside"><div class="box"><p class="kicker">Interested?</p><h3>{title}</h3>'
                '<ul class="facts-list"><li>{cal}{dur}</li><li>{comp}{typ}</li></ul>'
                '<a class="btn block" href="#enquire">Enquire about this tour</a>'
                '<a class="btn outline block" href="https://wa.me/{wa}?text={txt}" target="_blank" rel="noopener">{waicon}Ask on WhatsApp</a>'
                '<p class="muted small">Every tour can be changed to suit your dates, budget and interests.</p></div></aside>'
            ).format(title=esc(t["title"]), cal=ICON["calendar"], dur=esc(t.get("duration")), comp=ICON["compass"],
                     typ=self.tour_type(t), wa=esc(self.s.get("whatsapp")), txt=wa_text, waicon=ICON["whatsapp"])
            related = [r for r in self.site.tours if r.get("category") == t.get("category") and r["slug"] != t["slug"]][:3]
            html_ = (self.hero(t["title"], t.get("tagline"), t.get("image"), crumbs=[("Tours", listing), (t["title"], None)], facts=facts)
                     + '<section class="band"><div class="wrap tour-layout"><article class="prose">%s</article>%s</div></section>' % (body, aside)
                     + '<section class="band mist" id="enquire"><div class="wrap"><p class="kicker">Plan this trip</p><h2>Enquire about the %s</h2>%s</div></section>' % (esc(t["title"]), self.form(t))
                     + '<section class="band"><div class="wrap"><p class="kicker">You may also like</p><h2>More tours</h2><div class="grid cards3">%s</div></div></section>'
                     % "".join(self.card_tour(r) for r in related))
            self.page(t["url"], t["title"], html_, t.get("summary"), t.get("image"), "tour")

    def build_posts(self):
        for n, p in enumerate(self.site.posts):
            self.current = p
            body, _ = markdown(p["body"])
            meta = '<p class="facts"><span>%s%s</span>%s</p>' % (ICON["calendar"], self.nice_date(p["date"]),
                                                                ('<span>%s</span>' % esc(p["category"])) if p.get("category") else "")
            others = [o for o in self.site.posts if o is not p][:3]
            html_ = (self.hero(p["title"], None, p.get("image"), crumbs=[("Blog", "/blog/"), (p["title"], None)], facts=meta)
                     + '<section class="band"><div class="wrap narrow"><article class="prose">%s</article>'
                       '<p class="post-cta"><a class="btn" href="/contact-us/#plan">Plan your Sri Lanka trip</a> <a class="btn outline" href="/blog/">All articles</a></p></div></section>' % body
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
            f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % site_url)
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
        re.compile(r'(\s(?:href|src|action|poster)=")/(?!/)'),
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
    b.build_posts()
    n_red = b.build_redirects()
    n = b.build_extras()
    print("Built %d pages, %d tours, %d posts, %d redirects -> %s" % (n, len(site.tours), len(site.posts), n_red, OUT))
    base = os.environ.get("SITE_BASE_PATH", "")
    if apply_base_path(base):
        print("Links adjusted to work from the sub-folder %s" % base)


if __name__ == "__main__":
    main()
