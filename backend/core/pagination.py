from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

class MetadataLimitOffsetPagination(LimitOffsetPagination):
    max_limit = 500
    limit_query_param = "limit"
    offset_query_param = "offset"

    def get_paginated_response(self, data):
        limit = self.get_limit(self.request)
        offset = self.get_offset(self.request)
        total = getattr(self, 'count', None)

        page_count = len(data)  

        return Response({
            "metadata": {
                "result_set": {
                    "count": page_count,       
                    "offset": offset or 0,
                    "limit": limit if limit is not None else self.default_limit,
                    "total": total
                }
            },
            "results": data
        })
