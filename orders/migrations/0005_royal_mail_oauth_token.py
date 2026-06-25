from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_orderitem_lable_printed'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoyalMailOAuthToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_token', models.TextField()),
                ('refresh_token', models.TextField(blank=True, null=True)),
                ('token_type', models.CharField(blank=True, max_length=50, null=True)),
                ('scope', models.TextField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('raw_response', models.JSONField(blank=True, default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Royal Mail OAuth Token',
                'verbose_name_plural': 'Royal Mail OAuth Tokens',
                'db_table': 'royal_mail_oauth_tokens',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='royalmailoauthtoken',
            index=models.Index(fields=['is_active', '-updated_at'], name='royal_mail_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='royalmailoauthtoken',
            index=models.Index(fields=['expires_at'], name='royal_mail_expires_at_idx'),
        ),
    ]
