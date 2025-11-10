from rest_framework.pagination import PageNumberPagination


class Pagination(PageNumberPagination):
    """
    Custom pagination class for student listings
    """
    page_size = 10
    page_size_query_param = 'size'
    max_page_size = 100
    page_query_param = 'page'
