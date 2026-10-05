"""
Daily Creative Spark — built-in prompt bank
=============================================

Ten weeks of ready-written prompts (prompt_bank.json: 10 per weekday,
following prompt_generator.WEEKLY_PLAN), for when no AI is wanted or
available. Free, offline, instant.

pick_next() hands out the next prompt for a weekday that hasn't been used
yet, remembering used ids in a small JSON file in the data folder. When a
weekday's prompts have all been used, that weekday starts again from the
top.

To add prompts, append entries to prompt_bank.json with a new unique id;
they're picked up on the next restart.
"""

import json
from pathlib import Path

from prompt_generator import WEEKLY_PLAN, format_prompt_text

BANK_PATH = Path(__file__).with_name("prompt_bank.json")
USED_FILENAME = "prompt_bank_used.json"

# The parent-facing "Focus skill" line, one per weekday's writing type.
FOCUS_SKILLS = {
    "Monday": "Describing a character's looks and personality, giving reasons "
              "with 'because' (She is kind because she shares her toys).",
    "Tuesday": "Expanded noun phrases - two describing words before a noun "
               "(the cold, grey sky) - and words for the five senses.",
    "Wednesday": "Speech marks around spoken words, a new line for each speaker, "
                 "and stronger words than 'said' (whispered, shouted).",
    "Thursday": "Putting events in order with time connectives (first, then, "
                "after that, finally) and exclamation marks for exciting moments.",
    "Friday": "A three-paragraph story (beginning, problem, solution) with ideas "
              "joined by and, but, so, because.",
    "Saturday": "Writing in the first person and the past tense, and saying how "
                "you felt (I felt nervous when...).",
    "Sunday": "Using questions and exclamations to make imaginative writing "
              "lively (What if...? How amazing!).",
}

_bank = None


def load_bank():
    global _bank
    if _bank is None:
        _bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    return _bank


def _read_used(state_dir):
    try:
        return set(json.loads((Path(state_dir) / USED_FILENAME).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _write_used(state_dir, used):
    path = Path(state_dir) / USED_FILENAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(used)), encoding="utf-8")
    tmp.replace(path)


def pick_next(weekday, state_dir, student_name="Adeeba"):
    """Return the next unused prompt for weekday as worksheet text, plus
    where it sits in that weekday's list, and mark it used."""
    entries = load_bank().get(weekday) or []
    if not entries:
        raise ValueError(f"No prompts in the bank for {weekday!r}")

    used = _read_used(state_dir)
    unused = [e for e in entries if e["id"] not in used]
    restarted = not unused
    if restarted:
        used -= {e["id"] for e in entries}
        unused = entries

    entry = unused[0]
    used.add(entry["id"])
    _write_used(state_dir, used)

    data = {
        "focus_skill": entry.get("focus_skill") or FOCUS_SKILLS[weekday],
        "topic_title": entry["topic_title"],
        "prompt_starter": entry["prompt_starter"],
        "chat_questions": entry["chat_questions"],
        "word_vault": [{"word": w, "meaning": m} for w, m in entry["word_vault"]],
        "challenge": entry.get("challenge", ""),
    }
    return {
        "prompt_text": format_prompt_text(weekday, WEEKLY_PLAN[weekday][0], data, student_name),
        "number": entries.index(entry) + 1,
        "total": len(entries),
        "remaining": len(unused) - 1,
        "restarted": restarted,
    }
