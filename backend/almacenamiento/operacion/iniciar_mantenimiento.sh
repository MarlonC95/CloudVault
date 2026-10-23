#!/bin/sh
# Arranque supervisado; el entorno lo gestiona la instalación, sin escribir .env.
set -eu

modo=ejecutar
if [ "$#" -gt 0 ]; then
    if [ "$#" -eq 1 ] && [ "$1" = "--comprobar" ]; then
        modo=comprobar
    else
        printf '%s\n' 'Uso: sh iniciar_mantenimiento.sh [--comprobar]' >&2
        exit 2
    fi
fi

if [ "$modo" = ejecutar ] && [ "${ALMACENAMIENTO_MANTENIMIENTO_HABILITADO:-0}" != 1 ]; then
    printf '%s\n' '{"evento":"mantenimiento_inactivo","level":"error","message":"Activacion operativa pendiente; no se inicio el mantenimiento."}' >&2
    exit 2
fi

directorio=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$directorio/../.."
python_mantenimiento=${ALMACENAMIENTO_PYTHON:-python}

# Solo comprueba la interfaz; el constructor del proveedor debe ser sin efectos.
"$python_mantenimiento" -u manage.py verificar_proveedor_almacenamiento
if [ "$modo" = comprobar ]; then
    exit 0
fi

# exec entrega las señales y el código de salida del proceso al supervisor.
# El comando usa ALMACENAMIENTO_MANTENIMIENTO_INTERVALO, por defecto 60 s.
exec "$python_mantenimiento" -u manage.py mantener_cargas --continuo
