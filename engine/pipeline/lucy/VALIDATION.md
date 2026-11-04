# Validation of 0.10.0 — 2026-10-29

Updated all four editors to the main-branch commits resolved for this request. Retained Lucy's Spanish-only UI, 24px Inter menu rows, shared tabs and split view, persistent dark pages, multiple-font import, package/origin/storage identifiers and upgrade certificate. The supplied pink office image replaces the flower: its original JPEG bytes are used unchanged for the adaptive launcher and recent-apps icon.

| Editor | Version | Pinned main commit |
| --- | --- | --- |
| wordcraft | 0.12.0 | `aadb077e072b7de05f724e359d8db82e151f125c` |
| gridcraft | 0.13.0 | `146161b4b450a56e5e59a083ba0478582d1e602b` |
| deckcraft | 0.12.0 | `f893f6af7d36a5409fd804e81a34fd895cfefedf` |
| pdfcraft | 0.15.0 | `dc943eeb13a9609aae704e0708bd996f7c069148` |

The engines use craft-fonts `aced4137c022f1f587624d48e81ec77e1914a9cc`. Word's new shared translation input is craft-i18n `9205108cfdced5177706264038848b68b2422d2b`: only the two pinned Spanish catalogs and the checked local Spanish supplement are passed to its build. Foreign UI selectors/catalogs remain removed. Original document language metadata, formulas, technical identifiers, multilingual document font coverage and legal notices are preserved.

Release checks passed:

- All four WASM editors compile from the pinned commits and exact integration patches. Patch bytes, whitespace, installed source/font/catalog/patch hashes and every nested runtime asset verify. The new egui 0.37 inline JavaScript module is packaged for each editor; a regression check verifies its imports resolve locally.
- Host bridge and split regression suites pass: two-button Home, four Create choices, retained mixed-format tabs, picker/save/cancel protocols, source validation, focus/menu routing, viewport changes, dark preference and safe closing.
- Real editors import, edit and export DOCX, XLSX, PPTX and PDF with five retained tabs. DOCX typing/Undo/Redo and dark-view typing survive export. The spreadsheet preserves SUM(A1:B1) with cached result 12, and a second new workbook retains A1=42. PPTX is valid OOXML with its slide content. PDF retains its original text and newly typed marker.
- Light/dark exports preserve document XML, colours and PDF content streams. Pixel checks pass in all four real renderers. The spreadsheet's new automatic font-colour path is explicitly remapped for dark viewing, along with number-format colours and neutral pattern fills; the saved workbook is unchanged.
- Real split view passes for Word/PDF and presentation/spreadsheet pairs, independent PDF scrolling, retained instances, in-pane edits, narrow presentation Save As and all four exports. Split DOCX text, spreadsheet A1=42/formula=47, presentation content and six-page PDF text verify.
- Spanish UI/migration tests pass under en-US and ja-JP locales; a stored Japanese spreadsheet UI preference migrates to Spanish while retaining r1c1. Current catalog audit verifies singleton Spanish UI lists, 67 pruned retired UI/brand files, exact shared Spanish input and the absence of 2,228 sampled-source foreign catalog phrases in the Grid/PDF binaries.
- Word persists both valid fonts around an invalid middle selection. PDF's multiple-font picker supports cancellation, continues after an invalid file and exports both selected Inter faces with preserved paragraph text. PDF defaults to Hand, and both scaled tool buttons receive input.
- Android Java/resources compile for API 35. APK label Lucy, version 0.10.0, code 11, minimum API 26, target 35. No Internet or broad-storage permission. APK required entries, CRCs and every bundled asset match the final source. The icon matches the supplied JPEG exactly; the old flower and private signing key are absent.
- APK v2/v3 signatures verify with the retained certificate SHA-256 `a5c3123a0e39082abcd220c3854f83da2c9cafb0366ffb11de8f065e28b0818d`, preserving update compatibility.

Final APK: 63,729,572 bytes; SHA-256 `60f5fb14608d590e623852065d895565dfcd9db3fff2c29653dc47ea47cadb99`. Main-branch engine and font changes increase its size compared with 0.9.0; pruning UI code does not determine the complete binary size.

No Android device or emulator is connected. Physical acceptance testing on the TCL NXTPAPER 11 Plus/Android 15 remains pending. Full upstream native/desktop suites were not run: an initial pristine Deck `cargo xtask ci` completed formatting/dependency checks and stopped because the installed toolchain lacks Clippy. This validates the Android/WASM integration, not every upstream platform. No new claim is made about removing Android's required split-screen system bars. The website is unchanged.

Reproduce after building engines and providing the documented browser/toolchain paths:

```bash
python3 scripts/build_engines.py --verify
python3 tests/verify_engine_assets.py
node tests/bridge.cjs
node tests/split.cjs
python3 tests/make_fixtures.py
node tests/spanish.cjs
node tests/engines.cjs
python3 tests/verify_exports.py
python3 tests/verify_appearance.py
node tests/split-engines.cjs
python3 tests/verify_split.py
node tests/fonts.cjs
python3 tests/verify_fonts.py
python3 tests/verify_spanish.py --source-root /path/to/upstream
bash scripts/build_apk.sh
```

# Validation of 0.9.0 — 2026-10-24

- Built all four pinned WASM editors from the supplied integration patches with Spanish as the sole UI language. Removed 25 Word, 32 PDF and 17 spreadsheet foreign-language UI catalogs (74 total), plus Word's obsolete multilingual audit/pseudo-locale helpers. Presentation UI labels and command display names are translated into Spanish; command identifiers and document content retain their original semantics.
- All four installed engine manifests match their pinned commits, font sources, Spanish-only setting, pruning lists, asset hashes and final patch hashes. Patches exactly reproduce each modified checkout; `git diff --check HEAD` passes for all four. The builder deletes the listed foreign UI resources before compiling fresh checkouts and excludes their deleted contents from the distributed patches.
- Host/adapter tests pass: two-button Home, four Create choices, native picker/save/cancel protocols, mixed retained tabs, focus and menu routing, safe close, dark mode, resizing and split/unsplit. Updated UI expectations to Spanish.
- Actual WASM editors open and export DOCX, XLSX, PPTX and PDF. Verified DOCX undo/redo and edits, XLSX formula/cached result and a separate new workbook value, real PPTX OOXML, and edited PDF text. Switching appearance preserves exported content and colours in all four formats. Pixel checks confirm grey paper and light text in every renderer.
- Actual split view passes for Word/PDF and presentation/spreadsheet pairs, independent PDF scrolling, retained instances, in-pane edits and all four exports. Exported split DOCX contains the typed marker; spreadsheet A1=42 and dependent formula=47; presentation content and six-page PDF text remain intact.
- Spanish-only regression passes under en-US and ja-JP browser locales. A stored Japanese spreadsheet interface preference migrates to Spanish while preserving the r1c1 editing preference. All four engine HTML roots and the host declare Spanish. Checked 60 previously present German/French/Japanese/Chinese UI strings against the old and new WASM binaries: the selected foreign UI strings are absent from the new builds. The 74 pruned files are absent from the built source trees.
- Word accepts multiple selected font files, continues after an invalid middle file and persists both valid faces. PDF's multiple-file picker supports cancellation and both valid faces after an invalid entry; verified both embedded font programs and preserved paragraph text. PDF opens with Hand selected and the scaled quick-action buttons receive their clicks. Font/formula/document-language support is retained for imported documents; it is distinct from UI translations.
- Android Java/resources compile against API 35. Final APK label Lucy, version 0.9.0, code 10, minimum API 26, target 35; no INTERNET permission. APK v2/v3 signatures verify with the retained certificate SHA-256 `a5c3123a0e39082abcd220c3854f83da2c9cafb0366ffb11de8f065e28b0818d`, preserving update compatibility. All packed assets match the final local sources. The flower icon matches 0.8.0 byte for byte.
- Final APK size: 59,338,207 bytes (59.34 MB), versus 62,246,367 bytes in 0.8.0; 2,908,160 bytes smaller (4.67%).

No Android device or emulator is connected; physical acceptance testing on the TCL NXTPAPER 11 Plus/Android 15 remains pending. The full upstream native/desktop suites were not run; their stock multilingual/English UI expectations do not validate this Android integration. This release makes no new claim about removing Android's required split-screen system bars. Original notices, technical/file-format identifiers, imported document language metadata and multilingual document text/font coverage are preserved. Only the APK and source archive are updated; the website is unchanged.

Commands used (with existing Playwright/Chromium and pinned source paths supplied through environment variables):

```bash
python3 scripts/build_engines.py --verify
node tests/bridge.cjs
node tests/split.cjs
python3 tests/make_fixtures.py
node tests/spanish.cjs
node tests/engines.cjs
python3 tests/verify_exports.py
python3 tests/verify_appearance.py
node tests/split-engines.cjs
python3 tests/verify_split.py
node tests/fonts.cjs
python3 tests/verify_fonts.py
python3 tests/verify_spanish.py --source-root /path/to/upstream --baseline-apk /path/to/Lucy-0.8.0.apk
bash scripts/build_apk.sh
```

# Validation of 0.8.0 — 2026-10-24

Added Split/Unsplit immediately after Open a file in the existing 24px document strip. Both visible documents use their retained editor instances. The shared menu targets the touched side; choosing a hidden tab replaces that side. One open file leaves a second side ready for another file. Unsplit and Home retain the open sessions.

Release checks passed:

- The host/adapter regression suite covers the existing two-button Home, file creation, mixed tabs, saved copies, exports/cancellation, source validation, dark mode, Android Back and Spanish phone layout.
- The new split suite checks the button order/height, one-file empty side, two visible retained editors, focused-side menu routing, rejection of hidden/foreign focus messages, late imports without stealing focus, both visible animation loops and paused hidden/Home loops, view resizing, split/unsplit, Home and safe tab closure.
- Real WASM Word/PDF and presentation/spreadsheet pairs render together. PDF scroll input reaches only its own frame. In-pane Word and spreadsheet edits are exported; DOCX retains the typed marker, XLSX A1 is 42 and SUM cache is 47, PPTX retains its slide content, and the PDF retains all six pages and text. Presentation Save As temporarily scales to fit its half and returns afterward. Dark mode reaches every retained editor.
- The exact same four compiled engine assets and flower icon from 0.7.0 are retained; all engine source/font/patch manifests verify. Java/resources compile against Android API 35. APK label Lucy, version 0.8.0, code 9, minimum API 26 and target 35. No Internet permission.
- APK v2/v3 signatures verify with the existing certificate, SHA-256 `a5c3123a0e39082abcd220c3854f83da2c9cafb0366ffb11de8f065e28b0818d`.

APK size: 62246367 bytes; SHA-256 `55c2ce1e2044baae62bf24e3e9d85bbd0d4faaf92c285eb7fb69acc00905de68`.

The full upstream native/desktop suites were not rerun; these engine binaries are unchanged. No Android device or emulator is connected; physical testing on the TCL tablet remains outstanding. The unchanged editor binaries are reused and checked against their source/font/patch manifests. This release changes the host layout and focus bridge, with no system-bar policy changes.

## Prior release checks

# Validation of 0.7.0 — 2026-10-24

The app is named Lucy. The original user-supplied flower photo is bundled unchanged as an adaptive launcher icon and used in Android's recent-apps task description. Package ID, signing certificate and persistent origin/keys are kept for upgrades.

Source cleanup removes the unused Word Quick Access Toolbar controls, empty Help group and unreachable title-bar Save As branch, together with confirmed unused PDF home/tab helpers and associated obsolete tests/state, the unused host message paths and title-trim state, the unreferenced fetch script alias and stale archive metadata. The active PDF search-layout test is retained against the compact control. Native-only shared editor functionality is retained.

Release checks passed:

- Host bridge: minimal two-button Home, all four creation options, mixed document tabs, retained edits, compact menus, resized/split-sized viewports, save/export cancellation and source validation, Spanish mobile layout, and persistent dark preference.
- All four real WASM engines import, edit and export their primary formats after tab switching. DOCX typing/Undo/Redo, XLSX formula cache and independent second workbook, PPTX structure and PDF text edits verify. Pixel comparisons confirm grey pages/cells/slides with light text; dark viewing does not change exported document colours.
- Word and PDF import multiple selected fonts in one batch, skip an invalid middle file and preserve valid entries after it. Word's persisted font bytes match; the PDF export contains both selected font faces and preserves paragraph text.
- Source whitespace checks and reverse-application of the exact Word/PDF patches pass. All four installed engine manifests and asset hashes verify. Word's unused UI warnings are eliminated; remaining upstream WASM warnings refer to shared native-only paths with callers, which are retained.
- Android API 35 resources and Java compile from clean output directories. Package `io.github.pedroguille.folio`, version 0.7.0, code 8, minimum API 26, target 35. The launcher label resolves to Lucy; both launcher/round resources resolve to the adaptive flower icon. The APK's photograph matches the supplied image pixel for pixel.
- APK v2/v3 signatures verify with the previous preview certificate, SHA-256 `a5c3123a0e39082abcd220c3854f83da2c9cafb0366ffb11de8f065e28b0818d`. No Internet or broad storage permission.
- Download-page APK reconstruction matches the signed file's SHA-256; ZIP headers, CRC, entry bytes, central directory and persistent save link verify.

The signed APK is 62,246,367 bytes; SHA-256 `c89ea84a376c307a9be2403a97691351342584a7530bd4908a040ee906070aa6`.

The full upstream native/desktop CI suites were not run. There is no connected Android device or emulator; the launcher icon's actual OEM mask, physical split-screen behavior and Android font picker still need device acceptance testing.

## Previous release verification

# Validation of 0.6.0 — 2026-10-23

Home now contains exactly Open files and Create file. Create opens an accessible dialog with Document, Spreadsheet, Presentation and PDF. The sidebar, illustration, introduction, recent-file history, search, cards and footer are removed from HTML/CSS/JavaScript, as is the unused native openRecent handler. Saved copies and required legal notices remain in the existing document menu. No stored recovery is deleted.

Android now forwards every ClipData URI to WebView, deduplicates in selection order, falls back to Intent.data for one file and returns null on cancellation. Word retains its batch importer. PDF now requests multiple fonts and registers every supplied file before applying the first valid face to the paragraph once, continuing past invalid entries. Its static-font and embedding/license validation remains. Browser font reads are bounded before allocation to 16 MiB per file and 128 MiB per retained batch.

Checks for this release:

- Host suite covers the two Home buttons, all four Create options, Android Back/Escape dismissal, native Open, absence of the old Home nodes, mixed retained tabs/edits, viewport changes, exports/cancellations and persistent appearance. Saved copies is reached through the existing menu, names remain literal text and Share routes to its snapshot. English/Spanish phone layout checks included.
- Real Word WASM picker requests multiple selection. Dancing Script, a corrupt middle TTF and Noto Sans Thai import both valid files; their persisted IndexedDB bytes match both selected SHA-256 hashes.
- Real PDF WASM picker requests multiple selection. Cancellation retains the document. Static Inter Regular, a corrupt middle TTF and static Inter Medium export both embedded font faces and retain the paragraph text (tests/verify_fonts.py). A variable Dancing Script file was rejected with the existing static-instance error, confirming validation was retained.
- Regression demonstrated against the previous 0.5.1 PDF engine: the same test fails because that picker is single-select; it passes against the new engine.
- Real four-editor import/edit/export suite passes with five live frames: DOCX typing and Undo/Redo, XLSX formula/cache and A1 edit, valid PPTX, and added PDF text. Light/dark canonical document XML and PDF content streams remain identical; paper/cell/slide and text pixel checks pass.
- PDF compiles for wasm32-unknown-unknown. rustfmt checks both changed Rust files. All installed source/patch/font/asset hashes verify; the other three engine bundles are unchanged.
- Android API 35 resources and Java compile. APK io.github.pedroguille.folio, version 0.6.0, code 7, min API 26, target 35. APK v2/v3 signatures and the previous preview certificate verify. No Internet or broad storage permission.
- Spanish Home and Create dialog inspected visually in dark mode. Internal QA images remain excluded from deliverables.

No Android device/emulator is available. Actual TCL document-provider multi-selection, keyboard, rotation, and window behavior remain pending device verification. Compilation and Chromium checks do not substitute for that. This release makes no new claim to remove Android's mandatory split-screen bars. Full upstream desktop test suites were not run.

Reproduce after building engines and installing tests/requirements.txt and tests/package.json dependencies:

```bash
node tests/bridge.cjs
python3 tests/make_fixtures.py
node tests/engines.cjs
python3 tests/verify_exports.py
python3 tests/verify_appearance.py
node tests/fonts.cjs
python3 tests/verify_fonts.py
```

FOLIO_SOURCE_ROOT chooses the source checkout folder for openly licensed font fixtures (default .cache/sources). PLAYWRIGHT_MODULE and CHROMIUM_EXECUTABLE select existing browser dependencies.

## Retained validation of 0.5.1 — 2026-10-23

This patch addresses white Android system-bar areas in split screen. The light-only window background was left exposed when Android overrode the immersive request. The native window, task description, content root and WebView now share the selected appearance. A native preference restores that appearance before the WebView starts. Split-screen mode explicitly shows the required bars with contrasting icons; full screen retains immersive controls. Multi-window, configuration, focus, resume and appearance callbacks reapply the window settings without recreating the document sessions. The persistent FLAG_FULLSCREEN is cleared so it does not interfere with keyboard resizing.

Checks repeated for 0.5.1:

- Android API 35 resources and Java compile; APK v2/v3 signatures verify. Package io.github.pedroguille.folio, version code 6, minimum API 26, target API 35, same signing certificate as 0.5.0.
- The installed four engine bundles verify and are byte-for-byte identical to 0.5.0. No engine/source patches changed in this release.
- The host/bridge suite passes, including new repeated 680 × 800, 340 × 432 and 1280 × 720 viewport transitions. All four live editor frames and the Word test document state remain in place, with no host bands or horizontal page overflow.
- Insets are the per-edge union of the visible required system bars (only in multi-window), keyboard and cutout, rather than a sum. The API 26–29 fallback uses the delivered window insets; already consumed system space is not added again. Transient controls in full screen do not reserve persistent blank strips.

No Android device or emulator is connected. Compilation and host resize checks do not verify OEM system-bar rendering. Device acceptance checks still required: launch directly in split screen; enter/leave split screen repeatedly; move the divider in both orientations; toggle dark/light mode while split; switch focus to the other app; open/dismiss the keyboard and a document picker; return to full screen. Check that the OS bar areas match Folio, icons contrast, tabs/status controls remain reachable, and all documents/edits survive. Android requires the status bar in multi-window, so this patch blends that area instead of promising to remove it.

## Retained editor validation from 0.5.0

The four pinned Rust editor builds and their installed asset hashes verify against the final Folio patches, supplementary font pin and the pinned OFL Inter input. The signed Android package includes those exact verified assets.

Passed checks:

- The primary menu row in each editor is 24 logical pixels, with 12.5 pt Inter and semibold selection. A pixel comparison of the real Word renderer measures 30 px before and 24 px after: exactly 80%.
- The PDF floating toolbar is painted and hit tested through a 0.6 egui layer transform. Its white interior measured 44 × 214 px before and 26 × 128 px after (rounding at a 1× viewport). Both reduced Select and Hand buttons respond at their visible positions.
- A newly imported PDF immediately displays the Grab cursor. Selecting Select removes it; selecting Hand restores it.
- Open is between Home and the file tabs. The Spanish 412 × 915 phone test checks its order, visibility, one unique control, multi-file picker and cancellation without closing the four open documents.
- Chromium 156 with software WebGL 2 opens DOCX, XLSX, PPTX and PDF together, plus an independent second spreadsheet. Tabs, edits and frame instances survive switching and Home; there are no JavaScript errors.
- DOCX typing, Undo/Redo exports and typing in dark mode pass. XLSX retains SUM(A1:B1) and cached result 12. The new spreadsheet retains A1 = 42 after tab switching and export. PPTX exports valid OOXML with the slide text. PDF text added in dark mode survives export.
- Pixel comparisons verify grey paper/cells/slides and light text in all four formats. Dark/light exports have identical DOCX document/styles, XLSX sheet/styles and PPTX slide/theme XML, and identical PDF page content streams.
- Host checks cover export chunking, cancelled saves, revoked Blob URLs, message source validation, paused background rendering, originating-tab save routing, duplicate URI reuse, close protection, Home/Back and persistent appearance.
- Android API 35 resources and Java compile. APK v2/v3 signatures verify; package io.github.pedroguille.folio, version code 5, minimum API 26, target API 35. No Internet or broad storage permission.
- The certificate matches the previous preview: a5c3123a0e39082abcd220c3854f83da2c9cafb0366ffb11de8f065e28b0818d.

The APK remains a preview. Physical keyboard providers, external document providers and GPU performance still require a device check. Upstream desktop test suites were not run.

Reproduce import/edit/export and host checks after building:

```bash
python3 -m pip install -r tests/requirements.txt
npm --prefix tests install
npx --prefix tests playwright install chromium
node tests/bridge.cjs
python3 tests/make_fixtures.py
node tests/engines.cjs
python3 tests/verify_exports.py
python3 tests/verify_appearance.py
```

CHROMIUM_EXECUTABLE and PLAYWRIGHT_MODULE can select existing installations. Internal fixtures, exports and screenshots are under build/qa/ and excluded from source distribution.
