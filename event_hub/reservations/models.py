from django.db import models

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]
    
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='reservations')
    attendee_name = models.CharField(max_length=200)
    attendee_email = models.EmailField()
    seats_reserved = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.attendee_name} - {self.event.title} - {self.seats_reserved} seats"
    
    class Meta:
        ordering = ['-created_at']
