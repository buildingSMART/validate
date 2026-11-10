from django.urls import path

from ..report.views import report_html, report_pdf
from . import views

app_name = "ui"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard", views.dashboard, name="dashboard"),
    path("allowlist", views.allowlist, name="allowlist"),
    path("scorecards", views.scorecards, name="scorecards"),
    path("waiting_zone", views.waiting_zone, name="waiting_zone"),
    path("login", views.login, name="login"),
    path("logout", views.logout, name="logout"),
    path("callback", views.callback, name="callback"),
    path("upload", views.upload, name="upload"),
    path("delete", views.delete, name="delete"),
    path("delete/<str:id>", views.delete, name="delete-file"),
    path("affiliation", views.affiliation, name="affiliation"),
    path("report_pdf/<str:id>", report_pdf, name="report-pdf"),
]

for segment, kind in (("file", "file"), ("syntax", "syntax"), ("schema", "schema"),
                      ("rules", "normative"), ("industry", "industry"), ("bsdd", "bsdd")):
    urlpatterns += [
        path(f"report_{segment}/<str:id>", report_html, {"kind": kind}, name=f"report-{segment}"),
    ]

urlpatterns.append(path("<path:path>", views.not_found, name="not-found"))
