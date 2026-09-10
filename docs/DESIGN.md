# Gridiron Desk design system

Night Edition identity (chosen 2026-07, design-mock round 1) with the
Above the Fold hierarchy (chosen 2026-09-05, design-mock round 2; mocks in
`design-mocks/`). Presentation lives in `frontend/src/index.css`; the tokens
below are the contract every component draws from.

## Palette

| token | value | role |
|---|---|---|
| `--paper` | #161814 | page stock, warm near-black |
| `--paper-deep` | #20231D | lifted stock: table heads, hover, the GM's note |
| `--ink` | #EDE9DD | primary print, bone white |
| `--ink-soft` | #A9A491 | secondary print: meta, captions, unfavored figures |
| `--rule` / `--rule-soft` | rgba(237,233,221,.22 / .10) | hairlines, baseline grid |
| `--green` | #4DB47F | the single accent: the needle, the lead's kicker, the largest edges, points on the table |
| `--amber` | #D4A853 | settled: a finished game's row and its Final mark in the starters lists |
| `--clay` | #C4614E | the GM says no: a decline verdict, a starter listed out |

No glow, no shadows, no border radius. Team colors appear only inside logo chips.

## Type

- Serif body: Charter / Bitstream Charter / Sitka / Cambria / Georgia.
- Grotesque for names, figures and labels: Helvetica Neue / Helvetica / Arial.
- Mono for captions and stamps: the system monospace stack.

The scale (tokens in `:root`, phone values in the 680px media block):

| token | desktop | phone | used for |
|---|---|---|---|
| `--display` | 56px | 40px | the one thing that leads a page: the lead game's names and figures, the GM's points on the table |
| `--lede` | 28px | 22px | page and league names (`.bigname`, `.bigselect`), the market line in the lead |
| `--section` | 18px | 18px | day and group heads (`.dayhead h2`) |
| `--fig` | 16px | 16px | figures in the index and ledgers |
| `--body` | 15px | 15px | prose |
| `--cap` | 11px | 11px | the two small styles that survive: the kicker (grot 800, .18em, green) and the footnote (mono) |

Every other small-caps label from the card era is gone; a column header or a
group head says a thing once.

## Structure

- Nameplate (`.plate`): one sticky line of chrome: 34px Desk mark, 20px
  wordmark, the four sections inline, then the page's own controls and the
  account corner. Under 680px the sections hide and the bottom gutter
  carries navigation. Desks with sub-pages print a thin `.subnav` row.
- Page head (`.pagehead`): kicker, the page or league name at lede size (a
  native select dressed as the name where the reader picks a week), mono
  meta, and the page's controls pushed right.
- The lead (`.lead`): the Slate opens with one game at display size (the
  live game, else the next kickoff, else the last final) with the market
  line, the FPI line, a one-sentence read, and the full-width win gauge:
  one hairline and one green needle (`.lead-gauge`).
- The index (`.index`): every other game as one line, grouped by day in
  kickoff order, the kickoff printed beside the matchup. Columns: LINE
  (market, favorite by), FPI LINE (model, favorite by), WIN PROBABILITY
  (FPI), EDGE (model vs market, printed for the team the model likes more;
  the week's three largest in green). Records and probability hide under
  860px, the FPI column under 680px.
- Fantasy: each in-season league is a block (`.league`) with a page head
  and the GM's note (`.gm`) as its lead: the number left with the matchup
  and prose, the lineup card, the wire and the phones as tables right; the
  live matchup follows. Leagues without a roster print as one line each.

## Data honesty

The "model" figures are ESPN's Football Power Index (`teampredptdiff`,
`gameprojection`), never "the Desk's own model"; the front page prints the
FPI expected margin as a line beside the market line, and the edge is the
difference between the two. Fantasy projections are Sleeper's weekly
stat-level projections under each league's scoring, blended with the Desk
season model (see `PLAN-WEEK-ROOM.md`).
