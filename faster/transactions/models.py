from django.db import models


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

    def __str__(self):
        return f"{self.date} | {self.booking_text} | {self.category} | {self.amount}"
