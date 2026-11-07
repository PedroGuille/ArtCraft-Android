# Validación de Lucy Builder 2.2.0

Se mantienen los commits de `app/verified.json`. Las fuentes de desarrollo se resuelven desde main y quedan registradas por commit; los adaptadores revisados no sustituyen una versión solicitada por una antigua.

## Fuentes revisadas

| Aplicación | Versión | Commit |
| --- | --- | --- |
| WordCraft | 0.15.1 | `729cd0a5fc953bbedbfdec4f6af18ad6d1780b3b` |
| PDFcraft | 0.18.1 | `f42fda734243b66f54db87923d7c981d5221419e` |
| GridCraft | 0.16.0 | `6a8eb4ff42cfa88b5bdd3eec13c6db3874d95214` |
| DeckCraft | 0.15.0 | `159ed07eb3f0522a5dc97d7cf1858242a6638659` |
| CADCraft | 0.17.0 | `865fa9afb047e6a5053b8f51c3ad4feef90804d2` |

## Comprobaciones realizadas

- Preparación real de los cuatro editores contra sus fuentes actuales, en perfiles `all` y `es`: ocho integraciones sin conflictos.
- `cargo check --locked --target wasm32-unknown-unknown` de los cuatro binarios web, en ambos perfiles. Se conserva el modo oscuro, el puente de lectura de WordCraft y la generación de fuentes de DeckCraft. El perfil español usa las APIs actuales de internacionalización, con catálogos restringidos.
- CADCraft 0.17.0: integración desde el ZIP original sin conflictos; comprobación del motor, IO y renderizado nativos; comprobación de la interfaz WebAssembly y del código de la app de tablet con `desktop-preview`. El adaptador mantiene lectura por streaming, cachés y soporte de imágenes del código actual.
- CADCraft 0.16.0 y pruebas de su base 0.14: integración anterior conservada. El perfil nuevo sólo se aplica cuando coinciden todos sus hashes de entrada; se comprueba que cambios de escritorio diferentes no activen una sustitución revisada.
- Pruebas Python del constructor y adaptadores: 9 + 27 + 28, con una prueba anterior omitida por sus requisitos. Regresión JavaScript del menú, apariencia y lectura.
- Paquete Flatpak creado mediante las herramientas oficiales, con el mismo identificador y directorio de datos.

## Límites

Estas comprobaciones no generan ni enlazan APK ARM64 completas y no incluyen pruebas en un dispositivo físico. No se presentan como una prueba funcional integral de todas las aplicaciones. Los manifiestos web actuales de PhotoCraft, VectorCraft, LightCraft, DesignCraft, FigCraft, SoundCraft, FilmCraft y EffectCraft siguen ofreciendo los destinos usados por sus recetas; no se recompilaron sus ocho APK. Craft Anything y SolidCraft mantienen la descarga de fuentes.

Para compilar las fuentes nuevas, elegir **Desarrollo · main de GitHub**. La opción de versiones base guardadas continúa usando las anteriores. Cambios posteriores de upstream pueden necesitar otro ajuste; una integración con conflictos se detiene antes de descargar herramientas o crear una firma.
