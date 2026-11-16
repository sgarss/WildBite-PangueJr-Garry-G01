from django.contrib.admin.apps import AdminConfig


# Use the custom admin site
class WildBiteAdminConfig(AdminConfig):
    default_site = 'wildbite.admin_site.WildBiteAdminSite'
