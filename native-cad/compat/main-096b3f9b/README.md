Combinaciones revisadas para CADCraft 0.16.0, commit
`096b3f9be427830db5568a3a8ed2e8ba3e41ee66`, incluidas en Lucy Builder 2.0.3.

* DWG: conserva el posprocesado protegido, el presupuesto de celdas de tablas,
  alturas, orden de dibujo y corrección de MTEXT nuevos de upstream, junto con
  la importación tipada y el escritor incremental de Android. El lector tipado
  comparte el posprocesado nuevo y su protección frente a errores.
* Borrado: conserva `erase_kept` y OOPS para restaurar objetos borrados; la base
  de datos Android mantiene sus almacenes compartidos por fragmentos.
* Deshacer y rehacer: combina la nueva lógica de grupos LISP y de etiquetas con
  el límite de memoria de Android. `swap_in` ya incrementa la revisión, por lo
  que no se incrementa una segunda vez.
* Controles: conserva las métricas de caché Android y la nueva señal de geometría
  truncada, calculada sobre las partes y bloques compartidos de la escena.
* Interfaz: conserva la alternativa de comandos de upstream y QuickCalc junto
  con la salida del modo mano al introducir comandos y las preferencias táctiles.

Cada combinación solo se acepta para los SHA-256 exactos del archivo recibido
y del archivo Android original. Un cambio posterior diferente vuelve a pasar
por la combinación de tres vías y se detiene si requiere otra revisión.
