from django.db import migrations

SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


# Split "Garry S. Pangue Jr." into "Garry S." + "Pangue Jr."
def split_full_name(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():
        parts = user.full_name.split()
        last_count = 2 if len(parts) >= 3 and parts[-1].lower() in SUFFIXES else 1
        if len(parts) > last_count:
            user.first_name = " ".join(parts[:-last_count])
            user.last_name = " ".join(parts[-last_count:])
        else:
            user.first_name = " ".join(parts)
            user.last_name = ""
        user.save(update_fields=["first_name", "last_name"])


# Undo: join the names back together
def join_full_name(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():
        user.full_name = f"{user.first_name} {user.last_name}".strip()
        user.save(update_fields=["full_name"])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_profile_fields'),
    ]

    operations = [
        migrations.RunPython(split_full_name, join_full_name),
    ]
