# Validación de CadCraft Linux Builder 1.1.1

Fecha: 31 de octubre de 2026.

## Flujo automático

- Linux x86_64, Python 3.12 y Java 17.
- Descarga real automática del código oficial v0.15.1, revisión
  `660e15c9f494ce647e87de10adbb01a8786e0901`.
- SHA-256 del ZIP: `41e301a4436a29d7011393a753643279660720d61f18f8fc9c5d8a283054db03`.
- Integración sin conflictos, con los tres ajustes revisados para 0.15.1.
- Resolución de dependencias Android conservando todos los paquetes originales
  bloqueados del escritorio.
- 57 archivos propios Android y parches sobre la base compartida 0.14.0.

## Comprobaciones completadas

- 27 pruebas automáticas aprobadas: 20 del adaptador y siete del flujo Linux.
- Descarga por revisión inmutable, reutilización de ZIP verificado y nueva
  descarga cuando la caché está dañada.
- Descarga interrumpida: conserva el archivo anterior y elimina el parcial.
- Rechazo de etiquetas y servidores inesperados.
- Aislamiento de Rust respecto a RUSTFLAGS y wrappers externos; restauración
  del entorno del llamador incluso cuando falla una compilación.
- Sintaxis de los scripts Bash principales.
- Instalación real del toolchain fijado: Rust 1.99.1 oficial, SDK 36,
  build-tools 36.0.0 y NDK r28c, con comprobación de descargas.
- Prueba real de enlace ARM64: biblioteca Rust con Vec y vec!, usando std del
  mismo Rust oficial y NDK Clang; cuatro segmentos LOAD a 16 KiB y únicamente
  libdl.so/libc.so como dependencias dinámicas.

## Compilación completa

Se construyó correctamente una APK ARM64 de CadCraft **0.15.1** desde el ZIP
oficial descargado automáticamente. El perfil Android optimizado se completó
en 22 min 15 s en este entorno con dos trabajos; no es una estimación para otros
ordenadores. La compilación en tu PC puede tardar distinto.

Comprobaciones de la APK completa:

- Paquete `io.github.storytold.cadcraft`, versión 0.15.1 y versionCode 15001.
- ARM64, Android mínimo API 26 y target/compile API 36.
- Firma APK v2 y v3 válidas y alineación ZIP a 16 KiB.
- Cuatro segmentos ELF LOAD alineados a 16 KiB.
- Dependencias nativas: liblog.so, libandroid.so, libdl.so, libm.so y libc.so.
- Exportaciones `ANativeActivity_onCreate` y `android_main` presentes.
- Biblioteca dentro de la APK idéntica a la copia instalada sin símbolos.
- Build ID coincidente entre biblioteca instalada y símbolos conservados:
  `e9a6be2a4bfcb386b30d0e00d97e680a440c2b84`.
- ZIP de símbolos íntegro y biblioteca sin quitar símbolos idéntica al original.
- CRC de la APK e informe de procedencia/SHA-256 correctos.
- Los 591 paquetes originales del escritorio siguen bloqueados; se añaden 20.

El paquete ZIP del constructor se extrajo en una carpeta independiente: las
27 pruebas también pasan allí. Se verificaron todos los hashes de su contenido
y se descargó/preparó de nuevo la fuente oficial desde esa copia independiente.
No se incluyen herramientas descargadas, cachés, APK, símbolos ni claves privadas.

La recompilación real con caché también se completó. Se corrigió un problema del
puente winit que restablecía Cargo.lock y la configuración sin cambios, forzando
recompilaciones del renderizador y del motor. Ahora solo se conserva el lock si
sus paquetes coinciden exactamente con la fuente actual y la sustitución local
del winit 0.30.13 revisado; se mantiene la validación posterior de dependencias.

Con esa corrección, Cargo reutilizó todos los módulos Rust y completó esa fase
en **0,89 s**, sin líneas «Compiling». Ese tiempo corresponde a Cargo, no a todo
el comando: descarga de metadatos, Java, recursos, firma y empaquetado tienen
sus propios costes. La APK resultante pasó de nuevo firma/alineación/ELF y
conserva el mismo certificado de firma entre compilaciones.
No se ejecutaron las puertas CI completas de escritorio en esta entrega.

No se han probado Fedora, Ubuntu en un ordenador físico ni la ejecución de la
APK en una tableta física en este entorno. El flujo se comprueba en Linux
x86_64. Los lanzadores Docker heredados no se han ejecutado en esta entrega.

La compatibilidad con futuras publicaciones depende de sus cambios reales:
una combinación de texto limpia no demuestra compatibilidad de APIs. El flujo
se detiene ante conflictos o errores; no sustituye una fuente nueva por una
versión antigua para ocultarlos.

## Corrección Java 1.1.1

La versión 1.1.0 solicitaba --release 8. El JDK del usuario rechazó ese objetivo
después de compilar correctamente Rust. Ahora el empaquetador solicita
--release 17, acorde con el JDK mínimo admitido, y comprueba ese objetivo con
una compilación pequeña antes de descargar/preparar el proyecto.

Validación realizada con OpenJDK 17.0.20, SDK/build-tools 36 y min-api 26:

- Compilación de todas las clases Java de la actividad: major version 61.
- Conversión real con D8; classes.dex generado sin referencias sin resolver
  a java.lang.invoke.StringConcatFactory.
- APK completa generada, firmada v2/v3 y verificada; CRC y SHA-256 correctos.
- Bibliotecas nativas y alineación de 16 KiB comprobadas de nuevo.
- Todos los módulos Rust se reutilizaron: esa fase terminó en 0,50 s.
- Nueva regresión: un objetivo Java incompatible detiene el flujo antes de
  descargar fuentes o iniciar la compilación Rust.

Las pruebas de ejecución en una tableta física siguen pendientes. No se ha
probado esta corrección ejecutando un JDK más reciente en este entorno.
