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
POST /pack        a week of worksheets from the prompt bank in one PDF
GET  /download/<name>   re-download a PDF from history
POST /api/generate-prompt   start asking Gemini/Claude for a day's prompt
                   in the background; returns a job id
GET  /api/generate-prompt/<id>   poll that job: pending / done / error
POST /api/chat-prompt   the same request as text to paste into a chat app
POST /api/bank-prompt   the next unused prompt from the built-in prompt bank
GET  /healthz     plain 200 OK, for Docker/Synology health checks
"""

import datetime
import json
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path

from flask import (
    Flask, request, render_template, send_file, abort, redirect,
    url_for, flash, jsonify,
)

import prompt_bank
import prompt_generator
import worksheet

# send INFO logs (e.g. how long Gemini took) to stdout, i.e. `docker logs`
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_LIMIT = 30


def _meta_path(pdf_path):
    # each PDF gets a small sidecar with its topic, for the history list
    return pdf_path.with_suffix(".json")


def _read_title(pdf_path):
    try:
        meta = json.loads(_meta_path(pdf_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return " \u2014 ".join(v for v in (meta.get("day_label"), meta.get("topic_title")) if v)


def _history():
    files = sorted(
        OUTPUT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:HISTORY_LIMIT]
    return [
        {
            "name": f.name,
            "title": _read_title(f),
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
        weekdays=prompt_generator.WEEKDAYS,
        weekly_plan=prompt_generator.WEEKLY_PLAN,
        provider=prompt_generator.active_provider(),
    )


def _recent_topics(limit=14):
    files = sorted(OUTPUT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    topics = []
    for f in files[:limit]:
        try:
            meta = json.loads(_meta_path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        # a week pack lists its seven topics; a single sheet has one
        for topic in meta.get("topics") or [meta.get("topic_title")]:
            if topic and topic not in topics:
                topics.append(topic)
    return topics


def _generator_args():
    body = request.get_json(silent=True) or {}
    weekday = body.get("weekday") or ""
    if weekday not in prompt_generator.WEEKLY_PLAN:
        return None
    return dict(
        weekday=weekday,
        student_name=(body.get("student_name") or "").strip() or worksheet.DEFAULTS["student_name"],
        theme=(body.get("theme") or "")[:200],
        recent_topics=_recent_topics(),
    )


# Generating a prompt can take a minute or two, longer than a reverse proxy
# lets one request run, so POST starts a background job and the page polls
# GET until it's done. Jobs are small JSON files under OUTPUT_DIR so any
# gunicorn worker can answer the poll.
JOBS_DIR = OUTPUT_DIR / ".jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
JOB_MAX_AGE = 3600


def _job_path(job_id):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id or ""):
        return None
    return JOBS_DIR / f"{job_id}.json"


def _write_job(job_id, data):
    tmp = JOBS_DIR / f"{job_id}.tmp"
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(JOBS_DIR / f"{job_id}.json")


def _run_job(job_id, args):
    try:
        text = prompt_generator.generate_prompt_text(**args)
        _write_job(job_id, {"status": "done", "prompt_text": text})
    except prompt_generator.PromptGenerationError as exc:
        _write_job(job_id, {"status": "error", "error": str(exc)})
    except Exception:
        app.logger.exception("prompt generation failed")
        _write_job(job_id, {"status": "error", "error": "Something went wrong - check the logs."})


@app.route("/api/generate-prompt", methods=["POST"])
def api_generate_prompt():
    args = _generator_args()
    if args is None:
        return jsonify(error="Pick a day of the week."), 400
    if not prompt_generator.active_provider():
        return jsonify(error="No API key is set - use \"Copy for Gemini / Claude chat\"."), 400

    now = time.time()
    for old in JOBS_DIR.glob("*.json"):
        if now - old.stat().st_mtime > JOB_MAX_AGE:
            old.unlink(missing_ok=True)

    job_id = uuid.uuid4().hex
    _write_job(job_id, {"status": "pending"})
    threading.Thread(target=_run_job, args=(job_id, args), daemon=True).start()
    return jsonify(job_id=job_id), 202


@app.route("/api/generate-prompt/<job_id>", methods=["GET"])
def api_generate_prompt_status(job_id):
    path = _job_path(job_id)
    if path is None or not path.exists():
        return jsonify(status="error", error="That request has expired - try again."), 404
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.route("/api/bank-prompt", methods=["POST"])
def api_bank_prompt():
    args = _generator_args()
    if args is None:
        return jsonify(error="Pick a day of the week."), 400
    return jsonify(prompt_bank.pick_next(args["weekday"], OUTPUT_DIR, args["student_name"]))


@app.route("/api/chat-prompt", methods=["POST"])
def api_chat_prompt():
    args = _generator_args()
    if args is None:
        return jsonify(error="Pick a day of the week."), 400
    return jsonify(chat_text=prompt_generator.chat_prompt_text(**args))


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

    _apply_overrides(cfg)

    try:
        pdf_bytes = worksheet.generate_bytes(cfg)
    except Exception as exc:
        flash(f"Could not generate the PDF: {exc}")
        return redirect(url_for("index"))

    slug = worksheet.slugify(cfg.get("day_label") or cfg.get("topic_title"))
    meta = {k: cfg.get(k, "") for k in ("day_label", "topic_title")}
    return _save_and_send(pdf_bytes, slug, meta)


@app.route("/pack", methods=["POST"])
def pack():
    """A week of worksheets in one PDF: the next unused prompt-bank prompt
    for each of 7 days, starting from the day picked in the form."""
    start_day = request.form.get("weekday")
    if start_day not in prompt_generator.WEEKDAYS:
        start_day = prompt_generator.WEEKDAYS[datetime.date.today().weekday()]
    start_idx = prompt_generator.WEEKDAYS.index(start_day)
    student_name = (request.form.get("student_name") or "").strip() or worksheet.DEFAULTS["student_name"]
    with_dates = bool(request.form.get("pack_dates"))

    # the first date is the next start_day, today included
    today = datetime.date.today()
    first = today + datetime.timedelta(days=(start_idx - today.weekday()) % 7)

    cfgs = []
    for k in range(7):
        day = prompt_generator.WEEKDAYS[(start_idx + k) % 7]
        cfg = worksheet.parse_prompt(prompt_bank.pick_next(day, OUTPUT_DIR, student_name)["prompt_text"])
        _apply_overrides(cfg)
        if with_dates:
            date = first + datetime.timedelta(days=k)
            cfg["date_text"] = f"{date.day} {date:%b}"
            cfg["day_name"] = f"{date:%a}"
        cfgs.append(cfg)

    last = first + datetime.timedelta(days=6)
    span = f"{first.day} {first:%b} \u2013 {last.day} {last:%b}"
    try:
        pdf_bytes = worksheet.generate_pack_bytes(cfgs, title=f"Daily Creative Spark - week of {span}")
    except Exception as exc:
        flash(f"Could not generate the PDF: {exc}")
        return redirect(url_for("index"))

    meta = {
        "day_label": "Week pack",
        "topic_title": f"{start_day[:3]}\u2013{prompt_generator.WEEKDAYS[(start_idx + 6) % 7][:3]}, {span}",
        "topics": [c.get("topic_title", "") for c in cfgs],
    }
    return _save_and_send(pdf_bytes, f"week_pack_{first.isoformat()}", meta)


def _apply_overrides(cfg):
    """Optional per-request overrides from the form's "Settings" panel."""
    for field in ("student_name", "class_label", "goal", "footer_left", "footer_right"):
        val = (request.form.get(field) or "").strip()
        if val:
            cfg[field] = val
    if request.form.get("pages") in ("1", "2"):
        cfg["pages"] = int(request.form["pages"])


def _save_and_send(pdf_bytes, slug, meta):
    """Save a PDF (and its sidecar) to the history, prune old ones, and
    send it back to open in the browser."""
    filename = f"{slug}_{int(time.time())}.pdf"
    out_path = OUTPUT_DIR / filename
    out_path.write_bytes(pdf_bytes)
    _meta_path(out_path).write_text(json.dumps(meta), encoding="utf-8")

    all_files = sorted(OUTPUT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in all_files[HISTORY_LIMIT:]:
        old.unlink(missing_ok=True)
        _meta_path(old).unlink(missing_ok=True)

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
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
