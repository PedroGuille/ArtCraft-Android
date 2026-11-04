# Asset attribution

Lucy's launcher image (`app/src/main/res/drawable-nodpi/lucy_icon.jpg`) was supplied by the user as “36567.jpg” and is included unchanged at the user's request. The previous flower image is removed. Its copyright remains with its owner; the host's MIT licence does not relicense this image. Android applies its normal adaptive launcher mask.

The CSS document icons, interface design, and generated blank templates
(`app/src/main/assets/templates/blank.*`) are original host contributor work under
the MIT licence in `LICENSE`. Earlier releases were named Folio Office.

The bundled WebAssembly document engines are local integration forks of WordCraft, GridCraft,
DeckCraft, and PdfCraft at the exact source commits pinned in `engine-lock.json`.
`third_party/patches/` contains all source changes: compact chrome, removal of Account,
About and community promotions, and document viewing palettes. Each compiled asset has
a source/patch/font provenance and SHA-256 manifest. Source for every base engine is
available at `https://github.com/storytold/<engine>/tree/<source_commit>`.
They are MIT OR Apache-2.0. Their copyright notices, asset attribution, and accompanying
license texts are preserved under `third_party/`, bundled as `THIRD_PARTY_NOTICES.txt`,
and accessible through the ⋮ menu's open-source licences button. Supplementary
fonts come from the pinned craft-fonts source and are checksum verified. See the notices
for embedded font and dependency licences.

Lucy is an independent integration. It is not affiliated with or endorsed by the ArtCraft
team, ONLYOFFICE, Microsoft, Adobe, or their respective products.

Inter is the common Lucy menu font. Its Regular, Medium and SemiBold files come from the pinned WordCraft source recorded with SHA-256 hashes in `engine-lock.json` (`ui_fonts`), by Rasmus Andersson under OFL-1.1. No proprietary font is bundled. The host serves the verified Regular face; GridCraft and DeckCraft consume the same font data as a build input. The licence is retained at `third_party/wordcraft/assets/fonts/OFL-Inter.txt`.
