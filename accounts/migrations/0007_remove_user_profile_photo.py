from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_copy_photos_to_database'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='profile_photo',
        ),
    ]
