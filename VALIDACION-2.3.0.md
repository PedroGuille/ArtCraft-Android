# Validación de Lucy Builder 2.3.0

## Fuentes

| App | Commit |
| --- | --- |
| wordcraft | 05f781cfdac1d89034c0f4f5824b597ff845f2ef |
| pdfcraft | ba28458ad8bd8d8b5b83c14f643bfa8ce9592f60 |
| gridcraft | e9addf52fe68847e6c1310fcfa5d42b7aa8b9650 |
| deckcraft | 0623b430324cf4c3d1962e6ae7885cf30c011c5e |
| cadcraft | a3d9348f63c2ad35391cc93980dc7ee7366f2ad6 |

## Comprobaciones

- Pruebas Python y regresión JavaScript del constructor.
- Compilaciones release: CADCraft ARM64 nativo y los cuatro motores WebAssembly.
- Registro de la compilación release de DeckCraft: https://github.com/PedroGuille/ArtCraft-Android/actions/runs/42661556613/job/129314155900 (paso de compilación completado; el fallo posterior fue del empaquetado Flatpak).
- APK de Lucy con WordCraft, PDFcraft y GridCraft; se verifica que DeckCraft no esté incluido.
- PDFcraft incluye su worker OCR, modelos ONNX verificados por SHA-256, licencia y atribuciones.
- APK de CADCraft con firma verificada y soporte de páginas nativas de 16 KiB.
- Flatpak creado con las herramientas oficiales.

No se probaron en un dispositivo físico ni se recompilaron las otras diez aplicaciones del catálogo. Las versiones anteriores siguen disponibles. Cambios posteriores de main pueden necesitar adaptar las fuentes otra vez.
