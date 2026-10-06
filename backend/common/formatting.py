UNIDADES = ("B", "KB", "MB", "GB", "TB", "PB")


def bytes_legibles(valor):
    """Tamaño legible con punto decimal y base 1024 (contrato §0.6: "4.2 MB", "128 MB").

    No usar ``django.template.defaultfilters.filesizeformat``: con LANGUAGE_CODE="es-gt"
    devuelve coma decimal ("4,2 MB"), que rompe el formato del contrato.
    """
    tamano = float(valor)
    if tamano < 1024:
        return f"{int(tamano)} B"
    for unidad in UNIDADES[1:]:
        tamano /= 1024
        if round(tamano, 1) < 1024 or unidad == UNIDADES[-1]:
            texto = f"{tamano:.1f}".rstrip("0").rstrip(".")
            return f"{texto} {unidad}"
