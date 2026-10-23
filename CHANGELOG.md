# Changelog

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
