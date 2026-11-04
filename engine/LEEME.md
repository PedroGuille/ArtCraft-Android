# Lucy Builder para Linux 1.0.0

Descarga el código actual de `main` de Wordcraft, Gridcraft, Deckcraft y PDFcraft,
aplica las adaptaciones de Lucy y genera una APK Android firmada en tu PC.
No necesita Android Studio, Termux, una cuenta de GitHub, tokens ni servicios de
compilación externos.

## Un comando

Descargá `Lucy-Builder-Linux-1.0.0.run` y ejecutalo desde tu terminal:

```bash
bash ~/Descargas/Lucy-Builder-Linux-1.0.0.run
```

Si tu navegador lo guardó en otra carpeta, cambiá esa ruta. No hace falta
descomprimirlo ni darle permisos de ejecución. Leé y aceptá la licencia del SDK
de Android cuando aparezca la pregunta. El programa prepara automáticamente
Rust, su destino WebAssembly y el SDK; utiliza un JDK instalado si sirve o
descarga un JDK 17 oficial.

Al terminar, en la carpeta desde donde ejecutaste el comando se crea:

```text
Lucy-output/Lucy.apk
Lucy-output/Lucy-source.zip
Lucy-output/build-info.json
Lucy-output/build.log
```

`Lucy.apk` es la aplicación que se instala en Android 8 o posterior. Copiala al
dispositivo y abrila con su gestor de archivos. `Lucy-source.zip` contiene el
proyecto Android, las revisiones exactas y los parches utilizados. El informe
registra también la firma y el SHA-256 de la APK. Las compilaciones anteriores
se conservan dentro de `Lucy-output/builds/`.

La primera ejecución descarga y compila dependencias grandes: necesitás conexión,
varios GB de espacio libre y tiempo de compilación. La caché se reutiliza en las
siguientes ejecuciones; los editores sin cambios no se recompilan. No descargues
de nuevo el `.run` para consultar cambios de `main`: ejecutá el mismo comando.

## Requisitos de Linux

Esta edición funciona en Linux x86_64 con Python 3.11 o posterior y herramientas
básicas de C/C++. Si te avisa que faltan, en Fedora instalalas una sola vez:

```bash
sudo dnf install python3 git gcc gcc-c++ make
```

En Ubuntu/Debian, con Python 3.11 o posterior disponible:

```bash
sudo apt install python3 git build-essential
```

El constructor se ejecuta como tu usuario normal. No uses `sudo` para compilar.
No modifica el Java/Rust del sistema ni los archivos de inicio de tu terminal.
Las herramientas se descargan de sus distribuidores oficiales y se verifican
con los checksums publicados por ellos.

## Actualizar una Lucy que ya tenés instalada

Android exige conservar la misma firma para instalar una actualización encima
de la aplicación existente. Si tenés la copia de su firma anterior, importala
una sola vez:

```bash
bash ~/Descargas/Lucy-Builder-Linux-1.0.0.run --import-key ~/Descargas/Folio-Office-preview-signing-key.zip
```

También acepta un archivo `.jks`, `.keystore`, `.p12` o `.pfx`. Pide su contraseña
sin mostrarla; si es la copia original de Lucy/Folio, presioná Enter para usar
`android`. Si hay varias claves privadas, agregá `--key-alias nombre-del-alias`.
Una contraseña incorrecta no reemplaza la firma que ya esté guardada.

Sin una firma importada, crea una firma personal y la conserva para las próximas
APK. Esa firma nueva permite actualizar las APK creadas por este mismo
constructor; no permite actualizar una instalación que tenga otra firma.

Hacé una copia privada de la carpeta `signing` situada en:

```text
~/.local/share/lucy-builder/signing/
```

Si configuraste `XDG_DATA_HOME`, `LUCY_STATE_DIR` o `--state-dir`, se usa esa
ubicación en su lugar. El programa muestra la ruta exacta al finalizar. No
publiques esa carpeta: contiene tu clave y su contraseña. No se incluyen claves
privadas en el `.run`, el ZIP de código ni la APK.

## Opciones útiles

Elegir otra carpeta de salida y ajustar los trabajos simultáneos:

```bash
bash ~/Descargas/Lucy-Builder-Linux-1.0.0.run --output ~/Lucy-compilada --jobs 4
```

El valor predeterminado de `--jobs` se ajusta a la memoria disponible, con un
máximo de cuatro. Reducilo si el sistema se queda sin memoria.

Descargar y adaptar las fuentes sin instalar herramientas ni compilar:

```bash
bash ~/Descargas/Lucy-Builder-Linux-1.0.0.run --prepare-only
```

Se guardan en `~/.local/share/lucy-builder/work/engines/`. Las carpetas de trabajo
y de caché son administradas por el constructor. Si querés modificar las
fuentes manualmente, copialas a otra ubicación. El constructor detecta cambios
manuales y se detiene para conservarlos.

Usar explícitamente las revisiones base del perfil incluido:

```bash
bash ~/Descargas/Lucy-Builder-Linux-1.0.0.run --verified
```

Para reintentar exactamente la selección de fuentes de la última ejecución,
aunque hayan publicado más cambios mientras compilabas:

```bash
bash ~/Descargas/Lucy-Builder-Linux-1.0.0.run --repeat
```

Esto conserva las revisiones de los cuatro editores, las fuentes tipográficas y
los catálogos de esa selección. Sin esta opción se consulta de nuevo `main`.

Por defecto siempre consulta el `main` actual. Cada ejecución fija sus revisiones
Git antes de compilar. Si un cambio futuro es incompatible con las adaptaciones
de Lucy, se detiene y muestra el problema; no sustituye silenciosamente el
código nuevo por una versión antigua. En ese caso habrá que actualizar el perfil.
La última APK completa y la firma permanecen disponibles aunque falle una
compilación posterior.

Para una ejecución automatizada, tras leer la licencia del SDK se puede usar
`--accept-sdk-license`. Para automatizar una importación de firma, usá
`--import-password-env NOMBRE_DE_VARIABLE` con la contraseña en esa variable;
no la pongas en los argumentos del comando.

Ayuda completa:

```bash
bash ~/Descargas/Lucy-Builder-Linux-1.0.0.run --help
```

## Código y adaptaciones incluidas

El ZIP de distribución es el código del constructor. Extraelo y ejecutá
`bash lucy.sh` desde la carpeta que contiene. Para volver a empaquetar el `.run`
y su ZIP:

```bash
python3 build_distribution.py
```

No se necesita GitHub Actions. El constructor local incluye la aplicación Android
Lucy y sus perfiles: interfaz en español, icono del monitor rosa, pestañas,
división en dos documentos, modo oscuro, menús compactos y carga de varias
fuentes. Estos cambios se aplican a las fuentes originales antes de compilarlas.

Los proyectos originales están en:

- https://github.com/storytold/wordcraft
- https://github.com/storytold/gridcraft
- https://github.com/storytold/deckcraft
- https://github.com/storytold/pdfcraft

Los avisos y licencias de sus dependencias se conservan en el código y se
recopilan en la APK. El constructor está bajo la licencia MIT de `LICENSE`;
los componentes de terceros mantienen sus propias licencias.

Para ejecutar las pruebas del constructor (los casos de firma necesitan un JDK):

```bash
python3 -m unittest discover -s tests -v
```

La prueba de firma con las herramientas oficiales se activa indicando el SDK
que preparó el propio constructor:

```bash
LUCY_TEST_SDK=~/.local/share/lucy-builder/tools/android-sdk python3 -m unittest discover -s tests -v
```
