"""
Daily Creative Spark — monthly writing star chart
===================================================

A one-page A4 calendar for a month: the child colours a star on each day
she writes. Each day shows that weekday's writing type (from the weekly
plan), and underneath are a streak counter, milestone badges to colour,
and a reward agreed with a grown-up.

    star_chart_bytes(2026, 10, week_start="Saturday", student_name="Adeeba")
"""

import calendar
import datetime
import io

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from worksheet import (
    AMBER, BLUE, BLUE_LIGHT_BG, BOX_BORDER, DEFAULTS, GRAY, GREEN, INK, MARGIN,
    NAVY, PURPLE, STAR_GOLD, draw_star, rounded_rect,
)

PAGE_W, PAGE_H = A4
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# short forms of prompt_generator.WEEKLY_PLAN's writing types, to fit a cell
DAY_TYPES = {
    "Monday": "Character",
    "Tuesday": "Senses",
    "Wednesday": "Dialogue",
    "Thursday": "Adventure",
    "Friday": "Problem & Solution",
    "Saturday": "Diary / Letter",
    "Sunday": "Imagine If",
}

OUTSIDE_BG = HexColor("#F9FAFB")
MILESTONES = (5, 10, 15, 20, 25)


def star_chart_bytes(year, month, week_start="Saturday", student_name=None,
                     footer_left=None):
    student_name = student_name or DEFAULTS["student_name"]
    footer_left = footer_left if footer_left is not None else DEFAULTS["footer_left"]
    month_name = f"{calendar.month_name[month]} {year}"

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Writing Star Chart - {month_name}")

    x, w = MARGIN, PAGE_W - 2 * MARGIN
    top = PAGE_H - MARGIN

    # ----- header -----
    c.setStrokeColor(BOX_BORDER)
    c.setLineWidth(1)
    c.line(x, top, x + w, top)
    title = f"{student_name}'s Writing Star Chart"
    c.setFont("Helvetica-Bold", 19)
    c.setFillColor(NAVY)
    c.drawString(x, top - 27, title)

    badge_font = "Helvetica-Bold"
    bw = stringWidth(month_name, badge_font, 11) + 24
    rounded_rect(c, x + w - bw, top - 32, bw, 20, 10, fill=BLUE_LIGHT_BG, stroke=BLUE, line_width=1)
    c.setFont(badge_font, 11)
    c.setFillColor(BLUE)
    c.drawCentredString(x + w - bw / 2, top - 25.5, month_name)

    rule_y = top - 40
    c.setStrokeColor(NAVY)
    c.setLineWidth(2.2)
    c.line(x, rule_y, x + w, rule_y)

    c.setFont("Helvetica-Oblique", 10)
    c.setFillColor(GRAY)
    c.drawString(x, rule_y - 16,
                 "Colour a star every day you write. How many days in a row can you go?")

    # ----- calendar -----
    first_wd = WEEKDAYS.index(week_start) if week_start in WEEKDAYS else 5
    weeks = calendar.Calendar(firstweekday=first_wd).monthdatescalendar(year, month)
    col_w = w / 7
    head_h = 18
    grid_top = rule_y - 28
    bottom_block_h = 196
    grid_bottom = MARGIN + 22 + bottom_block_h + 12
    cell_h = (grid_top - head_h - grid_bottom) / len(weeks)

    day_names = [WEEKDAYS[(first_wd + i) % 7] for i in range(7)]
    rounded_rect(c, x, grid_top - head_h, w, head_h, 4, fill=BLUE_LIGHT_BG)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(NAVY)
    for i, name in enumerate(day_names):
        c.drawCentredString(x + col_w * (i + 0.5), grid_top - head_h + 5.5, name[:3].upper())

    pad = 2.5
    star_r = min(col_w, cell_h) * 0.27
    for row, week in enumerate(weeks):
        cy_top = grid_top - head_h - row * cell_h
        for col, day in enumerate(week):
            cx0 = x + col * col_w + pad
            cy0 = cy_top - cell_h + pad
            cw, ch = col_w - 2 * pad, cell_h - 2 * pad
            if day.month != month:
                rounded_rect(c, cx0, cy0, cw, ch, 5, fill=OUTSIDE_BG)
                continue
            rounded_rect(c, cx0, cy0, cw, ch, 5, stroke=BOX_BORDER, line_width=1)
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(INK)
            c.drawString(cx0 + 6, cy0 + ch - 14, str(day.day))
            draw_star(c, cx0 + cw / 2, cy0 + ch / 2 - 1, star_r, STAR_GOLD, line_width=1.4)
            label = DAY_TYPES[WEEKDAYS[day.weekday()]]
            size = 6.3
            while stringWidth(label, "Helvetica", size) > cw - 6 and size > 5:
                size -= 0.2
            c.setFont("Helvetica", size)
            c.setFillColor(GRAY)
            c.drawCentredString(cx0 + cw / 2, cy0 + 5, label)

    # ----- bottom: streaks, milestones, reward -----
    days_in_month = calendar.monthrange(year, month)[1]
    gap = 12
    half = (w - gap) / 2
    row1_h = 88
    row1_top = grid_bottom - 12

    def box(bx, by_top, bw_, bh, accent, heading):
        rounded_rect(c, bx, by_top - bh, bw_, bh, 4, stroke=BOX_BORDER, line_width=1)
        c.setFillColor(accent)
        c.rect(bx, by_top - bh, 4, bh, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(INK)
        c.drawString(bx + 16, by_top - 17, heading)

    box(x, row1_top, half, row1_h, AMBER, "MY STREAKS")
    c.setFont("Helvetica", 9.5)
    c.setFillColor(INK)
    lines = [
        f"Stars this month:  ........  out of {days_in_month}",
        "Longest streak:  ........  days in a row",
        "Best story this month:  " + "." * 26,
    ]
    for i, line in enumerate(lines):
        c.drawString(x + 16, row1_top - 38 - i * 18, line)

    mx = x + half + gap
    box(mx, row1_top, half, row1_h, GREEN, "MILESTONES")
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(GRAY)
    c.drawString(mx + 16 + stringWidth("MILESTONES  ", "Helvetica-Bold", 9.5), row1_top - 17,
                 "colour a badge when you reach it")
    slot = (half - 32) / len(MILESTONES)
    badge_r = min(slot * 0.38, 20)
    for i, n in enumerate(MILESTONES):
        bx = mx + 16 + slot * (i + 0.5)
        by = row1_top - 54
        c.setStrokeColor(GREEN)
        c.setLineWidth(1.4)
        c.circle(bx, by, badge_r, stroke=1, fill=0)
        draw_star(c, bx, by + 2, badge_r * 0.55, STAR_GOLD, line_width=1)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(INK)
        c.drawCentredString(bx, by - badge_r - 11, f"{n} stars")

    row2_top = row1_top - row1_h - gap
    row2_h = bottom_block_h - row1_h - gap
    box(x, row2_top, w, row2_h, PURPLE, "MY REWARD")
    c.setFont("Helvetica", 9.5)
    c.setFillColor(INK)
    dot_w = stringWidth(".", "Helvetica", 9.5)
    lead = "When I colour  ........  stars, my reward is:  "
    c.drawString(x + 16, row2_top - 38, lead)
    room = w - 32 - stringWidth(lead, "Helvetica", 9.5)
    c.setFillColor(GRAY)
    c.drawString(x + 16 + stringWidth(lead, "Helvetica", 9.5), row2_top - 38, "." * int(room / dot_w))
    c.setFillColor(INK)
    agreed = "Agreed by:  "
    c.drawString(x + 16, row2_top - 62, agreed)
    ax = x + 16 + stringWidth(agreed, "Helvetica", 9.5)
    seg = (w - 32 - (ax - x - 16)) / 2
    for i, who in enumerate(("(me)", "(grown-up)")):
        sx = ax + i * seg
        c.setFillColor(GRAY)
        c.drawString(sx, row2_top - 62, "." * int((seg - 70) / dot_w))
        c.setFont("Helvetica-Oblique", 8.5)
        c.drawString(sx + (seg - 66), row2_top - 62, who)
        c.setFont("Helvetica", 9.5)
    proud = "I'm proud of myself because:  "
    c.setFillColor(INK)
    c.drawString(x + 16, row2_top - 84, proud)
    c.setFillColor(GRAY)
    room = w - 32 - stringWidth(proud, "Helvetica", 9.5)
    c.drawString(x + 16 + stringWidth(proud, "Helvetica", 9.5), row2_top - 84, "." * int(room / dot_w))

    # ----- footer -----
    c.setFont("Helvetica", 8)
    c.setFillColor(GRAY)
    c.drawString(x, MARGIN + 4, footer_left)
    c.drawRightString(x + w, MARGIN + 4, "Daily Creative Spark • Monthly Star Chart")

    c.showPage()
    c.save()
    return buf.getvalue()


def month_choices(today=None, count=3):
    """(value, label) for this month and the next count-1, e.g.
    ("2026-10", "October 2026")."""
    today = today or datetime.date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(count):
        out.append((f"{y:04d}-{m:02d}", f"{calendar.month_name[m]} {y}"))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out
