from django.urls import path

from .views import ValidationRequestListAPIView, ValidationRequestDetailAPIView
from .views import ValidationTaskListAPIView, ValidationTaskDetailAPIView
from .views import ValidationOutcomeListAPIView, ValidationOutcomeDetailAPIView

urlpatterns = [
    path('validationrequest/',          ValidationRequestListAPIView.as_view()),
    path('validationrequest/<int:id>/', ValidationRequestDetailAPIView.as_view()),
    path('validationtask/',             ValidationTaskListAPIView.as_view()),
    path('validationtask/<int:id>/',    ValidationTaskDetailAPIView.as_view()),
    path('validationoutcome/',          ValidationOutcomeListAPIView.as_view()),
    path('validationoutcome/<int:id>/', ValidationOutcomeDetailAPIView.as_view()),
]
