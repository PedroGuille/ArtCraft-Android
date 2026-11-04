# Carpeta temporal de la APK generada

El adaptador 1.0.2 define TMPDIR con Activity.getCacheDir antes de llamar a NativeActivity.onCreate. Así la biblioteca estándar Rust usa la caché privada de CadCraft, incluso si su distribución tiene una ruta de reserva propia del entorno de compilación. La APK no necesita acceder a la carpeta del constructor y puede ejecutarse después de desinstalarlo.

No se altera el código de escritorio ni se incluyen bibliotecas compartidas del compilador dentro de CadCraft.
