#!/usr/bin/env python3
"""
Daily Creative Spark — web app
================================

A tiny Flask app that wraps worksheet.py: paste a day's prompt, get a
print-ready PDF back in the browser. Meant to run in Docker on a Synology
NAS (see Dockerfile / docker-compose.yml / README.md).

Routes
------
GET  /            form + recent-generations history
POST /generate    parse the pasted prompt, render a PDF, save it to
                   OUTPUT_DIR, stream it back to the browser (inline, so it
                   opens in the browser's PDF viewer ready to print/save)
GET  /download/<name>   re-download a PDF from history
GET  /healthz     plain 200 OK, for Docker/Synology health checks
"""

import os
import time
from pathlib import Path

from flask import (
    Flask, request, render_template, send_file, abort, redirect,
    url_for, flash,
)

import worksheet

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_LIMIT = 30


def _history():
    files = sorted(
        OUTPUT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:HISTORY_LIMIT]
    return [
        {
            "name": f.name,
            "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime)),
        }
        for f in files
    ]


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        example_prompt=worksheet.EXAMPLE_PROMPT,
        defaults=worksheet.DEFAULTS,
        history=_history(),
    )


@app.route("/generate", methods=["POST"])
def generate():
    prompt_text = (request.form.get("prompt_text") or "").strip()
    if not prompt_text:
        flash("Paste a day's prompt first.")
        return redirect(url_for("index"))

    try:
        cfg = worksheet.parse_prompt(prompt_text)
    except Exception as exc:  # malformed JSON, etc.
        flash(f"Could not parse that prompt: {exc}")
        return redirect(url_for("index"))

    if not cfg.get("topic_title") and not cfg.get("day_label"):
        flash(
            "Couldn't find a topic or day heading in that text — check it "
            "matches the expected format and try again."
        )
        return redirect(url_for("index"))

    # optional per-request overrides from the "Settings" panel
    for field in ("student_name", "class_label", "goal", "footer_left", "footer_right"):
        val = (request.form.get(field) or "").strip()
        if val:
            cfg[field] = val

    try:
        pdf_bytes = worksheet.generate_bytes(cfg)
    except Exception as exc:
        flash(f"Could not generate the PDF: {exc}")
        return redirect(url_for("index"))

    slug = worksheet.slugify(cfg.get("day_label") or cfg.get("topic_title"))
    filename = f"{slug}_{int(time.time())}.pdf"
    out_path = OUTPUT_DIR / filename
    out_path.write_bytes(pdf_bytes)

    # prune old history beyond the limit
    all_files = sorted(OUTPUT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in all_files[HISTORY_LIMIT:]:
        old.unlink(missing_ok=True)

    return send_file(
        out_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=filename,
    )


@app.route("/download/<path:name>", methods=["GET"])
def download(name):
    path = (OUTPUT_DIR / name).resolve()
    if path.parent != OUTPUT_DIR.resolve() or not path.exists():
        abort(404)
    return send_file(path, mimetype="application/pdf", as_attachment=True, download_name=name)


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
