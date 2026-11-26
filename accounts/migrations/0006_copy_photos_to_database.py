from django.conf import settings
from django.db import migrations
from django.utils import timezone

CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


# Move photos from the local media/ folder into the database (if the file is on this computer)
def copy_photos(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    ProfilePhoto = apps.get_model("accounts", "ProfilePhoto")
    media = settings.BASE_DIR / "media"

    for user in User.objects.exclude(profile_photo=""):
        path = media / user.profile_photo.name
        content_type = CONTENT_TYPES.get(path.suffix.lower())
        if content_type and path.is_file():
            now = timezone.now()
            ProfilePhoto.objects.create(
                user=user, image=path.read_bytes(), content_type=content_type, uploaded_at=now
            )
            user.photo_uploaded_at = now
            user.save(update_fields=["photo_uploaded_at"])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_profile_photos_table'),
    ]

    operations = [
        migrations.RunPython(copy_photos, migrations.RunPython.noop),
    ]
