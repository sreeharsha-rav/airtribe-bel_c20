from django.contrib import admin

from .models import Application, Company, Job

admin.site.register(Company)
admin.site.register(Job)
admin.site.register(Application)
