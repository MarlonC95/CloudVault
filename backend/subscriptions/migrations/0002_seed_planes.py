from django.db import migrations

PLANES = [
    {
        "slug": "gratuito",
        "nombre": "Gratuito",
        "precio_mensual": 0,
        "precio_anual": 0,
        "almacenamiento_bytes": 16106127360,
        "es_popular": False,
        "caracteristicas": [
            "15 GB almacenamiento",
            "1 Usuario",
            "Cifrado estándar",
            "Soporte por comunidad",
        ],
    },
    {
        "slug": "pro",
        "nombre": "Pro PaaS",
        "precio_mensual": 29,
        "precio_anual": 278,
        "almacenamiento_bytes": 107374182400,
        "es_popular": True,
        "caracteristicas": [
            "100 GB almacenamiento",
            "Hasta 5 Usuarios",
            "Cifrado de extremo a extremo",
            "Versionado de archivos",
            "Soporte 24/7",
        ],
    },
    {
        "slug": "empresarial",
        "nombre": "Empresarial",
        "precio_mensual": 99,
        "precio_anual": 950,
        "almacenamiento_bytes": None,
        "es_popular": False,
        "caracteristicas": [
            "Almacenamiento ilimitado",
            "Usuarios ilimitados",
            "Logs de auditoría avanzada",
            "API dedicada",
            "SLA del 99.9%",
        ],
    },
]


def crear_planes(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    for datos in PLANES:
        slug = datos["slug"]
        valores = {clave: valor for clave, valor in datos.items() if clave != "slug"}
        Plan.objects.update_or_create(slug=slug, defaults=valores)


def eliminar_planes(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.filter(slug__in=[datos["slug"] for datos in PLANES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_planes, eliminar_planes),
    ]
