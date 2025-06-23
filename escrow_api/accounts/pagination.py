from rest_framework.pagination import PageNumberPagination

class UserListPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_aize' # allows !page_size=<int>
    max_page_size = 50