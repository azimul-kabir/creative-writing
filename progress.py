"""
Daily Creative Spark — progress tracker & portfolio
=====================================================

Each finished worksheet can be logged with a photo of the page, how much
was written (sentences, paragraphs, Vault words), which checklist habits
were managed, the child's own stars and face, and a note from a grown-up.

Entries live in a small SQLite database and photos in a folder, both in
the data directory, so they survive container rebuilds. This module also
works out the numbers shown on the Progress page (streaks, averages,
checklist hit rates) and draws the sentences chart as inline SVG.
"""

import datetime
import json
import sqlite3
from html import escape
from pathlib import Path

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
MOODS = ("happy", "okay", "sad")
MOOD_EMOJI = {"happy": "\U0001F60A", "okay": "\U0001F610", "sad": "\U0001F61F"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    written_on    TEXT NOT NULL,          -- YYYY-MM-DD
    topic         TEXT NOT NULL,
    writing_type  TEXT NOT NULL DEFAULT '',
    sentences     INTEGER,
    paragraphs    INTEGER,
    vault_words   INTEGER,
    checklist     TEXT NOT NULL DEFAULT '[]',   -- JSON: items managed
    effort        INTEGER,                      -- 1-5 stars
    mood          TEXT NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT '',
    photos        TEXT NOT NULL DEFAULT '[]',   -- JSON: file names
    created_at    TEXT NOT NULL
)
"""


class Store:
    def __init__(self, data_dir):
        self.db_path = Path(data_dir) / "progress.db"
        self.photo_dir = Path(data_dir) / "portfolio"
        self.photo_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(_SCHEMA)

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    def add(self, entry, photos=()):
        """Save an entry; photos are (original_filename, file-like) pairs.
        Returns the new entry's id."""
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO entries (written_on, topic, writing_type, sentences, paragraphs,"
                " vault_words, checklist, effort, mood, note, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry["written_on"], entry["topic"], entry.get("writing_type", ""),
                    entry.get("sentences"), entry.get("paragraphs"), entry.get("vault_words"),
                    json.dumps(entry.get("checklist", [])), entry.get("effort"),
                    entry.get("mood", ""), entry.get("note", ""),
                    datetime.datetime.now().isoformat(timespec="seconds"),
                ),
            )
            entry_id = cur.lastrowid
            names = []
            for i, (filename, stream) in enumerate(photos, 1):
                ext = Path(filename or "").suffix.lower()
                if ext not in PHOTO_EXTS:
                    continue
                name = f"{entry_id}_{i}{ext}"
                with open(self.photo_dir / name, "wb") as out:
                    while chunk := stream.read(1 << 16):
                        out.write(chunk)
                names.append(name)
            db.execute("UPDATE entries SET photos = ? WHERE id = ?", (json.dumps(names), entry_id))
        return entry_id

    def delete(self, entry_id):
        with self._connect() as db:
            row = db.execute("SELECT photos FROM entries WHERE id = ?", (entry_id,)).fetchone()
            if row is None:
                return False
            for name in json.loads(row["photos"]):
                (self.photo_dir / name).unlink(missing_ok=True)
            db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        return True

    def entries(self):
        """All entries, newest first, as plain dicts."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM entries ORDER BY written_on DESC, id DESC").fetchall()
        out = []
        for r in rows:
            e = dict(r)
            e["checklist"] = json.loads(e["checklist"])
            e["photos"] = json.loads(e["photos"])
            e["mood_emoji"] = MOOD_EMOJI.get(e["mood"], "")
            out.append(e)
        return out

    def photo_path(self, name):
        """The path of a stored photo, or None if the name isn't one."""
        path = (self.photo_dir / name).resolve()
        if path.parent != self.photo_dir.resolve() or not path.is_file():
            return None
        return path


# ----------------------------------------------------------------------
# Numbers for the Progress page
# ----------------------------------------------------------------------

def _streaks(dates, today):
    """(current, longest) runs of consecutive days with writing. The
    current streak still counts if the last day written was yesterday."""
    days = sorted(set(dates))
    if not days:
        return 0, 0
    longest = run = 1
    for prev, cur in zip(days, days[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)
    current = 0
    day = today if today in days else today - datetime.timedelta(days=1)
    day_set = set(days)
    while day in day_set:
        current += 1
        day -= datetime.timedelta(days=1)
    return current, longest


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def stats(entries, checklist_items, today=None):
    today = today or datetime.date.today()
    dates = [datetime.date.fromisoformat(e["written_on"]) for e in entries]
    current, longest = _streaks(dates, today)
    oldest_first = list(reversed(entries))
    with_sentences = [e["sentences"] for e in oldest_first if e["sentences"] is not None]

    # how often each checklist habit was managed, most-missed first
    rates = []
    if entries:
        for item in checklist_items:
            hits = sum(1 for e in entries if item in e["checklist"])
            rates.append({"item": item, "hits": hits, "pct": round(100 * hits / len(entries))})
        rates.sort(key=lambda r: (r["pct"], r["item"]))

    by_type = {}
    for e in entries:
        if e["writing_type"] and e["sentences"] is not None:
            by_type.setdefault(e["writing_type"], []).append(e["sentences"])

    return {
        "total": len(entries),
        "this_month": sum(1 for d in dates if (d.year, d.month) == (today.year, today.month)),
        "current_streak": current,
        "longest_streak": longest,
        "recent_avg": _avg(with_sentences[-5:]),
        "first_avg": _avg(with_sentences[:5]) if len(with_sentences) >= 10 else None,
        "checklist_rates": rates,
        "by_type": sorted(((t, _avg(v), len(v)) for t, v in by_type.items()),
                          key=lambda x: -x[1]),
    }


# ----------------------------------------------------------------------
# Sentences-per-story chart (inline SVG; one series, so no legend)
# ----------------------------------------------------------------------

BAR = "#2563EB"        # the app's blue; passes the palette checks on white
GRID = "#E5E7EB"
AXIS_TEXT = "#6B7280"
GOAL = "#9CA3AF"


def sentences_chart_svg(entries, goal=(10, 15), limit=30):
    points = [e for e in reversed(entries) if e["sentences"] is not None][-limit:]
    if not points:
        return ""
    W, H = 640, 220
    left, right, top, bottom = 34, 10, 12, 30
    plot_w, plot_h = W - left - right, H - top - bottom
    peak = max(max(p["sentences"] for p in points), goal[1])
    y_max = ((peak + 4) // 5) * 5
    y = lambda v: top + plot_h * (1 - v / y_max)

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" class="chart" '
             f'aria-label="Sentences written in each of the last {len(points)} logged stories">']
    for v in range(0, y_max + 1, 5):
        parts.append(f'<line x1="{left}" x2="{W - right}" y1="{y(v):.1f}" y2="{y(v):.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{left - 6}" y="{y(v) + 3.5:.1f}" text-anchor="end" '
                     f'font-size="10" fill="{AXIS_TEXT}">{v}</text>')
    for g in goal:
        parts.append(f'<line x1="{left}" x2="{W - right}" y1="{y(g):.1f}" y2="{y(g):.1f}" '
                     f'stroke="{GOAL}" stroke-width="1" stroke-dasharray="4 3"/>')
    parts.append(f'<text x="{W - right}" y="{y(goal[1]) - 4:.1f}" text-anchor="end" '
                 f'font-size="10" fill="{AXIS_TEXT}">goal {goal[0]}–{goal[1]}</text>')

    slot = plot_w / len(points)
    bar_w = max(4.0, min(18.0, slot - 2))   # >= 2px gap between bars
    label_every = max(1, round(len(points) / 8))
    for i, p in enumerate(points):
        cx = left + slot * (i + 0.5)
        x0, x1 = cx - bar_w / 2, cx + bar_w / 2
        y0, yb = y(p["sentences"]), y(0)
        r = min(4.0, bar_w / 2, max(0.0, yb - y0))
        d = (f"M{x0:.1f},{yb:.1f} L{x0:.1f},{y0 + r:.1f} Q{x0:.1f},{y0:.1f} {x0 + r:.1f},{y0:.1f} "
             f"L{x1 - r:.1f},{y0:.1f} Q{x1:.1f},{y0:.1f} {x1:.1f},{y0 + r:.1f} L{x1:.1f},{yb:.1f} Z")
        day = datetime.date.fromisoformat(p["written_on"])
        tip = escape(f"{day.day} {day:%b}: {p['topic']} — {p['sentences']} sentences")
        # a full-height transparent hit area makes thin bars easy to hover
        parts.append(f'<g class="bar"><title>{tip}</title>'
                     f'<rect x="{left + slot * i:.1f}" y="{top}" width="{slot:.1f}" height="{plot_h}" fill="transparent"/>'
                     f'<path d="{d}" fill="{BAR}"/></g>')
        if i % label_every == 0 or i == len(points) - 1:
            parts.append(f'<text x="{cx:.1f}" y="{H - 10}" text-anchor="middle" font-size="10" '
                         f'fill="{AXIS_TEXT}">{day.day} {day:%b}</text>')
    parts.append("</svg>")
    return "".join(parts)
