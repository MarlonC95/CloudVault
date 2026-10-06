from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class EnvelopePagination(PageNumberPagination):
    """Paginación del contrato (§0.5): {"data": {count, next, previous, results}}."""

    page_size = 50

    def get_paginated_response(self, data):
        return Response({"data": {
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        }})
