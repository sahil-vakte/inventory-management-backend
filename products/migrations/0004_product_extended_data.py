# Generated for safe product CSV backup/extended data support.

import django.db.models.deletion
from django.db import migrations, models


class AddFieldIfMissing(migrations.AddField):
    """Add a model field only when the database column is not already present."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        field = to_state.apps.get_model(app_label, self.model_name)._meta.get_field(self.name)
        table_name = model._meta.db_table
        column_name = field.column
        existing_columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                schema_editor.connection.cursor(), table_name
            )
        }
        if column_name in existing_columns:
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # This migration is intentionally additive and non-destructive.
        return


class CreateModelIfMissing(migrations.CreateModel):
    """Create a model table only when it is not already present."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.name)
        if model._meta.db_table in schema_editor.connection.introspection.table_names():
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # Keep backup/extended data intact if a migration is rolled back locally.
        return


PRODUCT_FIELD_SPECS = [
    ('available_on_this_website', models.BooleanField(blank=True, null=True)),
    ('allow_sample_request', models.BooleanField(blank=True, null=True)),
    ('sample_request_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('parent_product_sash', models.CharField(blank=True, max_length=200, null=True)),
    ('price_break_1_deposit_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_1_allow_further_discounts', models.BooleanField(blank=True, null=True)),
    ('price_break_2_deposit_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_2_allow_further_discounts', models.BooleanField(blank=True, null=True)),
    ('price_break_3_deposit_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_3_allow_further_discounts', models.BooleanField(blank=True, null=True)),
    ('price_break_4_quantity', models.PositiveIntegerField(blank=True, null=True)),
    ('price_break_4_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_4_sale_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_4_deposit_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_4_allow_further_discounts', models.BooleanField(blank=True, null=True)),
    ('price_break_5_quantity', models.PositiveIntegerField(blank=True, null=True)),
    ('price_break_5_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_5_sale_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_5_deposit_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ('price_break_5_allow_further_discounts', models.BooleanField(blank=True, null=True)),
    ('meta_title', models.CharField(blank=True, max_length=500, null=True)),
    ('meta_keywords', models.TextField(blank=True, null=True)),
    ('meta_description', models.TextField(blank=True, null=True)),
]


EXTENDED_TEXT_FIELDS = [
    ('vs_parent_id', 'VS Parent ID'),
    ('vs_child_id', 'VS Child ID'),
    ('blank_column_3', 'blank_column_3'),
    ('parent_reference', 'Parent Reference'),
    ('child_reference', 'Child Reference'),
    ('blank_column_6', 'blank_column_6'),
    ('available_on_this_website', 'Available On This Website'),
    ('blank_column_8', 'blank_column_8'),
    ('parent_product_title', 'Parent Product Title'),
    ('child_product_title', 'Child Product Title'),
    ('product_subtitle', 'Product Subtitle'),
    ('product_summary', 'Product Summary'),
    ('product_description', 'Product Description'),
    ('blank_column_14', 'blank_column_14'),
    ('brand', 'Brand'),
    ('blank_column_16', 'blank_column_16'),
    ('categories', 'Categories'),
    ('blank_column_18', 'blank_column_18'),
    ('attribute_1_length', 'Attribute 1 (Length)'),
    ('attribute_2_colour', 'Attribute 2 (Colour)'),
    ('attribute_3_top_sizes', 'Attribute 3 (Top Sizes)'),
    ('attribute_4_dress_sizes', 'Attribute 4 (Dress Sizes)'),
    ('attribute_5_design', 'Attribute 5 (Design)'),
    ('attribute_6_print', 'Attribute 6 (Print)'),
    ('attribute_7_weight', 'Attribute 7 (Weight)'),
    ('attribute_8_width', 'Attribute 8 (Width)'),
    ('attribute_9_size', 'Attribute 9 (Size)'),
    ('attribute_10_choose_type', 'Attribute 10 (Choose Type)'),
    ('attribute_11_gift_card_value', 'Attribute 11 (Gift Card Value)'),
    ('attribute_12_colours_pf', 'Attribute 12 (Colours PF)'),
    ('blank_column_31', 'blank_column_31'),
    ('allow_sample_request', 'Allow Sample Request'),
    ('blank_column_33', 'blank_column_33'),
    ('sample_request_cost', 'Sample Request Cost'),
    ('blank_column_35', 'blank_column_35'),
    ('tag_13_sale', 'Tag 13 (Sale)'),
    ('tag_12_dressmaking_and_fashion', 'Tag 12 (Dressmaking & Fashion )'),
    ('tag_2_colours', 'Tag 2 (Colours)'),
    ('tag_8_matching_lycra_and_mesh', 'Tag 8 (Matching Lycra & Mesh )'),
    ('tag_3_material', 'Tag 3 (Material)'),
    ('tag_11_materials', 'Tag 11 (Materials)'),
    ('tag_1_print_texture', 'Tag 1 (Print/ Texture)'),
    ('tag_6_quantity_box', 'Tag 6 (Quantity Box)'),
    ('tag_4_trimmings', 'Tag 4 (Trimmings)'),
    ('blank_column_45', 'blank_column_45'),
    ('parent_downloads', 'Parent Downloads'),
    ('parent_product_sash', 'Parent Product Sash'),
    ('child_product_sash', 'Child Product Sash'),
    ('blank_column_49', 'blank_column_49'),
    ('model_number', 'Model Number'),
    ('ean', 'EAN'),
    ('mpn', 'MPN'),
    ('isbn', 'ISBN'),
    ('release_date', 'Release Date'),
    ('available_now', 'Available Now'),
    ('upc', 'UPC'),
    ('blank_column_57', 'blank_column_57'),
    ('deposit_price_inc_vat', 'Deposit Price (Inc VAT)'),
    ('rrp_price_inc_vat', 'RRP Price (Inc VAT)'),
    ('cost_price_inc_vat', 'Cost Price (Inc VAT)'),
    ('vat_rate', 'VAT Rate'),
    ('display_on_sale_page', 'Display On Sale Page'),
    ('blank_column_63', 'blank_column_63'),
    ('price_break_1_quantity', 'Price Break 1 (Quantity)'),
    ('price_break_1_price_inc_vat', 'Price Break 1 (Price Inc VAT)'),
    ('price_break_1_sale_price_inc_vat', 'Price Break 1 (Sale Price Inc VAT)'),
    ('price_break_1_deposit_price_inc_vat', 'Price Break 1 (Deposit Price Inc VAT)'),
    ('price_break_1_allow_further_discounts_inc_vat', 'Price Break 1 (Allow Further Discounts Inc VAT)'),
    ('price_break_2_quantity', 'Price Break 2 (Quantity)'),
    ('price_break_2_price_inc_vat', 'Price Break 2 (Price Inc VAT)'),
    ('price_break_2_sale_price_inc_vat', 'Price Break 2 (Sale Price Inc VAT)'),
    ('price_break_2_deposit_price_inc_vat', 'Price Break 2 (Deposit Price Inc VAT)'),
    ('price_break_2_allow_further_discounts_inc_vat', 'Price Break 2 (Allow Further Discounts Inc VAT)'),
    ('price_break_3_quantity', 'Price Break 3 (Quantity)'),
    ('price_break_3_price_inc_vat', 'Price Break 3 (Price Inc VAT)'),
    ('price_break_3_sale_price_inc_vat', 'Price Break 3 (Sale Price Inc VAT)'),
    ('price_break_3_deposit_price_inc_vat', 'Price Break 3 (Deposit Price Inc VAT)'),
    ('price_break_3_allow_further_discounts_inc_vat', 'Price Break 3 (Allow Further Discounts Inc VAT)'),
    ('price_break_4_quantity', 'Price Break 4 (Quantity)'),
    ('price_break_4_price_inc_vat', 'Price Break 4 (Price Inc VAT)'),
    ('price_break_4_sale_price_inc_vat', 'Price Break 4 (Sale Price Inc VAT)'),
    ('price_break_4_deposit_price_inc_vat', 'Price Break 4 (Deposit Price Inc VAT)'),
    ('price_break_4_allow_further_discounts_inc_vat', 'Price Break 4 (Allow Further Discounts Inc VAT)'),
    ('price_break_5_quantity', 'Price Break 5 (Quantity)'),
    ('price_break_5_price_inc_vat', 'Price Break 5 (Price Inc VAT)'),
    ('price_break_5_sale_price_inc_vat', 'Price Break 5 (Sale Price Inc VAT)'),
    ('price_break_5_deposit_price_inc_vat', 'Price Break 5 (Deposit Price Inc VAT)'),
    ('price_break_5_allow_further_discounts_inc_vat', 'Price Break 5 (Allow Further Discounts Inc VAT)'),
    ('blank_column_89', 'blank_column_89'),
    ('stock_value', 'Stock Value'),
    ('max_purchase_quantity', 'Max Purchase Quantity'),
    ('min_purchase_quantity', 'Min Purchase Quantity'),
    ('minimum_age', 'Minimum Age'),
    ('pick_location', 'Pick Location'),
    ('stock_message', 'Stock Message'),
    ('weight_in_kgs', 'Weight (in KGs)'),
    ('child_active', 'Child Active'),
    ('parent_active', 'Parent Active'),
    ('archive_delete', 'Archive (Delete)'),
    ('archive_redirect_url', 'Archive Redirect URL'),
    ('date_added', 'Date Added'),
    ('parent_product_url', 'Parent Product Url'),
    ('child_product_url', 'Child Product Url'),
    ('blank_column_104', 'blank_column_104'),
    ('parent_product_images', 'Parent Product Images'),
    ('child_product_images', 'Child Product Images'),
    ('blank_column_107', 'blank_column_107'),
    ('meta_title', 'Meta Title'),
    ('meta_keywords', 'Meta Keywords'),
    ('meta_description', 'Meta Description'),
    ('blank_column_111', 'blank_column_111'),
    ('personalisation_1_custom_cutting', 'Personalisation 1 (Custom Cutting)'),
    ('personalisation_2_matching_power_mesh', 'Personalisation 2 (Matching Power Mesh )'),
    ('blank_column_114', 'blank_column_114'),
    ('upselling_1_you_may_also_like', 'Upselling 1 (You May Also Like)'),
    ('upselling_2_other_colours', 'Upselling 2 (Other Colours)'),
    ('upselling_3_related_products', 'Upselling 3 (Related Products)'),
    ('blank_column_118', 'blank_column_118'),
    ('amazon_active_uk', 'Amazon Active (UK)'),
    ('amazon_sku_uk', 'Amazon SKU (UK)'),
    ('amazon_live_uk', 'Amazon Live (UK)'),
    ('amazon_title_uk', 'Amazon Title (UK)'),
    ('amazon_description_uk', 'Amazon Description (UK)'),
    ('amazon_selling_price_uk', 'Amazon Selling Price (UK)'),
    ('amazon_price_sync_uk', 'Amazon Price Sync (UK)'),
    ('amazon_prime_template_id_uk', 'Amazon Prime Template ID (UK)'),
    ('amazon_barcode_uk', 'Amazon Barcode (UK)'),
    ('amazon_product_type_uk', 'Amazon Product Type (UK)'),
    ('amazon_category_uk', 'Amazon Category (UK)'),
    ('amazon_brand_uk', 'Amazon Brand (UK)'),
    ('amazon_search_terms_uk', 'Amazon Search Terms (UK)'),
    ('amazon_barcode_type_uk', 'Amazon Barcode Type (UK)'),
    ('amazon_handling_time_uk', 'Amazon Handling Time (UK)'),
    ('amazon_asin_uk', 'Amazon ASIN (UK)'),
    ('blank_column_135', 'blank_column_135'),
    ('featured', 'Featured'),
    ('blank_column_137', 'blank_column_137'),
    ('courier_blacklist', 'Courier Blacklist'),
    ('blank_column_139', 'blank_column_139'),
    ('courier_whitelist', 'Courier Whitelist'),
    ('blank_column_141', 'blank_column_141'),
    ('trade_only_product', 'Trade Only Product'),
    ('blank_column_143', 'blank_column_143'),
    ('parent_commodity_code', 'Parent Commodity Code'),
    ('parent_country_of_origin', 'Parent Country Of Origin'),
    ('blank_column_146', 'blank_column_146'),
    ('child_commodity_code', 'Child Commodity Code'),
    ('child_country_of_origin', 'Child Country Of Origin'),
    ('child_customs_description', 'Child Customs Description'),
    ('blank_column_150', 'blank_column_150'),
]


def extended_model_fields():
    fields = [
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='extended_data', to='products.product')),
        ('source_file_name', models.CharField(max_length=255)),
        ('source_file_date', models.DateField(blank=True, null=True)),
        ('row_number', models.PositiveIntegerField()),
        ('row_hash', models.CharField(db_index=True, max_length=64)),
        ('import_batch_id', models.CharField(db_index=True, max_length=100)),
    ]
    fields.extend(
        (field_name, models.TextField(blank=True, db_column=db_column, null=True))
        for field_name, db_column in EXTENDED_TEXT_FIELDS
    )
    fields.extend([
        ('raw_data', models.JSONField(blank=True, null=True)),
        ('raw_headers', models.JSONField(blank=True, null=True)),
        ('is_active', models.BooleanField(default=True)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('updated_at', models.DateTimeField(auto_now=True)),
    ])
    return fields


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_alter_product_image_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Location',
                    fields=[
                        ('id', models.CharField(editable=False, max_length=10, primary_key=True, serialize=False)),
                        ('name', models.CharField(max_length=100, unique=True)),
                        ('description', models.TextField(blank=True, null=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        'db_table': 'locations',
                        'ordering': ['id'],
                    },
                )
            ],
        ),
        *[
            AddFieldIfMissing(
                model_name='product',
                name=field_name,
                field=field,
            )
            for field_name, field in PRODUCT_FIELD_SPECS
        ],
        CreateModelIfMissing(
            name='ProductExtendedData',
            fields=extended_model_fields(),
            options={
                'db_table': 'product_extended_data',
                'ordering': ['source_file_name', 'row_number'],
                'indexes': [
                    models.Index(fields=['source_file_name', 'row_number'], name='product_ext_file_row_idx'),
                    models.Index(fields=['import_batch_id'], name='product_ext_batch_idx'),
                    models.Index(fields=['row_hash'], name='product_ext_hash_idx'),
                    models.Index(fields=['product'], name='product_ext_product_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        fields=['source_file_name', 'row_number', 'import_batch_id'],
                        name='unique_product_extended_import_row',
                    ),
                ],
            },
        ),
    ]
