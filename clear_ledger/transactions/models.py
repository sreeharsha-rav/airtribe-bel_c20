from django.db import models


class Category(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'name')
    

class Label(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='labels')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'name')
    
    
class Transaction(models.Model):
    CREDIT = 'credit'
    DEBIT = 'debit'
    
    TRANSACTION_TYPE_CHOICES = [
        (CREDIT, 'Credit'),
        (DEBIT, 'Debit')
    ]
    
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, related_name='transactions')
    category = models.ForeignKey('transactions.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=6, choices=TRANSACTION_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    labels = models.ManyToManyField('transactions.Label', through='transactions.TransactionLabel', related_name='transactions', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

class TransactionLabel(models.Model):
    transaction = models.ForeignKey('transactions.Transaction', on_delete=models.CASCADE, related_name='transaction_labels')
    label = models.ForeignKey('transactions.Label', on_delete=models.CASCADE, related_name='label_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('transaction', 'label')
