# Compatibilidad con CadCraft 0.15.1

La base de integración permanece en 0.14.0. Se añadieron tres combinaciones revisadas de archivos para la fuente estable 0.15.1, commit `660e15c9f494ce647e87de10adbb01a8786e0901`:

- DWG: conservar la normalización y las protecciones nuevas del escritorio, junto con la importación directa y la escritura temporal de tablet.
- Texto: conservar la comprobación nueva del escritorio y los campos del caché compartido de tablet.
- Interfaz: conservar AutoComplete/fallback de comandos del escritorio y salir del modo mano al ejecutar un comando.

Cada combinación requiere coincidencia del SHA-256 de ambos archivos de entrada y valida el hash de su resultado. Cambios futuros diferentes siguen pasando por la combinación de tres vías; un conflicto desconocido detiene la preparación.

Se preparó la fuente real de 0.15.1 sin conflictos. La resolución Android conserva los 591 paquetes originales y añade 20. Las 20 pruebas del adaptador y las siete del flujo Linux pasan. El flujo Linux 1.1.1 completa la compilación real y el empaquetado de la APK ARM64. Las pruebas de ejecución en una tableta física siguen pendientes. Consulta VALIDACION.md para el alcance actual.
