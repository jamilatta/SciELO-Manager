from django.contrib import admin
from scielomanager.maintenancewindow.models import *


class EventAdmin(admin.ModelAdmin):

    list_display = ('title', 'begin_at', 'end_at', 'is_blocking_users', 'is_finished')

    def save_model(self, request, obj, form, change):
        #import pdb; pdb.set_trace()
        if obj.is_blocking_users == True:
            Event.objects.set_blocking_users_events_to_false()
        obj.save()

admin.site.register(Event, EventAdmin)