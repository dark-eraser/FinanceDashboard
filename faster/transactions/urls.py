from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path(
        "expenses-by-category/", views.expenses_by_category, name="expenses_by_category"
    ),
    path("income-by-category/", views.income_by_category, name="income_by_category"),
    path("expenses-vs-income/", views.expenses_vs_income, name="expenses_vs_income"),
    path("delete-file/<int:file_id>/", views.delete_file, name="delete_file"),
    # API endpoints
    path("api/transactions/", views.api_get_transactions, name="api_get_transactions"),
    path(
        "api/transactions/<int:transaction_id>/update-category/",
        views.api_update_category,
        name="api_update_category",
    ),
    path(
        "api/categories/create/", views.api_create_category, name="api_create_category"
    ),
]
