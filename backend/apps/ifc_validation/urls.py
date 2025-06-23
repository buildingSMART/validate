from django.urls import path

from .views import ValidationRequestListAPIView, ValidationRequestDetailAPIView
from .views import ValidationTaskListAPIView, ValidationTaskDetailAPIView
from .views import ValidationOutcomeListAPIView, ValidationOutcomeDetailAPIView
from .views import ModelListAPIView, ModelDetailAPIView

urlpatterns = [
    path('validationrequest/',          ValidationRequestListAPIView.as_view()),
    path('validationrequest/<str:id>/', ValidationRequestDetailAPIView.as_view()),
    path('validationtask/',             ValidationTaskListAPIView.as_view()),
    path('validationtask/<str:id>/',    ValidationTaskDetailAPIView.as_view()),
    path('validationoutcome/',          ValidationOutcomeListAPIView.as_view()),
    path('validationoutcome/<str:id>/', ValidationOutcomeDetailAPIView.as_view()),
    path('model/',                      ModelListAPIView.as_view()),
    path('model/<str:id>/',             ModelDetailAPIView.as_view()),
]
