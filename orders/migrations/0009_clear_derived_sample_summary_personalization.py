from django.db import migrations


def clear_derived_sample_summary_personalization(apps, schema_editor):
    OrderItem = apps.get_model('orders', 'OrderItem')
    for item in OrderItem.objects.filter(is_sample=True).iterator():
        update_fields = []
        sample_name = item.sample_name or ''

        if item.summary and sample_name and item.summary == sample_name:
            item.summary = None
            update_fields.append('summary')

        if item.personalization and sample_name:
            derived_values = {
                f'Design: {sample_name}',
                f'Length: {sample_name}',
                f'Sample: {sample_name}',
                f'Sample Name: {sample_name}',
            }
            if item.personalization in derived_values:
                item.personalization = None
                update_fields.append('personalization')

        if update_fields:
            item.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_backfill_length_sample_order_items'),
    ]

    operations = [
        migrations.RunPython(clear_derived_sample_summary_personalization, migrations.RunPython.noop),
    ]
