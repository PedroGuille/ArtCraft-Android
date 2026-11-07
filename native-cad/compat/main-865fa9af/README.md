# CADCraft 0.17.0 para el puerto de tablet

Revisión de escritorio: `865fa9afb047e6a5053b8f51c3ad4feef90804d2`.

El perfil conserva las nuevas APIs de DWG, VIEWTWIST, memoización de propiedades, imágenes y XCLIP, junto a las integraciones Android de lectura por streaming, cachés y escenas compartidas. Sólo se aplica si los 71 hashes de entrada del manifiesto coinciden; los cambios posteriores que no coincidan siguen la combinación normal y no se sobrescriben.

Se comprobaron los crates del motor nativo, la interfaz WebAssembly y la app con desktop-preview. No se enlazó una APK ARM64 ni se probó en una tablet física. Las bases anteriores continúan con el adaptador anterior.
