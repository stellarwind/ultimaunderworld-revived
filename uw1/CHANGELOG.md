# Changelog: Ultima Underworld port (uw1port)

For players. Each release's notes are drafted from here. Releases are tagged `uw1-vX.Y.Z`.

## Unreleased

- **New:** optional `smooth-weapon-sway` replaces the random weapon shake sampled each 3D frame with a smooth sway driven by the 256 Hz game clock. Only the draw offset changes; original random-number consumption, weapon state, attack frames and charge timing are preserved.

- **New:** with `modern-keys`, Tab toggles combat stance (draw/sheath) using the original F5 action. With `single-action-toggle` enabled, it acts once on release without repeating. Shift+Tab and Tab outside gameplay retain their original actions.

## 1.1.0 (24 October 2026)

This fork's first release, with a Windows x64 package.

- **New:** Single Action Toggle (`single-action-toggle`), an optional enhancement in the Enhancements tab. F1-F10 and the physical backtick/tilde mouse-look key activate once on release. Holding them no longer repeatedly toggles actions. Movement and ordinary text keys retain repeat, and opening settings or losing focus cancels pending toggle actions. Mouse-look must also be enabled for its toggle key.
- **Fixed:** the port now remembers the window's position, size and maximized state. Restoring a maximized window returns to its previous normal rectangle. Fullscreen and the settings panel's temporary resize do not overwrite that rectangle, and a rectangle on a disconnected monitor is fitted onto an available display. Placement is stored as `window-geometry` and `window-maximized` in the local settings file.
- **Changed:** UW1 reads original game assets only from `UW1` beside `uw1port.exe`, containing `UW.EXE` and the complete `DATA`, `CRIT`, `CUTS` and `SOUND` folders. Automatic game searches, CD-image extraction, the Game folder picker and the desktop `--data` option are removed.
- **Changed:** writable game files, saves and settings default to `uw1port-data` beside the executable. There is no automatic AppData or user-profile fallback; an unwritable local folder causes startup to fail. `UW1PORT_HOME` is ignored, while explicit `--home DIR` remains available.
- **Removed:** automatic session recording, session snapshots, the Record sessions setting and the `--record`/`--no-recording` switches. Developer replay support remains.
- **Removed:** this project's browser launcher, WebAssembly targets, web deployment workflow and browser-only adapters. The native SDL renderer remains.
- **Checked:** keyboard regression tests, window-placement regression tests, real Windows restarts in maximized and normal states, settings-panel resize recovery, release DLL packaging and repository checks. Full DOS byte-match/replay gates and macOS/Linux execution were not rerun for this release.
- **Dependency:** Exhume remains pinned, unchanged, at `a34316463c230bafa3d4f0aa3b894a574e5fc738`. It supplies build/decompilation tools and runtime code compiled into the port, including SDL integration, portability, DOS hardware emulation and sound support.

**Installation and upgrade:** extract the Windows package into a writable folder. Place your own original game files in its adjacent `UW1` folder. Game files and MT-32 ROMs are not included. Existing `UW1` and `uw1port-data` folders can stay in place when replacing the executable and DLLs. For an older installation, copy your settings, `DATA` overrides and `SAVE0`-`SAVE4` from the former home folder into `uw1port-data`; the port does not migrate or delete old files automatically. Enable Single Action Toggle in Enhancements and restart, or run `uw1port.exe --enhance single-action-toggle`.

## 1.0.2 (14 October 2026)

- **Fixed:** creating a female character crashed the game on choosing any portrait but the first (issue 8). DOS draws her; the port now does too.
- **Fixed:** opening the map could crash the game on a Mac with Apple silicon, and was one byte from doing so on other systems, on a level whose notes were all erased before a new level was first saved: the original game then reads that level's notes from another level's map, and one of those "notes" had no end (issue 7). The port now cuts such a note short; what the map shows is unchanged.
- **Fixed:** the recording of a session the port crashed in could be cut short on Windows, so that it did not replay to the crash: the crash handler did not see a fault on the game's thread, where the game runs (issue 8). The handler is now installed on the game's thread too, so the recording is written out whole.
- **Changed:** a session's recording folder now holds only what a replay of it needs from the home folder: the saved games and the `DATA` folder (`UW.CFG`, and any file of yours there that the port reads in place of the game's own, such as a translated `STRINGS.PAK`). Before, it copied everything else there too: a game copied out of GOG's CD image (`gog-cd`), MT-32 ROMs, or a game folder you put there, none of which belongs in a bug report. Links to folders or files elsewhere are not followed.
- **Fixed:** once the game had been running for a few minutes, a cutscene's colour cycling turned on every pass instead of at its own pace. It now keeps DOS's pace however long the game has run.
- **Fixed:** a strings file with a block larger than 32 KB (only modified or translated files have one; the GOG release's do not) gave garbled text. The port now reads it as DOS does.
- **Fixed:** restoring a game while running fast or falling could put you down a little further on than DOS does (issue 10). The original works out the first step after a restore in 16 bits, and the result wraps; the port worked it out in 32 bits. It now does as DOS does. Like DOS, a restore still keeps your speed and a fall in progress, so you can still take fall damage on loading.
- **Fixed:** offering a trader far more than their goods are worth could be refused in DOS, with your own appraisal calling it "an excellent deal", where the port accepted it and called it "a terrible deal". The original works out the deal in 16 bits, so a large enough gap (or a large stack, of gems say) wraps round; the port worked it out in 32 bits. It now does as DOS does.
- **Fixed:** killing a powerful creature worth a lot of experience (a headless or a dread spider, say) could take experience away in DOS, where the port gave a few thousand points. The original multiplies the reward in 16 bits; the port did it in 32. It now does as DOS does.
- **Fixed:** a fall at walking pace, paused partway (by opening and closing the restore prompt, say), could stop for a moment in mid-air in DOS, as if landing, where the port carried on down. The port now does as DOS does.
- **Fixed:** five more places where the original works in 16 bits and the port worked in 32 now do as DOS does, though none is known to show in an ordinary game: how hard a heavy creature knocks an object it falls on, the distance from a critter to a target 23 tiles or more away, the shading of an object about 23 tiles off, a value that conversations save for an NPC with 128 hit points or more, and the acceleration of a player carrying more than strength 34 allows.
- **New:** optional enhancement tidy-objects (issue 9; `--enhance tidy-objects`). In the original game, asking for part of a floor stack that turns out too heavy to pick up loses an object, and the game later says "Problems in object list" on entering that level. With it on, the port frees that object as UW2 does, and puts back objects lost this way when the message would appear, so saved games that already show it stop doing so.
- **New:** optional enhancement restore-at-rest (issue 10; `--enhance restore-at-rest`). A restored game starts at rest where it was saved, instead of keeping the speed and any fall of the game you restored from, so restoring while falling no longer hurts you. A game saved in mid-air still falls, from rest.

## 1.0.1 (10 October 2026)

- **Fixed:** sidestepping and walking backwards could stall or drift, depending on the way you faced: a sidestep might not move at all or slide off at an angle, and walking backwards might go nowhere. They now go the way you press, whichever way you face (issue 6). To do this the 3D view draws at most 32 frames a second, as in the UW2 port, which is what the game's movement was written for.
- **Fixed:** each play session's recording is now kept in its own folder under `recordings/` in the port's home folder, the newest five, as the documentation says. Before, there was one recording a day (in a `RECORDIN` folder), overwritten by each later session that day. An old `RECORDIN` folder there is no longer used and can be large: it is safe to delete.

## 1.0.0 (9 October 2026)

The first release of the native port of *Ultima Underworld: The Stygian Abyss* for macOS, Windows and Linux.

- Plays the game from your own GOG copy, found by itself (including inside GOG's Mac app), with FM, MT-32 (your own ROMs) and Sound Blaster speech.
- **New:** optional enhancements, all off by default (`--enhance list`; docs/ENHANCEMENTS.md). The first is `skip-intro`, which starts at the main menu. A session played with one says so in its log and recording.
- **New:** more optional enhancements: wrap-menu, fast-panels, free-heading (`--enhance list`).
- **New:** optional enhancements perspective (floors, ceilings and walls stay straight when you look up or down) and full-sprites (`--enhance list`).
- **New:** optional enhancements wide-pitch (look three times as far up and down, with no gaps in the floor or ceiling), mouse-look (the ` key: the mouse turns the view, a crosshair at the centre; `look-speed=` in the settings file) and invert-look (`--enhance list`).
- **New:** optional enhancements modern-keys (UltimaHacks' keys: WASD, Space to attack, Q and E to look and use, Z for the map, R and F for the panels) and rune-keys (Ctrl+Alt and a letter puts a rune on the shelf) (`--enhance list`).
- **New:** the port finds your MT-32 or CM-32L ROMs by itself: in a `roms` folder in its home folder, beside the game or the program, or where DOSBox keeps MT-32 ROMs. Any file names work (they are recognised by their contents), split halves are joined, and `--mt32-roms` takes a folder or one of the files. Or drop the ROM folder onto the app, the program or its window, and the music plays on the MT-32 from the next start; it moves there by itself, too, when ROMs turn up after a first run that had none.
- **New:** a settings screen: F11 (Cmd+, on macOS) opens it over the game, with the sound cards, volume, mouse, window, enhancements and the game folder, and the first run starts with it (docs/SETTINGS.md).
- **Improved:** the program no longer keeps a processor core busy while the game waits for its clock: much lower CPU use, quieter fans and longer battery life, with the game playing exactly as before.
- **Improved:** the cutscenes (the intro above all) and conversations take far less processor time: the expanded-memory emulation no longer copies a page out and back in each time the game maps the page it already has, which it does millions of times a minute there.
- Ten recorded DOS sessions replay in it identically to DOS, on all three systems.
- **Checked:** the packages are tested before release on nine systems (Windows Server 2022 and 2025, macOS 14, 15 and 15 on Intel, Ubuntu 22.04 and 24.04, Debian 12, Fedora 41), replaying the recorded sessions from the package itself, with the MT-32 music checked too.
- **Fixed before release:** the same two problems found in the UW2 port in October 2026: a freeze for good after the program was paused for a second or more, and runaway drawing when vsync is ignored or the window is in the background.
