# Changelog

## v1.0, October 24, 2026: player types, custom players and Community Pool
- **Player types** (Players column P, automatic): **A – Exact clone**, **B – Edited clone** (a clone with some numbers changed), **C – From scratch** (no clone).
- **Custom players.** Madden Tools › Create or edit a custom player opens a panel: B (quick) or C (more involved). Height, weight and skin tone first, then "Matter most for his position", then the other ratings folded away. Save any time; anything left alone stays at the default (his clone's number for B, the average NFL player at his position for C).
- Overall ratings use EA's own formula per position, worked out from EA's 2003-2007 rosters (matches every EA player to within 1 point). B moves the clone's overall by the change; C is worked out from all his numbers.
- **Custom Players** tab holds the numbers for B and C players, with a **Show** dropdown that shows only the ratings that matter for a group (QBs, linemen, kickers ...).
- **Switches.** Players: Show B and Show C (hide or show those rows). Build Your Squads: Allow B and Allow C (off = not counted, not on Rosters cards, not built).
- **Community Pool.** Submit a player (emails Malcolm a code), Add a pool submission (Master only), Add a player from the Community Pool.
- Roster Kit builds B and C players and lists anyone left out by a switch (tested; workbooks without custom players still build byte-identical rosters).

## October 23, 2026 (night): Roster Kit
- New one-file Windows program, MaddenRosterKit.exe (built on GitHub; no Python needed).
- One front door for every input: Google Sheets link, .xlsx, the tab CSVs, or an old v5 list.
- Output goes into month folders (output\YYYYMM); older files are sorted in too.
- Kit source, credits and the build recipe are in this repository.
- Tested: link-free inputs all build a byte-identical roster to the known-good build; the Windows program built a roster on a real PC that played in Madden 08.

## October 23, 2026 (evening): automatic script
- Players always shows 10 empty rows below the last player; no menu needed.
- Row colors follow the Settings cells by themselves (on open, and when you click back onto Players).
- Number of squads also applies itself when the workbook opens.
- Clone dropdowns reset themselves on open, after sorting, and when a Position or Clone is pasted.
- Menu items renamed so each says what it does; new **What do these do?** item and a MADDEN TOOLS MENU section in READ ME FIRST. "Show 10 more rows" removed (automatic now).

## October 23, 2026: first release

**Workbook (Master Madden List v6)**
- Build Your Squads is one row per squad. Set *Number of squads* (1–32) at the top; extra rows hide.
- New **Rosters** tab: one card per squad with its ready players and a colored status bar.
- Players column M (Squads) is a multi-pick list; a player can be on several squads and gets a copy on each.
- Row colors come from the Settings "made their bones" cells: color the cell, then Madden Tools › Apply colors.
- Renaming a squad moves its players; deleting one offers to clear it from Players; Madden Tools › Clean up squads finds leftovers.
- Squad names can't contain commas or start/end with a space (a trailing space broke chips).
- Two squads can't replace the same team; a real NFL team turns red and asks first.
- Pool: 240 players. New Bones places: Union, Caldwell, Elizabeth, Morris Knolls. Squad 7 *Out of Town Boys* (replaces Admirals A).

**Roster Kit**
- Base roster `FF-299team-reserves.ros`: 76 reserve slots, tested in the game.
- Builder reads the one-row layout, skips empty squads, warns about duplicate teams, and deletes leftover reserve copies.
- Skin tone now carries over (the face is matched to the tone).
- The finished roster is copied into `Documents\Madden NFL 08\Rosters` automatically.

**Proof:** a roster built from the workbook before and after the layout change is byte-identical.

## October 22, 2026
- Reserve slots added and tested; game limit of 299 teams found.
- Duplicate-team checks in the sheet, the script and the builder.

## October 21, 2026
- v6 created from the v5 Madison & Glassboro player list.
