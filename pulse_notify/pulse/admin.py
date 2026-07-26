from django.contrib import admin
from .models import User, PriceAlert, NotificationLog


admin.site.register(User)
admin.site.register(PriceAlert)
admin.site.register(NotificationLog)
