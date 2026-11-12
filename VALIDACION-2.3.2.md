# Lucy Builder 2.3.2

CADCraft 0.20.1: etiqueta v0.20.1, commit 7526dc62c14e71b3c8d46e73bbf1fa29ef506af1.

El perfil Android release-0.20.1 comprueba 71 entradas originales y aporta 26 archivos adaptados. Se conservan los perfiles anteriores, los editores ofimáticos y sus idiomas.

La adaptación conserva el guardado asíncrono de Android y el nuevo cierre de documentos de escritorio, con regresiones para las respuestas tardías del guardado.

La verificación de fuentes se reproduce con `python3 tools/check_cad0201.py FUENTES.zip`. Rechaza entradas alteradas y comprueba las versiones del manifiesto Android. El workflow de comprobación ejecuta también las pruebas del constructor y la comprobación de tipos para ARM64.

Esta actualización solo entrega código. No se generan APK ni Flatpak y no se ha probado en un dispositivo físico.
