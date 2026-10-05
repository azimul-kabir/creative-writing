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

**The worksheets it produces** — one A4 page each, generated from the
prompt text alone:

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/worksheet-day2.png" alt="Day 2 worksheet: The Busy Rainy Afternoon">
      <br><sub>Day 2 — <code>examples/day2_prompt.txt</code></sub>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/worksheet-day3.png" alt="Day 3 worksheet: The Robot Who Lost Its Shadow">
      <br><sub>Day 3 — a different prompt, same layout</sub>
    </td>
  </tr>
</table>

## What's in here

```
app.py                 Flask web app (the routes)
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
* Word Vault (Aim for 3): `pattered`, `gloomy`, `splashed`, `cosy`, `drenched`
* Star Challenge (Optional): Describe the rain puddles without using the word "water".
```

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
`draw_quest_box`, `draw_two_column`, `draw_story_area`,
`draw_footer_panel`) — colors are defined once at the top of the file
as `HexColor(...)` constants if you want to re-theme it (e.g. for a
different class or a different color per weekday).
