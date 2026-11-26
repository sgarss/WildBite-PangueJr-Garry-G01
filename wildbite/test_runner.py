from django.test.runner import DiscoverRunner


# Supabase's connection pooler won't let Django drop the test database,
# so keep it between runs (same as always passing --keepdb)
class SupabaseTestRunner(DiscoverRunner):
    def __init__(self, *args, **kwargs):
        kwargs["keepdb"] = True
        super().__init__(*args, **kwargs)
