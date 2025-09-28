from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("analytics/", views.analytics_dashboard, name="analytics_dashboard"),
    path(
        "expenses-by-category/", views.expenses_by_category, name="expenses_by_category"
    ),
]
