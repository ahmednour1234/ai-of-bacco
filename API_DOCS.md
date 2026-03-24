# AI of Qumta â€” API Documentation

**Base URL:** `http://localhost:8000/api/v1`  
**Interactive Docs (Debug mode):** `http://localhost:8000/docs` (Swagger UI) Â· `http://localhost:8000/redoc`

---

## Authentication

All published endpoints are currently **public** and do not require an `Authorization` header.

---

## Standard Response Envelope

All responses follow a consistent envelope:

```jsonc
// Success
{
  "success": true,
  "message": "...",
  "data": { ... },   // object or array
  "meta": null       // pagination meta when applicable
}

// Paginated
{
  "success": true,
  "message": null,
  "data": [ ... ],
  "meta": {
    "page": 1,
    "per_page": 15,
    "total": 100,
    "total_pages": 7
  }
}

// Error
{
  "success": false,
  "message": "Error description.",
  "errors": { "field": ["validation message"] },
  "data": null,
  "meta": null
}
```

---

## 2. Users

> Endpoints are public and do not require authentication.

### GET `/users/me`
Return the authenticated user's profile.

**Response `200`:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "John Doe",
    "email": "john@example.com",
    "is_active": true,
    "is_superuser": false,
    "org_id": "uuid",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00"
  }
}
```

---

### GET `/users/`
List all users in the current organization.

**Query Parameters:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `page` | int | `1` | Min 1 |
| `per_page` | int | `15` | 1â€“100 |

**Response `200`:** Paginated list of users.

---

### GET `/users/{user_id}`
Retrieve a single user by UUID.

**Path Params:** `user_id` â€” UUID

---

### PATCH `/users/{user_id}`
Update a user record.

**Request Body (all fields optional):**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | 1â€“255 characters |
| `email` | string (email) | |

**Response `200`:** Updated user object.

---

### DELETE `/users/{user_id}`
Delete a user.

**Response `204`:** No content.

---

## 2.1 Product Extraction

> Endpoint is public and does not require authentication.

### POST `/extract/products`
Extract product records from uploaded files (on-demand).

**Supported File Types:**
- `csv`
- `xlsx`, `xlsm`, `xltx`, `xltm`
- `pdf`
- Images: `png`, `jpg`, `jpeg`, `bmp`, `tiff`, `webp`

**Request:** `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | binary | ✅ | Source file for extraction |

**Example (curl):**
```bash
curl -X POST http://localhost:8000/api/v1/extract/products \
  -F "file=@products.xlsx"
```

**Response `200`:**
```json
{
  "success": true,
  "message": "Products extracted successfully.",
  "data": {
    "file_name": "products.xlsx",
    "file_type": "xlsx",
    "count": 2,
    "items": [
      {
        "product_name": "Cement Bag",
        "category": "Building Materials",
        "brand": "Suez",
        "quantity": 50,
        "unit": "bag",
        "source_line": "{'product_name': 'Cement Bag', 'category': 'Building Materials', 'brand': 'Suez', 'quantity': '50', 'unit': 'bag'}"
      }
    ]
  },
  "meta": null
}
```

**Possible Errors:**
- `422 Validation Error` - missing `file` field.
- `422 Validation Error` - uploaded file is empty.
- `422 Validation Error` - unsupported extension (allowed: `pdf`, image, excel, `csv`).

---

## 3. Products

> Endpoints are public and do not require authentication.

### GET `/products/`
List products with optional filtering.

**Query Parameters:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `page` | int | `1` | Min 1 |
| `per_page` | int | `15` | 1â€“100 |
| `search` | string | â€” | Full-text product name search |
| `category` | string | â€” | Filter by category |

**Response `200`:** Paginated list with fields: `id`, `name`, `slug`, `sku`, `category`, `unit`, `created_at`.

---

### POST `/products/`
Create a new product.

**Request Body:**
```json
{
  "name": "Stainless Steel Bolt M8",
  "sku": "BOLT-M8-SS",
  "category": "Fasteners",
  "unit": "pcs",
  "description": "High-grade stainless steel bolt.",
  "metadata": { "diameter": "8mm" }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | âœ… | 1â€“512 characters; slug auto-generated |
| `sku` | string | âŒ | Max 128 characters |
| `category` | string | âŒ | Max 255 characters |
| `unit` | string | âŒ | Max 64 characters (e.g. `pcs`, `kg`) |
| `description` | string | âŒ | |
| `metadata` | object | âŒ | Arbitrary JSON |

**Response `201`:**
```json
{
  "success": true,
  "message": "Product created.",
  "data": {
    "id": "uuid",
    "name": "Stainless Steel Bolt M8",
    "slug": "stainless-steel-bolt-m8",
    "sku": "BOLT-M8-SS",
    "category": "Fasteners",
    "unit": "pcs",
    "description": "High-grade stainless steel bolt.",
    "metadata": { "diameter": "8mm" },
    "org_id": "uuid",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00"
  }
}
```

---

### GET `/products/{product_id}`
Retrieve a single product by UUID.

**Response `200`:** Full `ProductResponseSchema` object.

---

### PATCH `/products/{product_id}`
Partially update a product. Slug regenerates when name changes.

**Request Body (all fields optional):**
```json
{
  "name": "Updated Name",
  "sku": "NEW-SKU",
  "category": "New Category",
  "unit": "kg",
  "description": "Updated description.",
  "metadata": {}
}
```

**Response `200`:** Updated product object.

---

### DELETE `/products/{product_id}`
Soft-delete a product.

**Response `204`:** No content.

---

### POST `/products/{product_id}/aliases`
Add an alternate name/alias to a product.

**Request Body:**
```json
{
  "product_id": "uuid",
  "alias_text": "M8 Bolt SS",
  "source": "manual",
  "language": "en"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `product_id` | UUID | âœ… | Must match path `product_id` |
| `alias_text` | string | âœ… | Min 1 character |
| `source` | string | âŒ | e.g. `manual`, `ai`, `import` |
| `language` | string | âŒ | Default `"en"` |

**Response `201`:**
```json
{
  "success": true,
  "message": "Alias added.",
  "data": {
    "id": "uuid",
    "product_id": "uuid",
    "alias_text": "M8 Bolt SS",
    "source": "manual",
    "language": "en",
    "created_at": "2026-01-01T00:00:00"
  }
}
```

---

## 4. Suppliers

> All endpoints require authentication.

### GET `/suppliers/`
List suppliers with optional search.

**Query Parameters:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `page` | int | `1` | |
| `per_page` | int | `15` | 1â€“100 |
| `search` | string | â€” | Name search |

---

### POST `/suppliers/`
Create a new supplier.

**Request Body:**
```json
{
  "name": "Acme Corp",
  "contact_email": "supply@acme.com",
  "website": "https://acme.com",
  "country": "US",
  "description": "Industrial supplier.",
  "metadata": {}
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | âœ… | 1â€“512 characters |
| `contact_email` | string (email) | âŒ | |
| `website` | string | âŒ | |
| `country` | string | âŒ | |
| `description` | string | âŒ | |
| `metadata` | object | âŒ | |

**Response `201`:**
```json
{
  "success": true,
  "message": "Supplier created.",
  "data": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "contact_email": "supply@acme.com",
    "website": "https://acme.com",
    "country": "US",
    "description": "Industrial supplier.",
    "metadata": {},
    "org_id": "uuid",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00"
  }
}
```

---

### GET `/suppliers/{supplier_id}`
Retrieve a single supplier.

---

### PATCH `/suppliers/{supplier_id}`
Update a supplier (all fields optional â€” same fields as create).

**Response `200`:** Updated supplier object.

---

### DELETE `/suppliers/{supplier_id}`
Delete a supplier.

**Response `204`:** No content.

---

## 5. Invoices

> Endpoints are public and do not require authentication.

### GET `/invoices/`
List invoices.

**Query Parameters:** `page`, `per_page`

---

### POST `/invoices/`
Create an invoice.

**Request Body:**
```json
{
  "document_id": "uuid",
  "supplier_id": "uuid",
  "invoice_number": "INV-2026-001",
  "invoice_date": "2026-01-15",
  "total_amount": 1500.00,
  "currency": "USD"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `document_id` | UUID | âŒ | Related uploaded document |
| `supplier_id` | UUID | âŒ | Related supplier |
| `invoice_number` | string | âŒ | Max 128 characters |
| `invoice_date` | date (`YYYY-MM-DD`) | âŒ | |
| `total_amount` | float | âŒ | |
| `currency` | string | âŒ | 3-letter code, default `"USD"` |

**Response `201`:** Full invoice object.

---

### GET `/invoices/{invoice_id}`
Retrieve a single invoice.

---

### PATCH `/invoices/{invoice_id}`
Update an invoice (all fields optional â€” excludes `document_id`).

**Request Body:**
```json
{
  "supplier_id": "uuid",
  "invoice_number": "INV-2026-002",
  "invoice_date": "2026-02-01",
  "total_amount": 2000.00,
  "currency": "EUR"
}
```

---

### DELETE `/invoices/{invoice_id}`
Delete an invoice.

**Response `204`:** No content.

---

## 6. Documents

> All endpoints require authentication. Documents are typically created automatically when a file is processed.

### GET `/documents/`
List documents.

**Query Parameters:** `page`, `per_page`

**Response `200`:** Paginated list with fields: `id`, `uploaded_file_id`, `doc_type`, `status`, `created_at`.

---

### GET `/documents/{document_id}`
Retrieve a single document including parsed data.

**Response `200`:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "uploaded_file_id": "uuid",
    "doc_type": "invoice",
    "status": "parsed",
    "raw_text": "...",
    "parsed_data": { "invoice_number": "INV-001" },
    "error_message": null,
    "org_id": "uuid",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00"
  }
}
```

**`doc_type` values:** `invoice`, `receipt`, `purchase_order`, `unknown`  
**`status` values:** `pending`, `processing`, `parsed`, `failed`

---

### PATCH `/documents/{document_id}`
Manually correct a document's parsed content.

**Request Body (all fields optional):**
```json
{
  "doc_type": "invoice",
  "raw_text": "Raw OCR text...",
  "parsed_data": { "invoice_number": "INV-001" }
}
```

---

### DELETE `/documents/{document_id}`
Delete a document.

**Response `204`:** No content.

---

## 7. Uploaded Files

> Endpoints are public and do not require authentication.

### POST `/files/`
Upload a file. Uses `multipart/form-data`.

**Form Fields:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | binary | âœ… | Any file type |

**Example (curl):**
```bash
curl -X POST http://localhost:8000/api/v1/files/ \
  -F "file=@invoice.pdf"
```

**Response `201`:**
```json
{
  "success": true,
  "message": "File uploaded.",
  "data": {
    "id": "uuid",
    "original_name": "invoice.pdf",
    "storage_path": "org-uuid/2026/01/invoice.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 204800,
    "file_type": "document",
    "status": "uploaded",
    "org_id": "uuid",
    "owner_id": "uuid",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00"
  }
}
```

**`file_type` values:** `document`, `image`, `spreadsheet`, `other`  
**`status` values:** `uploaded`, `processing`, `processed`, `failed`

---

### GET `/files/`
List uploaded files.

**Query Parameters:** `page`, `per_page`

---

### GET `/files/{file_id}`
Retrieve metadata for a single uploaded file.

---

### DELETE `/files/{file_id}`
Delete a file from storage and the database.

**Response `204`:** No content.

---

## 8. Price Estimations

> All endpoints require authentication.

### GET `/price-estimations/`
List price estimations.

**Query Parameters:**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `page` | int | `1` | |
| `per_page` | int | `15` | 1â€“100 |
| `product_id` | UUID | â€” | Filter by product |

---

### POST `/price-estimations/`
Create a price estimation for a product.

**Request Body:**
```json
{
  "product_id": "uuid",
  "estimated_price": 12.50,
  "currency": "USD",
  "confidence": 0.92,
  "source_type": "ai_estimated",
  "valid_from": "2026-01-01",
  "valid_to": "2026-06-30",
  "metadata": { "model": "gpt-4o" }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `product_id` | UUID | âœ… | |
| `estimated_price` | float | âœ… | Must be > 0 |
| `currency` | string | âŒ | 3-letter code, default `"USD"` |
| `confidence` | float | âŒ | 0.0 â€“ 1.0 |
| `source_type` | string | âŒ | See values below; default `ai_estimated` |
| `valid_from` | date | âŒ | `YYYY-MM-DD` |
| `valid_to` | date | âŒ | `YYYY-MM-DD` |
| `metadata` | object | âŒ | |

**`source_type` values:** `ai_estimated`, `manual`, `supplier_quote`, `market_data`

**Response `201`:** Full price estimation object.

---

### GET `/price-estimations/{estimation_id}`
Retrieve a single estimation.

---

### PATCH `/price-estimations/{estimation_id}`
Update an estimation (all fields optional â€” same as create except `product_id`).

---

### DELETE `/price-estimations/{estimation_id}`
Delete an estimation.

**Response `204`:** No content.

---

## 9. AI Jobs

> All endpoints require authentication. Jobs are created internally by Celery tasks; use these endpoints to poll status.

### GET `/ai-jobs/`
List AI jobs for the organization.

**Query Parameters:** `page`, `per_page`

**Response `200`:** Paginated list with fields: `id`, `job_type`, `status`, `document_id`, `created_at`, `completed_at`.

---

### GET `/ai-jobs/{job_id}`
Retrieve full details of an AI job including result payload.

**Response `200`:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "job_type": "document_parse",
    "status": "completed",
    "document_id": "uuid",
    "payload": { "file_id": "uuid" },
    "result": { "invoice_number": "INV-001", "total": 500 },
    "error_message": null,
    "started_at": "2026-01-01T10:00:00",
    "completed_at": "2026-01-01T10:00:05",
    "org_id": "uuid",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00"
  }
}
```

**`job_type` values:** `document_parse`, `price_estimation`, `product_classification`  
**`status` values:** `pending`, `running`, `completed`, `failed`

---

### DELETE `/ai-jobs/{job_id}`
Delete an AI job record.

**Response `204`:** No content.

---

## Error Codes

| HTTP Status | Meaning |
|-------------|---------|
| `400` | Bad Request / Validation Error |
| `403` | Forbidden â€” insufficient permissions |
| `404` | Resource not found |
| `422` | Unprocessable Entity â€” Pydantic validation failed |
| `500` | Internal Server Error |

---

## Common Pagination Response (`meta`)

```json
{
  "meta": {
    "page": 1,
    "per_page": 15,
    "total": 50,
    "total_pages": 4
  }
}
```
