# Madison Madden 08

Put the people you played with and against into **Madden NFL 08 (PC)**. Each person gets the exact ratings of an NFL great (a "clone"), joins one or more squads, and plays in the game as a real team.

**User Guide:** https://coachmalcolm.github.io/madden/

## The pieces

| Piece | What it is | Where |
|---|---|---|
| Master Madden List v6 | Google Sheet: players, custom players, squads, rosters, matchups, Community Pool | [Make your own copy](https://docs.google.com/spreadsheets/d/1oWacpslQbD5xzF-0GAfb7CrIAhQ-AIoXba38ctx5G14/copy) |
| Madden Tools | The workbook's menu (Apps Script). It comes with the copy. | Inside the workbook |
| Madden Roster Kit | Program for your PC that turns the workbook into a `.ros` roster file | [Download the latest](https://github.com/CoachMalcolm/madden/releases/latest) (`MaddenRosterKit-windows.zip`), or the source in `kit/` |
| User Guide | Step-by-step help, 8 steps | `index.html` → the link above |

## What you need

- Madden NFL 08 for PC with the **FF roster mod** (the kit's base roster is built for it; another mod can freeze the game at kickoff).
- Nothing else: the Windows download is a single program. (Running from the `kit/` source instead needs Python 3.)
- A Google account for your copy of the workbook.

## Limits worth knowing

- The game plays at most **299 teams**; 300 or more makes it quit before the coin toss.
- 223 teams come with the base roster; **76 reserve slots** (Broncos A, Raiders B, Admirals A …) hold your squads so every real NFL team stays in the game.
- Up to **32 squads**, **55 players** a squad, 1,500 players in the pool.
- **Ratings: standard Madden is 99.** Settings B5 is your limit for any rating (1–127; 127 is the most the game file holds), and Settings B6 is the OP line (99).
  - Typing a rating above B5 is refused.
  - A player who already has a higher number (brought in from a list with a higher limit, or because B5 was lowered) keeps it in the workbook, is flagged **at limit**, and plays at B5 in the roster.
  - Anyone who plays above 99 on his overall or any rating is flagged **OP** everywhere he shows up, and in the roster kit's report.
  - EA's own 100s are exempt: Devin Hester 2007 (Speed 100) and the Madden 99/2000 100 overalls (Barry Sanders, Jerry Rice, Deion Sanders, Shannon Sharpe, Mark Chmura, Tony Boselli, Mike Alstott).
- Weight can be typed up to 500 lbs and age up to 99; the game file holds 415 lbs and 63, so anything higher plays at those.

## Files

- `index.html`: the User Guide (GitHub Pages serves it).
- `kit/`: the Roster Kit source (builder, base rosters, ratings data).
- `workbook/Madden Tools v6 (player types).txt`: the workbook's Madden Tools script, newest version (paste into Extensions > Apps Script). Older versions are kept beside it.
- `.github/workflows/build-windows.yml`: builds `MaddenRosterKit.exe` and the download zip on GitHub.
- `CREDITS.md`: whose rosters and tools this is built on.
- `CHANGELOG.md`: what changed and when.
- `.nojekyll`: tells GitHub Pages to serve the files as they are.

## Credits

Made by Malcolm (Coach Malcolm) for the Madison and Glassboro crowd. Built on rosters made by others: see [CREDITS.md](CREDITS.md). Madden NFL 08 is © Electronic Arts; this project is a fan tool and is not affiliated with EA or the NFL.
