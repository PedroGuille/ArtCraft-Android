# Adaptadores de compatibilidad

Cada parche se generó contra el commit `base_commit` del manifiesto y se verifica por SHA-256 antes de aplicarlo. El constructor conserva el adaptador anterior para las bases guardadas. Ante un conflicto, restaura únicamente el checkout nuevo que acaba de crear y prueba el adaptador revisado mediante `git apply --3way --index`. Si vuelve a fallar, conserva el error y no compila.

Los parches `all` conservan la internacionalización de origen. Los parches `es` mantienen las traducciones anteriores de DeckCraft; `compatibility.spanish_only` restringe los catálogos del resto conservando sus APIs actuales. Las revisiones de catálogos propias de los editores se incluyen en el informe y la caché.

No editar un parche sin regenerar su hash. La huella agregada de los perfiles participa en las claves de preparación y compilación.
