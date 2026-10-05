#!/usr/bin/env python3
"""
Regenerate the README hero and screenshots in docs/.

Builds a throwaway data folder with demo content (a few worksheets, a week
pack, a star chart, and three weeks of logged stories whose "photos" are
rendered worksheet pages), runs the web app against it, and captures:

    docs/screenshots/web-form.png         main page, desktop
    docs/screenshots/web-mobile.png       main page, phone width
    docs/screenshots/progress.png         Progress & portfolio page
    docs/screenshots/worksheet-day2.png   example worksheet, page 1
    docs/screenshots/worksheet-day2-page2.png   ... page 2
    docs/screenshots/worksheet-day4.png   long-text example, page 1
    docs/screenshots/weekly-pack.png      page 1 of each sheet in a week pack
    docs/screenshots/star-chart.png       a monthly star chart
    docs/hero.png                         rendered from docs/hero.html

Needs the app's requirements plus Playwright (docs only, not the app):

    pip install -r requirements.txt playwright pymupdf
    playwright install chromium
    python3 docs/make_screenshots.py
"""

import datetime
import io
import os
import random
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SHOTS = DOCS / "screenshots"

# point the app at a temporary data folder before importing it, and pretend
# a Gemini key is set so every prompt button shows (no request is made)
DATA = Path(tempfile.mkdtemp(prefix="cw-docs-"))
os.environ["OUTPUT_DIR"] = str(DATA)
os.environ["GEMINI_API_KEY"] = "demo-key-for-screenshots"
sys.path.insert(0, str(ROOT))

import pymupdf  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

import app as webapp  # noqa: E402
import prompt_bank  # noqa: E402
import prompt_generator  # noqa: E402
import star_chart  # noqa: E402
import worksheet  # noqa: E402


def png_of_page(pdf_bytes, page, dpi):
    return pymupdf.open(stream=pdf_bytes, filetype="pdf")[page].get_pixmap(dpi=dpi).tobytes("png")


def seed_demo_data():
    """Recent worksheets, a week pack, a star chart and logged stories."""
    client = webapp.app.test_client()
    client.post("/generate", data={"prompt_text": (ROOT / "examples/day4_prompt.txt").read_text()})
    client.post("/generate", data={"prompt_text": (ROOT / "examples/day2_prompt.txt").read_text()})
    client.post("/star-chart", data={"chart_month": datetime.date.today().strftime("%Y-%m")})
    pack = client.post("/pack", data={"weekday": "Saturday", "pack_dates": "1"}).data

    random.seed(7)
    today = datetime.date.today()
    items = worksheet.DEFAULTS["checklist_items"]
    bank = prompt_bank.load_bank()
    notes = ["", "Great describing words today!", "Remember speech marks next time.",
             "Wrote a whole extra paragraph!", "Lovely ending - she read it aloud to Nanu."]
    for k in range(18):
        if k in (6, 11):
            continue  # a couple of missed days
        day = today - datetime.timedelta(days=17 - k)   # up to today, so the streak is live
        weekday = prompt_generator.WEEKDAYS[day.weekday()]
        entry = bank[weekday][k % 10]
        sheet = worksheet.generate_bytes(worksheet.parse_prompt(
            prompt_bank.pick_next(weekday, DATA)["prompt_text"]))
        photo = png_of_page(sheet, 0, 40)
        checks = [it for j, it in enumerate(items) if random.random() < (0.9 if j < 2 else 0.35 + k * 0.025)]
        client.post("/progress", content_type="multipart/form-data", data={
            "written_on": day.isoformat(),
            "topic": entry["topic_title"],
            "writing_type": prompt_generator.WEEKLY_PLAN[weekday][0],
            "sentences": str(min(16, 6 + k // 2 + random.randint(-1, 2))),
            "paragraphs": str(min(3, 1 + k // 5)),
            "vault_words": str(random.randint(2, 5)),
            "checklist": checks,
            "effort": str(random.randint(3, 5)),
            "mood": random.choice(["happy", "happy", "okay"]),
            "note": random.choice(notes),
            "photos": [(io.BytesIO(photo), "page.png")],
        })
    return pack


def worksheet_images(pack):
    day2 = worksheet.generate_bytes(worksheet.parse_prompt((ROOT / "examples/day2_prompt.txt").read_text()))
    day4 = worksheet.generate_bytes(worksheet.parse_prompt((ROOT / "examples/day4_prompt.txt").read_text()))
    (SHOTS / "worksheet-day2.png").write_bytes(png_of_page(day2, 0, 150))
    (SHOTS / "worksheet-day2-page2.png").write_bytes(png_of_page(day2, 1, 150))
    (SHOTS / "worksheet-day4.png").write_bytes(png_of_page(day4, 0, 150))
    month = datetime.date.today()
    chart = star_chart.star_chart_bytes(month.year, month.month, "Saturday")
    (SHOTS / "star-chart.png").write_bytes(png_of_page(chart, 0, 150))

    # page 1 of each sheet in the week pack, for the weekly-pack contact sheet
    doc = pymupdf.open(stream=pack, filetype="pdf")
    step = 2 if len(doc) == 14 else 1
    thumbs = []
    for i in range(0, len(doc), step):
        path = DATA / f"pack_{i // step}.png"
        path.write_bytes(doc[i].get_pixmap(dpi=60).tobytes("png"))
        thumbs.append(path)
    return thumbs


CONTACT_SHEET = """<!doctype html><meta charset="utf-8"><style>
body{{margin:0;padding:28px;background:#f8fafc;font-family:-apple-system,Helvetica,Arial,sans-serif;width:1240px}}
h2{{margin:0 0 4px;color:#1e40af;font-size:22px}} p{{margin:0 0 18px;color:#6b7280;font-size:14px}}
.grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:14px}}
figure{{margin:0}} img{{width:100%;border-radius:4px;box-shadow:0 6px 16px -6px rgba(30,64,175,.35),0 0 0 1px rgba(15,23,42,.08);background:#fff}}
figcaption{{text-align:center;font-size:13px;font-weight:600;color:#1f2937;margin-top:8px}}
</style><h2>One click, one week</h2><p>A Saturday-to-Friday pack: seven worksheets, each with that day's writing type and the date filled in.</p>
<div class="grid">{figs}</div>"""


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    pack = seed_demo_data()
    thumbs = worksheet_images(pack)

    server = make_server("127.0.0.1", 0, webapp.app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # main page, desktop: fill the prompt from the bank, open Settings
        page = browser.new_page(viewport={"width": 1000, "height": 900}, device_scale_factor=2)
        page.goto(base + "/")
        page.select_option("#gen_weekday", "Tuesday")
        page.once("dialog", lambda d: d.accept())
        page.click("#bank_btn")
        page.wait_for_function("document.getElementById('prompt_text').value.includes('Topic')")
        page.click("summary")
        page.screenshot(path=str(SHOTS / "web-form.png"), full_page=True)
        page.close()

        # main page, phone width
        page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                is_mobile=True, has_touch=True)
        page.goto(base + "/")
        page.screenshot(path=str(SHOTS / "web-mobile.png"),
                        clip={"x": 0, "y": 0, "width": 390, "height": 1500}, full_page=True)
        page.close()

        # progress page: down to the end of the second portfolio entry
        page = browser.new_page(viewport={"width": 1000, "height": 900}, device_scale_factor=2)
        page.goto(base + "/progress")
        page.wait_for_load_state("networkidle")
        # photos load lazily: scroll to the end so every one loads, then
        # measure (so the crop doesn't land mid-entry)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_load_state("networkidle")
        page.evaluate("window.scrollTo(0, 0)")
        box = page.locator(".entry").nth(1).bounding_box()
        page.screenshot(path=str(SHOTS / "progress.png"), full_page=True,
                        clip={"x": 0, "y": 0, "width": 1000, "height": box["y"] + box["height"]})
        page.close()

        # weekly pack contact sheet
        days = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
        figs = "".join(f'<figure><img src="{t.as_uri()}"><figcaption>{d}</figcaption></figure>'
                       for t, d in zip(thumbs, days))
        sheet = DATA / "contact.html"
        sheet.write_text(CONTACT_SHEET.format(figs=figs), encoding="utf-8")
        page = browser.new_page(viewport={"width": 1296, "height": 400}, device_scale_factor=2)
        page.goto(sheet.as_uri())
        page.screenshot(path=str(SHOTS / "weekly-pack.png"), full_page=True)
        page.close()

        # hero, from docs/hero.html (it uses the screenshots above)
        page = browser.new_page(viewport={"width": 1280, "height": 640}, device_scale_factor=2)
        page.goto((DOCS / "hero.html").as_uri())
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(DOCS / "hero.png"))
        page.close()

        browser.close()
    server.shutdown()
    for name in sorted(os.listdir(SHOTS)):
        print("wrote", SHOTS / name)
    print("wrote", DOCS / "hero.png")


if __name__ == "__main__":
    main()
