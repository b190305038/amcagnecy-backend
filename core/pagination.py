from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Page-number pagination. Clients may override with ?page_size=, up to 500.
    Pass ?page_size=all (or a large number) to fetch a whole collection, which
    the localStorage-style frontend expects when it hydrates a table."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 500

    def get_page_size(self, request):
        raw = request.query_params.get(self.page_size_query_param)
        if raw == "all":
            return self.max_page_size
        return super().get_page_size(request)
