# Uploading to the Steam Workshop

The upload uses Bannerlord's own uploader, `TaleWorlds.MountAndBlade.SteamWorkshop.exe` in the game's
`bin\Win64_Shipping_Client`. It rides the logged-in Steam client: no SteamCMD, no password. Have Steam
running and logged in.

Item: **3811452468** (created Private 2026-10-01 via `WorkshopCreate.xml` - never run that file again;
`WorkshopUpdate.xml` carries the ID). Page: https://steamcommunity.com/sharedfiles/filedetails/?id=3811452468

## Steps

1. **Cover** (already built; redo only with new screenshots). The raw shots live in `screenshots\`
   (gitignored). The published cover came from:
   ```powershell
   python tools\make_cover.py "screenshots\A1 Before marked.jpg" "screenshots\A2 After marked.jpg" --crop 100 130 3380 1300 --layout stack --no-crop --label-pos tr --tag-scale 0.6 --width 1920 --no-title
   ```
   Writes `docs\cover.jpg` (README image, and an extra screenshot on the Workshop page; `--png` adds a lossless copy).

   **Thumbnail** (the Workshop preview `WorkshopCreate.xml` uploads, square like TrainingBattles'):
   ```powershell
   python tools\make_thumbnail.py --variant v3
   ```
   Writes `docs\thumbnail_v3.jpg` (1024x1024, under 1 MB), the published thumbnail: BEFORE | AFTER of the
   Throwing Weapons block with enlarged marks, the Throwing filter icon in a gold ring at the top centre,
   title and tagline below. (The script can still render the rejected v1 / v2 drafts; they are not kept.)

2. **Package** a clean build:
   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\package.ps1
   ```
   Fills `dist\BetterSkirmisherSeparation` (what gets uploaded) and writes the release zip beside it.

3. **Upload.** First time only: `WorkshopCreate.xml` (created the Private item; never again). Every time
   after, build a one-off task from `WorkshopUpdate.xml` with `make_workshop_update.py`. It sends the
   content of `dist\BetterSkirmisherSeparation`, the description from `STEAM-DESCRIPTION.bbcode`
   (escaped, line breaks as `&#10;`), the change notes, and optionally the visibility
   (`Private` / `FriendsOnly` / `Public`; leave it out to keep the current one). The task goes to
   `%TEMP%\bss_workshop_update.xml` and the script prints the path:
   ```powershell
   $task = python tools\make_workshop_update.py --notes "v1.0.1 - what changed." --visibility Private
   & "D:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\bin\Win64_Shipping_Client\TaleWorlds.MountAndBlade.SteamWorkshop.exe" $task
   ```
   (`--no-description` skips the description.) Run it from a scratch folder; success = "Uploading done!".
   Every update re-uploads the module, so run `package.ps1 -Force` first. Going public later is the
   same command with `--visibility Public`.

4. **On the item page** (Owner Controls) - the uploader cannot do these: under "Add/edit images &
   videos" add `docs\cover.jpg` (the stacked before/after comparison) as the first screenshot, right
   after the thumbnail; under "Add/Remove Required Items" add Harmony (2859188632).

## Uploader quirks

- The root `<Tasks>` element must be the **first node** of the task file. An `<?xml?>` declaration
  or a comment above it makes the tool parse zero tasks and exit as if it succeeded.
- The item **title** comes from `module\SubModule.xml <Name>`, not the task file.
- It ends by writing `steam_workshop_uploader.txt` (gitignored) and crashing on a harmless
  press-any-key read. Judge success by **"Uploading done!"** in the output, never the exit code.
- `WorkshopUpdate.xml` on its own does not touch description or visibility; `make_workshop_update.py` adds them.
- It also writes `steam_appid.txt` (261550) into the working directory. Run it from a scratch folder
  (or the repo root, where both droppings are gitignored).
- What the task file can set (strings in the exe, 2026-10-01): `ModuleFolder`, `ItemDescription`, `Tags`,
  `Image`, `ChangeNotes`, `Visibility` (SetItemDescription / SetItemVisibility / SetItemPreview). It has
  NO call for extra screenshots (AddItemPreviewFile) or required items (AddDependency): those are
  item-page only. A description sent through `ItemDescription` sits in an XML attribute, so its line
  breaks must be written as `&#10;` (a raw newline becomes a space); Steam renders it as BBCode, max
  8000 characters.
