#!/usr/bin/env python3
"""Build the davysh.com drops log from the public Gumroad storefront.

Writes, relative to the site root:
  drops.json          data for every published product, newest first
  drops/img/*.webp    local copies of each product thumbnail (360w and 720w)
  drops/index.html    the region between <!-- drops:page:start/end --> markers
  drops/feed.xml      RSS 2.0 feed
  index.html          the region between <!-- drops:home:start/end --> markers
  sitemap.xml         <lastmod> of /drops/

Source (public, no login, no key)
  STORE/landing/embed is the page the public storefront at STORE loads in its
  frame. It carries a <script id="gumroad-data" type="application/json"> block
  with every product shown on the profile: name, url, thumbnail_url.
  Products the seller hides from the profile are not listed there, so they are
  not listed here either.
  Each product's public JSON (<url>.json) adds the stable id and created_at.

Launch date per product
  1. created_at from the product's public JSON (<url>.json). This is the
     timestamp Gumroad stores when the product is created. Fetched once per
     product and then kept in drops.json, so it never drifts.
  2. If that is unavailable, the date this script first saw the product
     ("first_seen"). Upgraded to created_at on a later run if it becomes available.
  Dates shown on the site are calendar days in DATE_TZ.

Only product names are published. Descriptions are never read into the output.

Usage
  python3 scripts/build_drops.py              # fetch the public storefront + build
  python3 scripts/build_drops.py --offline    # rebuild HTML from drops.json only

Python standard library only. If Pillow is installed, thumbnails are resized
to WebP; without it the original file is kept as is.
If the storefront cannot be read or looks wrong (no products, a count that does
not match its own total, or fewer than half of the drops already on record),
the script stops with an error and changes nothing.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

STORE = "https://davysh.gumroad.com"
STORE_DATA = STORE + "/landing/embed"
SITE = "https://davysh.com"
DATE_TZ = ZoneInfo("America/Panama")
HOME_COUNT = 4
# Only drops dated on or after this day (DATE_TZ) are listed on the home section,
# /drops/ and the feed. Older products are kept in drops.json under "before_cutoff"
# (id, url, date only) so their dates are not fetched again.
CUTOFF = dt.date(2026, 4, 1)
FEED_COUNT = 30
IMG_SIZES = (360, 720)
UA = "davysh-drops/1.0 (+https://davysh.com/drops/)"
ARROW = ('<svg class="ico" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">'
         '<path d="M7 17 17 7M9 7h8v8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"/></svg>')

ROOT = Path(__file__).resolve().parent.parent


def log(msg):
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------- http

def http_get(url, accept="application/json", tries=4):
    headers = {"User-Agent": UA, "Accept": accept}
    delay = 2.0
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            retry = e.code == 429 or e.code >= 500
            if not retry or attempt == tries:
                raise RuntimeError(f"HTTP {e.code} for {url}") from None
            wait = float(e.headers.get("Retry-After") or delay)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == tries:
                raise RuntimeError(f"network error for {url}: {e}") from None
            wait = delay
        time.sleep(min(wait, 60))
        delay *= 2


def permalink_of(url):
    return urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]


def fetch_storefront():
    """Products listed on the public storefront, in the order shown there."""
    body, _ = http_get(STORE_DATA, accept="text/html")
    m = re.search(r'<script id="gumroad-data" type="application/json">(.*?)</script>',
                  body.decode("utf-8"), re.S)
    if not m:
        raise RuntimeError("storefront data block not found")
    data = json.loads(m.group(1))
    products = data.get("products") or []
    total = data.get("products_total")
    if not products:
        raise RuntimeError("storefront lists no products")
    if isinstance(total, int) and total != len(products):
        raise RuntimeError(f"storefront lists {len(products)} of {total} products")
    out, seen = [], set()
    for p in products:
        url = (p.get("url") or "").split("?")[0]
        if not (url.startswith(STORE + "/l/") and p.get("name")):
            continue
        perm = permalink_of(url)
        if perm.lower() in seen:
            continue
        seen.add(perm.lower())
        out.append({"name": p["name"], "url": url, "permalink": perm,
                    "thumbnail_url": p.get("thumbnail_url") or p.get("cover_url")})
    return out


def fetch_public_json(product):
    """(id, created_at) from the public product JSON; either may be None."""
    try:
        body, _ = http_get(product["url"] + ".json")
        data = json.loads(body)
    except Exception as e:  # noqa: BLE001
        log(f"  public JSON unavailable for {product['url']}: {e}")
        return None, None
    if data.get("is_published") is False or permalink_of(data.get("url") or product["url"]).lower() != product["permalink"].lower():
        return None, None
    ts = data.get("created_at")
    try:
        dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        ts = None
    return data.get("id"), ts


# ---------------------------------------------------------------- naming

DECOR = re.compile(r"[\u2600-\u27BF\u2B00-\u2BFF\U0001F000-\U0001FAFF\uFE0F]")
SEP = re.compile(r"\s+[\u2014\u2013-]\s+")


def smart_case(text):
    shouting = not re.search(r"[a-z]", text)  # whole string in capitals
    def fix(m):
        w = m.group(0)
        if w.upper() == "VRCHAT":
            return "VRChat"
        if w == w.upper() and (len(w) >= 4 or (shouting and len(w) >= 2)):
            return w[0] + w[1:].lower()
        return w
    return re.sub(r"[A-Za-z\u00C0-\u024F]+", fix, text)


def clean_name(raw):
    """Gumroad title -> (title, subtitle). Formatting only; words are kept."""
    s = unicodedata.normalize("NFKC", raw)
    s = unicodedata.normalize("NFC", s)
    # "✧ Name ✧ — Kind" or "✧ Name ✧ Kind": the symbol pair wraps the title
    s = re.sub(r"^\s*(?:%s)\s*(.+?)\s*(?:%s)\s*(?:[\u2014\u2013-]\s*)?(?=\S)" % (DECOR.pattern, DECOR.pattern), lambda m: m.group(1) + " \u2014 ", s)
    s = DECOR.sub("", s)
    s = s.replace("'", "\u2019")
    s = re.sub(r"\s+", " ", s).strip(" -\u2014|\u00b7")
    s = re.sub(r"\s*\[VRChat\]", "", s, flags=re.I)
    parts = SEP.split(s, maxsplit=1)
    title = parts[0].strip()
    sub = parts[1].split(" | ")[0].strip() if len(parts) > 1 else ""
    return smart_case(title), smart_case(sub)


def slug_for(product):
    s = re.sub(r"[^a-z0-9]+", "-", product["permalink"].lower()).strip("-")
    return s or hashlib.sha1(product["url"].encode()).hexdigest()[:10]


# ---------------------------------------------------------------- images

def save_images(slug, src_url, img_dir):
    body, ctype = http_get(src_url, accept="image/*")
    if not ctype.startswith("image/"):
        raise RuntimeError(f"not an image: {ctype}")
    tag = hashlib.sha1(src_url.encode()).hexdigest()[:8]
    try:
        from io import BytesIO
        from PIL import Image
    except ImportError:
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}.get(ctype.split(";")[0], "img")
        name = f"{slug}-{tag}.{ext}"
        (img_dir / name).write_bytes(body)
        return {"src": f"/drops/img/{name}", "srcset": None, "w": None, "h": None}
    im = Image.open(BytesIO(body))
    im.seek(0)
    im = im.convert("RGBA")
    base = Image.new("RGBA", im.size, (17, 16, 19, 255))
    im = Image.alpha_composite(base, im).convert("RGB")
    files = []
    for w in IMG_SIZES:
        w2 = min(w, im.width)
        h2 = round(im.height * w2 / im.width)
        name = f"{slug}-{tag}-{w}.webp"
        im.resize((w2, h2), Image.LANCZOS).save(img_dir / name, "WEBP", quality=80, method=6)
        files.append((name, w2, h2))
    big = files[-1]
    return {"src": f"/drops/img/{big[0]}",
            "srcset": ", ".join(f"/drops/img/{n} {w}w" for n, w, _ in files),
            "w": big[1], "h": big[2]}


# ---------------------------------------------------------------- render

def esc(s):
    return html.escape(s, quote=True)


def fmt_day(d):
    return f"{d.day} {d.strftime('%b %Y')}"


def card(d, where):
    day = dt.date.fromisoformat(d["date"])
    img = d.get("image") or {}
    pic = ""
    if img.get("src"):
        srcset = f' srcset="{img["srcset"]}" sizes="(min-width: 1100px) 300px, (min-width: 700px) 30vw, 46vw"' if img.get("srcset") else ""
        dims = f' width="{img["w"]}" height="{img["h"]}"' if img.get("w") else ""
        pic = f'<img src="{img["src"]}"{srcset}{dims} alt="{esc(d["title"])}" loading="lazy" decoding="async">'
    ev = f'click-drop-{d["slug"]}-{where}'
    kind = f'<span class="drop-kind">{esc(d["subtitle"])}</span>' if d["subtitle"] else ""
    return (f'<li class="drop"><a class="drop-link" href="{esc(d["url"])}" rel="noopener" data-goatcounter-click="{ev}">'
            f'<span class="drop-plate">{pic}</span>'
            f'<time class="drop-date" datetime="{d["date"]}">{fmt_day(day)}</time>'
            f'<span class="drop-name">{esc(d["title"])}</span>{kind}</a></li>')


def render_home(drops):
    items = "\n        ".join(card(d, "home") for d in drops[:HOME_COUNT])
    return f"""
  <section class="drops-home" id="drops" aria-labelledby="drops-title">
    <div class="sec-head">
      <h2 id="drops-title" class="sec-title">Latest drops</h2>
      <span class="divider" aria-hidden="true"></span>
      <p class="sec-lede">The newest pieces on the shelf. Straight to the store.</p>
    </div>
    <ul class="drop-grid" aria-label="Latest drops">
        {items}
    </ul>
    <a class="btn btn-ghost drops-all" href="/drops/" data-goatcounter-click="click-drops-all-home">View all drops {ARROW}</a>
  </section>
  """


def render_page(drops):
    groups, order = {}, []
    for d in drops:
        day = dt.date.fromisoformat(d["date"])
        key = day.strftime("%Y-%m")
        if key not in groups:
            groups[key] = (day.strftime("%B %Y"), [])
            order.append(key)
        groups[key][1].append(d)
    blocks = []
    for key in order:
        label, items = groups[key]
        lis = "\n        ".join(card(d, "drops") for d in items)
        blocks.append(f"""    <section class="drop-month" aria-labelledby="m-{key}">
      <h2 id="m-{key}" class="drop-month-title">{label} <span class="drop-month-count">{len(items)}</span></h2>
      <ul class="drop-grid">
        {lis}
      </ul>
    </section>""")
    ld = {"@context": "https://schema.org", "@type": "ItemList", "@id": SITE + "/drops/#list",
          "name": "davysh drops", "numberOfItems": len(drops),
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": d["url"], "name": d["title"]}
                              for i, d in enumerate(drops)]}
    count = f'<p class="drops-count"><strong>{len(drops)}</strong> drops on the record</p>'
    return ("\n" + f'    {count}\n' + "\n".join(blocks) +
            f'\n    <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}</script>\n    ')


def render_feed(drops):
    def pub(d):
        return format_datetime(dt.datetime.strptime(d["published"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc), usegmt=True)
    items = []
    for d in drops[:FEED_COUNT]:
        title = d["title"] + (f" \u2014 {d['subtitle']}" if d["subtitle"] else "")
        img = d.get("image") or {}
        enc = ""
        if img.get("src"):
            enc = f'\n      <media:thumbnail url="{esc(SITE + img["src"])}"/>'
        items.append(f"""    <item>
      <title>{esc(title)}</title>
      <link>{esc(d["url"])}</link>
      <guid isPermaLink="false">gumroad:{esc(d["id"])}</guid>
      <pubDate>{pub(d)}</pubDate>{enc}
    </item>""")
    last = pub(drops[0]) if drops else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>davysh drops</title>
    <link>{SITE}/drops/</link>
    <atom:link href="{SITE}/drops/feed.xml" rel="self" type="application/rss+xml"/>
    <description>New VRChat avatars, worlds and gear from davysh, newest first.</description>
    <language>en</language>
    <lastBuildDate>{last}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""


def replace_block(path, name, content):
    text = path.read_text(encoding="utf-8")
    start, end = f"<!-- drops:{name}:start -->", f"<!-- drops:{name}:end -->"
    i, j = text.find(start), text.find(end)
    if i < 0 or j < i:
        raise RuntimeError(f"markers {start} / {end} not found in {path}")
    new = text[: i + len(start)] + content + text[j:]
    if new != text:
        path.write_text(new, encoding="utf-8")


def update_sitemap(path, drops):
    """Move <lastmod> of / and /drops/ forward to the newest drop date (never backwards)."""
    if not drops or not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    newest = max(d["date"] for d in drops)

    def bump(m):
        return m.group(1) + max(m.group(2), newest) + m.group(3)
    new = re.sub(r"(<loc>https://davysh\.com/(?:drops/)?</loc>\s*<lastmod>)([^<]*)(</lastmod>)", bump, text)
    if new != text:
        path.write_text(new, encoding="utf-8")


# ---------------------------------------------------------------- main

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def build(root, offline):
    data_path = root / "drops.json"
    img_dir = root / "drops" / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    stored = load_json(data_path, {"drops": []})
    existing = {d["id"]: d for d in stored.get("drops", []) + stored.get("before_cutoff", [])}

    if offline:
        drops = list(existing.values())
    else:
        excl_raw = load_json(root / "drops-exclude.json", {}).get("exclude", [])
        exclude = {str(x).strip().lower() for x in excl_raw if str(x).strip()}
        products = fetch_storefront()
        log(f"{len(products)} products on the public storefront")
        if existing and len(products) < len(existing) / 2:
            raise RuntimeError(f"storefront lists {len(products)} products, {len(existing)} on record; "
                               "refusing to drop more than half")
        by_url = {d["url"].lower(): d for d in existing.values()}
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        drops = []
        for p in products:
            slug = slug_for(p)
            if {slug, p["url"].lower(), p["permalink"].lower()} & exclude:
                log(f"  excluded: {slug}")
                continue
            old = by_url.get(p["url"].lower(), {})
            pid, published, source = old.get("id"), old.get("published"), old.get("date_source")
            if not pid or source != "created_at":
                new_id, ts = fetch_public_json(p)
                time.sleep(0.3)
                pid = new_id or pid
                if ts:
                    published, source = ts, "created_at"
                elif not published:
                    published, source = now, "first_seen"
            pid = pid or "url:" + p["permalink"].lower()
            keys = {pid.lower(), slug, p["url"].lower(), p["permalink"].lower()}
            if keys & exclude:
                log(f"  excluded: {slug}")
                continue
            local = dt.datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).astimezone(DATE_TZ)
            if local.date() < CUTOFF:
                drops.append({"id": pid, "url": p["url"], "date": local.date().isoformat(),
                              "published": published, "date_source": source})
                continue
            title, subtitle = clean_name(p["name"])
            src = p.get("thumbnail_url")
            image = old.get("image")
            if src and (old.get("image_source") != src or not image or not (root / image["src"].lstrip("/")).exists()):
                try:
                    image = save_images(slug, src, img_dir)
                    log(f"  image saved: {slug}")
                except Exception as e:  # noqa: BLE001
                    log(f"  image failed for {slug}: {e}")
                    image, src = (old.get("image"), old.get("image_source"))
            elif not src:
                image = None
            drops.append({
                "id": pid, "slug": slug, "name": p["name"], "title": title, "subtitle": subtitle,
                "url": p["url"], "date": local.date().isoformat(), "published": published,
                "date_source": source, "image": image, "image_source": src,
            })

    drops.sort(key=lambda d: (d["published"], d["id"]), reverse=True)
    older = [{k: d[k] for k in ("id", "url", "date", "published", "date_source")}
             for d in drops if d["date"] < CUTOFF.isoformat()]
    drops = [d for d in drops if d["date"] >= CUTOFF.isoformat() and d.get("title")]

    # remove images no longer referenced
    keep = set()
    for d in drops:
        img = d.get("image") or {}
        for part in ([img.get("src")] + [s.split()[0] for s in (img.get("srcset") or "").split(", ") if s]):
            if part:
                keep.add(Path(part).name)
    for f in img_dir.iterdir():
        if f.is_file() and f.name not in keep:
            f.unlink()

    out = {"_about": "Generated by scripts/build_drops.py from the public Gumroad storefront. Dates: see date_source "
                     "(created_at = Gumroad product creation time; first_seen = first time this script saw it). "
                     "Do not edit by hand except to remove an entry; use drops-exclude.json to hide products. "
                     f"Only drops dated {CUTOFF.isoformat()} or later are listed; older ones are in before_cutoff.",
           "cutoff": CUTOFF.isoformat(), "count": len(drops), "drops": drops, "before_cutoff": older}
    text = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if not data_path.exists() or data_path.read_text(encoding="utf-8") != text:
        data_path.write_text(text, encoding="utf-8")

    replace_block(root / "index.html", "home", render_home(drops))
    replace_block(root / "drops" / "index.html", "page", render_page(drops))
    feed = root / "drops" / "feed.xml"
    ftext = render_feed(drops)
    if not feed.exists() or feed.read_text(encoding="utf-8") != ftext:
        feed.write_text(ftext, encoding="utf-8")
    update_sitemap(root / "sitemap.xml", drops)
    srcs = {}
    for d in drops:
        srcs[d["date_source"]] = srcs.get(d["date_source"], 0) + 1
    log(f"{len(older)} dated before {CUTOFF.isoformat()}, not listed")
    log(f"{len(drops)} drops written ({', '.join(f'{k}: {v}' for k, v in sorted(srcs.items()))})")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT, help="site root (default: repo root)")
    ap.add_argument("--offline", action="store_true", help="rebuild pages from drops.json without any network access")
    a = ap.parse_args()
    try:
        return build(a.root.resolve(), a.offline)
    except RuntimeError as e:
        log(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
