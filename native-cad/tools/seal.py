#!/usr/bin/env python3
"""Update integrity hashes after deliberately editing tablet-owned sources."""
from pathlib import Path
import json
import sys

kit = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(kit))
import tablet


def main():
    manifest_path = kit / "adapter.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    owned = []
    for path in sorted((kit / "android").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            raise tablet.AdapterError(f"No se admiten enlaces en el adaptador: {path}")
        relative = tablet.relative_name(path.relative_to(kit / "android").as_posix())
        owned.append({"path": relative, "source": "android/" + relative,
                      "sha256": tablet.file_sha(path), "mode": 0o755 if relative.endswith(".sh") else 0o644})
    manifest["owned"] = owned
    tablet.write_json(manifest_path, manifest)
    tablet.load_adapter(kit)
    print(f"Verificados {len(owned)} archivos propios; hashes actualizados. Prepara de nuevo el ZIP original.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, tablet.AdapterError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
