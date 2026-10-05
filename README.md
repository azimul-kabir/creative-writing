<p align="center">
  <img src="docs/hero.png" alt="Daily Creative Spark — paste a day's writing prompt, get a print-ready A4 worksheet PDF" width="100%">
</p>

# creative-writing — Daily Creative Spark worksheet generator

A small web app: paste a day's writing prompt, get back a print-ready
"Daily Creative Spark" worksheet PDF (the same design as the original
worksheet), ready to download or print. Built to run in Docker on a
Synology NAS, but works anywhere Docker does.

## Screenshots

**The web app** — paste the prompt (or click *use example*), optionally
override the student name / class / goal / footer, and hit *Generate
PDF*. Every worksheet you make is kept under *Recent worksheets*.

<p align="center">
  <img src="docs/screenshots/web-form.png" alt="The web form with the Day 2 example prompt filled in, the Settings panel open, and three recent worksheets listed" width="760">
</p>

It also works from a phone on the same network — the layout collapses to
a single column and the history list stacks so nothing runs off-screen:

<p align="center">
  <img src="docs/screenshots/web-mobile.png" alt="The web app on a phone-width screen, with the example prompt filled in and the recent worksheets stacked" width="280">
</p>

**The worksheets it produces** — two A4 pages each, generated from the
prompt text alone and pitched at age 8–9 (Cambridge Stage 3/4):

- **Page 1** has the writing quest, chat questions, a Word Vault with a
  short meaning under each word, a *Plan it first* strip (Beginning →
  Middle → End with hint questions), the start of the story, and a
  checklist of Stage 3/4 writing habits (joining words, paragraphs,
  speech marks, reading it back). Stars and faces are left empty for the
  writer to colour in herself.
- **Page 2** is a full page of ruled lines to carry on the story, with an
  *Edit & improve* box at the bottom: swap two plain words for stronger
  ones, count sentences and paragraphs, and a line for a grown-up's
  comment.

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/worksheet-day2.png" alt="Day 2 worksheet, page 1: The Busy Rainy Afternoon">
      <br><sub>Day 2, page 1 — <code>examples/day2_prompt.txt</code></sub>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/worksheet-day2-page2.png" alt="Day 2 worksheet, page 2: more writing lines and an Edit and improve box">
      <br><sub>Day 2, page 2 — more writing space</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/worksheet-day4.png" alt="Day 4 worksheet, page 1: The Day My School Bag Grew Wings">
      <br><sub>Day 4 — <code>examples/day4_prompt.txt</code> (long lines wrap)</sub>
    </td>
    <td></td>
  </tr>
</table>

Pick *1 page* under Settings (or set `PAGES: "1"` in
`docker-compose.yml`) if you only want the first sheet.

## What's in here

```
app.py                 Flask web app (the routes)
prompt_generator.py     "Make today's prompt" — Gemini / Claude / copy-for-chat
prompt_bank.py          "Pick from prompt bank" — hands out the next unused prompt
prompt_bank.json        the 70 ready-written prompts (10 per weekday); add your own here
star_chart.py           the printable monthly writing star chart
progress.py             progress tracker & portfolio: storage, stats, sentences chart
templates/progress.html the Progress & portfolio page
worksheet.py            Core module: PDF drawing engine + prompt parser
                        (also runnable as a CLI — see below)
templates/index.html    The single-page form + history UI
requirements.txt        Python deps
Dockerfile              Container image
docker-compose.yml      One-file deploy (works in Synology Container Manager)
examples/day2_prompt.txt  A sample prompt in the expected format
docs/                   README hero image + screenshots
                        (docs/hero.html is the hero's source)
```

## Make today's prompt (prompt bank, Gemini, Claude, or copy-paste)

Don't want to write the day's prompt yourself? The box at the top of the
form makes one for you:

1. Pick the **day**. It defaults to today, and each day has its own
   writing focus, so a week works through a mix of Cambridge Stage 3
   skills:

   | Day | Writing type | Skill practised |
   |---|---|---|
   | Monday | Character Description | describing looks and personality, giving reasons with *because* |
   | Tuesday | Setting & Senses | two describing words before a noun; sight, sound, smell, touch, taste |
   | Wednesday | Dialogue | speech marks; stronger words than *said* |
   | Thursday | Adventure Story | time connectives (*first, then, finally*); exclamation marks |
   | Friday | Problem & Solution Story | three paragraphs joined with *and, but, so, because* |
   | Saturday | Diary or Letter | first person, past tense, feelings |
   | Sunday | Imagine If... | questions and exclamations |

2. Optionally type a **theme** (space, Eid, a lost kitten...). The
   prompt bank ignores themes.
3. Then pick one of these:
   - **Pick from prompt bank** (free, offline, instant). Fills in the
     next unused ready-written prompt for that day. The bank has 70
     prompts, 10 for each weekday, so it covers 10 weeks. Press it again
     for a different one. When a day's 10 are all used, that day starts
     again from the first. Used prompts are remembered in
     `data/prompt_bank_used.json`; delete that file to start the whole
     bank over.
   - **Print a week from the bank** makes **one PDF with 7
     worksheets**, starting from the day you picked (choose Saturday for
     a Saturday-to-Friday week). Each sheet gets the next unused bank
     prompt for its day, and with *print dates on the sheets* ticked,
     its Date and Day boxes are filled in (e.g. "11 Oct", "Sat"). It
     uses your Settings, so with 2 pages per sheet it's 14 pages: print
     double-sided and there's one sheet of paper per day.
   - **Generate today's prompt** (needs an API key, see below). The
     prompt box fills in by itself, usually within a minute.
   - **Copy for Gemini / Claude chat** (no key needed). This copies a
     ready-made message. Paste it into the Gemini app or claude.ai, which
     your Gemini or Claude subscription covers, then paste the reply's
     code block into the prompt box.
4. Read it over, edit anything, then press **Generate PDF**.

Every option gives you a topic, story starter, chat questions, Word Vault
words *with meanings*, and a Star Challenge, written for an 8-year-old in
Dhaka. It mixes everyday Bangladeshi life with fantasy and adventure,
uses British spelling, and avoids topics from your recent worksheets. The
request never includes her name or school; the name is only added
locally. The weekly plan and the instructions live at the top of
`prompt_generator.py` if you want to change them.

### Monthly star chart

Below the prompt box is **Monthly star chart**. Pick the month (this month or
one of the next two) and the day your week starts on (Saturday, Sunday or
Monday), then press **Print star chart**. You get one A4 page:

- **A calendar for the month.** Each day has an empty star to colour on days
  she writes, and the writing type for that weekday (Character, Senses,
  Dialogue...).
- **My streaks:** stars this month, longest streak, and best story.
- **Milestones:** badges at 5, 10, 15, 20 and 25 stars to colour in.
- **My reward:** "When I colour __ stars, my reward is __", signed by her and
  a grown-up, plus "I'm proud of myself because…".

It uses the name and footer from Settings. Star charts appear in *Recent
worksheets*, but their titles aren't treated as story topics.

### API keys (optional)

Put a key in a file called `.env` next to `docker-compose.yml` (it's
git-ignored), then rebuild with `docker compose up -d --build`:

```
# free: create one at https://aistudio.google.com/apikey
GEMINI_API_KEY=...
```

- **Gemini** (`GEMINI_API_KEY`) is **free**. The free tier's daily limit
  is far more than one prompt a day. On the free tier, Google may use
  requests to improve its products. It tries `gemini-3.8-flash` first.
  If that model is overloaded ("high demand") or its free quota is used
  up, it moves on to `gemini-3.7-flash`, then `gemini-3.5-flash`. Each
  model gets up to 40 seconds (the last one gets whatever is left), and
  all of them 2 minutes together (`PROMPT_TIMEOUT`, in seconds). The page
  keeps checking back while it waits, so a slow reply isn't cut off by a
  reverse proxy. To change the list, set `GEMINI_MODEL` to
  comma-separated model IDs.
- **Claude** (`ANTHROPIC_API_KEY`, from
  [console.anthropic.com](https://console.anthropic.com)) is paid
  separately from a Claude Pro subscription, at roughly 5–10 US cents a
  prompt with the default model.

If both keys are set, Gemini is used unless `PROMPT_PROVIDER=claude`.
When running locally without Docker, `export GEMINI_API_KEY=...` before
`python3 app.py`.

**Paste-back tip:** the prompt box accepts text pasted from a chat app
as-is. Code fences, **bold** labels and a "Here's your prompt!" line
are all ignored.

## Progress & portfolio

The **Progress & portfolio** link at the top of the main page opens a page
for keeping track of her writing over the term.

**Log a finished worksheet.** Fill in:
- the date and topic (recent topics are suggested as you type);
- a **photo of the pages** (on a phone this offers the camera);
- sentences, paragraphs and Vault words used;
- which **Detective checklist** habits she managed;
- her own **stars** and **face**;
- a note from you.

In *Recent worksheets*, each sheet's **Log it** link opens the form with the
topic and writing type already filled in.

**See progress at a glance:**
- stories logged, this month, current and longest streak;
- average sentences in her last 5 stories, compared with her first 5;
- a chart of sentences per story, with the 10–15 goal marked;
- how often she manages each checklist habit, most-missed first;
- average sentences by writing type.

**The portfolio** keeps every logged story, newest first, with its photo,
numbers and your note. Tap a photo to see it full size.

Everything is stored on the NAS in the data folder: `data/progress.db` (a
SQLite database) and `data/portfolio/` (the photos). It's covered by the same
volume, so it survives rebuilds; back up `data/` to keep it safe. Uploads are
limited to 40 MB at a time.

## The prompt format

Paste something shaped like this (this is exactly the format from the
original request — field order doesn't matter, but keep the `* Label:`
bullets):

```
Day 2 (Tuesday): Sensory Description

* Focus Skill: Expanded noun phrases (adding two vivid adjectives before a noun) and sound/sight sensory words.
* Topic: The Busy Rainy Afternoon
* Story / Prompt Starter: "Looking out my window, the sky turned a dark, moody grey..."
* 3-Minute Chat Prompts (Ask Adeeba):
   1. What sounds do the raindrops make against the glass or on the balcony?
   2. What do the streets and trees look like when it pours?
   3. What is your favourite thing to eat, drink, or do while listening to the storm?
* Word Vault (Aim for 3): `pattered` (tapped lightly), `gloomy` (dark and sad), `splashed` (water jumped up), `cosy` (warm and snug), `drenched` (very, very wet)
* Star Challenge (Optional): Describe the rain puddles without using the word "water".
```

**Word Vault meanings** are optional: put a short, child-friendly meaning
in brackets after a word — `` `drenched` (very, very wet) `` — and it's
printed under that word's chip. `` `drenched` = very wet `` works too
(brackets are safer if the meaning has a comma). Keep meanings to a few
words so they fit.

Long topics, story starters and focus skills wrap onto extra lines, and
the quest box grows to fit them.

The parser is forgiving about label wording (`Story Starter` / `Prompt
Starter`, `Chat Questions` / `Chat Prompts`, `Challenge` / `Bonus
Challenge`, etc.) — it matches on keywords, not exact text. If you'd
rather hand it exact data, you can also paste raw JSON (starting with
`{`) with the fields listed at the top of `worksheet.py`.

The "Settings" panel on the page lets you override the student name,
class label, goal text, and footer text for a single worksheet without
editing anything — the values baked into the Docker image (below) are
just the defaults.

## Run it locally (no Docker)

```bash
pip install -r requirements.txt
python3 app.py
# open http://localhost:5000
```

Or use the generator straight from the command line, no server needed:

```bash
python3 worksheet.py examples/day2_prompt.txt
# -> day_2_tuesday_worksheet.pdf
```

## Build & run with Docker

```bash
docker build -t creative-writing .
docker run -d --name creative-writing \
  -p 5000:5000 \
  -v "$(pwd)/data:/data" \
  -e STUDENT_NAME="Adeeba" \
  -e CLASS_LABEL="Class II • Cambridge" \
  creative-writing
```

Or the same thing with compose:

```bash
docker compose up -d --build
```

Then open `http://<host>:5000`.

## Deploying on a Synology NAS

The easiest path is **Container Manager → Project**, which reads
`docker-compose.yml` directly:

1. Copy this whole folder onto the NAS (e.g. via File Station or a
   shared folder mounted from your computer) — for example to
   `/docker/creative-writing`.
2. Open **Container Manager** → **Project** → **Create**.
3. Set the project name (e.g. `creative-writing`), point **Path** at the
   folder you copied, and choose **docker-compose.yml** as the source.
4. Build and start the project. Synology will build the image from the
   `Dockerfile` and start the container with the volume/env settings
   from `docker-compose.yml`.
5. Once it's running, browse to `http://<nas-ip>:5000` from any device
   on your network.

If you'd rather not use Container Manager's Project feature, you can
also build the image over SSH with the plain `docker build` /
`docker run` commands above — Synology's Docker/Container Manager ships
a compatible `docker` CLI.

**Persisting worksheets:** the compose file mounts `./data` (inside the
project folder) to `/data` in the container — every generated PDF is
saved there and listed on the page under "Recent worksheets", so it
survives container restarts and image rebuilds.

**Changing the port:** edit the `ports:` line in `docker-compose.yml`
(e.g. `"8080:5000"`) if 5000 is already used on your NAS.

## Pushing this to your GitHub repo

If you're setting this up from the zip rather than already being inside
a git checkout:

```bash
cd creative-writing
git init
git add .
git commit -m "Initial commit: Daily Creative Spark worksheet generator"
git branch -M main
git remote add origin https://github.com/azimul-kabir/creative-writing.git
git push -u origin main
```

(If the GitHub repo already has a README/license from creation, do
`git pull --rebase origin main` before the push, or push with `--force`
if you're sure the repo is otherwise empty.)

## Customizing the design

All drawing logic lives in `worksheet.py` (`draw_header`,
`draw_quest_box`, `draw_two_column`, `draw_plan_strip`,
`draw_story_area`, `draw_footer_panel`) — colors are defined once at the top of the file
as `HexColor(...)` constants if you want to re-theme it (e.g. for a
different class or a different color per weekday).

Via JSON input you can also set:

- `plan_labels`: e.g. `["Who?", "Where?", "What happens?"]`, or
  `[["Beginning", "Who? Where?"], ...]` to add a hint after each label,
  or `[]` to hide the plan strip
- `line_spacing_mm`: the gap between writing lines (default 9)
- `guide_lines`: `true` adds a dotted mid-line for letter sizing, which
  helps younger writers
- `story_lines`: a fixed number of page-1 writing lines (by default it
  fills the space)
- `pages`: `1` or `2`
