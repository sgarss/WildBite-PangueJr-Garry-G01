from django.contrib import admin
from django.shortcuts import redirect


class WildBiteAdminSite(admin.AdminSite):
    # Logged-in users without admin access go to their own dashboard
    def login(self, request, extra_context=None):
        if request.user.is_authenticated and not self.has_permission(request):
            return redirect('accounts:dashboard')
        return super().login(request, extra_context)
