from django.urls import re_path

from .views import ValidationRequestListAPIView, ValidationRequestDetailAPIView
from .views import ValidationTaskListAPIView, ValidationTaskDetailAPIView
from .views import ValidationOutcomeListAPIView, ValidationOutcomeDetailAPIView
from .views import ModelListAPIView, ModelDetailAPIView


urlpatterns = [

    # REST API
    # using re_path to make trailing slashes optional
    re_path(r'validationrequest/?$',                ValidationRequestListAPIView.as_view()),
    re_path(r'validationrequest/(?P<id>[\w-]+)/?$', ValidationRequestDetailAPIView.as_view()),
    re_path(r'validationtask/?$',                   ValidationTaskListAPIView.as_view()),
    re_path(r'validationtask/(?P<id>[\w-]+)/?$',    ValidationTaskDetailAPIView.as_view()),
    re_path(r'validationoutcome/?$',                ValidationOutcomeListAPIView.as_view()),
    re_path(r'validationoutcome/(?P<id>[\w-]+)/?$', ValidationOutcomeDetailAPIView.as_view()),
    re_path(r'model/?$',                            ModelListAPIView.as_view()),
    re_path(r'model/(?P<id>[\w-]+)/?$',             ModelDetailAPIView.as_view()),
]
