"""Evaluación de preflight sin SDK, credenciales ni operaciones remotas."""

ORIGEN_ENSAYO = "http://127.0.0.1:8765"


def evaluar_preflight(estado, headers, *, origen=ORIGEN_ENSAYO, metodo="PUT",
                      encabezados=("content-type",)):
    normalizados = {nombre.lower(): valor for nombre, valor in headers.items()}
    metodos = {valor.strip().upper() for valor in normalizados.get(
        "access-control-allow-methods", "").split(",")}
    permitidos = {valor.strip().lower() for valor in normalizados.get(
        "access-control-allow-headers", "").split(",")}
    resultado = {
        "estado_http": estado,
        "estado_correcto": estado in {200, 204},
        "permite_origen": normalizados.get("access-control-allow-origin") == origen,
        "permite_metodo": metodo.upper() in metodos,
        "permite_headers": "*" in permitidos or set(encabezados) <= permitidos,
    }
    resultado["aprobado"] = all(resultado[nombre] for nombre in (
        "estado_correcto", "permite_origen", "permite_metodo", "permite_headers"))
    return resultado
