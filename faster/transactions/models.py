from django.db import models


class DashboardSettings(models.Model):
    """Store dashboard-wide settings like excluded categories"""

    excluded_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="List of category names to exclude from dashboard calculations and displays",
    )

    class Meta:
        verbose_name_plural = "Dashboard Settings"

    def __str__(self):
        return (
            f"Dashboard Settings (Excluding {len(self.excluded_categories)} categories)"
        )

    @staticmethod
    def get_settings():
        """Get or create the dashboard settings"""
        settings, created = DashboardSettings.objects.get_or_create(pk=1)
        return settings

    @staticmethod
    def get_excluded_categories():
        """Get list of excluded categories"""
        settings = DashboardSettings.get_settings()
        return settings.excluded_categories or []


class UploadedFile(models.Model):
    name = models.CharField(max_length=256)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    uploaded_file = models.ForeignKey(
        UploadedFile, on_delete=models.CASCADE, related_name="transactions"
    )
    date = models.CharField(max_length=32, blank=True)
    booking_text = models.CharField(max_length=256, blank=True)
    category = models.CharField(max_length=64, blank=True)
    amount = models.FloatField(blank=True, null=True)
    currency = models.CharField(max_length=10, blank=True, default="")

    # Semantic categorization fields
    category_confidence = models.FloatField(
        blank=True,
        null=True,
        help_text="Confidence score for category prediction (0.0-1.0)",
    )
    is_manually_categorized = models.BooleanField(
        default=False, help_text="True if category was manually set by user"
    )
    predicted_category = models.CharField(
        max_length=64,
        blank=True,
        help_text="Original predicted category before manual correction",
    )

    def __str__(self):
        return f"{self.date} | {self.booking_text} | {self.category} | {self.amount} {self.currency}"
