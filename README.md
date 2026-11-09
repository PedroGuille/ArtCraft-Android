# Lucy Builder 2.3.0

Aplicación **Linux x86_64 Flatpak. Descarga código fuente de la suite Craft y genera APK Android localmente, probablemente deje de funcionar en futuras actualizaciones, pero es mas facil de mantener que portear cada app por separado

## Instalar o actualizar

Cerrá Lucy Builder y abrí el Flatpak nuevo en el gestor de software. También podés ejecutar:

```sh
flatpak install --user --reinstall ./Lucy-Builder-2.3.0-x86_64.flatpak
flatpak run io.github.pedroguille.LucyBuilder
```

El identificador y el directorio de datos son los mismos. Se conservan firmas, preferencias y descargas. No desinstales ni borres los datos para actualizar. GNOME SDK 51 proporciona GTK, Python y compiladores Linux dentro del Flatpak; se descarga desde Flathub la primera vez.

## Aplicaciones individuales

Marcá una o varias aplicaciones y elegí **Descargar fuentes** o **Compilar APK individuales**. Cada aplicación genera su propia APK, icono, identificador y firma persistente, portee CADCraft y Lucy(aplicacion que permite usar 4 apps en diferentes pesatañas de una sola ventana y con un modo oscuro que cambia el color de los documentos y no solo la interfaz).

| Aplicaciones                                                                                   | Android                                                                              |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| WordCraft, PDFcraft, GridCraft, DeckCraft                                                      | Adaptador de Lucy                                                                    |
| CADCraft                                                                                       | Puerto nativo Android para ARM64, con el adaptador de tablet incluido                |
| PhotoCraft, VectorCraft, LightCraft, DesignCraft, FigCraft, SoundCraft, FilmCraft, EffectCraft | Compilación WebAssembly desde el código fuente y adaptación mediante Android WebView |
| Craft Anything, SolidCraft                                                                     | Descarga de fuentes; no hay port Android compatible incluida                         |


## Elegir la versión

En Configuración → Fuentes a compilar:

* **Versiones base guardadas**: usa los commits incluidos en `app/verified.json`; no consulta main ni reemplaza las referencias cuando aparece otra versión.
* **Última versión publicada**: consulta la última release del repositorio y resuelve su tag al commit exacto antes de descargar.
* **Desarrollo · main de GitHub**: consulta la rama actual. Puede necesitar adaptar el port de Android cuando upstream cambia.

Si falla una versión nueva, seleccioná la base guardada y compilá de nuevo. Las compilaciones nuevas no sobrescriben las referencias base. Los commits se incluyen en el informe del resultado. La selección se aplica también a Descargar fuentes y a las aplicaciones individuales.

La base ofimática es WordCraft 0.14.0, PDFcraft 0.17.0, GridCraft 0.15.0 y DeckCraft 0.15.0; CADCraft queda en 0.16.0. Los otros diez proyectos tienen instantáneas fijas de sus fuentes actuales para reproducibilidad, con menos validación Android. Una referencia fija no garantiza compatibilidad con todas las recetas ni elimina la necesidad de conexión para la primera descarga.

## Compatibilidad actualizada

Lucy Builder 2.3.0 añade adaptadores revisados para las fuentes de WordCraft 0.15.1, PDFcraft 0.18.1, GridCraft 0.16.0, DeckCraft 0.15.0 y CADCraft 0.17.0 revisadas el 9 de noviembre de 2026. Elegí **Revisadas · 09/11/2026** para reproducir esta entrega. Se conservan las versiones base anteriores, las publicaciones y main.

Una revisión exacta usa su adaptador revisado. Otras fuentes prueban la integración anterior y después la revisada; si ambos fallan, detiene la compilación y muestra los archivos afectados. Nunca sustituye las fuentes nuevas por un motor antiguo. Los perfiles de idiomas mantienen sus catálogos y la caché distingue los adaptadores.

## Idiomas

Se puede elegir entre incluir solo español o todos los idiomas


## Generar APK

En Aplicaciones, seleccioná las apps y pulsá **Compilar APK individuales**. Cada producto tiene su identidad y firma. En Componer Lucy, elegí entre uno y cuatro editores: WordCraft, PDFcraft, GridCraft y DeckCraft. La APK contiene solo los editores elegidos.

CADCraft usa un puerto nativo ARM64. PhotoCraft, VectorCraft, LightCraft, DesignCraft, FigCraft, SoundCraft, FilmCraft y EffectCraft usan adaptaciones WebAssembly/WebView experimentales. Craft Anything y SolidCraft permiten descargar fuentes; no tienen receta Android incluida.

Antes de la primera compilación, elegí carpeta de salida, trabajos simultáneos y aceptá la licencia del SDK. Se descargan y reutilizan Android SDK 36, Java 17 y Rust 1.99.1; CADCraft añade NDK r28c. Por defecto los resultados van a Descargas/Lucy-Builds. 


## Recompilar el constructor

```sh
python3 build_flatpak.py
python3 release_source.py
```

También se incluye el manifiesto estándar en `flatpak/io.github.pedroguille.LucyBuilder.json` para flatpak-builder. El código del constructor es MIT; las fuentes de cada aplicación conservan sus licencias y atribuciones.

No se realizaron compilaciones completas de todas las APK con el perfil multilingüe de esta entrega. Las comprobaciones realizadas se describen en VALIDACION-2.3.0.md.

## Porque solo Linux y Flatpak
Es mas facil de hacer y mantener, también es mas facil de usar sin sufrir dependency hell