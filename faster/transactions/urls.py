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
    path("monthly-budget/", views.monthly_budget, name="monthly_budget"),
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
    path("api/dashboard-data/", views.dashboard_data_ajax, name="dashboard_data_ajax"),
    path(
        "api/dashboard-monthly-data/",
        views.dashboard_monthly_data_ajax,
        name="dashboard_monthly_data_ajax",
    ),
    path(
        "api/expenses-by-category-data/",
        views.expenses_by_category_data_ajax,
        name="expenses_by_category_data_ajax",
    ),
    path(
        "api/expenses-vs-income-data/",
        views.expenses_vs_income_data_ajax,
        name="expenses_vs_income_data_ajax",
    ),
    path(
        "api/income-by-category-data/",
        views.income_by_category_data_ajax,
        name="income_by_category_data_ajax",
    ),
    # Semantic categorization endpoints
    path(
        "api/categorization/stats/",
        views.api_categorization_stats,
        name="api_categorization_stats",
    ),
    path(
        "api/categorization/recategorize/",
        views.api_recategorize_uncategorized,
        name="api_recategorize_uncategorized",
    ),
    path(
        "api/categorization/low-confidence/",
        views.api_low_confidence_transactions,
        name="api_low_confidence_transactions",
    ),
    path(
        "api/categorization/suggestions/",
        views.api_get_category_suggestions,
        name="api_get_category_suggestions",
    ),
    path(
        "api/excluded-categories/",
        views.api_update_excluded_categories,
        name="api_update_excluded_categories",
    ),
    path(
        "api/budget-comparison/",
        views.api_budget_comparison,
        name="api_budget_comparison",
    ),
]
