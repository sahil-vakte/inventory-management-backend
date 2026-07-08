import re
from django.db import migrations, models


SAMPLE_TEXT_PATTERN = re.compile(
    r'\((?P<label>design|sample(?:\s+name)?|personalisation|personalization)\s*:\s*(?P<value>[^)]*sample[^)]*)\)',
    re.IGNORECASE,
)
LENGTH_SAMPLE_PATTERN = re.compile(
    r'length\s*:\s*(?P<value>sample\s*\([^)]*\)|sample\b[^,;]*)',
    re.IGNORECASE,
)


def backfill_length_sample_metadata(apps, schema_editor):
    OrderItem = apps.get_model('orders', 'OrderItem')
    sample_candidates = OrderItem.objects.filter(
        models.Q(product_name__icontains='sample') | models.Q(sku__istartswith='SAMPLE-')
    )
    for item in sample_candidates.iterator():
        source_text = ' '.join(filter(None, [item.sku, item.product_name]))
        match = SAMPLE_TEXT_PATTERN.search(source_text)
        length_match = LENGTH_SAMPLE_PATTERN.search(source_text)
        sku_is_sample = str(item.sku or '').upper().startswith('SAMPLE-')
        if (
            not match
            and not length_match
            and not sku_is_sample
            and 'sample request' not in source_text.lower()
            and 'length: sample' not in source_text.lower()
        ):
            continue

        update_fields = []
        if match:
            label = match.group('label').strip()
            value = match.group('value').strip()
            if not item.sample_name:
                item.sample_name = value
                update_fields.append('sample_name')
            if not item.personalization:
                item.personalization = f"{label.title()}: {value}"
                update_fields.append('personalization')
            if not item.summary:
                item.summary = value
                update_fields.append('summary')
        if length_match:
            value = ' '.join(length_match.group('value').strip().split())
            if not item.sample_name:
                item.sample_name = value
                update_fields.append('sample_name')
            if not item.personalization:
                item.personalization = f"Length: {value}"
                update_fields.append('personalization')
            if not item.summary:
                item.summary = value
                update_fields.append('summary')
        if sku_is_sample and not item.sample_name:
            item.sample_name = 'Sample'
            update_fields.append('sample_name')
            if not item.summary:
                item.summary = 'Sample'
                update_fields.append('summary')
        if not item.is_sample:
            item.is_sample = True
            update_fields.append('is_sample')

        if update_fields:
            item.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_tiaknight_sample_time_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_length_sample_metadata, migrations.RunPython.noop),
    ]
