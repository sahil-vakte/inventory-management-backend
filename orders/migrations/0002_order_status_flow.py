# Generated for the order status workflow update.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_status_values(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    OrderStatusHistory = apps.get_model('orders', 'OrderStatusHistory')

    status_map = {
        'PENDING': 'NEW',
        'CONFIRMED': 'LABEL_PRINTED',
        'PROCESSING': 'IN_PROGRESS',
        'DELIVERED': 'COMPLETED',
        'ON_HOLD': 'NEW',
    }

    for old_status, new_status in status_map.items():
        Order.objects.filter(order_status=old_status).update(order_status=new_status)
        OrderStatusHistory.objects.filter(from_status=old_status).update(from_status=new_status)
        OrderStatusHistory.objects.filter(to_status=old_status).update(to_status=new_status)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='orderitem',
            name='product',
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='stock_fulfilled',
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='stock_reserved',
        ),
        migrations.AddField(
            model_name='order',
            name='assigned_to',
            field=models.ForeignKey(blank=True, help_text='Employee assigned to handle this order', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_orders', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='assigned_to',
            field=models.ForeignKey(blank=True, help_text='Employee assigned to pick/process this item', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_order_items', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='ebay_item_id',
            field=models.CharField(blank=True, help_text='eBay Item ID if order is from eBay', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='processing_status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('PICKED', 'Picked'), ('EXCEPTION', 'Exception'), ('COMPLETED', 'Completed')], default='PENDING', help_text='Current processing status of this item', max_length=20),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='quantity_ordered',
            field=models.PositiveIntegerField(default=1, help_text='Original quantity ordered'),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='quantity_processed',
            field=models.PositiveIntegerField(default=0, help_text='Quantity already picked/processed'),
        ),
        migrations.RunPython(forwards_status_values, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='order_source',
            field=models.CharField(choices=[('MANUAL', 'Manual Entry'), ('XML', 'XML Import'), ('EBAY', 'eBay'), ('API', 'API'), ('WEBSITE', 'Website')], default='MANUAL', help_text='Source of order', max_length=50),
        ),
        migrations.AlterField(
            model_name='order',
            name='order_status',
            field=models.CharField(choices=[('NEW', 'New'), ('LABEL_PRINTED', 'Label Printed'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('SHIPPED', 'Shipped'), ('CANCELLED', 'Cancelled')], default='NEW', max_length=20),
        ),
        migrations.AlterField(
            model_name='orderstatushistory',
            name='from_status',
            field=models.CharField(blank=True, choices=[('NEW', 'New'), ('LABEL_PRINTED', 'Label Printed'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('SHIPPED', 'Shipped'), ('CANCELLED', 'Cancelled')], max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='orderstatushistory',
            name='to_status',
            field=models.CharField(choices=[('NEW', 'New'), ('LABEL_PRINTED', 'Label Printed'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('SHIPPED', 'Shipped'), ('CANCELLED', 'Cancelled')], max_length=20),
        ),
    ]
