from django.urls import path

from . import views

app_name = "compartir"
urlpatterns = [
    path("enlaces-compartidos/", views.EnlacesView.as_view(), name="enlaces"),
    path("enlaces-compartidos/<uuid:pk>/", views.EnlaceDetalleView.as_view(), name="enlace"),
    path("permisos-recurso/", views.PermisosView.as_view(), name="permisos"),
    path("permisos-recurso/<int:pk>/", views.PermisoDetalleView.as_view(), name="permiso"),
    path("compartidos-conmigo/", views.CompartidosView.as_view(), name="compartidos"),
    path("compartidos-conmigo/carpetas/<uuid:pk>/contenido/", views.ContenidoCompartidoView.as_view(),
         name="contenido-compartido"),
    path("archivos/<uuid:pk>/vista-previa/", views.VistaPreviaView.as_view(), name="vista-previa"),
    path("publico/<str:token>/", views.PublicoView.as_view(), name="publico"),
    path("publico/<str:token>/acceso/", views.AccesoPublicoView.as_view(), name="publico-acceso"),
    path("publico/<str:token>/contenido/", views.ContenidoPublicoView.as_view(), name="publico-contenido"),
    path("publico/<str:token>/archivos/<uuid:pk>/", views.ArchivoPublicoView.as_view(), name="publico-archivo"),
]
