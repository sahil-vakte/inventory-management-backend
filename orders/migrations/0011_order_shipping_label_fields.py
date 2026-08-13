from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_order_batches'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='royal_mail_order_identifier',
            field=models.CharField(
                blank=True,
                help_text='Royal Mail Click & Drop order identifier used for label retrieval',
                max_length=120,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_label_file',
            field=models.CharField(
                blank=True,
                help_text='Stored printable carrier label file path under MEDIA_ROOT',
                max_length=500,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_label_downloaded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
