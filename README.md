# Madison Madden 08

Put the people you played with and against into **Madden NFL 08 (PC)**. Each person gets the exact ratings of an NFL great (a "clone"), joins one or more squads, and plays in the game as a real team.

**User Guide:** https://coachmalcolm.github.io/madden/

## The pieces

| Piece | What it is | Where |
|---|---|---|
| Master Madden List v6 | Google Sheet: players, squads, rosters, matchups | [Make your own copy](https://docs.google.com/spreadsheets/d/1oWacpslQbD5xzF-0GAfb7CrIAhQ-AIoXba38ctx5G14/copy) |
| Madden Tools | The workbook's menu (Apps Script). It comes with the copy. | Inside the workbook |
| Madden Roster Kit | Folder on your PC that turns the workbook into a `.ros` roster file | Sent by Malcolm (not in this repo yet) |
| User Guide | Step-by-step help, 8 steps | `index.html` → the link above |

## What you need

- Madden NFL 08 for PC with the **FF roster mod** (the kit's base roster is built for it; another mod can freeze the game at kickoff).
- Python 3 (tick *Add python.exe to PATH* when installing). A no-install version is planned.
- A Google account for your copy of the workbook.

## Limits worth knowing

- The game plays at most **299 teams**; 300 or more makes it quit before the coin toss.
- 223 teams come with the base roster; **76 reserve slots** (Broncos A, Raiders B, Admirals A …) hold your squads so every real NFL team stays in the game.
- Up to **32 squads**, **55 players** a squad, 1,500 players in the pool.

## Files

- `index.html`: the User Guide (GitHub Pages serves it).
- `CHANGELOG.md`: what changed and when.
- `.nojekyll`: tells GitHub Pages to serve the files as they are.

## Credits

Made by Malcolm (Coach Malcolm) for the Madison and Glassboro crowd. Madden NFL 08 is © Electronic Arts; this project is a fan tool and is not affiliated with EA or the NFL.
