"""Conserva informes originales y genera matriz consolidada saneada, sin red."""

import argparse
import hashlib
import json
from pathlib import Path

from .tests_persistencia.aceptacion import combinar_railway, guardar_informe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for nombre in ("local", "railway", "entorno", "auth", "informe"):
        parser.add_argument("--" + nombre, type=Path, required=True)
    args = parser.parse_args()
    fuentes = {k: getattr(args, k) for k in ("local", "railway", "entorno", "auth")}
    contenido = {k: json.loads(p.read_text()) for k, p in fuentes.items()}
    informe = combinar_railway(contenido["local"], contenido["railway"], contenido["entorno"], contenido["auth"])
    informe["sha256_informes_origen"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes.values()}
    guardar_informe(args.informe, informe)
    print(json.dumps({"pruebas_locales": informe["conteo_pruebas"],
                      "matriz": informe["conteo_matriz_fase8"], "integracion_completa_certificada": False}))
    return 0 if contenido["local"].get("ejecucion_local_aprobada") and contenido["auth"].get("regresion_auth_aprobada") and informe["railway_s3_operaciones_aprobadas"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
