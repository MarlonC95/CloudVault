"""Worker acotado de hash final. Entrada técnica por stdin; sin SQL ni .env."""

import json
import sys

from .configuracion_s3 import ConfiguracionS3
from .contrato import PoliticaCarga
from .s3 import ClienteS3, ErrorS3, _clave


def ejecutar(datos, *, cliente_factory=None):
    if not isinstance(datos, dict) or set(datos) != {"clave", "tamano_bytes"}:
        raise ValueError("Entrada técnica inválida")
    clave, tamano = datos["clave"], datos["tamano_bytes"]
    _clave(clave, propia=True)
    if "/publicaciones/" not in clave or type(tamano) is not int or not 0 <= tamano <= 5 << 30:
        raise ValueError("Publicación inválida")
    cliente = (cliente_factory() if cliente_factory else
               ClienteS3(ConfiguracionS3.desde_entorno(),
                         politica=PoliticaCarga(maximo_archivo_bytes=max(1, tamano))))
    try:
        contenido = cliente.verificar_contenido(clave, maximo_bytes=tamano)
        return {"tamano_bytes": contenido.tamano_bytes, "sha256": contenido.sha256}
    finally:
        cliente.cerrar()


def main():
    try:
        entrada = sys.stdin.buffer.read(2049)
        if len(entrada) > 2048:
            raise ValueError("Entrada excesiva")
        resultado = ejecutar(json.loads(entrada))
        print(json.dumps(resultado))
        return 0
    except ErrorS3 as exc:
        print(json.dumps({"error": "contenido" if exc.tipo == "contenido" else "servicio"}))
    except Exception:
        # Nunca traceback, SDK debug, credenciales, URL ni body del proveedor.
        print(json.dumps({"error": "servicio"}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
