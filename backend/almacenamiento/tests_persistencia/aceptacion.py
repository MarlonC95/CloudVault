"""Matriz de fase 8 basada en IDs ejecutados; sin trazas ni datos privados.

APROBADO_LOCAL acredita exclusivamente el alcance declarado. Nunca transforma
un doble de negocio/S3 en integración real ni un diagnóstico de auth en regresión.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess


def pg(modulo, clase, metodo):
    return f"almacenamiento.tests_persistencia.test_{modulo}.{clase}.test_{metodo}"


def unidad(modulo, clase, metodo):
    return f"almacenamiento.tests.test_{modulo}.{clase}.test_{metodo}"


def inicio(metodo):
    return pg("inicio", "InicioPersistenteTests", metodo)


def confirmar(metodo):
    return pg("confirmacion", "ConfirmacionPersistenteTests", metodo)


def descargar(metodo):
    return pg("descarga", "DescargaPersistenteTests", metodo)


def mantener(metodo):
    return pg("mantenimiento", "MantenimientoPersistenteTests", metodo)


def http(metodo):
    return pg("aceptacion", "AceptacionHTTPTests", metodo)


# ID, caso, estado inicial/request y acción, HTTP, SQL, S3, cuota final, tests.
# Expectativas explícitas: el informe agrega los resultados reales de cada ID.
MATRIZ = [
    ("A01", "Inicio válido", "Ámbito vigente Q=100/U=80; JSON de 5 bytes; iniciar", "201", "PENDING + auditoría; sin archivo", "Firma local, sin transferencia", "U=80/R=5", [inicio("respuesta_durable_sesion_auditoria_y_sin_archivo_ni_consumo"), inicio("endpoint_201_con_postgresql_y_firma_offline")]),
    ("A02", "JWT ausente/expirado/manipulado", "Solicitar las rutas sin JWT o con JWT inválido", "401", "Sin reserva/registro", "Sin URL/cliente", "Sin variación", [unidad("inicio_http", "InicioHTTPTests", "sin_jwt_no_llama_dependencias"), unidad("inicio_http", "InicioHTTPTests", "jwt_invalido_no_llama_dependencias"), unidad("descarga", "DescargaHTTPTests", "jwt_ausente_invalido_y_vencido_no_llaman_dependencias")]),
    ("A03", "Lector intenta cargar", "Miembros 0/1/2/3 en SQL; rol 1 inicia", "403", "Sin sesión del lector", "Sin objeto", "R=15 de otros roles", [http("roles_cero_dos_tres_permitidos_y_lector_sin_efectos")]),
    ("A04", "Propietario rol 0", "Rol 0 inicia junto con roles 2/3", "201", "Una sesión por actor autorizado", "Sin objeto", "U=0/R=15", [http("roles_cero_dos_tres_permitidos_y_lector_sin_efectos")]),
    ("A05", "Carpeta de otra organización", "Iniciar con carpeta ajena y UUID inexistente", "403 idéntico", "Sin filas/auditoría", "Sin objeto", "U=0/R=0", [http("carpeta_ajena_y_desconocida_mismo_rechazo")]),
    ("A06", "Contexto ambiguo/personal", "Raíz con dos membresías o ninguna", "400/403", "Sin sesión", "Sin objeto", "U=0/R=0", [http("raiz_ambigua_y_personal_sin_ambito_no_reservan")]),
    ("A07", "Nombre/MIME inválidos", "JSON con vacío/largo/CRLF/MIME inválido", "400", "Sin sesión/auditoría", "Sin objeto", "U=0/R=0", [http("entradas_invalidas_http_no_dejan_filas")]),
    ("A08", "Bytes estrictos/campos extras", "JSON con negativo/fracción/bool/string/extra", "400", "Sin filas", "Sin objeto", "U=0/R=0", [http("entradas_invalidas_http_no_dejan_filas")]),
    ("A09", "Cero bytes", "Q=20/R=20; iniciar vacío; luego U>Q o ámbito inactivo", "201/409/503", "Solo dos sesiones aceptadas", "Sin objeto", "R=20; sin incremento de U", [http("cero_bytes_en_cuota_exacta_y_ambito_bloqueado"), confirmar("archivo_vacio_hash_correcto_consumo_cero")]),
    ("A10", "Límite operativo", "Configurar máximo 10; iniciar 10 y 11", "201/400", "Una sesión de 10", "Sin objeto; no subir archivos grandes", "U=0/R=10", [http("limite_operativo_exacto_http_y_un_byte_superior")]),
    ("A11", "Cuota exacta/exceso", "U=80/R=15/Q=100; iniciar 5 luego 1", "201/409", "Dos sesiones totales", "Sin objeto", "U=80/R=20", [inicio("limite_exacto_y_exceso_no_firma")]),
    ("A12", "Competencia por último espacio", "Dos conexiones sincronizadas; U=80/Q=100; reservar 15 cada una", "201 + 409", "Una sesión/evento", "Sin objeto", "U=80/R=15<=Q", [inicio("dos_conexiones_no_reservan_el_mismo_ultimo_espacio")]),
    ("A13", "Cuota compartida", "Dos actores reservan 15+5; otra org reserva 20", "201/409", "Reservas por organización", "Sin objeto", "R=20 en cada org; U=0", [http("varios_actores_comparten_reserva_y_otra_org_independiente")]),
    ("A14", "Plan no utilizable", "Eliminar/vencer/desactivar/duplicar suscripciones y comenzar", "503", "Sin sesión", "Sin objeto", "U=0/R=0", [http("planes_ausente_vencido_inactivo_duplicado_rechazados")]),
    ("A15", "Cambio de plan bajo lock", "Otra conexión baja Q mientras inicio espera; bajar Q tras COPY", "409", "Sin publicación indebida", "Final conservado para reconciliación", "Cuota actual, sin consumo", [inicio("downgrade_bloqueado_se_lee_despues_del_cambio"), confirmar("downgrade_despues_copy_no_publica")]),
    ("A16", "Respuesta de inicio perdida", "Dos inicios aceptados tras simular pérdida de respuesta", "201 cada uno", "UUID y eventos distintos", "Firmas locales distintas", "U=80/R=10", [inicio("respuesta_perdida_y_reintento_no_prometen_idempotencia")]),
    ("A17", "Header de idempotencia no definido", "Repetir header idéntico sin exigir extensión del PDF", "201/201", "Dos UUID; sin deduplicación prometida", "Sin objeto", "U=0/R=10", [http("header_idempotencia_no_deduplica_ni_se_exige")]),
    ("B01", "PUT directo real", "Firmar y transferir bytes desde cliente al proveedor", "PUT 2xx", "Django no recibe binario", "Objeto real íntegro", "No aplicable al ensayo S3", []),
    ("B02", "Firma alterada/vencida", "PUT/GET vencidos, host/header firmado alterados", "Proveedor 401/403", "Sin publicación", "Rechazo real", "Sin consumo", []),
    ("B03", "PUT mayor a reserva", "Reserva 5; objeto de 6; confirmar y vencer para limpiar", "400", "CANCELED; sin archivo", "Sin COPY; temporal eliminado", "U=0/R=0", [http("put_mayor_rechazado_y_temporal_limpiado")]),
    ("B04", "CORS en navegador", "Preflight y fetch PUT/GET desde origen de prueba", "OPTIONS/PUT/GET 2xx", "Sin binario en Django", "Bytes/ETag accesibles al navegador", "No aplicable al ensayo", []),
    ("B05", "Capacidades reales S3", "COPY, hash y sondas checksum/precondición", "Capacidades registradas", "No asumir versionado/condiciones", "Final real verificado", "No aplicable al ensayo", []),
    ("C01", "Confirmación correcta", "PENDING + objeto de 5; confirmar", "200", "Un archivo/CONFIRMED/PUBLISHED/evento", "Una copia final/hash/tipo seguro", "U=85/R=0", [confirmar("confirmacion_durable_id_hash_mime_evento_y_incremento_unico"), http("recorrido_http_completo_y_limpieza_conserva_final")]),
    ("C02", "PUT ausente/incompleto", "Confirmar sin temporal y con contenido truncado", "404/400 o reintento", "Sin metadatos falsos", "Sin final publicado", "Sin consumo", [confirmar("temporal_ausente_reintentable_sin_ledger"), confirmar("final_corto_detectado_por_hash_cancela")]),
    ("C03", "Tamaño/hash incoherentes", "Temporal excedido o final corto; pista ETag errónea", "400", "Sin archivo; cancelación cuando corresponde", "No publica bytes no verificados", "Libera reserva cancelada", [confirmar("tamano_temporal_incorrecto_cancela_y_libera_una_vez"), confirmar("final_corto_detectado_por_hash_cancela"), confirmar("etag_pista_incorrecta_rechaza_sin_cancelar_o_copiar")]),
    ("C04", "MIME engañoso", "Declarar text/html; publicar y descargar como adjunto", "200", "application/octet-stream", "Final con tipo seguro", "U=5/R=0", [http("recorrido_http_completo_y_limpieza_conserva_final"), confirmar("final_mime_no_seguro_no_publica")]),
    ("C05", "Confirmación repetida/concurrente", "Dos conexiones durante COPY; repetir tras commit", "200/503 reintentable", "Una fila/uso/evento", "Una sola copia", "U=85/R=0", [confirmar("dos_confirmaciones_un_publicador_y_respuesta_recuperable"), confirmar("repetir_en_otro_servicio_sin_s3_copia_evento_o_consumo_extra")]),
    ("C06", "Reutilizar temporal tras confirmar", "Sobrescribir temporal tras publicación y repetir", "200 mismo resultado", "Sin segundo archivo/uso", "Final conserva bytes verificados", "U=85/R=0", [confirmar("origen_cambia_durante_copy_hash_del_final_recibido")]),
    ("C07", "Cambio durante publicación", "Cambiar temporal durante COPY y final durante hash", "200 verificado o rechazo", "Sin resultado inconsistente", "Hash del final recibido; rechazo de cambio detectado", "Sin doble consumo", [confirmar("origen_cambia_durante_copy_hash_del_final_recibido"), confirmar("final_cambia_durante_verificacion_rechazo_sin_exito")]),
    ("C08", "Permiso/destino revocado", "Revocar después de hash o cambiar destino bajo cuota", "403/rechazo", "Sin publicación", "Final en reconciliación si COPY concluyó", "Sin consumo", [confirmar("revocacion_despues_verificar_y_en_reintento_confirmado"), inicio("destino_cambia_bajo_bloqueo_y_no_reserva")]),
    ("C09", "Autoridad de consumo", "Proveedor sin trigger; luego trigger SQL real de ensayo; simular autoridad doble", "200/rechazo 500 seguro", "Un incremento; doble ajuste revierte", "Final recuperable; no compensar borrando", "U=5; segunda reserva R=5 tras rollback", [http("recorrido_http_completo_y_limpieza_conserva_final"), http("trigger_sql_consumo_unico_y_doble_autoridad_revierte")]),
    ("C10", "COPY + fallo SQL/auditoría", "Inyectar fallo tras copia y reintentar", "Sin éxito inicial; recuperación", "Rollback; PREPARED durable; archivo único al recuperar", "Final preservado; sin recopy", "U=80 luego 85", [confirmar("registro_sql_fallido_revierte_y_recupera_final_sin_copy"), confirmar("auditoria_fallida_revierte_metadatos_consumo_y_sesion")]),
    ("C11", "Commit + respuesta perdida", "Confirmar y descartar respuesta; otro servicio repite", "200 mismo resultado", "Mismo ID/fila/evento", "Sin nueva COPY/DELETE", "U=85 una vez", [confirmar("repetir_en_otro_servicio_sin_s3_copia_evento_o_consumo_extra")]),
    ("C12", "Reinicio con PREPARED", "Ledger durable; proceso Python nuevo lee; recupera final", "200 sin recopy", "PENDING/PREPARED visibles entre procesos; PUBLISHED final", "Final de ensayo conservado", "U=5/R=0", [http("prepared_durable_visible_en_otro_proceso_y_recuperable"), mantener("prepared_antiguo_y_head_ausente_no_prueban_copy_finalizado")]),
    ("D01", "Descarga autorizada íntegra", "Publicación verificada; GET HTTP local de cinco bytes", "200", "Auditoría de emisión; sin nuevo uso", "Bytes/hash finales idénticos", "Sin variación", [descargar("get_real_local_bytes_del_final_anonimo_y_vencido_denegados")]),
    ("D02", "Descarga ajena/pendiente/papelera", "Consultar otro ámbito, papelera y ledger no publicado", "404/rechazo", "Sin emisión válida", "Sin nueva URL", "U=5/R=0 sin variación", [http("descarga_ajena_y_papelera_sin_url_ni_consumo_extra"), descargar("estado_no_confirmado_y_ledger_no_publicado_no_firman")]),
    ("D03", "GET anónimo/vencido", "GET local sin capability/vencido", "403", "Sin ajuste", "Rechazo del servidor HTTP de ensayo", "Sin variación", [descargar("get_real_local_bytes_del_final_anonimo_y_vencido_denegados")]),
    ("D04", "Unicode/CRLF", "Firmar nombre Unicode; rechazar controles/rutas", "Firma válida o 400", "No normalizar nombre inseguro silenciosamente", "attachment seguro", "Sin variación", [unidad("descarga", "FirmaDescargaTests", "nombre_unicode_comillas_punto_y_coma_percent_encoded"), unidad("descarga", "FirmaDescargaTests", "rechaza_controles_paths_surrogates_y_temporales")]),
    ("D05", "Final ausente", "Borrar final del doble; solicitar descarga", "503", "Inconsistencia auditada", "Sin URL", "Sin nuevo uso", [descargar("objeto_perdido_registra_inconsistencia_sin_firmar")]),
    ("E01", "Cancelación/vencimiento repetidos", "Cancelar dos veces; ejecutar vencimiento", "Interno; no ruta pública", "Transición/evento únicos", "Sin borrar bajo URL vigente; limpia tras margen", "U=80/R=0", [mantener("cancelar_libera_una_vez_sin_borrar_bajo_url_vigente"), mantener("vencimiento_y_borrado_sin_ledger_recuperables")]),
    ("E02", "Cancelar vs confirmar", "Conexiones independientes y pausa explícita", "Un desenlace; rival reintenta/rechaza", "Sin CONFIRMED y CANCELED simultáneos", "No elimina final confirmado", "Sin doble ajuste", [mantener("confirmacion_activa_excluye_limpieza_y_cancelacion"), mantener("cancelacion_activa_impide_confirmacion_concurrente")]),
    ("E03", "Limpiar vs confirmar/referencias", "Competir durante COPY; referencia incluso papelera", "Trabajo pendiente/rechazo seguro", "Referencias protegidas", "No elimina final referenciado", "Sin descuento", [mantener("confirmacion_activa_excluye_limpieza_y_cancelacion"), mantener("final_fallido_con_referencia_en_papelera_no_se_borra")]),
    ("E04", "PUT tardío", "Recrear temporal tras VERIFIED; nuevo barrido", "Comando interno", "Tombstone durable; verificación posterior", "Reaparición eliminada", "Sin cambio de U", [mantener("put_tardio_reaparece_y_tombstone_programa_otro_barrido")]),
    ("E05", "Worker/scheduler ausentes", "Interrumpir worker; proveedor ausente; luego reconstruir", "Reintento durable", "Pendiente recuperable; reserva vencida no cuenta", "Sin borrado por falta de evidencia", "Reserva correcta con scheduler retrasado", [mantener("caida_worker_despues_delete_deja_trabajo_durable"), mantener("reserva_vencida_no_cuenta_con_scheduler_retrasado"), mantener("trabajo_reconstruido_sin_entrega_a_cola")]),
    ("E06", "Entrega duplicada", "Dos workers reales; clave técnica ajena", "Un claim; trabajo diferido", "Sin doble transición/consumo", "Sin borrar publicación ni UUID ajeno", "Sin descuento", [mantener("dos_workers_comparten_reclamo_y_no_borran_publicacion"), mantener("no_borrar_claves_ajenas_o_publicacion_de_otro_uuid")]),
    ("F01", "Errores sin secretos", "Inyectar fallo privado SDK/DB y JSON inválido", "Formato/código esperado", "Rollback cuando aplica", "Sin URL/credenciales en respuesta/log", "Sin efecto parcial", [unidad("inicio_http", "InicioHTTPTests", "error_interno_no_imprime_datos_privados"), unidad("descarga", "DescargaHTTPTests", "error_privado_no_sale_en_respuesta_o_logs"), inicio("auditoria_obligatoria_fallida_revierte_reserva")]),
    ("F02", "Límite entre instancias", "Servicios/conexiones independientes comparten contador", "429 y Retry-After", "Solo emisión aceptada cuenta", "Una sola firma aceptada", "Sin cuota adicional", [inicio("limite_persistente_429_en_otro_servicio"), descargar("dos_conexiones_comparten_limite_una_firma_y_un_429"), descargar("endpoint_http_200_429_y_retry_after")]),
    ("F03", "Regresión funcional de auth", "Ejecutar rutas reales contra SQL literal; diagnosticar mapping", "Registro 201/login y recuperación 200 requeridos", "Identidad/hashes/eventos válidos requeridos", "No aplica", "No aplica", [pg("aceptacion", "CompatibilidadAuthTests", "mapping_fecha_de_auth_no_existe_en_referencia_literal"), pg("aceptacion", "CompatibilidadAuthTests", "registro_login_recuperacion_reproducen_bloqueo_sin_secretos")]),
    ("F04", "Reconstrucción/reinicio", "Controlador instala SQL literal; reinicia PostgreSQL y comprueba fila durable", "No aplica al reinicio DB", "Fila sobrevive restart; clúster privado eliminado al final", "Persistencia S3 exige perfil real separado", "Sin datos de aplicación", [http("prepared_durable_visible_en_otro_proceso_y_recuperable")]),
]

LIMITES = {
    "B01": "Transferencia real requiere ensayo S3 separado; esta suite nunca conecta al bucket.",
    "B02": "Rechazo real de firmas/host/headers requiere proveedor real; no lo demuestra una firma offline.",
    "B04": "CORS exige navegador y bucket reales; el preflight unitario no basta.",
    "B05": "Capacidades del bucket requieren ensayo real fechado, independiente de dobles.",
    "C03": "El PDF no aporta checksum esperado del cliente: hash acredita bytes recibidos, no el original pretendido.",
    "C09": "Trigger exclusivo del clúster desechable; mecanismo compartido pendiente de Marlon/German.",
    "D01": "HTTP local real; autorización del servidor de ensayo sustituye SigV4 del proveedor.",
    "D03": "Rechazo HTTP local; no equivale a rechazo Railway.",
    "F03": "BLOQUEADO: auth usa usuarios.fecha_creacion y el SQL literal define creado_en; las tres rutas devuelven 500 seguro. Responsable: autenticación/Marlon.",
    "F04": "Reinicio real de PostgreSQL propio; persistencia/reinicio de S3 y despliegue pendientes.",
}


def metadatos(repo):
    import django
    repo = Path(repo)
    archivos = list((repo / "backend/almacenamiento").rglob("*.py"))
    archivos += list((repo / "backend/almacenamiento/sql").glob("*.sql"))
    referencias = [repo / "agente/referencias/esquema-vigente.sql", repo / "agente/referencias/contrato-api-vigente.pdf"]
    # Los documentos personales no son dependencias del ejecutor funcional.
    archivos += [p for p in referencias if p.is_file()]
    hashes = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(archivos)}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, env={"GIT_OPTIONAL_LOCKS": "0"},
                            check=True, capture_output=True, text=True).stdout.strip()
    return {"fecha_utc": datetime.now(timezone.utc).isoformat(), "commit_base": commit,
            "codigo": "Archivos de trabajo identificados por SHA256; no se efectuó commit.",
            "hashes": hashes, "referencias_locales_ausentes": [str(p.relative_to(repo)) for p in referencias if not p.is_file()],
            "python": platform.python_version(), "django": django.get_version(),
            "proveedor": "S3/negocio sintéticos; firmas SDK offline; HTTP local de ensayo",
            "base": "PostgreSQL privado en socket Unix, sin TCP/.env/DB compartida"}


def crear_informe(resultados, contexto, *, salida, limpio):
    # Lista blanca: jamás serializar excepción, motivo del skip, request o URL.
    pruebas = [{"id": r["id"], "estado": r["estado"], "segundos": round(r["segundos"], 4)} for r in resultados]
    indice = {p["id"]: p for p in pruebas}
    casos = []
    for codigo, caso, accion, esperado_http, sql, s3, cuota, requeridos in MATRIZ:
        evidencia = [indice.get(t, {"id": t, "estado": "NO_EJECUTADO"}) for t in requeridos]
        estados = {p["estado"] for p in evidencia}
        estado = "APROBADO_LOCAL" if evidencia and estados == {"APROBADO"} else "BLOQUEADO"
        if "FALLIDO" in estados:
            estado = "FALLIDO"
        if codigo == "F03" and estado != "FALLIDO":
            estado = "BLOQUEADO"
        if codigo == "F04" and contexto.get("reinicio_postgresql_verificado") is not True:
            estado = "BLOQUEADO"
        casos.append({"id": codigo, "caso": caso, "estado_local": estado,
            "integracion_equipo": "BLOQUEADO", "estado_inicial_request_accion": accion,
            "http_esperado": esperado_http, "sql_esperado": sql, "s3_esperado": s3,
            "cuota_final_esperada": cuota, "pruebas_ejecutadas": evidencia,
            "limite": LIMITES.get(codigo, "Proveedor de negocio/S3 y JWT autorizado sustituidos; no certifica integración del equipo.")})
    conteo = Counter(p["estado"] for p in pruebas)
    requeridos = {t for fila in MATRIZ for t in fila[-1]}
    conservacion = contexto.get("temporales_conservados_por_instruccion") is True
    aprobado = (bool(pruebas) and salida == 0 and (limpio or conservacion) and conteo["APROBADO"] == len(pruebas)
                and requeridos.issubset(indice) and len(indice) == len(pruebas))
    return {"version": 1, "ambiente": contexto, "ejecucion_local_aprobada": aprobado,
            "integracion_completa_certificada": False, "salida_suite": salida,
            "cluster_temporal_eliminado": limpio, "conteo_pruebas": dict(conteo),
            "temporales_conservados_por_instruccion": conservacion,
            "conteo_matriz_local": dict(Counter(c["estado_local"] for c in casos)),
            "matriz": casos, "pruebas": pruebas,
            "dependencias": ["German: proveedor real de permisos/destino/cuota/metadatos/referencias y protocolo de locks.",
                "Marlon: instalación SQL técnico, grants y autoridad real de uso.",
                "Autenticación/Marlon: compatibilidad de fecha_creacion/creado_en antes de regresión funcional.",
                "Mily/equipo: flujo real de navegador e integración; despliegue/reinicio del perfil real."]}


def guardar_informe(ruta, informe):
    Path(ruta).write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n")


def combinar_minio(sql, s3, controlador):
    """Solo resultados frescos de hijos del controlador local, no Railway.

    La limpieza y salidas verificadas son necesarias; nunca certificar equipo.
    Cada capacidad tiene sus indicadores requeridos, no basta un exit cero.
    """
    informe = json.loads(json.dumps(sql))
    listo = (s3.get("perfil") == "minio" and sql.get("ejecucion_local_aprobada") is True
        and controlador.get("salida_sql_s3") == controlador.get("salida_s3") == 0
        and controlador.get("contenedor_eliminado") is True and controlador.get("datos_minio_eliminados") is True
        and s3.get("objetos_propios_limpiados") is True)
    requisitos = {"B01": ("put_firmado", "head_tamano_mime", "hash_contenido"),
        "B02": ("put_header_alterado_denegado", "get_firma_alterada_denegado", "get_host_alterado_rechazado", "get_expirado_denegado", "put_expirado_denegado"),
        "B04": (), "B05": ("copia_bytes_exactos", "hash_contenido"),
        "D03": ("get_anonimo_denegado", "get_expirado_denegado")}
    for caso in informe["matriz"]:
        caso["estado_fase8"] = caso["estado_local"]
        codigo = caso["id"]
        if codigo in requisitos:
            aprobado = listo and all(s3.get(k) is True for k in requisitos[codigo])
            if codigo == "B04":
                aprobado = (aprobado and s3.get("preflight", {}).get("aprobado") is True
                    and all(s3.get("navegador", {}).get(k) is True for k in ("put", "get", "bytes", "etag")))
            if aprobado:
                caso["estado_fase8"] = "APROBADO_S3_LOCAL"
                caso["evidencia_s3"] = "resultado-fase-08-minio-s3.json"
                caso["limite"] = "MinIO local real; no certifica Railway ni APIs de negocio del equipo."
        if codigo == "F04":
            caso["estado_fase8"] = ("APROBADO_REINICIO_LOCAL" if listo
                and controlador.get("reinicio_minio_hash_verificado") is True
                and sql["ambiente"].get("reinicio_postgresql_verificado") is True else "BLOQUEADO")
        if listo and codigo in ("C01", "C04", "C05", "C06", "C10", "D01", "E03"):
            metodo = ("copy_real_sql_fallido_recupera_sin_recopiar" if codigo == "C10"
                      else "flujo_http_put_copy_hash_descarga_y_limpieza_reales")
            prueba = next((p for p in sql["pruebas"] if p["id"] ==
                f"almacenamiento.tests_persistencia.minio_real.MinioRealTests.test_{metodo}"), None)
            if prueba and prueba["estado"] == "APROBADO":
                caso["pruebas_ejecutadas"].append(prueba)
                caso["evidencia_s3"] = "resultado-fase-08-minio-sql.json"
                caso["limite"] += " También ejecutado con PostgreSQL/MinIO reales; negocio/JWT autorizado continúan sustituidos."
    informe["conteo_matriz_fase8"] = dict(Counter(c["estado_fase8"] for c in informe["matriz"]))
    informe["evidencia_controlador"] = controlador
    informe["estado_fase8"] = "IMPLEMENTADA_LOCALMENTE_CON_BLOQUEOS_DE_INTEGRACION"
    informe["integracion_completa_certificada"] = False
    return informe


def combinar_railway(local, s3, entorno, auth):
    """Consolida perfiles ejecutados separados; conserva límites de cada uno."""
    informe = json.loads(json.dumps(local))
    listo = (s3.get("perfil") == "railway" and s3.get("operaciones_aprobadas") is True
             and entorno.get("env_sin_cambios") is True)
    capacidades = {
        "B01": ("put_firmado", "head_tamano_mime", "hash_contenido"),
        "B02": ("put_header_alterado_denegado", "get_firma_alterada_denegado", "get_host_alterado_rechazado", "get_expirado_denegado", "put_expirado_denegado"),
        "B04": (), "B05": ("copia_bytes_exactos", "hash_contenido"),
        "D03": ("get_anonimo_denegado", "get_expirado_denegado"),
    }
    for caso in informe["matriz"]:
        codigo = caso["id"]
        caso["estado_fase8"] = caso["estado_local"]
        if codigo in capacidades:
            aprobado = listo and all(s3.get(k) is True for k in capacidades[codigo])
            if codigo == "B04":
                aprobado = (aprobado and s3.get("preflight", {}).get("aprobado") is True
                    and all(s3.get("navegador", {}).get(k) is True for k in ("put","get","bytes","etag")))
            caso["estado_fase8"] = "APROBADO_RAILWAY" if aprobado else "BLOQUEADO"
            caso["evidencia_s3"] = "resultado-fase-08-reinicio-railway.json"
            caso["limite"] = "Cliente/bucket Railway reales; no acredita las APIs de negocio/JWT/cuota del equipo. Host alterado produjo rechazo de ruta, no prueba del mecanismo interno de firma."
        if codigo == "F03":
            aprobado = (auth.get("regresion_auth_aprobada") is True
                and auth.get("ambiente", {}).get("perfil") == "AUTH_COMPAT_FECHA_OBSERVADA")
            caso["estado_fase8"] = "APROBADO_AUTH_COMPAT_LOCAL" if aprobado else "BLOQUEADO"
            caso["evidencia_auth"] = "resultado-fase-08-reinicio-auth.json"
            caso["limite"] = "Regresión existente ejecutada en DB privada con mapping de fecha observado. El SQL literal de referencia continúa incompatible; no se modificó auth ni DB compartida."
        if codigo == "F04":
            caso["estado_fase8"] = "BLOQUEADO"
            caso["limite"] = "Reinicio PostgreSQL privado aprobado; no se reinició Railway ni se certificó reconstrucción/despliegue real."
    informe["conteo_matriz_fase8"] = dict(Counter(c["estado_fase8"] for c in informe["matriz"]))
    informe["estado_fase8"] = "IMPLEMENTADA_Y_PROBADA_CON_INTEGRACION_PENDIENTE"
    informe["railway_s3_operaciones_aprobadas"] = listo
    informe["sql_real_solo_lectura_conectado"] = entorno.get("sql_conectado") is True
    informe["env_sin_cambios"] = entorno.get("env_sin_cambios") is True
    informe["objetos_conservados_por_instruccion"] = s3.get("objetos_conservados_por_instruccion") is True
    informe["capacidades_railway"] = {k: s3.get(k) for k in ("copia_condicional_rechaza_etag_distinto", "checksum_sha256_retornado", "version_devuelta")}
    informe["entorno_real"] = entorno
    informe["integracion_completa_certificada"] = False
    return informe
