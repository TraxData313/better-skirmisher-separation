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
   python tools\make_thumbnail.py
   ```
   Renders `tools\preview_thumbnail.html` with headless Edge into `docs\thumbnail.jpg` (1024x1024, under
   1 MB): BEFORE/AFTER of the Throwing Weapons block with enlarged marks, title and tagline below.

   Three thumbnails to choose from (all 1024x1024, under 1 MB); `WorkshopCreate.xml` points at option 1:
   - **Option 1** `docs\thumbnail.jpg` (`python tools\make_thumbnail.py`): BEFORE | AFTER, big title.
   - **Option 2** `docs\thumbnail_v2.jpg` (`python tools\make_thumbnail.py --variant v2`, template
     `tools\preview_thumbnail_v2.html`): the Order of Battle card of formation 2 with the Throwing filter
     ringed and magnified ("Throwing ✓"), then BEFORE (Legionaries, red X) | AFTER (all javelin throwers).
   - **Option 3** `docs\thumbnail_v3.jpg` (`python tools\make_thumbnail.py --variant v3`, template
     `tools\preview_thumbnail_v3.html`): option 1's layout with the Throwing filter icon (cut from the card)
     in a glowing gold ring, top centre on the split line: with the Throwing filter on, before -> after.
   To use option 2 or 3, set `<Image>` in `WorkshopCreate.xml` to `docs\thumbnail_v2.jpg` / `docs\thumbnail_v3.jpg`;
   the others can go up as extra screenshots on the item page.

2. **Package** a clean build:
   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\package.ps1
   ```
   Fills `dist\BetterSkirmisherSeparation` (what gets uploaded) and writes the release zip beside it.

3. **Upload.** First time: `WorkshopCreate.xml` (creates a Private item). Every time after:
   `WorkshopUpdate.xml` (put the item ID in place of `ITEM_ID` and set `ChangeNotes` first).
   ```powershell
   & "D:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord\bin\Win64_Shipping_Client\TaleWorlds.MountAndBlade.SteamWorkshop.exe" "C:\Users\Trax\Documents\BannerlordMods\better_skirmisher_separation\tools\WorkshopCreate.xml"
   ```

4. **On the item page** (Owner Controls): paste `tools\STEAM-DESCRIPTION.bbcode` as the description,
   flip Private to Public, and add the Harmony required item. Under "Add/edit images & videos" add
   `docs\cover.jpg` (the stacked before/after comparison) as the first screenshot, right after the thumbnail. Put the Workshop link into `README.md`
   in place of `STEAM_WORKSHOP_URL`, and the item ID into `WorkshopUpdate.xml`.

## Uploader quirks

- The root `<Tasks>` element must be the **first node** of the task file. An `<?xml?>` declaration
  or a comment above it makes the tool parse zero tasks and exit as if it succeeded.
- The item **title** comes from `module\SubModule.xml <Name>`, not the task file.
- It ends by writing `steam_workshop_uploader.txt` (gitignored) and crashing on a harmless
  press-any-key read. Judge success by **"Uploading done!"** in the output, never the exit code.
- `WorkshopUpdate.xml` does not touch title, description or visibility; edit those on the item page.
- It also writes `steam_appid.txt` (261550) into the working directory. Run it from a scratch folder
  (or the repo root, where both droppings are gitignored).
- What the task file can set (strings in the exe, 2026-10-01): `ModuleFolder`, `ItemDescription`, `Tags`,
  `Image`, `ChangeNotes`, `Visibility` (SetItemDescription / SetItemVisibility / SetItemPreview). It has
  NO call for extra screenshots (AddItemPreviewFile) or required items (AddDependency): those are
  item-page only. A description sent through `ItemDescription` sits in an XML attribute, so its line
  breaks must be written as `&#10;` (a raw newline becomes a space); Steam renders it as BBCode, max
  8000 characters.
