# Integración Android de Lucy para el constructor de Linux

Este directorio contiene el host Android, las plantillas y los perfiles de
adaptación. El programa `lucy.py` del constructor de Linux selecciona las
revisiones y utiliza `../build_lucy.py` para integrar las modificaciones,
actualizar el lock y generar una APK. El constructor la firma y la verifica
en el PC del usuario. El proceso actual y sus límites se documentan en
`LEEME.md` y `VALIDACION.md` de la distribución de Lucy Builder Linux.

Las comprobaciones de versiones anteriores conservadas en VALIDATION.md son
históricas, no certifican una versión futura generada. Cada construcción produce
su propio build-info.json y vuelve a comprobar los motores empaquetados.

## Documentación de la integración anterior

# Lucy for Android

An independent Android office suite combining the real WordCraft, GridCraft, DeckCraft,
and PdfCraft editors in one application. Documents are edited on the device using the
upstream Rust engines compiled to WebAssembly. This is a working first preview,
not a claim of ONLYOFFICE feature parity.

Lucy was previously named Folio Office. Lucy uses the newly supplied pink office illustration as its launcher and recent-apps icon; the previous flower image is removed. Its Android application ID, signing key, offline origin and stored settings remain compatible with previous installs.

## Install and use

Install `Lucy-0.10.0.apk` on Android 8.0 or newer. Android System WebView needs
WebAssembly and WebGL 2 support; keep it current. A tablet or landscape screen is
recommended for the existing ribbon interfaces. This universal APK works on ARM64,
ARM32, and x86 devices when their WebView supports these features.

- In full screen, Android status and navigation bars stay hidden. Swipe from an edge to show Android controls temporarily. In split screen, the bars required by Android blend with the selected light/dark appearance, including during resizing. Only the actual bar, keyboard and cutout insets are reserved; open tabs remain in place when switching window modes.
- **Split / Unsplit**, immediately after **Open a file**, shows two document tabs side by side. If only one file is open, the second side offers Open a file. Tap a document side, then choose a tab to replace that side; selecting an already visible tab focuses it. Badges 1 and 2 identify the visible tabs, and a thin border marks the side addressed by the shared menu. Unsplit expands the focused document while every other tab stays open. Both visible editors render; hidden tabs and Home pause their animation callbacks. Splitting never reparents or reloads an iframe.
- **Home → Open a file → document tabs** is the fixed top-left order whenever documents are open. Opening or cancelling another file keeps the existing tabs and edits.
- Each editor's primary menu row now measures **24 logical pixels**, 80% of Word's previous 30. All four use the pinned OFL **Inter** family for interface text; document and cell fonts are unchanged.
- PDFs open with **Hand** selected. Their floating quick-action bar renders and receives clicks at **60%** scale.
- **Open a file** selects one or several documents from Android’s file picker. Each
  file opens in its own tab across the top; Word, PDF, spreadsheets and presentations
  can stay open together, including several documents of the same type.
- Tap a tab to return to its editor with its current edits, selection and undo history.
  Swipe the tab strip sideways on a phone. The existing **⋮** menu beside the tabs
  now holds Create, Save copy, Undo, Redo, Back to editor (Esc), Paste, Show keyboard,
  dark mode and interface scale. The document strip is now **24 CSS pixels**,
  half its previous height. The duplicate editor title strips are removed in Rust.
  Account, About, and Discord screens, their commands and compiled promotional
  translations are removed from the bundled editor forks.
- **Dark mode** changes white document pages/cells/slides to grey and black text
  to white across all open editors. It is a persistent viewing preference. Word
  and PDF use native display palettes; spreadsheets remap screen paints and
  presentations remap neutral screen pixels. Coloured slide pixels are retained.
  Monochrome pictures in presentations also follow the screen palette. Document
  fills, font colours, undo history and exported files keep their original data.
- **Home** and Android Back from an editor keep all tabs open. The **×** on a tab
  closes only that document after confirmation. Back from Home confirms exiting
  when documents are open. Save copies before closing a tab or exiting.
- With a hardware keyboard: **Ctrl+Tab** / **Ctrl+Shift+Tab** switch documents,
  **Ctrl+O** opens another file and **Ctrl+W** requests closing the active tab.
  Reopening the same Android document URI returns to its existing tab.
- Home contains only **Open files** and **Create file**. Create opens a chooser for Document (DOCX), Spreadsheet (XLSX), Presentation (PPTX), or PDF. The former sidebar, introduction, recent-file history, search and cards are removed from the HTML, JavaScript and CSS.
- **⋮ → Save copy**, or the editor's Save/Export command, opens Android's save dialog.
  Presentations first show a format chooser: keep **PPTX**, then tap **Download**.
  Exports use a new file selected by the user; the imported original is not overwritten.
- **Saved copies** keeps a private copy of each completed export, even when the save
  dialog is cancelled or the provider fails. Open, share, or explicitly delete these
  copies from **⋮ → Saved copies**. These are exported snapshots, **not automatic recovery of unsaved edits**.
- The menu’s **Show keyboard** action requests Android's keyboard. Tap the document/cell/text box to
  choose an editing target. **Paste** sends Android clipboard text to that editor.
- The menu’s interface scale action cycles 100%, 85%, 70%, and 50%.
- Android **Open with** and **Share to** accept the primary document formats.
- Multi-file font picks pass every selected URI to the WebView. Word’s Add Font accepts the whole batch; PDF’s Load font now registers each selected TTF/OTF, continues past invalid entries, and applies the first valid face once. PDF embedding/license validation remains in place: use a static TTF/OTF instance for PDF, since variable font programs remain unsupported.
- The host and all four editor interfaces are Spanish only, independent of device language or an older saved language preference. Other UI catalogs are deleted from the source before building, and language selectors are removed. File-format identifiers, document language metadata, formulas and font coverage remain intact.

No account, subscription, server, analytics, or `INTERNET` permission is required.
Files in a cloud document provider may require that provider's network connection.

## Code cleanup in 0.7.0

Removed Word's unused Quick Access Toolbar controls, empty Help group and unreachable title-bar Save As branch, together with their obsolete UI tests. Removed the unused PDF home module and internal tab-strip/context-menu helpers after their UI was replaced by the Android host, plus their obsolete state and tests. The search-layout test now exercises the active compact search control. Removed stale iframe fullscreen/import acknowledgements, title-cropping state, an unreferenced build-script alias and obsolete prebuilt-archive metadata. APK assembly clears generated classes/resources before compiling, so deleted code cannot persist from an earlier build. Shared desktop code with native callers, legal notices, source pins, build scripts and regression tests are retained.

## Format support

| Editor | Primary read/write formats | Additional import/export |
|---|---|---|
| WordCraft 0.12.0 | DOCX | ODT, RTF, TXT, Markdown and HTML; PDF export; legacy DOC import |
| GridCraft 0.13.0 | XLSX, CSV, TSV | PDF export; legacy XLS and ODS/XLSB data import |
| DeckCraft 0.12.0 | PPTX, `.deckcraft` | PDF and image export; slide show |
| PdfCraft 0.15.0 | PDF | Reading, annotations, page organization and editing tools |

Depth and fidelity are those of the upstream alpha editors. Unsupported objects,
fonts, formulas, encrypted files, tracked changes, media and complex layouts may
behave differently from Microsoft Office or ONLYOFFICE. Legacy `.ppt` is unsupported.
The integration caps individual imports and exports at **100 MiB**; large documents
can exhaust WebView memory before reaching that limit. Keep original documents.

## Build an APK

Prerequisites: Linux x86_64, JDK 17, Python 3.12+, Git, Rust stable (edition 2024),
the `wasm32-unknown-unknown` target, and Android SDK packages
`platforms;android-35` and `build-tools;35.0.0`. The pinned engine sources require
Rust 1.95 or newer.

```bash
rustup target add wasm32-unknown-unknown
export ANDROID_SDK_ROOT=/path/to/Android/Sdk
bash scripts/build_apk.sh
# build/Lucy-0.10.0.apk
```

The first build fetches the exact source commits in `engine-lock.json`, prunes the non-Spanish UI catalogs listed in `source_prune`, applies the
four patches in `third_party/patches/`, compiles the custom editors with Cargo,
and packages their WebAssembly using wasm-bindgen, including the nested JavaScript modules needed by egui 0.37. Only the pinned Spanish shared catalogs are downloaded, with SHA-256 checks.
The builder verifies and uses wasm-bindgen matching each Cargo lockfile.
Missing Linux build tools are downloaded with official SHA-256 verification. Build artifacts are
cached under `.cache/`. Subsequent APK assembly verifies every engine asset against
its source/patch manifest and reuses it. To rebuild all engines explicitly:

```bash
python3 scripts/build_engines.py
# Optional smaller bundles, with an additional Binaryen 128 pass:
python3 scripts/build_engines.py --optimize-wasm
```

Optional supplementary fonts come from the pinned craft-fonts source in
`engine-lock.json`. Their manifest SHA-256 checks are verified before embedding.
Required copyright and font licence notices are retained in `third_party/` and
`THIRD_PARTY_NOTICES.txt`. The installed app needs no server or network.

Android Studio/Gradle project files are also provided. Build the engines and run
`python3 scripts/create_templates.py` before opening the Android project.

The script's default signing key is a **local preview key**, generated in `.cache/`.
It is intentionally not included in the source archive. To make updateable builds,
retain your own key and set `FOLIO_KEYSTORE`, `FOLIO_KEY_ALIAS`, and
`FOLIO_KEYSTORE_PASSWORD`. A build signed with a different key requires uninstalling
the previous preview; export recovery copies before uninstalling.
The supplied APK's preview key is retained in a separate private build checkpoint,
`Folio-Office-preview-signing-key.zip`, to support future updates of this preview.
The GitHub Actions workflow builds a downloadable preview APK, without publishing it.

## Architecture

`MainActivity.java` owns Android's Storage Access Framework, WebView, clipboard,
bounded file transfer, document routing, and recovery snapshots.
`RecoveryProvider.java` grants read-only access to a specific snapshot when the user
opens the Android share sheet. `Storage.java` bounds copies and sanitizes names.

The responsive `index.html` / `shell.js` / `shell.css` host retains a separate
same-origin iframe for every open document. A shared, scrollable tab strip routes
activation and closure by session. Two selected sessions can occupy the left/right halves of the same editor stage; visibility and menu focus are separate, so both sides remain interactive while commands address the touched side. Inactive editors retain their viewport and WASM
memory while the adapter pauses their animation callbacks to reduce rendering work.
The Android activity uses one task so Open With/Share adds a tab to the workspace.
The Android host toolbar is removed, with its actions in the existing tab-strip
menu. Patched Rust editors omit their duplicate title strips, so the canvas uses
its actual viewport without cropping. `engine-adapter.js` sets the host's
appearance preference before the engine starts and forwards later changes without
reloading any open document. The adapter feeds files through the editors' existing
drag/drop input, translates Android toolbar commands, and adapts browser saves to
Android. File bytes are transferred in 64 KiB chunks, flushed and synced to a recovery
file, and only then offered to a user-selected document provider. A cancelled or failed
export is reported as such. Export acknowledgments reach editors using the File System
Access API; anchor-download-only editors may mark their internal document clean before
Android finishes. Lucy always confirms closing a tab, independent of that flag.
Imports, loading state, zoom, clipboard replies and export acknowledgments route to
their originating session even when another document is active. A tab cannot close
while its export is queued or waiting for the Android provider. Closing it releases
only its staged import; saved recovery snapshots remain available.

All assets and documents are served from an intercepted private HTTPS origin. Unknown
network requests and external navigations are blocked. JavaScript is restricted to
bundled content, and no broad device storage permission is requested. Source notices
are preserved under `third_party/` and available through the ⋮ menu’s open-source licences button.

## Current limits and next development steps

- The editing interfaces are upstream desktop ribbons rendered in an Android WebView;
  a dedicated touch ribbon and deeper gesture support remain future work.
- All open editors remain in memory; the practical tab count depends on device RAM.
  Background rendering pauses, but open documents still consume memory.
- Export snapshots survive process death; unsaved changes held only in WASM memory do not.
- Office printing, background autosave and full native selection handles remain
  future work.
- This preview has not been tested on a physical Android device. See `VALIDATION.md`
  for the actual build, browser integration checks, and remaining device checks.

Engine revisions, source commits and pinned interface-font hashes are in `engine-lock.json`.
To change engines, update those pins deliberately and rerun the integration tests.

## Credits and licensing

Lucy host: MIT. WordCraft, GridCraft, DeckCraft and PdfCraft: MIT OR Apache-2.0,
copyright ArtCraft Team and their contributors. Embedded assets retain their own
licenses. See `ATTRIBUTION.md`, `third_party/`, and bundled `THIRD_PARTY_NOTICES.txt`.
Lucy is independent and is not endorsed by these projects or ONLYOFFICE.
