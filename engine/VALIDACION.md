# Validación de Lucy Builder Linux 1.0.0

Comprobaciones realizadas el 31 de octubre de 2026 en Linux x86_64
(Ubuntu 24.04), con Python 3.12, JDK 17 y Rust 1.99.1 / LLVM 23.1.1.

## Fuentes compiladas

Estas revisiones se consultaron en `main` y se fijaron antes de compilar:

| Editor | Versión | Revisión |
| --- | --- | --- |
| Wordcraft | 0.13.2 | `6e0f7e79edabf5904ecb73104e809e6f053d9d27` |
| Gridcraft | 0.14.2 | `a85b1aea3a8a3369581a749d8da041e4db014504` |
| Deckcraft | 0.13.1 | `82573331a8f2b87ccb536b9b66d55b90295f2111` |
| PDFcraft | 0.16.1 | `eea00a6186546762d11d857666249672bff3fcad` |

El perfil PDF incorpora el nuevo control de sombras de borde de página y
conserva las adaptaciones de Lucy. La selección se pudo repetir con `--repeat`.

## Resultados

- 25 pruebas del constructor aprobadas, incluyendo importación real de JKS,
  conservación del certificado, firma PKCS12 con el SDK oficial, protección de
  la APK anterior, reintentos con salidas independientes y comprobación del
  `.run` con entrada de terminal y entrada redirigida.
- Preparación automática del SDK 36 y del destino `wasm32-unknown-unknown`
  con el mismo compilador Rust. También se probó la descarga y extracción del
  JDK 17 oficial cuando falta un JDK del sistema.
- Compilación real de los cuatro editores desde sus fuentes; generación de la
  APK, firma v2/v3 y comprobación de alineación con las herramientas oficiales.
- Nombre Android `Lucy`, paquete `io.github.pedroguille.folio`, mínimo API 26 y
  destino API 35, comprobados en el manifiesto compilado.
- Segunda ejecución completa con las mismas revisiones: los cuatro motores
  se reutilizaron tras verificar sus archivos, sin recompilar Rust. Se mantuvo
  el certificado y se generó una nueva APK con una versión posterior.
- Verificación de los módulos JavaScript, WebAssembly y dependencias locales
  extraídos de la APK firmada.
- Pruebas en Chromium con esos mismos recursos: cuatro documentos abiertos,
  cambios de pestaña sin perder ediciones, exportación DOCX/XLSX/PPTX/PDF,
  fórmula y resultado de hoja de cálculo, deshacer/rehacer de Word y edición
  de texto PDF. Los archivos exportados se analizaron de forma independiente.
- El modo oscuro conservó el contenido y los colores de los archivos guardados
  en los cuatro formatos. Se comprobó la herramienta Mano predeterminada y la
  recepción de clics en los botones PDF reducidos.
- Vista dividida con Word/PDF y presentación/hoja de cálculo: dos vistas
  simultáneas, desplazamiento independiente, edición y exportación, conservación
  de instancias al dividir, desdividir y volver a Inicio.
- Exclusión de claves privadas del `.run`, del ZIP de código y de la APK.

## Alcance

La comprobación de los editores usa los recursos reales de la APK en Chromium.
No se ejecutó la APK en un dispositivo Android físico durante esta validación.
Fedora dispone de las instrucciones de instalación de dependencias en `LEEME.md`;
la compilación aquí se realizó en Ubuntu. Un cambio futuro incompatible de los
proyectos originales puede exigir actualizar el perfil de integración.

Cada compilación del usuario registra sus propias revisiones, versión de Rust,
certificado y SHA-256 en `build-info.json`. Su firma personal y la fecha de
compilación hacen que el hash de su APK sea diferente al de esta comprobación.
