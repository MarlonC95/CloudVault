#!/bin/sh
set -eu

# El volumen node_modules persiste entre reconstrucciones de la imagen.
# Sin esta comprobación puede ocultar las dependencias del módulo nuevo.
if ! cmp -s package-lock.json node_modules/.cloudvault-package-lock.json; then
    npm ci --no-audit --no-fund
    cp package-lock.json node_modules/.cloudvault-package-lock.json
fi

exec "$@"
