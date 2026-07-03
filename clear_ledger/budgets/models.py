from django.db import models


class Budget(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey('transactions.Category', on_delete=models.CASCADE, related_name='budgets')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    month = models.PositiveSmallIntegerField()  # 1-12 for January to December
    year = models.PositiveSmallIntegerField()  # e.g., 2024
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'category', 'month', 'year')
