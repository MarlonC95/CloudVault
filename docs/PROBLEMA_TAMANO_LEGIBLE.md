# Problema: `tamano_legible` salía con coma decimal ("4,2 MB")

## Qué pasaba
El contrato (`API_CONTRACTS.md` §0.6) define `tamano_legible` como texto con **punto** decimal: `"4.2 MB"`, `"128 MB"`, `"840 KB"`.
El endpoint de archivos devolvía `"4,2 MB"` y `"1,4 GB"` (coma).

## Causa
`FileMetadataSerializer.get_tamano_legible` usaba `django.template.defaultfilters.filesizeformat`.
Ese filtro **respeta el idioma activo** de Django. El proyecto está configurado con
`LANGUAGE_CODE = "es-gt"` y `USE_I18N = True` (`backend/cloudvault/settings.py`), así que el
separador decimal pasa a ser la coma. Ejemplo comprobado en el shell de Django:
`filesizeformat(4404019)` → `"4,2 MB"`.

No lo detectó ninguna prueba porque ninguna comparaba el texto exacto, y el contrato no se rompía
en estructura (el campo existía y era string), solo en formato.

## Por qué importa
- El frontend interpreta ese texto: `frontend/src/utils/filtrosArchivos.ts` (`parsearTamanoAMb` /
  `cumpleRangoTamano`) lo convierte a número para los filtros de tamaño (pequeño/mediano/grande).
  Con `"4,2"` la conversión puede dar un valor incorrecto o `NaN`, y el filtro fallaría en silencio.
- Es una desviación del contrato que el equipo de frontend no esperaba.
- El mismo riesgo aplicaba a cualquier texto numérico formateado con el locale (por ejemplo, otros listados).

## Corrección
- Nuevo `backend/common/formatting.py::bytes_legibles(valor)`: formato fijo, **independiente del idioma**,
  base 1024, una decimal máxima y sin ".0" sobrante (`4404019 → "4.2 MB"`, `128 MiB → "128 MB"`).
  Maneja el borde de redondeo (1023.99 MB se muestra como `1 GB`, no `1024 MB`).
- `storage/serializers.py` ahora usa esa función en lugar de `filesizeformat`.
- `subscriptions/services.py` reutiliza la misma función (antes tenía su propia copia equivalente),
  manteniendo `None → "Ilimitado"` para planes.

## Pruebas añadidas
- `common/tests.py::FormatoTamanoTests`: casos del contrato y sin coma.
- `storage/tests/test_tamano_legible.py`: el serializer devuelve `"4.2 MB"` para 4 404 019 bytes.

## Regla para el futuro
No usar `filesizeformat`, `floatformat`, `intcomma` ni formateo con `locale` en respuestas de API:
cambian con el idioma. Para textos de contrato, formatear manualmente (f-strings) o devolver el
valor crudo (`tamano_bytes`) y dejar que el cliente lo muestre.
