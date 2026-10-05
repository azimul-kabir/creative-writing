"""
Daily Creative Spark — "Generate today's prompt"
==================================================

Writes a day's writing prompt as text in the same format you'd paste by
hand (see README "The prompt format"), so it drops straight into the web
form's textarea, where it can be edited before the PDF is made.

Three ways to get one:

* Gemini (free tier) — set GEMINI_API_KEY (free from aistudio.google.com)
* Claude (paid API)  — set ANTHROPIC_API_KEY
* No key at all      — chat_prompt_text() builds the same request as a
  message to paste into the Gemini app or claude.ai, whose reply is
  pasted back into the form.

With both keys set, Gemini is used unless PROMPT_PROVIDER=claude.

Each weekday has a fixed writing focus (WEEKLY_PLAN) so a week works
through a progression of Cambridge Stage 3 skills; the topic, questions,
and words change every time.

The requests never include the child's name or school: the name is only
added locally, when the text is formatted.
"""

import json
import os

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

# weekday -> (category shown on the worksheet, the skill to practise)
WEEKLY_PLAN = {
    "Monday": (
        "Character Description",
        "Describing what a character looks like and what they are like inside, "
        "giving reasons with 'because'.",
    ),
    "Tuesday": (
        "Setting & Senses",
        "Expanded noun phrases (two describing words before a noun) and words "
        "for what you can see, hear, smell, touch and taste.",
    ),
    "Wednesday": (
        "Dialogue",
        "Using speech marks correctly and stronger words than 'said' "
        "(whispered, shouted, giggled).",
    ),
    "Thursday": (
        "Adventure Story",
        "Putting events in order with time connectives (first, then, next, "
        "after that, finally) and exclamation marks for excitement.",
    ),
    "Friday": (
        "Problem & Solution Story",
        "A three-paragraph story (beginning, problem, how it is solved) joined "
        "with and, but, so, because.",
    ),
    "Saturday": (
        "Diary or Letter",
        "Writing in the first person and the past tense, and saying how you felt.",
    ),
    "Sunday": (
        "Imagine If...",
        "Using questions and exclamations to make imaginative writing lively.",
    ),
}

SYSTEM_PROMPT = """You write one day's creative-writing prompt for a worksheet a parent prints at home.

The writer is an 8-year-old girl in Class II at a Cambridge curriculum school in Dhaka, Bangladesh (Cambridge Primary English Stage 3). She writes 10-15 sentences in 3 paragraphs.

What makes a good prompt for her:
- A topic an 8-year-old finds exciting or funny, which she can picture straight away. Mix everyday life (school, family, Dhaka, rain, festivals such as Eid or Pohela Boishakh, rickshaws, the rooftop, the market) with fantasy, animals, space and adventure. Keep it warm; nothing scary or sad.
- A story starter of one or two sentences in the first person that stops mid-moment with "..." so she wants to carry on.
- Three short chat questions a parent asks out loud to get ideas flowing. Each asks about something she can imagine or remember, not a yes/no question. Under 20 words each.
- Five Word Vault words that stretch her a little past everyday words and fit the topic and today's skill. Each has a child-friendly meaning of 2 to 5 words, written so an 8-year-old understands it without help.
- One optional Star Challenge that practises today's skill in a playful way, in one sentence.
- Use British spelling (colour, favourite, cosy). Write every child-facing line in words she can read herself.

The focus skill line is for the parent: one sentence naming the skill, with a tiny example if it helps."""

USER_PROMPT = """Write the prompt for {weekday}.

Today's writing type: {category}
Today's skill: {skill}
{theme_line}{avoid_line}"""

# Appended for the copy-into-a-chat-app version, which has to come back as
# paste-ready text rather than JSON.
CHAT_FORMAT = """
Reply with only the worksheet prompt inside one code block, in exactly this format (keep the labels and the backticks around each Word Vault word):

```
{example}```"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "focus_skill": {"type": "string"},
        "topic_title": {"type": "string"},
        "prompt_starter": {"type": "string"},
        "chat_questions": {"type": "array", "items": {"type": "string"}},
        "word_vault": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["word", "meaning"],
                "additionalProperties": False,
            },
        },
        "challenge": {"type": "string"},
    },
    "required": [
        "focus_skill", "topic_title", "prompt_starter",
        "chat_questions", "word_vault", "challenge",
    ],
    "additionalProperties": False,
}


class PromptGenerationError(Exception):
    """A user-facing reason the prompt couldn't be generated."""


def active_provider():
    """'gemini', 'claude', or None when no API key is configured."""
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    has_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
    preferred = (os.environ.get("PROMPT_PROVIDER") or "").strip().lower()
    if preferred == "claude" and has_claude:
        return "claude"
    if preferred == "gemini" and has_gemini:
        return "gemini"
    if has_gemini:
        return "gemini"
    if has_claude:
        return "claude"
    return None


def _user_prompt(weekday, theme, recent_topics):
    if weekday not in WEEKLY_PLAN:
        raise PromptGenerationError(f"Unknown weekday: {weekday!r}")
    category, skill = WEEKLY_PLAN[weekday]
    theme = (theme or "").strip()
    theme_line = f"Theme she asked for: {theme}\n" if theme else ""
    recent = [t for t in recent_topics if t][:14]
    avoid_line = (
        "Recent topics she has already written about (choose something different):\n"
        + "\n".join(f"- {t}" for t in recent) + "\n"
    ) if recent else ""
    return USER_PROMPT.format(
        weekday=weekday, category=category, skill=skill,
        theme_line=theme_line, avoid_line=avoid_line,
    )


def generate_prompt_text(weekday, student_name="Adeeba", theme="", recent_topics=()):
    """Ask the configured model for a prompt; return it as worksheet text."""
    user = _user_prompt(weekday, theme, recent_topics)
    provider = active_provider()
    if provider == "gemini":
        raw = _ask_gemini(user)
    elif provider == "claude":
        raw = _ask_claude(user)
    else:
        raise PromptGenerationError(
            "No API key is set, so use \"Copy for Gemini / Claude chat\" instead "
            "(or add a free GEMINI_API_KEY).")
    try:
        data = json.loads(raw)
    except ValueError:
        raise PromptGenerationError("The answer wasn't in the expected format - try again.")
    return format_prompt_text(weekday, WEEKLY_PLAN[weekday][0], data, student_name)


def chat_prompt_text(weekday, student_name="Adeeba", theme="", recent_topics=()):
    """The same request as one message to paste into the Gemini app or
    claude.ai, asking for a reply that can be pasted straight back."""
    user = _user_prompt(weekday, theme, recent_topics)
    example = format_prompt_text(weekday, WEEKLY_PLAN[weekday][0], {
        "focus_skill": "...",
        "topic_title": "...",
        "prompt_starter": "...",
        "chat_questions": ["...", "...", "..."],
        "word_vault": [{"word": "word", "meaning": "short meaning"}] * 5,
        "challenge": "...",
    }, student_name)
    return f"{SYSTEM_PROMPT}\n\n{user}{CHAT_FORMAT.format(example=example)}"


def _ask_gemini(user):
    from google import genai

    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            input=user,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": OUTPUT_SCHEMA,
            },
            timeout=90.0,
        )
    except Exception as exc:
        # The SDK's error classes aren't exported publicly, so sort by the
        # HTTP status they carry; anything that isn't an API error re-raises.
        if not type(exc).__module__.startswith("google."):
            raise
        status = getattr(exc, "status_code", None)
        if status in (401, 403) or "API_KEY_INVALID" in str(exc):
            raise PromptGenerationError(
                "The Gemini API key was rejected - check GEMINI_API_KEY.")
        if status == 429:
            raise PromptGenerationError(
                "Gemini's free daily limit is used up (or it's busy) - try again later.")
        if status:
            raise PromptGenerationError(f"Gemini returned an error ({status}).")
        raise PromptGenerationError("Couldn't reach Gemini - check the internet connection.")

    if interaction.status != "completed" or not interaction.output_text:
        raise PromptGenerationError(
            "Gemini didn't finish the prompt - try again or pick a different theme.")
    return interaction.output_text


def _ask_claude(user):
    import anthropic

    try:
        client = anthropic.Anthropic(timeout=90.0)
        response = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        raise PromptGenerationError(
            "The Anthropic API key was rejected - check ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        raise PromptGenerationError("Claude is busy right now - try again in a minute.")
    except anthropic.APIStatusError as exc:
        raise PromptGenerationError(f"Claude returned an error ({exc.status_code}).")
    except anthropic.APIConnectionError:
        raise PromptGenerationError("Couldn't reach Claude - check the internet connection.")

    if response.stop_reason == "refusal":
        raise PromptGenerationError("Claude declined that request - try a different theme.")
    if response.stop_reason == "max_tokens":
        raise PromptGenerationError("Claude's answer was cut off - please try again.")
    return next((b.text for b in response.content if b.type == "text"), "")


def format_prompt_text(weekday, category, data, student_name="Adeeba"):
    """Turn the generated fields into the hand-written prompt format that
    worksheet.parse_prompt() reads."""
    day_num = WEEKDAYS.index(weekday) + 1
    starter = data["prompt_starter"].strip().strip('"“”')
    vault = ", ".join(
        f"`{w['word'].strip()}` ({w['meaning'].strip().rstrip('.')})"
        for w in data["word_vault"]
    )
    lines = [
        f"Day {day_num} ({weekday}): {category}",
        "",
        f"* Focus Skill: {data['focus_skill'].strip()}",
        f"* Topic: {data['topic_title'].strip()}",
        f'* Story / Prompt Starter: "{starter}"',
        f"* 3-Minute Chat Prompts (Ask {student_name}):",
    ]
    lines += [f"   {i}. {q.strip()}" for i, q in enumerate(data["chat_questions"], 1)]
    lines.append(f"* Word Vault (Aim for 3): {vault}")
    if data.get("challenge", "").strip():
        lines.append(f"* Star Challenge (Optional): {data['challenge'].strip()}")
    return "\n".join(lines) + "\n"
