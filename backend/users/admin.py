from django.contrib import admin

from users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "full_name", "is_staff", "is_active", "date_joined"]
    search_fields = ["email", "full_name"]
    exclude = ["password"]
