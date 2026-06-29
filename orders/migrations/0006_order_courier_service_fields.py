from django.db import migrations, models


def normalize_courier_service_name(value):
    if value is None:
        return ''
    return ' '.join(str(value).strip().split())


def courier_service_code(value):
    name = normalize_courier_service_name(value)
    if not name:
        return ''

    key = name.lower()
    exact_map = {
        'standard delivery': 'STD',
        'super saver postage': 'STD',
        'international delivery': 'INT',
        'european delivery (5-7 days)': 'INT',
        'next day delivery (next working day if ordered before 1pm)': 'NEXT DAY',
        'next day by 12pm (next working day if ordered before 1pm)': 'NEXT DAY 12',
        'saturday delivery (on orders placed before 1pm)': 'SATURDAY',
        'collect in store': 'Collect in Store',
    }
    if key in exact_map:
        return exact_map[key]
    if 'collect in store' in key:
        return 'Collect in Store'
    if 'saturday delivery' in key:
        return 'SATURDAY'
    if 'next day by 12' in key or 'next day 12' in key:
        return 'NEXT DAY 12'
    if 'next day delivery' in key or key == 'next day':
        return 'NEXT DAY'
    if 'international delivery' in key or 'european delivery' in key:
        return 'INT'
    if 'standard delivery' in key or 'super saver postage' in key:
        return 'STD'
    return ''


def backfill_courier_fields(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for order in Order.objects.all().iterator():
        raw_name = order.courier_service_name or order.shipping_method or order.carrier
        service_name = normalize_courier_service_name(raw_name)
        service_code = courier_service_code(service_name)
        update_fields = []
        if service_name and not order.courier_service_name:
            order.courier_service_name = service_name
            update_fields.append('courier_service_name')
        if service_code and not order.courier_service_code:
            order.courier_service_code = service_code
            update_fields.append('courier_service_code')
        if update_fields:
            order.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_royal_mail_oauth_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='courier_service_name',
            field=models.CharField(blank=True, help_text='Raw courier/delivery service received from Tiaknight', max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='courier_service_code',
            field=models.CharField(blank=True, help_text='WIMS label/export code derived from courier service', max_length=50, null=True),
        ),
        migrations.RunPython(backfill_courier_fields, migrations.RunPython.noop),
    ]
