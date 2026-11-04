#!/usr/bin/env python3
"""Verify the linked Android library without loading or executing it."""
import struct
import sys
from pathlib import Path
SYSTEM_LIBS = {"libc.so", "libdl.so", "libm.so", "liblog.so", "libandroid.so", "libz.so", "libEGL.so", "libGLESv2.so", "libGLESv3.so", "libvulkan.so"}
class BuildError(Exception):
    pass

def inspect_elf(data, abi="arm64-v8a"):
    machine = {"arm64-v8a": 183, "x86_64": 62}.get(abi)
    if machine is None or len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != machine:
        raise BuildError("La biblioteca generada no corresponde a Android " + abi + ".")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phsize, phnum = struct.unpack_from("<HH", data, 54)
    if phnum > 128 or phsize < 56 or phoff + phsize * phnum > len(data):
        raise BuildError("Cabecera ELF inválida.")
    segments, dynamic = [], None
    for i in range(phnum):
        p = struct.unpack_from("<IIQQQQQQ", data, phoff + i * phsize)
        if p[0] == 1:
            if p[7] < 16384 or p[2] % p[7] != p[3] % p[7]:
                raise BuildError("La biblioteca no está alineada para páginas de 16 KiB.")
            segments.append(p)
        if p[0] == 2:
            dynamic = p
    if not segments or not dynamic or dynamic[2] + dynamic[5] > len(data) or dynamic[5] > 1024 * 1024:
        raise BuildError("No se pudo verificar la biblioteca nativa.")
    entries = []
    for pos in range(dynamic[2], dynamic[2] + dynamic[5] - 15, 16):
        tag, value = struct.unpack_from("<qQ", data, pos)
        if tag == 0:
            break
        entries.append((tag, value))
    strings = next((value for tag, value in entries if tag == 5), None)
    sizes = next((value for tag, value in entries if tag == 10), 0)
    if strings is None or sizes > 8 * 1024 * 1024:
        raise BuildError("No se pudo verificar el enlace de bibliotecas.")
    string_offset = next((p[2] + strings - p[3] for p in segments if p[3] <= strings < p[3] + p[5]), None)
    if string_offset is None or string_offset + sizes > len(data):
        raise BuildError("Tabla de nombres ELF inválida.")
    names = data[string_offset:string_offset + sizes]
    needed = []
    for tag, value in entries:
        if tag in (1, 15, 29):
            if value >= len(names):
                raise BuildError("Referencia ELF inválida.")
            text = names[value:].split(b"\0", 1)[0].decode("ascii", errors="strict")
            if tag == 1:
                needed.append(text)
            elif "/data/" in text or "termux" in text or text not in ("", "$ORIGIN"):
                raise BuildError("La biblioteca contiene rutas de Termux y no sería una aplicación independiente.")
    unsupported = set(needed) - SYSTEM_LIBS
    if unsupported:
        raise BuildError("La aplicación enlaza bibliotecas ajenas a Android: " + ", ".join(sorted(unsupported)))
    return {"abi": abi, "load_alignment": [p[7] for p in segments], "needed_libraries": needed}

if __name__ == "__main__":
    try:
        print("Android ELF:", inspect_elf(Path(sys.argv[1]).read_bytes(), sys.argv[2] if len(sys.argv) > 2 else "arm64-v8a"))
    except (OSError, BuildError) as error:
        raise SystemExit(str(error))
