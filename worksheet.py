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
goal              : str   e.g. "5-8 complete sentences"
focus_skill       : str   optional
topic_title       : str
prompt_starter    : str   the quoted opening line
chat_questions    : list of [label, question]
word_vault        : list of str
vault_instruction : str   e.g. "Use at least 3!" / "Aim for 3"
challenge         : str   optional
checklist_items   : list of str
story_lines       : int   default 15
footer_left       : str
footer_right      : str
"""

import io
import json
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

# ----------------------------------------------------------------------
# Site-wide defaults — override per-request from the web form, or edit
# these (or set the matching environment variables in docker-compose.yml).
# ----------------------------------------------------------------------
import os

DEFAULTS = {
    "student_name": os.environ.get("STUDENT_NAME", "Adeeba"),
    "class_label": os.environ.get("CLASS_LABEL", "Class II \u2022 Cambridge"),
    "goal": os.environ.get("DEFAULT_GOAL", "5\u20138 complete sentences"),
    "vault_instruction": "Use at least 3!",
    "checklist_items": [
        "Capital letters at start",
        "Full stops at the end",
        "Finger spaces between words",
        "Used 3 Vault words",
    ],
    "story_lines": 15,
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

    baseline = top_y - 27

    title_text = "Daily Creative Spark"
    title_size = 19
    c.setFont("Helvetica-Bold", title_size)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, baseline, title_text)
    title_w = stringWidth(title_text, "Helvetica-Bold", title_size)

    field_size = 9.3
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

    day_x = right_field("Day:", "", right_edge, dotted_width=38)
    date_x = right_field("Date:", "", day_x - 16, dotted_width=55)
    writer_x = right_field("Writer:", cfg.get("student_name", ""), date_x - 16, bold_value=True)

    badge_text = cfg.get("class_label", "") or cfg.get("day_label", "")
    badge_font_size = 9.3
    badge_pad_x = 8
    badge_x = MARGIN + title_w + 12
    available = max(writer_x - 12 - badge_x, 40)
    badge_w = stringWidth(badge_text, "Helvetica-Bold", badge_font_size) + 2 * badge_pad_x
    while badge_w > available and badge_font_size > 6.5:
        badge_font_size -= 0.4
        badge_w = stringWidth(badge_text, "Helvetica-Bold", badge_font_size) + 2 * badge_pad_x
    badge_w = min(badge_w, available)
    badge_h = 18
    badge_y = baseline - 3
    rounded_rect(c, badge_x, badge_y, badge_w, badge_h, badge_h / 2,
                 fill=BLUE_LIGHT_BG, stroke=BLUE_BORDER, line_width=1)
    c.setFont("Helvetica-Bold", badge_font_size)
    c.setFillColor(BLUE)
    c.drawString(badge_x + badge_pad_x, badge_y + 5.5, badge_text)

    rule_y = top_y - 40
    c.setStrokeColor(NAVY)
    c.setLineWidth(2.2)
    c.line(MARGIN, rule_y, PAGE_W - MARGIN, rule_y)
    return rule_y


def draw_quest_box(c, cfg, top_y):
    box_h = 68 if cfg.get("focus_skill") else 56
    x, w = MARGIN, PAGE_W - 2 * MARGIN
    y = top_y - box_h

    rounded_rect(c, x, y, w, box_h, 4, fill=BLUE_LIGHT_BG)
    c.setFillColor(BLUE)
    c.rect(x, y, 4, box_h, stroke=0, fill=1)

    pad = 16
    ty = top_y - 13
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(BLUE)
    c.drawString(x + pad, ty, "TODAY'S WRITING QUEST")

    goal = cfg.get("goal", "")
    category = cfg.get("category", "")
    goal_text = f"Goal: {goal}" if goal else ""
    if category:
        goal_text = f"{goal_text}  \u2022  {category}" if goal_text else category
    if goal_text:
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(INK)
        c.drawRightString(x + w - pad, ty, goal_text)

    ty -= 18
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(INK)
    c.drawString(x + pad, ty, cfg.get("topic_title", ""))

    ty -= 16
    c.setFont("Helvetica-Oblique", 10.5)
    c.setFillColor(HexColor("#374151"))
    quote = cfg.get("prompt_starter", "")
    if quote and not quote.startswith("\u201c"):
        quote = f"\u201c{quote}\u201d"
    c.drawString(x + pad, ty, quote)

    focus = cfg.get("focus_skill")
    if focus:
        ty -= 14
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(GRAY)
        c.drawString(x + pad, ty, f"Focus skill: {focus}")

    return y


def draw_two_column(c, cfg, top_y):
    gap = 16
    col_w = (PAGE_W - 2 * MARGIN - gap) / 2
    left_x = MARGIN
    right_x = MARGIN + col_w + gap

    chat_qs = cfg.get("chat_questions", [])
    vault_words = cfg.get("word_vault", [])
    challenge = cfg.get("challenge", "")

    chat_line_h = 15
    chat_body_h = 26 + len(chat_qs) * chat_line_h

    chip_pad_x, chip_gap, chip_h = 10, 8, 22
    chip_font = "Helvetica-Bold"
    chip_size = 9.5
    lines, cur_line, cur_w = [], [], 0
    max_chip_w = col_w - 32
    for word in vault_words:
        ww = stringWidth(word, chip_font, chip_size) + 2 * chip_pad_x
        if cur_w + ww + (chip_gap if cur_line else 0) > max_chip_w and cur_line:
            lines.append(cur_line)
            cur_line, cur_w = [], 0
        cur_line.append((word, ww))
        cur_w += ww + (chip_gap if len(cur_line) > 1 else 0)
    if cur_line:
        lines.append(cur_line)
    vault_chip_rows = len(lines)
    vault_body_h = 30 + vault_chip_rows * (chip_h + 6)
    challenge_lines = []
    if challenge:
        challenge_lines = wrap_text(f"Challenge: {challenge}", "Helvetica-Oblique", 9, col_w - 32)
        vault_body_h += 6 + len(challenge_lines) * 12

    box_h = max(chat_body_h, vault_body_h, 70)
    y = top_y - box_h

    # ----- Chat & Think box -----
    rounded_rect(c, left_x, y, col_w, box_h, 4, stroke=BOX_BORDER, line_width=1)
    c.setFillColor(GREEN)
    c.rect(left_x, y, 4, box_h, stroke=0, fill=1)
    pad = 16
    ty = top_y - 20
    c.setFont("Helvetica-Bold", 10.5)
    c.setFillColor(INK)
    c.drawString(left_x + pad, ty, "3-MINUTE CHAT & THINK")
    ty -= 20
    c.setFont("Helvetica", 9.7)
    for label, question in chat_qs:
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9.7)
        prefix = f"{label}  " if label else "\u2022  "
        c.drawString(left_x + pad, ty, prefix)
        pw = stringWidth(prefix, "Helvetica-Bold", 9.7)
        c.setFont("Helvetica", 9.7)
        avail = col_w - 2 * pad - pw
        qlines = wrap_text(question, "Helvetica", 9.7, avail)
        if not qlines:
            qlines = [""]
        c.drawString(left_x + pad + pw, ty, qlines[0])
        for extra in qlines[1:]:
            ty -= 13
            c.drawString(left_x + pad + pw, ty, extra)
        ty -= chat_line_h

    # ----- Word Vault box -----
    rounded_rect(c, right_x, y, col_w, box_h, 4, stroke=BOX_BORDER, line_width=1)
    c.setFillColor(AMBER)
    c.rect(right_x, y, 4, box_h, stroke=0, fill=1)
    ty = top_y - 20
    label = "WRITER'S WORD VAULT"
    instr = cfg.get("vault_instruction") or "Use at least 3!"
    c.setFont("Helvetica-Bold", 10.5)
    c.setFillColor(INK)
    c.drawString(right_x + pad, ty, f"{label} ({instr.upper()})")

    ty -= 22
    for row in lines:
        rh_y = ty - chip_h + 5
        cx = right_x + pad
        for word, ww in row:
            rounded_rect(c, cx, rh_y, ww, chip_h, chip_h / 2, fill=CHIP_BG)
            c.setFont(chip_font, chip_size)
            c.setFillColor(CHIP_TEXT)
            c.drawCentredString(cx + ww / 2, rh_y + 6.5, word)
            cx += ww + chip_gap
        ty -= (chip_h + 6)

    if challenge_lines:
        ty -= 4
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(GRAY)
        for cl in challenge_lines:
            c.drawString(right_x + pad, ty, cl)
            ty -= 12

    return y


def draw_story_area(c, cfg, top_y, bottom_limit):
    x, w = MARGIN, PAGE_W - 2 * MARGIN
    header_h = 22
    box_h = top_y - bottom_limit
    y = bottom_limit

    rounded_rect(c, x, y, w, box_h, 4, stroke=BOX_BORDER, line_width=1)

    pad = 16
    ty = top_y - 15
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(INK)
    name = cfg.get("student_name", "Writer")
    c.drawString(x + pad, ty, f"{name}'s Story Area")

    c.setFont("Helvetica-Oblique", 8.5)
    c.setFillColor(GRAY)
    c.drawRightString(x + w - pad, ty, "Dotted line = guide for lowercase letters")

    n_lines = cfg.get("story_lines", 15)
    top_pad = 11
    bottom_pad = 10
    usable_h = box_h - header_h - top_pad - bottom_pad
    step = usable_h / n_lines
    line_y = top_y - header_h - top_pad

    for i in range(n_lines):
        base_y = line_y - i * step
        c.setStrokeColor(LINE_GRAY)
        c.setLineWidth(0.8)
        c.line(x + pad, base_y, x + w - pad, base_y)
        dotted_y = base_y + step * 0.42
        c.setStrokeColor(DOT_GRAY)
        c.setDash(1, 2)
        c.setLineWidth(0.8)
        c.line(x + pad, dotted_y, x + w - pad, dotted_y)
        c.setDash()

    return y


def draw_footer_panel(c, cfg, top_y):
    x, w = MARGIN, PAGE_W - 2 * MARGIN
    box_h = 58
    y = top_y - box_h
    rounded_rect(c, x, y, w, box_h, 4, stroke=BOX_BORDER, line_width=1)

    pad = 16
    split = x + w * 0.66
    c.setStrokeColor(BOX_BORDER)
    c.setLineWidth(1)
    c.line(split, y + 8, split, y + box_h - 8)

    ty = top_y - 15
    name = cfg.get("student_name", "Writer")
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(INK)
    c.drawString(x + pad, ty, f"{name.upper()}'S DETECTIVE CHECKLIST")

    items = cfg.get("checklist_items") or DEFAULTS["checklist_items"]
    col1 = items[0::2]
    col2 = items[1::2]
    box_sz = 9
    row_h = 14
    cy = ty - 16

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
            c.rect(cx, yy - box_sz + 2, box_sz, box_sz, stroke=1, fill=0)
            c.setFont("Helvetica", 8.6)
            c.setFillColor(INK)
            text_w = col_w - box_sz - 6
            it_lines = wrap_text(it, "Helvetica", 8.6, text_w) or [it]
            c.drawString(cx + box_sz + 6, yy, it_lines[0])
            for extra in it_lines[1:]:
                yy -= 10
                c.drawString(cx + box_sz + 6, yy, extra)
            yy -= row_h

    draw_checks(col1, col1_x)
    draw_checks(col2, col2_x)

    rx = split + 16
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(rx, ty, "Today's Effort:")
    star_x = rx + stringWidth("Today's Effort: ", "Helvetica-Bold", 10)
    c.setFont("Helvetica", 13)
    c.setFillColor(HexColor("#F59E0B"))
    c.drawString(star_x, ty - 1, "\u2605 \u2605 \u2605 \u2605 \u2605")

    c.setFont("Helvetica", 9)
    c.setFillColor(GRAY)
    c.drawString(rx, ty - 22, "Favorite word " + name + " used: " + "." * 24)

    return y


def draw_page_footer(c, cfg, bottom_y):
    x = MARGIN
    w = PAGE_W - 2 * MARGIN
    c.setStrokeColor(PAGE_BORDER)
    c.setDash(1, 2)
    c.setLineWidth(0.8)
    c.line(x, bottom_y, x + w, bottom_y)
    c.setDash()
    c.setFont("Helvetica", 8.5)
    c.setFillColor(GRAY)
    c.drawString(x, bottom_y - 14, cfg.get("footer_left", ""))
    c.drawRightString(x + w, bottom_y - 14, cfg.get("footer_right", ""))


def _render(c, cfg):
    c.setTitle(f"Daily Creative Spark - {cfg.get('day_label', '')}".strip())
    top_y = PAGE_H - MARGIN
    rule_y = draw_header(c, cfg, top_y)
    y = draw_quest_box(c, cfg, rule_y - 11)
    y = draw_two_column(c, cfg, y - 11)
    footer_reserved = 58 + 11 + 22
    story_bottom = footer_reserved + MARGIN
    y = draw_story_area(c, cfg, y - 11, story_bottom)
    y2 = draw_footer_panel(c, cfg, y - 6)
    draw_page_footer(c, cfg, y2 - 9)
    c.showPage()
    c.save()


def generate(cfg, out_path):
    """Render cfg to a PDF file on disk."""
    full_cfg = {**DEFAULTS, **cfg}
    c = canvas.Canvas(out_path, pagesize=A4)
    _render(c, full_cfg)


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
                words = re.findall(r"`([^`]+)`", value)
                if not words:
                    words = [w.strip().strip('"\u201c\u201d') for w in value.split(",") if w.strip()]
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
* Word Vault (Aim for 3): `pattered`, `gloomy`, `splashed`, `cosy`, `drenched`
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
