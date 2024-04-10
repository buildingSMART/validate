from django.urls import path

from .views_legacy import me, models_paginated, download, upload, delete, revalidate
from .views_legacy import report, report_error

urlpatterns = [

    # 'Flask'-way of doing things; backend for legacy API (< 0.6)
    path('api/me',                                              me),
    path('api/models_paginated/<int:start>/<int:end>',          models_paginated),
    path('api/download/<str:id>',                               download),
    path('api/',                                                upload),
    path('api/delete/<str:ids>',                                delete),
    path('api/revalidate/<str:ids>',                            revalidate),
    path('api/report/<str:id>',                                 report),
    path('api/report_error/<str:name>/<str:msg>/<str:stack>',   report_error),

    # vs

    # 'DRF'-way of doing things... (WIP)
    # path('api/upload/',                                         UploadAPIView.as_view(),   name="drf_upload"),            # ./bff/api/
]
