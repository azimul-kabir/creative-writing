#!/usr/bin/env python3
"""
Daily Creative Spark — worksheet generator (core module)
==========================================================

Recreates the "Daily Creative Spark" writing-practice worksheet design as a
one-page A4 PDF.

This module is used two ways:

1. Imported by app.py (the web app) — parse_prompt() turns the free-text
   prompt you paste into the web form into a config dict, generate_bytes()
   renders it to PDF bytes in memory.

2. Run directly as a CLI for local/offline use:

       python3 worksheet.py my_prompt.txt
       python3 worksheet.py my_config.json

   With no argument it renders the built-in DAY 2 example. Text files are
   parsed with parse_prompt(); .json files are loaded as a config dict
   directly (same fields as parse_prompt() produces — see CONFIG FIELDS).

CONFIG FIELDS
-------------
student_name      : str
class_label       : str   e.g. "Class II - Cambridge"
day_label         : str   e.g. "Day 2 (Tuesday)" — used for the filename
category          : str   optional, e.g. "Sensory Description"
goal              : str   e.g. "10-15 sentences in 3 paragraphs"
focus_skill       : str   optional
topic_title       : str
prompt_starter    : str   the quoted opening line
chat_questions    : list of [label, question]
word_vault        : list of str, or [word, meaning] pairs — a meaning is
                    printed in small text under the word's chip
vault_instruction : str   e.g. "Use at least 3!" / "Aim for 3"
challenge         : str   optional
checklist_items   : list of str
plan_labels       : list of str or [label, hint] — the "Plan it" boxes,
                    default Beginning / Middle / End; [] hides the strip
story_lines       : int   page-1 writing rows; default fills the space
line_spacing_mm   : float gap between ruled lines, default 9
guide_lines       : bool  dotted mid-line for letter sizing, default off
pages             : int   2 (default) adds a full lined writing page with
                    an "Edit & improve" box; 1 = single sheet
footer_left       : str
footer_right      : str
"""

import io
import json
import math
import os
import re
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

# ----------------------------------------------------------------------
# Palette
# ----------------------------------------------------------------------
NAVY = HexColor("#1E40AF")
BLUE = HexColor("#2563EB")
BLUE_LIGHT_BG = HexColor("#EFF6FF")
BLUE_BORDER = HexColor("#93C5FD")
GREEN = HexColor("#16A34A")
AMBER = HexColor("#D97706")
PURPLE = HexColor("#7C3AED")
PURPLE_BG = HexColor("#F5F3FF")
STAR_GOLD = HexColor("#F59E0B")
CHIP_BG = HexColor("#DBEAFE")
CHIP_TEXT = HexColor("#1D4ED8")
INK = HexColor("#1F2937")
GRAY = HexColor("#6B7280")
LINE_GRAY = HexColor("#4B5563")
DOT_GRAY = HexColor("#B9C1CC")
BOX_BORDER = HexColor("#D1D5DB")
PAGE_BORDER = HexColor("#E5E7EB")

PAGE_W, PAGE_H = A4
MARGIN = 40
MM = 72 / 25.4

# ----------------------------------------------------------------------
# Site-wide defaults — override per-request from the web form, or edit
# these (or set the matching environment variables in docker-compose.yml).
# ----------------------------------------------------------------------
DEFAULTS = {
    "student_name": os.environ.get("STUDENT_NAME", "Adeeba"),
    "class_label": os.environ.get("CLASS_LABEL", "Class II \u2022 Cambridge"),
    "goal": os.environ.get("DEFAULT_GOAL", "10\u201315 sentences in 3 paragraphs"),
    "vault_instruction": "Use at least 3!",
    # Cambridge Stage 3/4 writing habits (age 8-9)
    "checklist_items": [
        "Capital letters & full stops",
        "Used 3 Vault words",
        "Joined ideas: and, but, so, because",
        "New paragraph: start, middle, end",
        "Speech marks when people talk",
        "Read it back & fixed mistakes",
    ],
    "plan_labels": [
        ["Beginning", "Who? Where? When?"],
        ["Middle", "What goes wrong?"],
        ["End", "How is it fixed? Feelings?"],
    ],
    "story_lines": None,       # page-1 writing rows; None = fill the space
    "line_spacing_mm": 9,      # ruled-line gap; ~9 mm suits age 8-9
    "guide_lines": False,      # dotted mid-line for letter sizing (younger writers)
    "pages": int(os.environ.get("PAGES", "2")),  # 2 = add a full writing page
    "footer_left": os.environ.get(
        "FOOTER_LEFT", "Scholastica Primary English Support \u2022 Stage 3"
    ),
    "footer_right": os.environ.get("FOOTER_RIGHT", "A4 Daily Writing Challenge Worksheet"),
}


def wrap_text(text, font, size, max_width):
    """Greedy word-wrap; returns a list of lines that fit max_width."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if stringWidth(trial, font, size) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


MEANING_FONT = "Helvetica"
MEANING_SIZE = 6.8
MEANING_LEAD = 8

_VAULT_ENTRY_RE = re.compile(r"^(.*?)\s*(?:\((.*)\)|(?:=|:|\s[-–—])\s*(.+))\s*$")


def split_vault_entry(entry):
    """A Word Vault entry is a plain word, a [word, meaning] pair, or a
    string like "drenched (very wet)" / "drenched = very wet".
    Returns (word, meaning) with meaning "" when there isn't one."""
    if isinstance(entry, (list, tuple)):
        word = str(entry[0]) if entry else ""
        meaning = str(entry[1]) if len(entry) > 1 else ""
        return word.strip(), meaning.strip()
    text = str(entry).strip()
    m = _VAULT_ENTRY_RE.match(text)
    if m and m.group(1):
        return m.group(1).strip(), (m.group(2) or m.group(3) or "").strip()
    return text, ""


def rounded_rect(c, x, y, w, h, r, fill=None, stroke=None, line_width=1):
    c.saveState()
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(line_width)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke is not None else 0,
                fill=1 if fill is not None else 0)
    c.restoreState()


def draw_header(c, cfg, top_y):
    c.setStrokeColor(PAGE_BORDER)
    c.setLineWidth(1)
    c.line(MARGIN, top_y, PAGE_W - MARGIN, top_y)

    baseline = top_y - 23

    title_text = "Daily Creative Spark"
    title_size = 16.5
    c.setFont("Helvetica-Bold", title_size)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, baseline, title_text)
    title_w = stringWidth(title_text, "Helvetica-Bold", title_size)

    field_size = 8.5
    c.setFont("Helvetica", field_size)
    c.setFillColor(INK)
    right_edge = PAGE_W - MARGIN
    y = baseline + 1

    def right_field(label, value, x_end, dotted_width=0, bold_value=False):
        s = f"{label} "
        w = stringWidth(s, "Helvetica", field_size)
        val_w = stringWidth(value, "Helvetica-Bold" if bold_value else "Helvetica", field_size) if value else dotted_width
        x_start = x_end - w - val_w
        c.setFont("Helvetica", field_size)
        c.setFillColor(INK)
        c.drawString(x_start, y, s)
        vx = x_start + w
        if value:
            c.setFont("Helvetica-Bold" if bold_value else "Helvetica", field_size)
            c.drawString(vx, y, value)
        elif dotted_width:
            c.setFont("Helvetica", field_size)
            c.setFillColor(GRAY)
            c.drawString(vx, y, "." * int(dotted_width / 3.0))
        return x_start

    day_x = right_field("Day:", "", right_edge - 8, dotted_width=38)
    date_x = right_field("Date:", "", day_x - 20, dotted_width=55)
    writer_x = right_field("Writer:", cfg.get("student_name", ""), date_x - 16, bold_value=True)

    badge_text = cfg.get("class_label", "") or cfg.get("day_label", "")
    badge_font_size = 8.5
    badge_pad_x = 7
    badge_x = MARGIN + title_w + 12
    available = max(writer_x - 12 - badge_x, 40)
    badge_w = stringWidth(badge_text, "Helvetica-Bold", badge_font_size) + 2 * badge_pad_x
    while badge_w > available and badge_font_size > 6.5:
        badge_font_size -= 0.4
        badge_w = stringWidth(badge_text, "Helvetica-Bold", badge_font_size) + 2 * badge_pad_x
    badge_w = min(badge_w, available)
    badge_h = 16
    badge_y = baseline - 2.5
    rounded_rect(c, badge_x, badge_y, badge_w, badge_h, badge_h / 2,
                 fill=BLUE_LIGHT_BG, stroke=BLUE_BORDER, line_width=1)
    c.setFont("Helvetica-Bold", badge_font_size)
    c.setFillColor(BLUE)
    c.drawString(badge_x + badge_pad_x, badge_y + 4.8, badge_text)

    rule_y = top_y - 33
    c.setStrokeColor(NAVY)
    c.setLineWidth(2.2)
    c.line(MARGIN, rule_y, PAGE_W - MARGIN, rule_y)
    return rule_y


def draw_quest_box(c, cfg, top_y):
    x, w = MARGIN, PAGE_W - 2 * MARGIN
    pad = 16
    text_w = w - 2 * pad

    # Long topics / starters / focus skills wrap onto extra lines and the
    # box grows to fit, instead of running off the page.
    title_lines = wrap_text(cfg.get("topic_title", ""), "Helvetica-Bold", 12.5, text_w) or [""]
    quote = cfg.get("prompt_starter", "")
    if quote and not quote.startswith("“"):
        quote = f"“{quote}”"
    quote_lines = wrap_text(quote, "Helvetica-Oblique", 9.5, text_w) or [""]
    focus = cfg.get("focus_skill")
    focus_lines = wrap_text(f"Focus skill: {focus}", "Helvetica-Oblique", 8.3, text_w) if focus else []

    box_h = (41 + 15 * (len(title_lines) - 1) + 12 * (len(quote_lines) - 1)
             + 12 * len(focus_lines) + (5 if focus_lines else 6))
    y = top_y - box_h

    rounded_rect(c, x, y, w, box_h, 4, fill=BLUE_LIGHT_BG)
    c.setFillColor(BLUE)
    c.rect(x, y, 4, box_h, stroke=0, fill=1)

    ty = top_y - 11
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(BLUE)
    c.drawString(x + pad, ty, "TODAY'S WRITING QUEST")

    goal = cfg.get("goal", "")
    category = cfg.get("category", "")
    goal_text = f"Goal: {goal}" if goal else ""
    if category:
        goal_text = f"{goal_text}  \u2022  {category}" if goal_text else category
    if goal_text:
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(INK)
        c.drawRightString(x + w - pad, ty, goal_text)

    ty -= 16
    c.setFont("Helvetica-Bold", 12.5)
    c.setFillColor(INK)
    for i, line in enumerate(title_lines):
        if i:
            ty -= 15
        c.drawString(x + pad, ty, line)

    ty -= 14
    c.setFont("Helvetica-Oblique", 9.5)
    c.setFillColor(HexColor("#374151"))
    for i, line in enumerate(quote_lines):
        if i:
            ty -= 12
        c.drawString(x + pad, ty, line)

    c.setFont("Helvetica-Oblique", 8.3)
    c.setFillColor(GRAY)
    for line in focus_lines:
        ty -= 12
        c.drawString(x + pad, ty, line)

    return y


def draw_two_column(c, cfg, top_y):
    gap = 16
    col_w = (PAGE_W - 2 * MARGIN - gap) / 2
    left_x = MARGIN
    right_x = MARGIN + col_w + gap

    chat_qs = cfg.get("chat_questions", [])
    vault_words = cfg.get("word_vault", [])
    challenge = cfg.get("challenge", "")

    chat_line_h = 13
    chat_pad = 16
    extra_wrap_lines = 0
    for label, question in chat_qs:
        prefix = f"{label}  " if label else "•  "
        pw = stringWidth(prefix, "Helvetica-Bold", 9.0)
        avail = col_w - 2 * chat_pad - pw
        qlines = wrap_text(question, "Helvetica", 9.0, avail) or [""]
        extra_wrap_lines += len(qlines) - 1
    chat_body_h = 22 + len(chat_qs) * chat_line_h + extra_wrap_lines * 11

    chip_pad_x, chip_gap, chip_h = 9, 7, 20
    chip_font = "Helvetica-Bold"
    chip_size = 8.7
    max_chip_w = col_w - 32

    # Each item is (word, chip_w, slot_w, meaning_lines): the slot is wide
    # enough for the chip and for its meaning wrapped underneath.
    items = []
    for entry in vault_words:
        word, meaning = split_vault_entry(entry)
        chip_w = stringWidth(word, chip_font, chip_size) + 2 * chip_pad_x
        slot_w = chip_w
        m_lines = []
        if meaning:
            meaning_w = stringWidth(meaning, MEANING_FONT, MEANING_SIZE)
            slot_w = min(max(chip_w, min(meaning_w, 96)), max_chip_w)
            m_lines = wrap_text(meaning, MEANING_FONT, MEANING_SIZE, slot_w)
        items.append((word, chip_w, slot_w, m_lines))

    lines, cur_line, cur_w = [], [], 0
    for item in items:
        sw = item[2]
        if cur_w + sw + (chip_gap if cur_line else 0) > max_chip_w and cur_line:
            lines.append(cur_line)
            cur_line, cur_w = [], 0
        cur_line.append(item)
        cur_w += sw + (chip_gap if len(cur_line) > 1 else 0)
    if cur_line:
        lines.append(cur_line)

    def row_h(row):
        n_meaning = max(len(it[3]) for it in row)
        return chip_h + 5 + (2 + n_meaning * MEANING_LEAD if n_meaning else 0)

    vault_body_h = 26 + sum(row_h(row) for row in lines)
    challenge_lines = []
    if challenge:
        challenge_lines = wrap_text(f"Challenge: {challenge}", "Helvetica-Oblique", 8.3, col_w - 32)
        vault_body_h += 5 + len(challenge_lines) * 11

    box_h = max(chat_body_h, vault_body_h, 60)
    y = top_y - box_h

    # ----- Chat & Think box -----
    rounded_rect(c, left_x, y, col_w, box_h, 4, stroke=BOX_BORDER, line_width=1)
    c.setFillColor(GREEN)
    c.rect(left_x, y, 4, box_h, stroke=0, fill=1)
    pad = 16
    ty = top_y - 17
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(INK)
    c.drawString(left_x + pad, ty, "3-MINUTE CHAT & THINK")
    ty -= 17
    c.setFont("Helvetica", 9.0)
    for label, question in chat_qs:
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9.0)
        prefix = f"{label}  " if label else "\u2022  "
        c.drawString(left_x + pad, ty, prefix)
        pw = stringWidth(prefix, "Helvetica-Bold", 9.0)
        c.setFont("Helvetica", 9.0)
        avail = col_w - 2 * pad - pw
        qlines = wrap_text(question, "Helvetica", 9.0, avail)
        if not qlines:
            qlines = [""]
        c.drawString(left_x + pad + pw, ty, qlines[0])
        for extra in qlines[1:]:
            ty -= 11
            c.drawString(left_x + pad + pw, ty, extra)
        ty -= chat_line_h

    # ----- Word Vault box -----
    rounded_rect(c, right_x, y, col_w, box_h, 4, stroke=BOX_BORDER, line_width=1)
    c.setFillColor(AMBER)
    c.rect(right_x, y, 4, box_h, stroke=0, fill=1)
    ty = top_y - 17
    label = "WRITER'S WORD VAULT"
    instr = cfg.get("vault_instruction") or "Use at least 3!"
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(INK)
    c.drawString(right_x + pad, ty, f"{label} ({instr.upper()})")

    ty -= 19
    for row in lines:
        rh_y = ty - chip_h + 5
        cx = right_x + pad
        for word, chip_w, slot_w, m_lines in row:
            chip_x = cx + (slot_w - chip_w) / 2
            rounded_rect(c, chip_x, rh_y, chip_w, chip_h, chip_h / 2, fill=CHIP_BG)
            c.setFont(chip_font, chip_size)
            c.setFillColor(CHIP_TEXT)
            c.drawCentredString(cx + slot_w / 2, rh_y + 6, word)
            my = rh_y - 2 - MEANING_SIZE
            c.setFont(MEANING_FONT, MEANING_SIZE)
            c.setFillColor(GRAY)
            for ml in m_lines:
                c.drawCentredString(cx + slot_w / 2, my, ml)
                my -= MEANING_LEAD
            cx += slot_w + chip_gap
        ty -= row_h(row)

    if challenge_lines:
        ty -= 3
        c.setFont("Helvetica-Oblique", 8.3)
        c.setFillColor(GRAY)
        for cl in challenge_lines:
            c.drawString(right_x + pad, ty, cl)
            ty -= 11

    return y


def draw_plan_strip(c, cfg, top_y):
    """A row of "Plan it" boxes (Beginning -> Middle -> End by default) for
    a quick sketch or a few words before writing."""
    labels = cfg.get("plan_labels") or []
    x, w = MARGIN, PAGE_W - 2 * MARGIN
    box_h = 66
    y = top_y - box_h

    rounded_rect(c, x, y, w, box_h, 4, stroke=BOX_BORDER, line_width=1)
    c.setFillColor(PURPLE)
    c.rect(x, y, 4, box_h, stroke=0, fill=1)

    pad = 16
    ty = top_y - 15
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(INK)
    c.drawString(x + pad, ty, "PLAN IT FIRST")
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(GRAY)
    c.drawRightString(x + w - pad, ty, "Draw a little picture or write 2–3 words in each box")

    arrow_gap = 18
    n = len(labels)
    inner_w = w - 2 * pad
    cell_w = (inner_w - (n - 1) * arrow_gap) / n
    cell_top = ty - 7
    cell_bottom = y + 8
    cell_h = cell_top - cell_bottom
    cx = x + pad
    for i, entry in enumerate(labels):
        label, hint = (entry[0], entry[1] if len(entry) > 1 else "") \
            if isinstance(entry, (list, tuple)) else (entry, "")
        rounded_rect(c, cx, cell_bottom, cell_w, cell_h, 4, fill=PURPLE_BG)
        c.setFont("Helvetica-Bold", 7.8)
        c.setFillColor(PURPLE)
        head = f"{i + 1}  {label}"
        c.drawString(cx + 6, cell_top - 10, head)
        if hint:
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(GRAY)
            c.drawString(cx + 6 + stringWidth(head + "  ", "Helvetica-Bold", 7.8),
                         cell_top - 10, hint)
        if i < n - 1:
            ax = cx + cell_w + 4
            ay = cell_bottom + cell_h / 2
            c.setStrokeColor(PURPLE)
            c.setLineWidth(1.2)
            c.line(ax, ay, ax + arrow_gap - 10, ay)
            p = c.beginPath()
            p.moveTo(ax + arrow_gap - 8, ay)
            p.lineTo(ax + arrow_gap - 12, ay + 3)
            p.lineTo(ax + arrow_gap - 12, ay - 3)
            p.close()
            c.setFillColor(PURPLE)
            c.drawPath(p, stroke=0, fill=1)
        cx += cell_w + arrow_gap

    return y


def draw_story_area(c, cfg, top_y, bottom_limit, title, hint="", n_rows=None,
                    corner_note=""):
    """Lined writing box from top_y down to bottom_limit. n_rows=None fits
    as many rows as line_spacing_mm allows; the last rule sits on the
    bottom of the box."""
    x, w = MARGIN, PAGE_W - 2 * MARGIN
    header_h = 19
    box_h = top_y - bottom_limit
    y = bottom_limit

    rounded_rect(c, x, y, w, box_h, 4, stroke=BOX_BORDER, line_width=1)

    pad = 16
    ty = top_y - 13
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(x + pad, ty, title)

    if hint:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(GRAY)
        c.drawRightString(x + w - pad, ty, hint)

    top_pad = 8
    bottom_pad = 16 if corner_note else 12
    usable_h = box_h - header_h - top_pad - bottom_pad
    if not n_rows:
        n_rows = int(usable_h // (float(cfg.get("line_spacing_mm") or 9) * MM))
    n_rows = max(int(n_rows), 1)
    step = usable_h / n_rows
    line_y = top_y - header_h - top_pad
    guides = cfg.get("guide_lines")

    # with no guides, the top rule is just the first line's ceiling, so
    # it's drawn lighter
    for i in range(n_rows + 1):
        base_y = line_y - i * step
        c.setStrokeColor(LINE_GRAY if (i or guides) else BOX_BORDER)
        c.setLineWidth(0.8)
        c.line(x + pad, base_y, x + w - pad, base_y)
        if i > 0 and guides:
            dotted_y = base_y + step * 0.42
            c.setStrokeColor(DOT_GRAY)
            c.setDash(1, 2)
            c.line(x + pad, dotted_y, x + w - pad, dotted_y)
            c.setDash()

    if corner_note:
        c.setFont("Helvetica-Bold", 7.8)
        c.setFillColor(BLUE)
        c.drawRightString(x + w - pad, y + 5, corner_note)

    return y


def draw_star(c, cx, cy, r, stroke, line_width=1):
    """Outlined five-point star, left empty for colouring in."""
    p = c.beginPath()
    for k in range(10):
        rad = r if k % 2 == 0 else r * 0.42
        ang = math.radians(90 + k * 36)
        px, py = cx + rad * math.cos(ang), cy + rad * math.sin(ang)
        if k == 0:
            p.moveTo(px, py)
        else:
            p.lineTo(px, py)
    p.close()
    c.setStrokeColor(stroke)
    c.setLineWidth(line_width)
    c.setLineJoin(1)
    c.drawPath(p, stroke=1, fill=0)


def draw_face(c, cx, cy, r, mood):
    """Outlined face for circling/colouring: mood is 'happy', 'okay' or 'sad'."""
    c.setStrokeColor(LINE_GRAY)
    c.setLineWidth(0.9)
    c.circle(cx, cy, r, stroke=1, fill=0)
    c.setFillColor(LINE_GRAY)
    c.circle(cx - r * 0.35, cy + r * 0.25, r * 0.11, stroke=0, fill=1)
    c.circle(cx + r * 0.35, cy + r * 0.25, r * 0.11, stroke=0, fill=1)
    mw = r * 0.5
    if mood == "happy":
        c.arc(cx - mw, cy - r * 0.6, cx + mw, cy + r * 0.1, 200, 140)
    elif mood == "sad":
        c.arc(cx - mw, cy - r * 0.75, cx + mw, cy - r * 0.05, 20, 140)
    else:
        c.line(cx - mw * 0.8, cy - r * 0.35, cx + mw * 0.8, cy - r * 0.35)


FOOTER_PANEL_H = 70


def draw_footer_panel(c, cfg, top_y):
    x, w = MARGIN, PAGE_W - 2 * MARGIN
    box_h = FOOTER_PANEL_H
    y = top_y - box_h
    rounded_rect(c, x, y, w, box_h, 4, stroke=BOX_BORDER, line_width=1)

    pad = 16
    split = x + w * 0.64
    c.setStrokeColor(BOX_BORDER)
    c.setLineWidth(1)
    c.line(split, y + 7, split, y + box_h - 7)

    ty = top_y - 14
    name = cfg.get("student_name", "Writer")
    c.setFont("Helvetica-Bold", 8.7)
    c.setFillColor(INK)
    c.drawString(x + pad, ty, f"{name.upper()}'S DETECTIVE CHECKLIST")

    items = cfg.get("checklist_items") or DEFAULTS["checklist_items"]
    half = (len(items) + 1) // 2
    col1 = items[:half]
    col2 = items[half:]
    box_sz = 8.5
    row_h = 14.5
    cy = ty - 17

    left_region_w = split - x
    col_gap = 10
    col_w = (left_region_w - 2 * pad - col_gap) / 2
    col1_x = x + pad
    col2_x = col1_x + col_w + col_gap

    def draw_checks(items_col, cx):
        yy = cy
        for it in items_col:
            c.setStrokeColor(GRAY)
            c.setLineWidth(1)
            c.rect(cx, yy - 1.5, box_sz, box_sz, stroke=1, fill=0)
            c.setFillColor(INK)
            text_w = col_w - box_sz - 6
            size = 8
            while stringWidth(it, "Helvetica", size) > text_w and size > 6.8:
                size -= 0.2
            c.setFont("Helvetica", size)
            it_lines = wrap_text(it, "Helvetica", size, text_w) or [it]
            c.drawString(cx + box_sz + 6, yy, it_lines[0])
            for extra in it_lines[1:]:
                yy -= 9
                c.drawString(cx + box_sz + 6, yy, extra)
            yy -= row_h

    draw_checks(col1, col1_x)
    draw_checks(col2, col2_x)

    # Right side: things for the child to colour / circle herself.
    rx = split + 14
    label_font, label_size = "Helvetica-Bold", 8.7
    icons_x = rx + max(stringWidth(t, label_font, label_size)
                       for t in ("My effort:", "Writing felt:")) + 10

    c.setFont(label_font, label_size)
    c.setFillColor(INK)
    c.drawString(rx, ty, "My effort:")
    for k in range(5):
        draw_star(c, icons_x + 6 + k * 16, ty + 3, 6.3, STAR_GOLD, line_width=1.1)

    fy = ty - 19
    c.setFont(label_font, label_size)
    c.setFillColor(INK)
    c.drawString(rx, fy, "Writing felt:")
    for k, mood in enumerate(("happy", "okay", "sad")):
        draw_face(c, icons_x + 6 + k * 20, fy + 3, 6.8, mood)

    c.setFont("Helvetica", 8.3)
    c.setFillColor(GRAY)
    c.drawString(rx, ty - 39, "Best word I used: " + "." * 24)

    return y


def draw_continued_header(c, cfg, top_y):
    """Slim page-2 header: title, writer, date, and the topic again."""
    c.setStrokeColor(PAGE_BORDER)
    c.setLineWidth(1)
    c.line(MARGIN, top_y, PAGE_W - MARGIN, top_y)

    baseline = top_y - 20
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, baseline, "Daily Creative Spark")
    tw = stringWidth("Daily Creative Spark", "Helvetica-Bold", 13)
    c.setFont("Helvetica", 9)
    c.setFillColor(GRAY)
    c.drawString(MARGIN + tw + 8, baseline, "\u2022  page 2")

    name = cfg.get("student_name", "")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(INK)
    right = PAGE_W - MARGIN
    c.drawRightString(right, baseline, "Date: " + "." * 18)
    date_w = stringWidth("Date: " + "." * 18, "Helvetica", 8.5)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawRightString(right - date_w - 18, baseline, name)
    c.setFont("Helvetica", 8.5)
    c.drawRightString(right - date_w - 18 - stringWidth(name, "Helvetica-Bold", 8.5),
                      baseline, "Writer: ")

    rule_y = top_y - 29
    c.setStrokeColor(NAVY)
    c.setLineWidth(2.2)
    c.line(MARGIN, rule_y, PAGE_W - MARGIN, rule_y)

    topic = cfg.get("topic_title", "")
    if topic:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(INK)
        lines = wrap_text(topic, "Helvetica-Bold", 11, PAGE_W - 2 * MARGIN) or [""]
        ty = rule_y - 16
        c.drawString(MARGIN, ty, lines[0])
        return ty - 9
    return rule_y - 9


EDIT_PANEL_H = 84


def draw_edit_panel(c, cfg, top_y):
    """Page-2 "Edit & improve" box: upgrade two words, count sentences and
    paragraphs, and a line for a grown-up's comment."""
    x, w = MARGIN, PAGE_W - 2 * MARGIN
    box_h = EDIT_PANEL_H
    y = top_y - box_h
    rounded_rect(c, x, y, w, box_h, 4, fill=BLUE_LIGHT_BG)
    c.setFillColor(GREEN)
    c.rect(x, y, 4, box_h, stroke=0, fill=1)

    pad = 16
    split = x + w * 0.5
    ty = top_y - 15
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(INK)
    c.drawString(x + pad, ty, "EDIT & IMPROVE")
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(GRAY)
    c.drawString(x + pad + stringWidth("EDIT & IMPROVE  ", "Helvetica-Bold", 9.5), ty,
                 "Read your story out loud first!")

    # left: upgrade two plain words
    c.setFont("Helvetica", 8.5)
    c.setFillColor(INK)
    c.drawString(x + pad, ty - 18, "Swap 2 plain words for stronger ones:")
    for k in range(2):
        ry = ty - 38 - k * 18
        c.setFont("Helvetica", 8.5)
        c.setFillColor(GRAY)
        c.drawString(x + pad, ry, "." * 26)
        ax = x + pad + stringWidth("." * 26, "Helvetica", 8.5) + 8
        c.setStrokeColor(GREEN)
        c.setLineWidth(1.2)
        c.line(ax, ry + 3, ax + 14, ry + 3)
        p = c.beginPath()
        p.moveTo(ax + 18, ry + 3)
        p.lineTo(ax + 13, ry + 6)
        p.lineTo(ax + 13, ry)
        p.close()
        c.setFillColor(GREEN)
        c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(GRAY)
        c.drawString(ax + 26, ry, "." * 26)

    # right: counts and a grown-up's comment
    rx = split + 14
    c.setFont("Helvetica", 8.5)
    c.setFillColor(INK)
    c.drawString(rx, ty - 18, "I wrote ........ sentences in ........ paragraphs.")
    c.drawString(rx, ty - 38, "Grown-up's comment:")
    c.setFillColor(GRAY)
    cw = stringWidth("Grown-up's comment: ", "Helvetica", 8.5)
    dots = int((x + w - pad - rx - cw) / stringWidth(".", "Helvetica", 8.5))
    c.drawString(rx + cw, ty - 38, "." * dots)
    full = int((x + w - pad - rx) / stringWidth(".", "Helvetica", 8.5))
    c.drawString(rx, ty - 56, "." * full)

    return y


def draw_page_footer(c, cfg, bottom_y):
    x = MARGIN
    w = PAGE_W - 2 * MARGIN
    c.setStrokeColor(PAGE_BORDER)
    c.setDash(1, 2)
    c.setLineWidth(0.8)
    c.line(x, bottom_y, x + w, bottom_y)
    c.setDash()
    c.setFont("Helvetica", 8)
    c.setFillColor(GRAY)
    c.drawString(x, bottom_y - 12, cfg.get("footer_left", ""))
    c.drawRightString(x + w, bottom_y - 12, cfg.get("footer_right", ""))


def _render(c, cfg):
    c.setTitle(f"Daily Creative Spark - {cfg.get('day_label', '')}".strip())
    two_pages = int(cfg.get("pages") or 1) >= 2
    name = cfg.get("student_name", "Writer")

    # ----- page 1: the quest, ideas, plan, and the start of the story -----
    top_y = PAGE_H - MARGIN
    rule_y = draw_header(c, cfg, top_y)
    y = draw_quest_box(c, cfg, rule_y - 9)
    y = draw_two_column(c, cfg, y - 9)
    if cfg.get("plan_labels"):
        y = draw_plan_strip(c, cfg, y - 9)
    story_bottom = MARGIN + 23 + FOOTER_PANEL_H + 5
    y = draw_story_area(
        c, cfg, y - 9, story_bottom, f"{name}'s Story",
        hint="Start a new paragraph for the middle and the end",
        n_rows=cfg.get("story_lines"),
        corner_note="Keep going on page 2  \u00bb" if two_pages else "",
    )
    y2 = draw_footer_panel(c, cfg, y - 5)
    draw_page_footer(c, cfg, y2 - 8)
    c.showPage()

    # ----- page 2: more writing space + edit & improve -----
    if two_pages:
        y = draw_continued_header(c, cfg, PAGE_H - MARGIN)
        story_bottom = MARGIN + 23 + EDIT_PANEL_H + 5
        y = draw_story_area(c, cfg, y, story_bottom, f"{name}'s Story (continued)",
                            hint="Remember: new paragraph = new line, start a little in")
        y2 = draw_edit_panel(c, cfg, y - 5)
        draw_page_footer(c, cfg, y2 - 8)
        c.showPage()

    c.save()


def generate(cfg, out_path):
    """Render cfg to a PDF file on disk."""
    with open(out_path, "wb") as f:
        f.write(generate_bytes(cfg))


def generate_bytes(cfg):
    """Render cfg to PDF bytes (for serving from a web app, no disk write)."""
    full_cfg = {**DEFAULTS, **cfg}
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _render(c, full_cfg)
    return buf.getvalue()


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text or "").strip().lower()
    return re.sub(r"[\s-]+", "_", text) or "worksheet"


# ----------------------------------------------------------------------
# Free-text prompt parser
# ----------------------------------------------------------------------
# Understands prompts shaped like:
#
#   Day 2 (Tuesday): Sensory Description
#
#   * Focus Skill: Expanded noun phrases ...
#   * Topic: The Busy Rainy Afternoon
#   * Story / Prompt Starter: "Looking out my window, the sky turned..."
#   * 3-Minute Chat Prompts (Ask Adeeba):
#      1. What sounds do the raindrops make...?
#      2. What do the streets and trees look like when it pours?
#      3. What is your favourite thing to eat, drink, or do...?
#   * Word Vault (Aim for 3): `pattered`, `gloomy`, `splashed`, `cosy`
#   * Star Challenge (Optional): Describe the rain puddles without...
#
# Field labels are matched loosely (case-insensitive, punctuation-insensitive)
# so small wording variations ("Prompt Starter", "Story Starter", "Chat
# Questions", "Bonus Challenge", ...) still land in the right slot.

_TOP_BULLET_RE = re.compile(r"^\s*[*\-\u2022]\s*(.+?)\s*:\s*(.*)$")
_NUMBERED_RE = re.compile(r"^\s*(\d+)[.)]\s*(.*)$")
_VAULT_TICK_RE = re.compile(r"`([^`]+)`\s*(?:\(([^)]*)\)|[=:]\s*([^,`]+))?")
_DAY_HEADER_RE = re.compile(r"^\s*(Day\s+\S+(?:\s*\([^)]*\))?)\s*:?\s*(.*)$", re.IGNORECASE)


def _norm_key(label):
    return re.sub(r"[^a-z0-9]", "", label.lower())


_KEY_MAP = {
    "focusskill": "focus_skill",
    "focus": "focus_skill",
    "topic": "topic_title",
    "storypromptstarter": "prompt_starter",
    "promptstarter": "prompt_starter",
    "storystarter": "prompt_starter",
    "story": "prompt_starter",
    "goal": "goal",
    "wordvault": "word_vault",
    "vault": "word_vault",
}


def _is_chat_label(norm):
    return "chat" in norm


def _is_challenge_label(norm):
    return "challenge" in norm or "bonus" in norm or "starchallenge" in norm


def parse_prompt(text):
    """Parse a free-text day-prompt (as in the module docstring) into a
    config dict suitable for generate()/generate_bytes(). Also accepts raw
    JSON (a string starting with '{') and returns it parsed as-is."""
    text = text.strip()
    if not text:
        return {}
    if text.startswith("{"):
        return json.loads(text)

    lines = text.splitlines()
    cfg = {}

    # First non-empty line: "Day 2 (Tuesday): Sensory Description"
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines):
        m = _DAY_HEADER_RE.match(lines[i])
        if m:
            cfg["day_label"] = m.group(1).strip()
            if m.group(2).strip():
                cfg["category"] = m.group(2).strip()
            i += 1
        # else: leave i where it is — no recognizable day header, fall
        # through and let the bullet parser scan the whole text.

    chat_questions = []
    current_key = None  # 'chat_questions' while collecting numbered lines

    for line in lines[i:]:
        if not line.strip():
            continue

        m = _TOP_BULLET_RE.match(line)
        if m:
            label, value = m.group(1), m.group(2)
            norm = _norm_key(label)
            current_key = None

            if _is_chat_label(norm):
                current_key = "chat_questions"
                continue
            if _is_challenge_label(norm):
                cfg["challenge"] = value.strip().strip('"').strip("\u201c\u201d")
                continue
            if "wordvault" in norm or norm == "vault":
                # capture an "(Aim for 3)" / "(Use at least 3!)" instruction
                instr_m = re.search(r"\(([^)]*)\)", label)
                if instr_m:
                    cfg["vault_instruction"] = instr_m.group(1).strip()
                # `drenched` (very wet), `gloomy` = dark and sad, `cosy`
                words = []
                for word, paren, eq in _VAULT_TICK_RE.findall(value):
                    meaning = (paren or eq).strip()
                    words.append([word.strip(), meaning] if meaning else word.strip())
                if not words:
                    # no backticks: split on commas that aren't inside (...)
                    words = [w.strip().strip('"\u201c\u201d')
                             for w in re.split(r",(?![^()]*\))", value) if w.strip()]
                cfg["word_vault"] = words
                continue

            mapped = _KEY_MAP.get(norm)
            if mapped:
                cleaned = value.strip()
                if mapped == "prompt_starter":
                    cleaned = cleaned.strip('"').strip("\u201c\u201d")
                cfg[mapped] = cleaned
                continue

            # Unrecognized top-level bullet — ignore rather than guess.
            continue

        if current_key == "chat_questions":
            nm = _NUMBERED_RE.match(line)
            if nm:
                chat_questions.append([nm.group(1), nm.group(2).strip()])
                continue
            # a bullet-style sub-line instead of a numbered one
            bm = re.match(r"^\s*[*\-\u2022]\s*(.+)$", line)
            if bm:
                chat_questions.append(["", bm.group(1).strip()])
                continue

    if chat_questions:
        cfg["chat_questions"] = chat_questions

    return cfg


# ----------------------------------------------------------------------
# Built-in example (used when the CLI is run with no arguments)
# ----------------------------------------------------------------------
EXAMPLE_PROMPT = """Day 2 (Tuesday): Sensory Description

* Focus Skill: Expanded noun phrases (adding two vivid adjectives before a noun) and sound/sight sensory words.
* Topic: The Busy Rainy Afternoon
* Story / Prompt Starter: "Looking out my window, the sky turned a dark, moody grey..."
* 3-Minute Chat Prompts (Ask Adeeba):
   1. What sounds do the raindrops make against the glass or on the balcony?
   2. What do the streets and trees look like when it pours?
   3. What is your favourite thing to eat, drink, or do while listening to the storm?
* Word Vault (Aim for 3): `pattered` (tapped lightly), `gloomy` (dark and sad), `splashed` (water jumped up), `cosy` (warm and snug), `drenched` (very, very wet)
* Star Challenge (Optional): Describe the rain puddles without using the word "water".
"""


def main():
    args = sys.argv[1:]
    if args:
        path = args[0]
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        cfg = json.loads(raw) if path.endswith(".json") else parse_prompt(raw)
    else:
        cfg = parse_prompt(EXAMPLE_PROMPT)

    day_slug = slugify(cfg.get("day_label") or cfg.get("topic_title") or "worksheet")
    out_path = f"{day_slug}_worksheet.pdf"
    generate(cfg, out_path)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
