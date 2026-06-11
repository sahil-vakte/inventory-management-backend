# Product CSV Import TODO - 2026-06-11

## Goal

Save every column from the full backup CSV in the database, but only use and expose the finalized product columns in application import responses and product APIs.

The full backup CSV is the source-of-truth archive. `Finalised_Product_Columns.csv` is the public/working product contract derived from that backup.

## Implementation Status

Started on 2026-06-11.

Completed:

- Added missing finalized-column fields to `Product` using additive nullable fields.
- Added `ProductExtendedData` as a supplementary backup/extended table.
- Added 150 backup CSV fields to `ProductExtendedData`.
- Added safe migration `products.0004_product_extended_data`.
- Applied the products migration locally.
- Added Django admin registration for `ProductExtendedData`.
- Added management command `import_product_backup_csv`.
- Updated `/api/v1/products/import-excel/` to accept backup CSV uploads as well as legacy Excel uploads.
- Updated Postman collection entry for product import with CSV dry-run/batch options.
- Verified dry-run import against 5 real rows from `Actual_Product_Data_BackUp_11062026.csv`.
- Updated CSV import to avoid duplicate `ProductExtendedData` rows on repeated `/api/v1/products/import-excel/` uploads.
- Updated full CSV uploads through `/api/v1/products/import-excel/` to run in the background and return `202 Accepted` to avoid 60-second request timeouts.
- Added `/api/v1/products/import-status/?batch_id=...` for checking CSV import progress summary.

Pending before full import:

- Review mapping choices for product/category/brand handling.
- Run a larger dry-run sample.
- Run full import only after approval.
- Decide whether any internal API endpoint is needed for extended source data.

## Non-Negotiable Safety Rules

- Do not break or rewrite the current product flow.
- Do not delete, rename, or recreate existing tables.
- Do not delete, rename, or alter existing fields unless absolutely required.
- Do not remove existing APIs, serializers, views, URLs, permissions, or model relationships.
- Do not change existing API response behavior unless the change is strictly additive and backward compatible.
- Preserve all existing database records.
- All new product fields must be nullable or have safe defaults so migrations work with existing rows.
- All import work must be additive: current product APIs continue to work, extended backup data is supplementary.
- Primary and secondary location remain on `StockItem` only.

## Source Files

- Full backup source: `C:\Users\banda\Downloads\Actual_Product_Data_BackUp_11062026.csv`
- Finalized column source: `C:\Users\banda\Downloads\Finalised_Product_Columns.csv`

## Current File Summary

- `Actual_Product_Data_BackUp_11062026.csv`
  - Rows: 192,930 data rows
  - Columns: 150 CSV columns
  - Non-blank header columns: 124
  - Blank header positions: 3, 6, 8, 14, 16, 18, 31, 33, 35, 45, 49, 57, 63, 89, 104, 107, 111, 114, 118, 135, 137, 139, 141, 143, 146, 150
  - Contains the full export, including extra fields and blank columns.
  - Must be preserved in the database as the complete source backup.

- `Finalised_Product_Columns.csv`
  - Rows: 191,835 data rows
  - Contains only the columns we want to use in the system.
  - This file defines the allowed product API/import response shape.

## Finalized Columns To Use

The import should only use these columns:

- VS Parent ID
- VS Child ID
- Parent Reference
- Available On This Website
- Parent Product Title
- Child Product Title
- Product Subtitle
- Product Summary
- Product Description
- Categories
- Attribute 1 (Length)
- Allow Sample Request
- Sample Request Cost
- Tag 2 (Colours)
- Tag 3 (Material)
- Tag 1 (Print/ Texture)
- Parent Product Sash
- RRP Price (Inc VAT)
- Cost Price (Inc VAT)
- VAT Rate
- Display On Sale Page
- Price Break 1 (Quantity)
- Price Break 1 (Price Inc VAT)
- Price Break 1 (Sale Price Inc VAT)
- Price Break 1 (Deposit Price Inc VAT)
- Price Break 1 (Allow Further Discounts Inc VAT)
- Price Break 2 (Quantity)
- Price Break 2 (Price Inc VAT)
- Price Break 2 (Sale Price Inc VAT)
- Price Break 2 (Deposit Price Inc VAT)
- Price Break 2 (Allow Further Discounts Inc VAT)
- Price Break 3 (Quantity)
- Price Break 3 (Price Inc VAT)
- Price Break 3 (Sale Price Inc VAT)
- Price Break 3 (Deposit Price Inc VAT)
- Price Break 3 (Allow Further Discounts Inc VAT)
- Price Break 4 (Quantity)
- Price Break 4 (Price Inc VAT)
- Price Break 4 (Sale Price Inc VAT)
- Price Break 4 (Deposit Price Inc VAT)
- Price Break 4 (Allow Further Discounts Inc VAT)
- Price Break 5 (Quantity)
- Price Break 5 (Price Inc VAT)
- Price Break 5 (Sale Price Inc VAT)
- Price Break 5 (Deposit Price Inc VAT)
- Price Break 5 (Allow Further Discounts Inc VAT)
- Stock Value
- Weight (in KGs)
- Parent Product Url
- Child Product Url
- Parent Product Images
- Child Product Images
- Meta Title
- Meta Keywords
- Meta Description

## Current Tables Checked

Current Django models are mapped to these database tables:

- `products.Location` -> `locations`
- `products.Category` -> `categories`
- `products.Brand` -> `brands`
- `products.Product` -> `products`
- `colors.Color` -> `colors`
- `stock.StockItem` -> `stock`
- `stock.StockMovement` -> `stock_movements`
- `orders.Order` -> `orders`
- `orders.OrderItem` -> `order_items`
- `orders.OrderStatusHistory` -> `order_status_history`
- `accounts.UserType` -> `accounts_usertype`
- `accounts.Profile` -> `accounts_profile`

Migration status note:

- Product, stock, color, auth, session, admin, and token migrations are applied.
- `orders.0002_order_status_flow` is pending and should be applied before relying on the latest order status workflow.

## Current Product/Stock Model Fit

Fields already available on `Product` for finalized CSV:

- `vs_parent_id`
- `vs_child_id`
- `parent_reference`
- `parent_product_title`
- `child_product_title`
- `product_subtitle`
- `product_summary`
- `product_description`
- `categories`
- `attribute_length`
- `tag_colours`
- `tag_material`
- `tag_print_texture`
- `rrp_price_inc_vat`
- `cost_price_inc_vat`
- `vat_rate`
- `display_on_sale_page`
- `price_break_1_quantity`
- `price_break_1_price`
- `price_break_1_sale_price`
- `price_break_2_quantity`
- `price_break_2_price`
- `price_break_2_sale_price`
- `price_break_3_quantity`
- `price_break_3_price`
- `price_break_3_sale_price`
- `stock_value`
- `weight_kg`
- `parent_product_url`
- `child_product_url`
- `parent_product_images`
- `child_product_images`

Fields available in related models:

- `Stock Value` is now mapped to `StockItem.available_stock_in_mtr` during backup CSV import. The product `stock_value` field is still preserved separately for backward-compatible product data.
- Backup CSV import also creates/updates related `Brand`, `Category`, `Color`, `StockItem`, and `Location` records where matching source columns exist. All related records use existing unique keys with `get_or_create`/`update_or_create` so re-uploading the same file updates existing rows instead of creating duplicates.
- Stock `is_active` now follows the imported product state. If either imported product active flag makes the product inactive, the related stock row is also saved as inactive.
- SKU/product lookup can use `StockItem.sku` and `Product.vs_child_id`.
- Primary and secondary locations belong only to `StockItem`.
- Color data can map to `Color` only if the CSV values can be normalized into `color_code` and `color_name`.
- Categories can map to `Category` through `Product.categories`.

## Required Model Changes

Add a backup/extended table/model to preserve every column from `Actual_Product_Data_BackUp_11062026.csv`.

Recommended model:

- `ProductExtendedData`
  - `id`
  - `product` as `ForeignKey(Product, on_delete=models.CASCADE, related_name="extended_data", null=True, blank=True)`
  - `source_file_name`
  - `source_file_date`
  - `row_number`
  - `row_hash`
  - `import_batch_id`
  - One nullable model field for each backup CSV column.
  - Generated fields for blank-header positions, for example `blank_column_3`, `blank_column_6`, etc.
  - Optional `raw_data` as `JSONField` for audit/debugging and exact re-import support.
  - Optional `raw_headers` as `JSONField` for preserving the original header order.
  - `is_active`
  - `created_at`
  - `updated_at`

Purpose:

- Store all 150 CSV positions from the backup file as DB-backed data.
- Keep field names close to source columns using sanitized Django field names and `db_column` for the original CSV header where practical.
- Preserve blank header columns using generated field names such as `blank_column_3`.
- Preserve original header names and original row values accurately enough for audit/re-import.
- Keep this source table separate from the normalized `Product` table.
- Use this table for recovery, future mapping, and checking whether finalized columns came from the backup correctly.

Relationship decision:

- Use `ForeignKey` first, not `OneToOneField`, because backup uniqueness must be proven before enforcing one extended row per product.
- Link to `Product` by the normalized product created/found from `VS Child ID` where possible.
- Allow `product=null` for rows that cannot safely map to a product, so raw backup rows are still preserved.

Add these fields to `Product` because they exist in the finalized CSV response shape but are not currently stored:

- `available_on_this_website` as `BooleanField(default=True)`
- `allow_sample_request` as `BooleanField(default=False)`
- `sample_request_cost` as `DecimalField(max_digits=10, decimal_places=2, default=0.00)`
- `parent_product_sash` as `CharField(max_length=200, blank=True, null=True)`
- `meta_title` as `CharField(max_length=500, blank=True, null=True)`
- `meta_keywords` as `TextField(blank=True, null=True)`
- `meta_description` as `TextField(blank=True, null=True)`

Add missing price-break fields to `Product`:

- `price_break_1_deposit_price`
- `price_break_1_allow_further_discounts`
- `price_break_2_deposit_price`
- `price_break_2_allow_further_discounts`
- `price_break_3_deposit_price`
- `price_break_3_allow_further_discounts`
- `price_break_4_quantity`
- `price_break_4_price`
- `price_break_4_sale_price`
- `price_break_4_deposit_price`
- `price_break_4_allow_further_discounts`
- `price_break_5_quantity`
- `price_break_5_price`
- `price_break_5_sale_price`
- `price_break_5_deposit_price`
- `price_break_5_allow_further_discounts`

Model/API cleanup needed:

- Keep `Actual_Product_Data_BackUp_11062026.csv` as the database persistence source.
- Use `Finalised_Product_Columns.csv` only to define what the system returns or actively works with.
- API responses should include only finalized columns unless an admin/audit endpoint explicitly requests extended source data.
- Add an internal/admin endpoint or management command to inspect extended source data when needed.
- Decide whether `Finalised_Product_Columns.csv` has a reliable SKU column. It currently has `VS Child ID` and URLs, but no explicit `SKU` or `Child Reference` column.
- Current `Product` model still has `child_reference`, but the finalized CSV does not include `Child Reference`. Decide whether `child_reference` should be generated from `VS Child ID`, left blank, or re-added to the finalized CSV.
- Current `ProductListSerializer` and `ProductDetailSerializer` reference `primary_location` and `secondary_location` through `Product`, but locations must stay only on `StockItem`. Fix this only in a backward-compatible way and avoid breaking existing product endpoints.
- Existing product import endpoint only accepts Excel files and reads the `Product Master` sheet. Keep that existing behavior intact; add a separate management command for the backup CSV import.
- Existing product import maps `Child` instead of `Child Reference`; this needs correction or removal for the finalized CSV flow.
- Existing product import handles only price breaks 1 to 3 partially. Extend it to all finalized price break columns.
- Existing product import does not store SEO fields, sample request fields, sash, or website availability. Add those mappings after model fields are added.
- Decide whether product images should remain URL fields or move to a separate product image table for multiple image URLs.
- Decide whether categories should be created from the CSV text automatically or rejected when not already present.

## Migration Safety Plan

Before generating migrations:

- Inspect the actual database columns for `products`.
- Inspect Django model fields for `Product`.
- Compare `Finalised_Product_Columns.csv` mapped fields against both model fields and DB columns.
- Add only fields that are missing from both the model and database.
- If a DB column exists but the model field is missing, do not create a duplicate column. Add the model field with the existing `db_column` if appropriate, then generate a safe migration.
- If a migration exists but is unapplied, do not create a conflicting migration. Update the plan or add a dependent migration safely.
- Run `makemigrations --dry-run --check` or inspect generated operations before applying.
- Run `manage.py check` after model changes.
- Run focused product/stock tests after migrations.

Migration rules:

- New `Product` fields should be `null=True, blank=True` unless a safe default is required.
- New decimal fields should use explicit `max_digits` and `decimal_places`.
- New boolean fields should use safe defaults only when that matches existing behavior.
- No destructive operations: no `RemoveField`, no table recreation, no data loss operations.
- Migration must be compatible with SQLite locally and PostgreSQL in production.
- Use separate additive migrations for Product fields and `ProductExtendedData` if that makes review safer.

Duplicate-column prevention:

- Add a pre-migration inspection step or helper script that checks existing table columns with `connection.introspection.get_table_description`.
- Compare against planned `db_column` names.
- Skip or adjust any field whose DB column already exists.
- Record the result in import/migration logs.

## Import Utility Plan

Create a Django management command:

- `python manage.py import_product_backup_csv --file <path> --batch-id <id> --dry-run`

Responsibilities:

- Read `Actual_Product_Data_BackUp_11062026.csv`.
- Normalize headers while preserving original header order.
- Persist every CSV column into `ProductExtendedData`.
- Map finalized columns into `Product`.
- Avoid duplicate products by using `VS Child ID` as the primary Product identity where valid.
- Avoid duplicate extended rows by using `row_hash`, `source_file_name`, and `row_number` or a batch-aware uniqueness strategy.
- Use `transaction.atomic()` for controlled chunks.
- Use `bulk_create` and `bulk_update` where safe for large imports.
- Log created/updated/skipped/error counts.
- Write validation errors to an import report instead of silently ignoring rows.
- Support `--dry-run` before writing anything.
- Support chunking so large CSV imports do not exhaust memory.

Validation handling:

- Treat empty strings, whitespace-only cells, and NaN-like values as null where appropriate.
- Validate numeric fields before decimal/integer conversion.
- Validate boolean-like values consistently.
- Validate `VS Child ID` before mapping to `Product`.
- Keep unmapped or invalid rows in `ProductExtendedData` where possible, with `product=null`.
- Do not allow one bad row to abort the entire import unless the file itself is unreadable.

Admin/serializer plan:

- Register `ProductExtendedData` in admin as read-only/searchable enough for support.
- Add admin filters for `source_file_name`, `import_batch_id`, `is_active`, and created date.
- Do not expose extended backup columns in existing public product APIs by default.
- If serializer updates are needed, keep them additive or create a dedicated internal serializer/endpoint for extended data.

## TODO

1. Keep the full backup CSV unchanged as the source archive.
2. Save every column from `Actual_Product_Data_BackUp_11062026.csv` into `ProductExtendedData`.
3. Use `Finalised_Product_Columns.csv` as the allowed API/import response schema.
4. Inspect current DB columns and model fields before adding any field.
5. Apply only missing `Product` model fields from finalized columns.
6. Create `ProductExtendedData` with all backup CSV columns.
7. Generate safe additive migrations only.
8. Review generated migrations for duplicate-column risk before applying.
9. Register `ProductExtendedData` in Django admin.
10. Update serializers only if needed, and only in a backward-compatible/additive way.
11. Keep existing product APIs, views, permissions, URLs, and behavior intact.
12. Compare finalized columns against current Django product, stock, category, brand, color, and image models.
13. Create a field mapping document from finalized CSV columns to backend model fields.
14. Create a raw-to-finalized projection/mapping layer:
    - Read from extended source row
    - Normalize only finalized columns
    - Save/update normalized product records
    - Return only finalized fields in APIs
15. Decide how parent and child rows should be stored:
   - Parent product data
   - Child/SKU product data
   - Stock quantity
   - Categories
   - Colours/material/texture tags
   - Product images
   - Pricing and price breaks
   - SEO metadata
16. Validate row count difference between backup and finalized files before import.
17. Add import validation rules:
   - Required SKU/reference fields
   - Duplicate SKU detection
   - Numeric price and stock checks
   - Boolean field normalization
   - Image URL parsing
   - Category/tag cleanup
18. Build a management command to persist the full backup row and project only finalized columns.
19. Save skipped/invalid rows into an error report instead of silently ignoring them.
20. Test import with a small sample before importing the full backup CSV.
21. After import, verify:
    - Total imported parent products
    - Total imported child/SKU records
    - Total extended source rows saved
    - Extended source row count matches the backup CSV import count
    - Stock quantity totals
    - Product details API by SKU
    - Product list API
    - Stock API by SKU
22. Run `manage.py check`, migration checks, and focused tests.

## Important Notes

- Do not expose extra columns from the full backup CSV unless they are later added to the finalized column list.
- Extra columns from the full backup CSV must still be saved in `ProductExtendedData`.
- Extra columns should not be exposed in normal product APIs unless they are later added to the finalized column list.
- The full backup file should remain available for reference and recovery.
- The finalized CSV is the working response contract for now.
- No product data has been imported by this TODO creation.
- Existing Product table remains primary.
- `ProductExtendedData` is supplementary extended storage only.
- `/api/v1/products/import-excel/` must remain idempotent for CSV uploads: repeated upload of the same CSV rows should update existing rows, not create duplicates.
- Full backup CSV imports are too large for a normal synchronous API request. Default API behavior should start the import in the background; use `dry_run`, `limit`, or `sync=true` only for small tests.
