MADISON MADDEN 08 ROSTER KIT
============================
Turns the player spreadsheet into a Madden NFL 08 (PC) roster file (.ros).
Every player is an exact-ratings clone of one real NFL player-season.
Step-by-step help: https://coachmalcolm.github.io/madden/

WHAT YOU NEED (one time)
  Windows: unzip MaddenRosterKit-windows.zip anywhere. Nothing to install.
  (Running from source instead: Python 3 from python.org, tick "Add python.exe to PATH".)

CUSTOM PLAYERS
  Players made with Madden Tools > Create or edit a custom player are saved on the workbook's
  Custom Players tab. The kit reads it automatically (also from a Custom Players CSV):
    A = his clone with your numbers on top; B = from scratch, built on an average player at his
    position. Blank numbers keep the default. The overall uses EA's formula for the position.
  The report lists every custom player under "custom players".

BUILD A ROSTER (the easy way)
  1. Double-click MaddenRosterKit.exe (from source: "Madden Roster Kit.bat").
  2. Give it your list, any of these:
       - your Google Sheets link (the sheet must be shared "Anyone with the link"),
       - the workbook as .xlsx (File > Download > Microsoft Excel),
       - the CSV files for Players and Build Your Squads (and Settings if you like):
         File > Download > Comma-separated values on each tab; drag them all in at once,
       - an old v5 list saved as .csv.
     Paste the link or drag the file(s) into the window, press Enter.
  3. Type a roster name, 8 letters or numbers (e.g. SQUADS1).
  4. The roster and report land in output\YYYYMM (this month), and the roster is copied into
     Documents\Madden NFL 08\Rosters. Older loose files in output get sorted into month folders.

BUILD FROM THE MASTER MADDEN LIST v6
  1. In the workbook, Build Your Squads: set Number of squads (1-32) at the top, then one row per
     squad: its name, the team it Replaces, and optionally the City and Nickname the game shows.
     Pick a RESERVE SLOT (Broncos A, Raiders B, Admirals A ... 76 of them) and every real team stays
     in the game: your squad wears that team's uniforms, logo and stadium. In the game's team select
     it appears under the team it borrows from (Broncos A > under BRONCOS), showing your nickname.
     Picking a real NFL team instead replaces that team (the sheet turns it red and asks first).
  2. Players tab, column N (Squads): pick every squad each player is on. Several are allowed.
     Empty squads are skipped when building.
  3. File > Download > Microsoft Excel (.xlsx). Put the file in the "input" folder.
  4. Drag the .xlsx onto BUILD_ROSTER.bat (it also still takes the old .csv). Type a short name (SQUADS1). Done.
  5. output\SQUADS1.ros is the roster; output\SQUADS1_report.txt lists what was built.
     The .ros is also copied straight into Documents\Madden NFL 08\Rosters (same name; an older
     file with that name is replaced). Use --no-copy to skip that.
  What it does: your players go on the replaced team. For each position still below the Settings
  minimum, the replaced team's best player at that position stays. The rest of a reserve slot is
  deleted (they are only copies, and this keeps room in the file); the rest of a real team goes to
  free agency. Skin tone is applied. In Madden 08 the FACE carries the skin colour, so when the
  sheet's skin tone differs from the clone's face, the player gets a stock face of that tone (the
  same one every build). Any rating over the OP limit puts [OP] in the report title.
  Checks first and stops on: over 55 (players + open spots), same name and position twice on a squad,
  a squad with no team picked, two squads replacing the same team, clones that don't match.

OLDER SIX-COLUMN LAYOUT
  Workbooks from before 10/23 (squads in columns, tick boxes P-U on Players) still build the same
  way; the builder reads both layouts and gives the identical roster from the same squads.
  A player on a squad name that isn't on Build Your Squads (misspelled, renamed, or past the
  Number of squads) is left out, and the report names the squad and the Players rows.

BUILD A ROSTER THE OLD WAY (v5 sheet, CSV)
  1. In your copy of the spreadsheet, on "Alumni & Teammates":
       - give each player a Position, a Clone (Clone check says OK) and a Madden Team.
  2. File > Download > Comma-separated values (.csv). Put the file in the "input" folder.
  3. Team names: edit input\teams.csv (Madden Team, New City, New Nickname). Leave a team out to keep its name.
  4. Drag the CSV onto BUILD_ROSTER.bat. Type a short name (MAGOLD6). Done.
  5. output\MAGOLD6.ros  is the roster;  output\MAGOLD6_report.txt  lists what was built.
  6. Copy the .ros into  Documents\Madden NFL 08\Rosters  and in Madden: Main Menu > Menu > Files > Load.

THE ONE RULE
  The base roster must match the mod installed on the PC, or the game freezes at kickoff.
  rosters\base\FF-223team-base.ros matches Malcolm's FF mod (223 teams, 1,400 uniforms).
  rosters\base\FF-299team-reserves.ros = that roster + 76 reserve slots (the v6 builder's default).
  The list of slots is in FF-299team-reserves.ros.json.
  GAME LIMIT: 299 teams. At 300 or more every game quits before the coin toss (tested 10/22),
  even though the file has room for 301. New teams or custom assets must REPLACE a reserve slot.
  lib\reserve_team.py makes reserve slots (tested 10/22: reserve vs real, reserve vs reserve,
  reserve vs its own source team all play).
  Different mod?  python madden_build.py input\players.csv NAME --base "path\to\that mod's roster.ros"

WHAT THE BUILDER CHECKS BEFORE BUILDING (and stops on errors)
  - clone exists in the ratings database and plays the same position
  - team exists in the base roster
  - same name at the same position twice  (use --allow-dupes if intended)
  - warns on shared jersey numbers within a team
  - lists players skipped because they have no clone yet

WHAT IT DOES
  - copies each clone's full player record from its source roster, puts on the name and number
  - over 55 on a team: releases the lowest-rated NFL players (created players are never cut)
  - depth chart: your guys first at their position, best returners at KR/PR, your kicker on kickoffs
  - renames teams (city + nickname; the 3-letter code stays so the artwork still matches)
  - matches look settings (sleeves, face mask, skin code...) to what the base roster uses; ratings untouched
  - recalculates the file checksums so Madden accepts it

OPTIONS
  --check-only    run the checks, build nothing
  --no-depth      keep the base roster's depth chart
  --teams FILE    team renames file
  --base FILE     base roster for a different mod

FOLDERS
  lib\              the code (tdb.py reads roster files, clone.py writes them, build_showdown.py builds)
  data\             greats_v3.json: 30,527 player versions with every rating and where each lives
  rosters\sources\  the rosters clones are copied from (1995-2007, ROJO 2020, JINX 2026, GHT 1.5)
  rosters\base\     base rosters to build on
