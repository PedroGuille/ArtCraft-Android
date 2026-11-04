# CadCraft Linux Builder 1.1.1

Descarga el código oficial de CadCraft y crea su edición Android Tablet con un
comando desde **Linux x86_64**. La adaptación Android permanece separada del
escritorio. El proceso funciona en el ordenador; instala después la APK en la
tableta.

## Fedora: primera ejecución

Instala los requisitos del sistema una vez:

```bash
sudo dnf install -y git curl unzip xz python3 java-21-openjdk-devel gcc-c++ make pkgconf-pkg-config
```

Descomprime este paquete y ejecuta:

```bash
unzip CADCraft-Linux-Builder-1.1.1.zip
cd CADCraft-Linux-Builder-1.1.1
bash build.sh
```

El programa busca la última publicación estable, descarga su fuente oficial,
integra los cambios Tablet, prepara Rust y Android SDK/NDK en su propia carpeta
y compila una APK ARM64 firmada. Al finalizar muestra la ruta de la APK. Los
resultados, registros, hashes y símbolos nativos están en `dist/`.

**Conserva esta carpeta.** Las siguientes compilaciones reutilizan descargas y
caché. La primera necesita varios GB de descarga y espacio; reserva al menos
15 GiB libres, preferiblemente 25 GiB. La duración depende del procesador y la
conexión. Se seleccionan hasta ocho trabajos según la memoria disponible.

No necesitas Termux, la app Constructor, Docker ni una cuenta de GitHub. El
programa no publica nada, no ejecuta sudo, no modifica tu configuración del
terminal y usa su propia instalación de Rust.

Requisitos: Python 3.11+, JDK 17+ y herramientas de desarrollo. La interfaz se
compila para Java 17 y D8 la convierte para Android API 26. Antes de construir
Rust se comprueba que el compilador acepta ese objetivo. En Ubuntu 24.04 o
Debian con Java 21:

```bash
sudo apt install -y git curl unzip xz-utils python3 openjdk-21-jdk-headless build-essential pkg-config
```

## Opciones

```bash
# Versión concreta en lugar de la última.
bash build.sh --version 0.15.1

# Solo descargar y preparar el código, sin instalar herramientas ni crear APK.
bash build.sh --prepare-only

# Menor consumo de memoria durante la compilación.
bash build.sh --jobs 2

# Usar la clave de firma de tus APK anteriores.
bash build.sh --keystore /ruta/absoluta/preview.keystore
```

La clave compatible usa el alias `androiddebugkey` y la contraseña `android`,
como las versiones Tablet de prueba anteriores. Este paquete no contiene
ninguna clave privada. Sin `--keystore`, se crea y conserva una en
`private/preview.keystore`. Guárdala y no la publiques: para actualizar una app
instalada, Android exige la misma firma. Una clave nueva no permite actualizar
una APK firmada con otra clave.

Si interrumpes el proceso, vuelve a ejecutar el comando. Las descargas completas
se comprueban antes de reutilizarlas; las instalaciones incompletas del SDK/NDK
se rehacen. Si falta una dependencia del sistema, se indica qué instalar.

## Compatibilidad al actualizar

La integración revisada usa CadCraft **v0.15.1**, revisión
`660e15c9f494ce647e87de10adbb01a8786e0901`. La selección de la última versión es
automática; `--version 0.15.1` permite fijar una fuente conocida.

Se comparan el escritorio original, tus cambios Tablet y el escritorio nuevo.
Se conservan los cambios independientes y se detiene la compilación si hay
conflictos. El informe aparece en
`work/<revision>-<adaptador>/.tablet/report.json`. No se puede garantizar que
cualquier API futura funcione sin actualizar el adaptador. Una combinación de
texto sin conflictos todavía puede fallar al compilar por cambios de API.

El ZIP original no cambia. El comando automático no sobrescribe tus ediciones
manuales de las fuentes generadas. Cada revisión o adaptación utiliza una
carpeta identificada por sus hashes.

Herramientas fijadas: Rust 1.99.1 oficial, SDK Android 36, build-tools 36.0.0 y
NDK r28c. El compilador Rust y sus bibliotecas Android proceden de la misma
publicación oficial; no se mezclan con bibliotecas de Termux. Se comprueban la
ABI, la alineación a páginas de 16 KiB y las dependencias nativas de Android.

## Organización

| Ruta | Contenido |
| --- | --- |
| `build.sh`, `linux.py` | Descarga automática y compilación Linux |
| `tablet.py` | Validación de ZIP, combinación y empaquetado |
| `android/` | Módulos propios de Android, interfaz, Java y empaquetado |
| `integration/`, `compat/` | Cambios compartidos y combinaciones revisadas |
| `adapter.json` | Herramientas, base e integridad |
| `cache/` | Fuentes descargadas, herramientas y caché de compilación |
| `work/` | Fuentes combinadas para compilar |
| `dist/` | APK, símbolos de esa compilación y registro |
| `private/` | Tu clave de firma; no publiques esta carpeta |

Después de editar archivos propios en `android/`, ejecuta
`python3 tools/seal.py` y prepara una carpeta nueva. No edites
`integration/base/`: es la referencia original para las combinaciones.

## Uso avanzado con una fuente local

Para preparar un ZIP existente o recompilar cambios deliberados, carga el
entorno privado desde la carpeta de este paquete:

```bash
export RUSTUP_HOME="$PWD/cache/toolchain/rustup"
export CARGO_HOME="$PWD/cache/toolchain/cargo"
export PATH="$CARGO_HOME/bin:$PATH"
export RUSTUP_TOOLCHAIN=1.99.1
export ANDROID_HOME="$PWD/cache/toolchain/android"
export ANDROID_NDK_HOME="$ANDROID_HOME/android-ndk-r28c"
python3 tablet.py prepare /ruta/cadcraft-0.15.1.zip --output work/manual
python3 tablet.py compile work/manual --artifacts dist/manual
```

Para el emulador x86_64, instala también su biblioteca Rust y usa `--abi x86_64`
en `tablet.py compile`. La automatización principal construye ARM64.

Pruebas del adaptador y flujo Linux:

```bash
python3 -m unittest discover -s tests -v
```

Los lanzadores Docker anteriores quedan como opción avanzada. El flujo Linux
principal no los necesita. Consulta `VALIDACION.md` para el alcance comprobado.

## Licencia

MIT OR Apache-2.0, como CadCraft. Se conservan las licencias y atribuciones
originales. La fuente y dependencias descargadas mantienen sus propios avisos.

## Continuar una compilación fallida de 1.1.0

Si el JDK rechaza «release version 8 not supported», puedes corregir tu carpeta
actual sin trasladar la caché ni la clave de firma. Desde esa carpeta:

```bash
sed -i 's/--release 8 /--release 17 /' android/packaging/android/build.sh
python3 tools/seal.py
bash build.sh --version 0.15.1
```

El sellado actualiza la integridad del archivo propio modificado. El comando
prepara otra fuente con ese cambio y conserva las herramientas y los módulos
Rust compilados en la misma carpeta. Esta corrección ya viene incluida en 1.1.1.
