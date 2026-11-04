Combinaciones revisadas para main de CADCraft
`d7ef7da872fbd4158a5b2fc493f2da191f461d03` (0.15.1), incluidas en Lucy Builder.

* `spatial.rs`: el índice Android ya usa árboles inmutables por fragmento y
  reconstruye el árbol superior completo. Conserva ese diseño, que evita la
  secuencia remove/insert de rstar que corrige upstream en #2468. La nueva
  función de parcheo del índice plano no se aplica a la estructura de dos niveles.
* `draw.rs`: conserva el recorte nuevo de líneas discontinuas al área visible
  (#2299), junto con la geometría compartida y los cachés Android. Las primitivas
  transformadas entregan un Cow de puntos; el contorno se obtiene desde
  `primitive.fill_outlines()` antes de dibujar en coordenadas de pantalla.

Cada combinación se acepta solamente para los SHA-256 exactos de los dos archivos
de entrada. Otros cambios futuros siguen pasando por la combinación de tres vías
y se detienen si existe un conflicto nuevo.
