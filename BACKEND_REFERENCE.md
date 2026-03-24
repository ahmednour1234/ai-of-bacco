# ðŸ“¦ AI of Qumta â€” Backend Reference (API + Database)

> **Ø§Ù„Ù‡Ø¯Ù Ù…Ù† Ù‡Ø°Ø§ Ø§Ù„Ù…Ù„Ù**: Ø´Ø±Ø­ ÙƒØ§Ù…Ù„ Ù„ÙƒÙ„ endpoint ÙÙŠ Ø§Ù„Ù€ APIØŒ Ø¥ÙŠÙ‡ Ø§Ù„Ù„ÙŠ Ø¨ÙŠØªØ¨Ø¹Øª ÙÙŠÙ‡ØŒ ÙˆØ¥ÙŠÙ‡ Ø§Ù„Ù„ÙŠ Ø¨Ø±Ø¬Ø¹ØŒ ÙˆØ¥Ø²Ø§ÙŠ Ø§Ù„Ù€ database Ù…Ø¨Ù†ÙŠØ©.  
> Base URL Ù„ÙƒÙ„ Ø§Ù„Ù€ requests: `http://<host>:8000/api/v1`

---

## ðŸ”‘ Authentication

Ø­Ø§Ù„ÙŠÙ‹Ø§ ÙƒÙ„ Ø§Ù„Ù€ APIs Ø§Ù„Ø£Ø³Ø§Ø³ÙŠØ© Ø´ØºØ§Ù„Ø© **Ø¨Ø¯ÙˆÙ† Auth**.

- ØªÙ‚Ø¯Ø± ØªØ³ØªØ¯Ø¹ÙŠ Ø§Ù„Ù€ endpoints Ù…Ø¨Ø§Ø´Ø±Ø© Ø¨Ø¯ÙˆÙ† `Authorization` header.
- endpoints Ø¨ØªØ§Ø¹Ø© `/auth/*` **Ø§ØªØ´Ø§Ù„Øª Ù…Ù† Ø§Ù„Ù€ API Ø§Ù„Ù…Ù†Ø´ÙˆØ±**.

---

## ðŸ“‹ Table of Contents

1. [Users](#2-users)
2. [Product Extraction](#21-product-extraction)
3. [Products](#3-products)
4. [Product Aliases](#4-product-aliases)
5. [Suppliers](#5-suppliers)
6. [Supplier Products](#6-supplier-products)
7. [Invoices](#7-invoices)
8. [Invoice Items](#8-invoice-items)
9. [Documents](#9-documents)
10. [Uploaded Files](#10-uploaded-files)
11. [Price Estimations](#11-price-estimations)
12. [AI Jobs](#12-ai-jobs)
13. [Database Schema](#13-database-schema)
14. [Standard Response Format](#14-standard-response-format)

---

## 2. Users

### `GET /users/me` â€” Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„ÙŠÙˆØ²Ø± Ø§Ù„Ø­Ø§Ù„ÙŠ
**Response**: Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„ÙŠÙˆØ²Ø± Ø§Ù„Ù„ÙŠ Ø¹Ø§Ù…Ù„ login.

**Possible Errors:**
- Ù„Ø§ ÙŠÙˆØ¬Ø¯ auth Ù…Ø·Ù„ÙˆØ¨ Ø­Ø§Ù„ÙŠÙ‹Ø§ Ù„Ù‡Ø°Ø§ Ø§Ù„Ù€ endpoint.

---

### `GET /users/` â€” Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„ÙŠÙˆØ²Ø±Ø²
**Query Params:**
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `page` | int | 1 | Ø±Ù‚Ù… Ø§Ù„ØµÙØ­Ø© |
| `per_page` | int | 15 | 1â€“100 |

**Possible Errors:**
- `422 Validation Error` â€” Ù„Ùˆ `page` Ø£Ùˆ `per_page` Ù‚ÙŠÙ…ØªÙ‡Ù… ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `GET /users/{user_id}` â€” ÙŠÙˆØ²Ø± Ù…Ø¹ÙŠÙ†

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙŠÙˆØ²Ø± ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

### `PATCH /users/{user_id}` â€” ØªØ¹Ø¯ÙŠÙ„ ÙŠÙˆØ²Ø±
**Request Body:**
```json
{
  "name": "Ahmed Updated",
  "email": "new@example.com"
}
```
*(ÙƒÙ„ Ø§Ù„Ù€ fields Ø§Ø®ØªÙŠØ§Ø±ÙŠØ©)*

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙŠÙˆØ²Ø± ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `409 Conflict` â€” Ù„Ùˆ Ø§Ù„Ù€ email Ø§Ù„Ø¬Ø¯ÙŠØ¯ Ù…Ø³ØªØ®Ø¯Ù… Ù…Ù† ÙŠÙˆØ²Ø± Ø¢Ø®Ø±.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±Ø³Ù„Ø© Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `DELETE /users/{user_id}` â€” Ø­Ø°Ù ÙŠÙˆØ²Ø± (204)

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙŠÙˆØ²Ø± ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

## 2.1 Product Extraction

### `POST /extract/products` â€” Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ù„Ù…Ù†ØªØ¬Ø§Øª Ù…Ù† Ù…Ù„Ù
Ø§Ù„Ù€ endpoint Ø¯Ù‡ Ø¨ÙŠØ³ØªØ®Ø±Ø¬ Ù„ÙƒÙ„ item:
- `product_name`
- `category`
- `brand`
- `quantity`
- `unit`

**Content-Type:** `multipart/form-data`

| Form Field | Type | Required | Notes |
|------------|------|----------|-------|
| `file` | UploadFile | âœ… | CSV / Excel / PDF / Image |

**Supported Extensions:**
- `csv`
- `xlsx`, `xlsm`, `xltx`, `xltm`
- `pdf`
- `png`, `jpg`, `jpeg`, `bmp`, `tiff`, `webp`

**Response** (200):
```json
{
  "success": true,
  "message": "Products extracted successfully.",
  "data": {
    "file_name": "products.csv",
    "file_type": "csv",
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
  }
}
```

**Possible Errors:**
- `422 Validation Error` â€” Ù„Ùˆ Ù…ÙÙŠØ´ `file` ÙÙŠ Ø§Ù„Ù€ multipart request.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ù…Ù„Ù ÙØ§Ø¶ÙŠ.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø§Ù…ØªØ¯Ø§Ø¯ ØºÙŠØ± Ù…Ø¯Ø¹ÙˆÙ… (Ø§Ù„Ù…Ø¯Ø¹ÙˆÙ…: pdf/image/excel/csv).

---

## 3. Products

### `GET /products/` â€” Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ù…Ù†ØªØ¬Ø§Øª
**Query Params:**
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `page` | int | 1 | â€” |
| `per_page` | int | 15 | â€” |
| `search` | string | null | Ø¨Ø­Ø« ÙÙŠ Ø§Ù„Ø§Ø³Ù… |
| `category` | string | null | ÙÙ„ØªØ± Ø¨Ø§Ù„ÙƒØ§ØªÙŠØ¬ÙˆØ±ÙŠ |

**Possible Errors:**
- `422 Validation Error` â€” Ù„Ùˆ `page` Ø£Ùˆ `per_page` Ù‚ÙŠÙ…ØªÙ‡Ù… ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `POST /products/` â€” Ø¥Ø¶Ø§ÙØ© Ù…Ù†ØªØ¬ Ø¬Ø¯ÙŠØ¯
**Request Body:**
```json
{
  "name": "Cement Bag 50kg",
  "sku": "CEM-50",
  "category": "Building Materials",
  "unit": "bag",
  "description": "Portland cement 50kg bag",
  "metadata": {
    "brand": "Suez Cement",
    "weight_kg": 50
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | âœ… | 1â€“512 Ø­Ø±Ù |
| `sku` | string | âŒ | ÙƒÙˆØ¯ Ø§Ù„Ù…Ù†ØªØ¬ØŒ max 128 |
| `category` | string | âŒ | max 255 |
| `unit` | string | âŒ | ÙˆØ­Ø¯Ø© Ø§Ù„Ù‚ÙŠØ§Ø³ØŒ max 64 |
| `description` | string | âŒ | ÙˆØµÙ |
| `metadata` | object | âŒ | Ø£ÙŠ Ø¨ÙŠØ§Ù†Ø§Øª Ø¥Ø¶Ø§ÙÙŠØ© JSON |

**Response** (201):
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Cement Bag 50kg",
    "slug": "cement-bag-50kg",
    "sku": "CEM-50",
    "category": "Building Materials",
    "unit": "bag",
    "description": "Portland cement 50kg bag",
    "metadata": { "brand": "Suez Cement", "weight_kg": 50 },
    "org_id": "uuid",
    "created_at": "...",
    "updated_at": "..."
  }
}
```

**Possible Errors:**
- `409 Conflict` â€” Ù„Ùˆ ÙÙŠÙ‡ Ù…Ù†ØªØ¬ Ø¨Ù†ÙØ³ Ø§Ù„Ø§Ø³Ù…/slug Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ù†Ø§Ù‚ØµØ© Ø£Ùˆ Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `GET /products/{product_id}` â€” Ù…Ù†ØªØ¬ Ù…Ø¹ÙŠÙ†

**Possible Errors:**
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù…Ù†ØªØ¬ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

### `PATCH /products/{product_id}` â€” ØªØ¹Ø¯ÙŠÙ„ Ù…Ù†ØªØ¬
Ù†ÙØ³ fields Ø§Ù„Ù€ createØŒ ÙƒÙ„Ù‡Ø§ Ø§Ø®ØªÙŠØ§Ø±ÙŠØ©.

**Possible Errors:**
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù…Ù†ØªØ¬ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `409 Conflict` â€” Ù„Ùˆ Ø§Ù„Ø§Ø³Ù… Ø§Ù„Ø¬Ø¯ÙŠØ¯ ÙŠØ³Ø¨Ø¨ ØªØ¹Ø§Ø±Ø¶ Ù…Ø¹ Ù…Ù†ØªØ¬ Ù…ÙˆØ¬ÙˆØ¯.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±Ø³Ù„Ø© Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `DELETE /products/{product_id}` â€” Ø­Ø°Ù Ù…Ù†ØªØ¬ (204)

**Possible Errors:**
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù…Ù†ØªØ¬ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

## 4. Product Aliases

> Ø§Ù„Ø£Ø³Ù…Ø§Ø¡ Ø§Ù„Ø¨Ø¯ÙŠÙ„Ø© Ù„Ù„Ù…Ù†ØªØ¬ (Ù…Ø«Ù„Ø§Ù‹: Ù†ÙØ³ Ø§Ù„Ù…Ù†ØªØ¬ Ø¨Ø£Ø³Ù…Ø§Ø¡ Ù…Ø®ØªÙ„ÙØ© ÙÙŠ Ø§Ù„ÙÙˆØ§ØªÙŠØ±).

### `POST /products/{product_id}/aliases` â€” Ø¥Ø¶Ø§ÙØ© alias
**Request Body:**
```json
{
  "product_id": "uuid-of-product",
  "alias_text": "Ø§Ø³Ù…Ù†Øª Ø¨ÙˆØ±ØªÙ„Ø§Ù†Ø¯",
  "source": "invoice",
  "language": "ar"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `product_id` | UUID | âœ… | â€” |
| `alias_text` | string | âœ… | Ø§Ù„Ø§Ø³Ù… Ø§Ù„Ø¨Ø¯ÙŠÙ„ |
| `source` | string | âŒ | `invoice` / `manual` / etc. |
| `language` | string | âŒ | default `"en"` |

**Possible Errors:**
- `422 Validation Error` â€” Ù„Ùˆ `alias_text` Ø£Ùˆ Ø¨Ø§Ù‚ÙŠ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `GET /products/{product_id}/aliases` â€” ÙƒÙ„ aliases Ø§Ù„Ù…Ù†ØªØ¬

**Possible Errors:**
- Ù„Ø§ ÙŠÙˆØ¬Ø¯ auth Ù…Ø·Ù„ÙˆØ¨ Ø­Ø§Ù„ÙŠÙ‹Ø§ Ù„Ù‡Ø°Ø§ Ø§Ù„Ù€ endpoint.

---

## 5. Suppliers

### `GET /suppliers/` â€” Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ù…ÙˆØ±Ø¯ÙŠÙ†
**Query Params:** `page`, `per_page`, `search`

**Possible Errors:**
- `422 Validation Error` â€” Ù„Ùˆ `page` Ø£Ùˆ `per_page` Ù‚ÙŠÙ…ØªÙ‡Ù… ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `POST /suppliers/` â€” Ø¥Ø¶Ø§ÙØ© Ù…ÙˆØ±Ø¯
**Request Body:**
```json
{
  "name": "Al-Ahram Trading Co.",
  "contact_email": "supplier@ahram.com",
  "website": "https://ahram.com",
  "country": "Egypt",
  "description": "General trading company",
  "metadata": {
    "tax_id": "1234567"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | âœ… | 1â€“512 Ø­Ø±Ù |
| `contact_email` | email | âŒ | â€” |
| `website` | string | âŒ | max 512 |
| `country` | string | âŒ | max 100 |
| `description` | string | âŒ | â€” |
| `metadata` | object | âŒ | JSON |

**Response** (201): `id, name, slug, contact_email, website, country, description, metadata, org_id, created_at, updated_at`

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `409 Conflict` â€” Ù„Ùˆ Ø§Ù„Ù…ÙˆØ±Ø¯ Ù…ÙˆØ¬ÙˆØ¯ Ø¨Ø§Ù„ÙØ¹Ù„ Ø¨Ù†ÙØ³ Ø§Ù„Ø§Ø³Ù…/slug Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ù†Ø§Ù‚ØµØ© Ø£Ùˆ Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `GET /suppliers/{supplier_id}` â€” Ù…ÙˆØ±Ø¯ Ù…Ø¹ÙŠÙ†
**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù…ÙˆØ±Ø¯ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

### `PATCH /suppliers/{supplier_id}` â€” ØªØ¹Ø¯ÙŠÙ„ Ù…ÙˆØ±Ø¯ (ÙƒÙ„ fields Ø§Ø®ØªÙŠØ§Ø±ÙŠØ©)
**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù…ÙˆØ±Ø¯ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±Ø³Ù„Ø© Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

### `DELETE /suppliers/{supplier_id}` â€” Ø­Ø°Ù Ù…ÙˆØ±Ø¯ (204)
**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù…ÙˆØ±Ø¯ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

## 6. Supplier Products

> Ø±Ø¨Ø· Ù…ÙˆØ±Ø¯ Ø¨Ù…Ù†ØªØ¬ + Ø³Ø¹Ø± ÙˆØªØ§Ø±ÙŠØ®.

### `POST /supplier-products/` â€” Ø±Ø¨Ø· Ù…ÙˆØ±Ø¯ Ø¨Ù…Ù†ØªØ¬ *(endpoint planned)*
**Request Body:**
```json
{
  "supplier_id": "uuid",
  "product_id": "uuid",
  "supplier_sku": "SUP-CEM-001",
  "price": 125.50,
  "currency": "EGP",
  "effective_date": "2026-03-01"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `supplier_id` | UUID | âœ… | â€” |
| `product_id` | UUID | âœ… | â€” |
| `supplier_sku` | string | âŒ | ÙƒÙˆØ¯ Ø§Ù„Ù…Ù†ØªØ¬ Ø¹Ù†Ø¯ Ø§Ù„Ù…ÙˆØ±Ø¯ |
| `price` | float | âŒ | Ø§Ù„Ø³Ø¹Ø± |
| `currency` | string | âŒ | default `"USD"`, max 3 chars |
| `effective_date` | date | âŒ | ØªØ§Ø±ÙŠØ® Ø¨Ø¯Ø§ÙŠØ© Ø§Ù„Ø³Ø¹Ø± |

**Ù…Ù„Ø§Ø­Ø¸Ø© Ø£Ø®Ø·Ø§Ø¡:** Ø¨Ù…Ø§ Ø¥Ù† Ø§Ù„Ù€ endpoint Ø¯Ù‡ Ù„Ø³Ù‡ planned ÙˆÙ…Ø´ Ù…ØªÙ†ÙØ° ÙÙŠ Ø§Ù„ÙƒÙˆØ¯ Ø­Ø§Ù„ÙŠÙ‹Ø§ØŒ Ù…ÙÙŠØ´ runtime errors Ù…ÙˆØ«Ù‚Ø© Ù„Ù‡ Ø¨Ø´ÙƒÙ„ Ù†Ù‡Ø§Ø¦ÙŠ. Ø§Ù„Ù…ØªÙˆÙ‚Ø¹ Ù„Ø§Ø­Ù‚Ù‹Ø§ Ø¹Ù„Ù‰ Ø§Ù„Ø£Ù‚Ù„ `401` Ùˆ`403` Ùˆ`422` Ø­Ø³Ø¨ Ù†ÙØ³ Ø§Ù„Ù‚ÙˆØ§Ø¹Ø¯ Ø§Ù„Ø¹Ø§Ù…Ø©.

---

## 7. Invoices

### `GET /invoices/` â€” Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„ÙÙˆØ§ØªÙŠØ±
**Query Params:** `page`, `per_page`

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `422 Validation Error` â€” Ù„Ùˆ `page` Ø£Ùˆ `per_page` Ù‚ÙŠÙ…ØªÙ‡Ù… ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `POST /invoices/` â€” Ø¥Ù†Ø´Ø§Ø¡ ÙØ§ØªÙˆØ±Ø©
**Request Body:**
```json
{
  "document_id": "uuid-or-null",
  "supplier_id": "uuid-or-null",
  "invoice_number": "INV-2026-001",
  "invoice_date": "2026-03-15",
  "total_amount": 15750.00,
  "currency": "EGP"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `document_id` | UUID | âŒ | Ù„Ùˆ Ø§Ù„ÙØ§ØªÙˆØ±Ø© Ø¬Ø§Øª Ù…Ù† Ù…Ù„Ù Ù…Ø±ÙÙˆØ¹ |
| `supplier_id` | UUID | âŒ | Ø§Ù„Ù…ÙˆØ±Ø¯ |
| `invoice_number` | string | âŒ | Ø±Ù‚Ù… Ø§Ù„ÙØ§ØªÙˆØ±Ø©ØŒ max 128 |
| `invoice_date` | date | âŒ | `YYYY-MM-DD` |
| `total_amount` | float | âŒ | Ø§Ù„Ø¥Ø¬Ù…Ø§Ù„ÙŠ |
| `currency` | string | âŒ | default `"USD"` |

**Possible Errors:**
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±Ø³Ù„Ø© Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `GET /invoices/{invoice_id}` â€” ÙØ§ØªÙˆØ±Ø© Ù…Ø¹ÙŠÙ†Ø©
**Possible Errors:**
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙØ§ØªÙˆØ±Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø© Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

### `PATCH /invoices/{invoice_id}` â€” ØªØ¹Ø¯ÙŠÙ„ (Ø¨Ø¯ÙˆÙ† `document_id`)
**Possible Errors:**
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙØ§ØªÙˆØ±Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø© Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±Ø³Ù„Ø© Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

### `DELETE /invoices/{invoice_id}` â€” Ø­Ø°Ù (204)
**Possible Errors:**
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙØ§ØªÙˆØ±Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø© Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

## 8. Invoice Items

> Ø¨Ù†ÙˆØ¯ Ø§Ù„ÙØ§ØªÙˆØ±Ø© (Ù…Ø®Ø²Ù†Ø© ÙÙŠ Ø¬Ø¯ÙˆÙ„ `invoice_items`) â€” Ø¨ÙŠØªØ¹Ù…Ù„ÙˆØ§ Ø¹Ø§Ø¯Ø©Ù‹ Ù…Ù† Ø§Ù„Ù€ AI pipeline.

**Schema Ù„Ù„Ù€ item:**
| Field | Type | Notes |
|-------|------|-------|
| `invoice_id` | UUID | FK Ù„Ù„ÙØ§ØªÙˆØ±Ø© |
| `product_id` | UUID | FK Ù„Ù„Ù…Ù†ØªØ¬ (nullable) |
| `raw_description` | string | Ø§Ù„Ù†Øµ Ø§Ù„Ø®Ø§Ù… Ù…Ù† Ø§Ù„ÙØ§ØªÙˆØ±Ø© |
| `line_number` | int | Ø±Ù‚Ù… Ø§Ù„Ø³Ø·Ø± |
| `quantity` | decimal | Ø§Ù„ÙƒÙ…ÙŠØ© |
| `unit` | string | Ø§Ù„ÙˆØ­Ø¯Ø© |
| `unit_price` | decimal | Ø³Ø¹Ø± Ø§Ù„ÙˆØ­Ø¯Ø© |
| `total_price` | decimal | Ø§Ù„Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ù„Ù„Ø¨Ù†Ø¯ |
| `currency` | string | default `"USD"` |

---

## 9. Documents

> Ø§Ù„Ù€ Documents Ø¨ØªØªØ¹Ù…Ù„ **Ø£ÙˆØªÙˆÙ…Ø§ØªÙŠÙƒ** Ù…Ù† Ø§Ù„Ù€ AI pipeline Ø¨Ø¹Ø¯ Ø±ÙØ¹ Ù…Ù„Ù. Ù…Ø´ Ø¨ØªØªØ¹Ù…Ù„ manually.

### `GET /documents/` â€” Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„ÙˆØ«Ø§Ø¦Ù‚
**Query Params:** `page`, `per_page`

**Response item:** `id, uploaded_file_id, doc_type, status, created_at`

**`doc_type` values:** `invoice` | `supplier_catalog` | `price_list` | `other`  
**`status` values:** `pending` | `parsing` | `extracting` | `completed` | `failed`

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `422 Validation Error` â€” Ù„Ùˆ `page` Ø£Ùˆ `per_page` Ù‚ÙŠÙ…ØªÙ‡Ù… ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `GET /documents/{document_id}` â€” ÙˆØ«ÙŠÙ‚Ø© Ù…Ø¹ÙŠÙ†Ø©
**Response ÙŠØªØ¶Ù…Ù†:** `raw_text, parsed_data (JSON), error_message`

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙˆØ«ÙŠÙ‚Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø© Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

### `PATCH /documents/{document_id}` â€” ØªØ¹Ø¯ÙŠÙ„ ÙŠØ¯ÙˆÙŠ
```json
{
  "doc_type": "invoice",
  "raw_text": "text content...",
  "parsed_data": { "key": "value" }
}
```

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙˆØ«ÙŠÙ‚Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø© Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±Ø³Ù„Ø© Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `DELETE /documents/{document_id}` â€” Ø­Ø°Ù (204)

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ÙˆØ«ÙŠÙ‚Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø© Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

## 10. Uploaded Files

### `POST /files/` â€” Ø±ÙØ¹ Ù…Ù„Ù
**Content-Type:** `multipart/form-data`

| Form Field | Type | Required | Notes |
|------------|------|----------|-------|
| `file` | UploadFile | âœ… | PDF / image |

**Response** (201):
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "original_name": "invoice_march.pdf",
    "storage_path": "org-uuid/pdf/invoice_march.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 204800,
    "file_type": "pdf",
    "status": "pending",
    "org_id": "uuid",
    "owner_id": "uuid",
    "created_at": "...",
    "updated_at": "..."
  }
}
```

**`file_type` values:** `pdf` | `image` | `invoice` | `supplier_file` | `other`  
**`status` values:** `pending` | `processing` | `processed` | `failed`

**Possible Errors:**
- `422 Validation Error` â€” Ù„Ùˆ `file` Ù…Ø´ Ù…Ø¨Ø¹ÙˆØª Ø£Ùˆ Ø§Ù„Ù€ multipart request ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `GET /files/` â€” Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø±ÙÙˆØ¹Ø©
**Possible Errors:**
- `422 Validation Error` â€” Ù„Ùˆ `page` Ø£Ùˆ `per_page` Ù‚ÙŠÙ…ØªÙ‡Ù… ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

### `GET /files/{file_id}` â€” Ù…Ù„Ù Ù…Ø¹ÙŠÙ†
**Possible Errors:**
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù…Ù„Ù ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

### `DELETE /files/{file_id}` â€” Ø­Ø°Ù (204) + Ø¨ÙŠÙ…Ø³Ø­ Ø§Ù„Ù…Ù„Ù Ù…Ù† Ø§Ù„ØªØ®Ø²ÙŠÙ†
**Possible Errors:**
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù…Ù„Ù ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

## 11. Price Estimations

### `GET /price-estimations/` â€” Ù‚Ø§Ø¦Ù…Ø© ØªÙ‚Ø¯ÙŠØ±Ø§Øª Ø§Ù„Ø£Ø³Ø¹Ø§Ø±
**Query Params:**
| Param | Type | Notes |
|-------|------|-------|
| `page` | int | â€” |
| `per_page` | int | â€” |
| `product_id` | UUID | ÙÙ„ØªØ± Ø¨Ù…Ù†ØªØ¬ Ù…Ø¹ÙŠÙ† |

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `422 Validation Error` â€” Ù„Ùˆ `page` Ø£Ùˆ `per_page` Ø£Ùˆ `product_id` Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `POST /price-estimations/` â€” Ø¥Ø¶Ø§ÙØ© ØªÙ‚Ø¯ÙŠØ± Ø³Ø¹Ø±
**Request Body:**
```json
{
  "product_id": "uuid",
  "estimated_price": 125.50,
  "currency": "EGP",
  "confidence": 0.87,
  "source_type": "historical_invoice",
  "valid_from": "2026-01-01",
  "valid_to": "2026-12-31",
  "metadata": {
    "source_invoice_id": "uuid"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `product_id` | UUID | âœ… | â€” |
| `estimated_price` | float | âœ… | Ù„Ø§Ø²Ù… ÙŠÙƒÙˆÙ† > 0 |
| `currency` | string | âŒ | default `"USD"` |
| `confidence` | float | âŒ | 0.0 â€“ 1.0 |
| `source_type` | enum | âŒ | Ø´ÙˆÙ Ø§Ù„Ù‚ÙŠÙ… ØªØ­Øª |
| `valid_from` | date | âŒ | `YYYY-MM-DD` |
| `valid_to` | date | âŒ | `YYYY-MM-DD` |
| `metadata` | object | âŒ | JSON |

**`source_type` values:**
- `historical_invoice` â€” Ù…Ù† ÙÙˆØ§ØªÙŠØ± Ø³Ø§Ø¨Ù‚Ø©
- `supplier_catalog` â€” Ù…Ù† ÙƒØ§ØªØ§Ù„ÙˆØ¬ Ø§Ù„Ù…ÙˆØ±Ø¯
- `web_scrape` â€” Ù…Ù† Ø§Ù„Ø¥Ù†ØªØ±Ù†Øª
- `ai_estimated` â€” ØªÙ‚Ø¯ÙŠØ± Ø§Ù„Ù€ AI (default)
- `manual` â€” Ø¥Ø¯Ø®Ø§Ù„ ÙŠØ¯ÙˆÙŠ

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ù†Ø§Ù‚ØµØ© Ø£Ùˆ Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

---

### `GET /price-estimations/{estimation_id}` â€” ØªÙ‚Ø¯ÙŠØ± Ù…Ø¹ÙŠÙ†
**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ØªÙ‚Ø¯ÙŠØ± ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

### `PATCH /price-estimations/{estimation_id}` â€” ØªØ¹Ø¯ÙŠÙ„ (Ø¨Ø¯ÙˆÙ† `product_id`)
**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ØªÙ‚Ø¯ÙŠØ± ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `422 Validation Error` â€” Ù„Ùˆ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±Ø³Ù„Ø© Ø¨ØµÙŠØºØ© ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

### `DELETE /price-estimations/{estimation_id}` â€” Ø­Ø°Ù (204)
**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„ØªÙ‚Ø¯ÙŠØ± ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

## 12. AI Jobs

> Ø§Ù„Ù€ jobs Ø¨ØªØªØ¹Ù…Ù„ **Ø£ÙˆØªÙˆÙ…Ø§ØªÙŠÙƒ** Ù…Ù† Ø§Ù„Ù€ Celery tasks. Ø§Ù„Ù€ API read-only (Ø¹Ø¯Ø§ Ø§Ù„Ø­Ø°Ù).

### `GET /ai-jobs/` â€” Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ù€ jobs
**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `422 Validation Error` â€” Ù„Ùˆ `page` Ø£Ùˆ `per_page` Ù‚ÙŠÙ…ØªÙ‡Ù… ØºÙŠØ± ØµØ­ÙŠØ­Ø©.

### `GET /ai-jobs/{job_id}` â€” job Ù…Ø¹ÙŠÙ†

**Response ÙŠØªØ¶Ù…Ù†:** `job_type, status, payload, result, error_message, started_at, completed_at`

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù€ job ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

**`job_type` values:** `ocr` | `pdf_parse` | `image_parse` | `product_extraction` | `price_estimation` | `embedding` | `web_scrape`  
**`status` values:** `pending` | `running` | `completed` | `failed` | `cancelled`

### `DELETE /ai-jobs/{job_id}` â€” Ø­Ø°Ù (204)

**Possible Errors:**
- `403 Forbidden` â€” Ù„Ùˆ Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø·Ù„.
- `404 Not Found` â€” Ù„Ùˆ Ø§Ù„Ù€ job ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø§Ø®Ù„ Ù†ÙØ³ Ø§Ù„Ù€ organization.

---

## 13. Database Schema

### Ø¬Ø¯ÙˆÙ„ Ø§Ù„Ø¹Ù„Ø§Ù‚Ø§Øª (ERD Summary)

```
organizations
    â”‚
    â”œâ”€â”€< users (org_id)
    â”œâ”€â”€< products (org_id)
    â”œâ”€â”€< suppliers (org_id)
    â”œâ”€â”€< uploaded_files (org_id)
    â”œâ”€â”€< documents (org_id)
    â”œâ”€â”€< invoices (org_id)
    â”œâ”€â”€< price_estimations (org_id)
    â”œâ”€â”€< extracted_items (org_id)
    â””â”€â”€< ai_jobs (org_id)

uploaded_files â”€â”€1:1â”€â”€> documents
documents â”€â”€1:manyâ”€â”€> extracted_items
documents â”€â”€1:1â”€â”€> invoices
documents â”€â”€1:manyâ”€â”€> ai_jobs

invoices â”€â”€1:manyâ”€â”€> invoice_items
invoice_items >â”€â”€< products (product_id)

products â”€â”€1:manyâ”€â”€> product_aliases
products >â”€â”€< suppliers (via supplier_products)
products â”€â”€1:manyâ”€â”€> price_estimations
```

---

### ÙƒÙ„ Ø§Ù„Ø¬Ø¯Ø§ÙˆÙ„ ÙˆØ¹Ù…ÙˆØ¯Ù‡Ø§

#### `organizations`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | auto-generated |
| `name` | VARCHAR(255) | NOT NULL |
| `slug` | VARCHAR(255) | UNIQUE |
| `description` | TEXT | nullable |
| `is_active` | BOOLEAN | default true |
| `created_at` | TIMESTAMPTZ | auto |
| `updated_at` | TIMESTAMPTZ | auto |
| `deleted_at` | TIMESTAMPTZ | nullable (soft delete) |

---

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `name` | VARCHAR(255) | NOT NULL |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL |
| `hashed_password` | VARCHAR(255) | NOT NULL |
| `is_active` | BOOLEAN | default true |
| `is_superuser` | BOOLEAN | default false |
| `org_id` | UUID (FKâ†’organizations) | CASCADE |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |
| `deleted_at` | TIMESTAMPTZ | nullable |

---

#### `products`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `name` | VARCHAR(512) | NOT NULL |
| `slug` | VARCHAR(512) | NOT NULL, indexed |
| `sku` | VARCHAR(128) | nullable |
| `category` | VARCHAR(255) | nullable |
| `unit` | VARCHAR(64) | nullable |
| `description` | TEXT | nullable |
| `metadata` | JSONB | nullable, default `{}` |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `owner_id` | UUID (FKâ†’users) | nullable |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |
| `deleted_at` | TIMESTAMPTZ | nullable |

---

#### `product_aliases`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `product_id` | UUID (FKâ†’products) | CASCADE |
| `alias_text` | TEXT | NOT NULL |
| `source` | VARCHAR(128) | nullable |
| `language` | VARCHAR(10) | default `"en"` |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `owner_id` | UUID | nullable |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |

---

#### `suppliers`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `name` | VARCHAR(512) | NOT NULL |
| `slug` | VARCHAR(512) | NOT NULL |
| `contact_email` | VARCHAR(255) | nullable |
| `website` | VARCHAR(512) | nullable |
| `country` | VARCHAR(100) | nullable |
| `description` | TEXT | nullable |
| `metadata` | JSONB | nullable, default `{}` |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `owner_id` | UUID | nullable |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |
| `deleted_at` | TIMESTAMPTZ | nullable |

---

#### `supplier_products`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `supplier_id` | UUID (FKâ†’suppliers) | CASCADE |
| `product_id` | UUID (FKâ†’products) | CASCADE |
| `supplier_sku` | VARCHAR(128) | nullable |
| `price` | NUMERIC(14,4) | nullable |
| `currency` | VARCHAR(3) | default `"USD"` |
| `effective_date` | DATE | nullable |
| `is_active` | BOOLEAN | default true |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |

---

#### `uploaded_files`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `original_name` | VARCHAR(512) | NOT NULL |
| `storage_path` | VARCHAR(1024) | NOT NULL |
| `mime_type` | VARCHAR(128) | NOT NULL |
| `size_bytes` | BIGINT | NOT NULL, default 0 |
| `file_type` | ENUM | `pdf/image/invoice/supplier_file/other` |
| `status` | ENUM | `pending/processing/processed/failed` |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `owner_id` | UUID (FKâ†’users) | nullable |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |
| `deleted_at` | TIMESTAMPTZ | nullable |

---

#### `documents`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `uploaded_file_id` | UUID (FKâ†’uploaded_files) | CASCADE |
| `doc_type` | ENUM | `invoice/supplier_catalog/price_list/other` |
| `status` | ENUM | `pending/parsing/extracting/completed/failed` |
| `raw_text` | TEXT | nullable |
| `parsed_data` | JSONB | nullable |
| `error_message` | TEXT | nullable |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `owner_id` | UUID | nullable |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |
| `deleted_at` | TIMESTAMPTZ | nullable |

---

#### `invoices`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `document_id` | UUID (FKâ†’documents) | SET NULL on delete, nullable |
| `supplier_id` | UUID (FKâ†’suppliers) | SET NULL on delete, nullable |
| `invoice_number` | VARCHAR(128) | nullable |
| `invoice_date` | DATE | nullable |
| `total_amount` | NUMERIC(14,4) | nullable |
| `currency` | VARCHAR(3) | NOT NULL, default `"USD"` |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `owner_id` | UUID | nullable |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |
| `deleted_at` | TIMESTAMPTZ | nullable |

---

#### `invoice_items`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `invoice_id` | UUID (FKâ†’invoices) | CASCADE |
| `product_id` | UUID (FKâ†’products) | SET NULL on delete, nullable |
| `raw_description` | TEXT | nullable |
| `line_number` | INTEGER | nullable |
| `quantity` | NUMERIC(12,4) | nullable |
| `unit` | VARCHAR(64) | nullable |
| `unit_price` | NUMERIC(14,4) | nullable |
| `total_price` | NUMERIC(14,4) | nullable |
| `currency` | VARCHAR(3) | default `"USD"` |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |

---

#### `price_estimations`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `product_id` | UUID (FKâ†’products) | CASCADE |
| `estimated_price` | NUMERIC(14,4) | NOT NULL |
| `currency` | VARCHAR(3) | NOT NULL, default `"USD"` |
| `confidence` | FLOAT | nullable, 0.0â€“1.0 |
| `source_type` | ENUM | `historical_invoice/supplier_catalog/web_scrape/ai_estimated/manual` |
| `valid_from` | DATE | nullable |
| `valid_to` | DATE | nullable |
| `metadata` | JSONB | nullable, default `{}` |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |

---

#### `extracted_items`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `document_id` | UUID (FKâ†’documents) | CASCADE |
| `raw_text` | TEXT | NOT NULL |
| `normalized_text` | TEXT | nullable |
| `matched_product_id` | UUID (FKâ†’products) | SET NULL, nullable |
| `confidence_score` | FLOAT | nullable |
| `is_reviewed` | BOOLEAN | default false |
| `metadata` | JSONB | nullable, default `{}` |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |

---

#### `ai_jobs`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | â€” |
| `job_type` | ENUM | `ocr/pdf_parse/image_parse/product_extraction/price_estimation/embedding/web_scrape` |
| `status` | ENUM | `pending/running/completed/failed/cancelled` |
| `document_id` | UUID (FKâ†’documents) | SET NULL, nullable |
| `payload` | JSONB | nullable, default `{}` |
| `result` | JSONB | nullable |
| `error_message` | TEXT | nullable |
| `started_at` | TIMESTAMPTZ | nullable |
| `completed_at` | TIMESTAMPTZ | nullable |
| `org_id` | UUID (FKâ†’organizations) | â€” |
| `created_at` | TIMESTAMPTZ | â€” |
| `updated_at` | TIMESTAMPTZ | â€” |

---

## 14. Standard Response Format

### Single item response:
```json
{
  "success": true,
  "message": "OK",
  "data": { ...object },
  "meta": null
}
```

### Paginated response:
```json
{
  "success": true,
  "message": "OK",
  "data": [ ...array ],
  "meta": {
    "total": 50,
    "page": 1,
    "per_page": 15,
    "last_page": 4,
    "from": 1,
    "to": 15
  }
}
```

### Error response:
```json
{
  "success": false,
  "message": "Error description",
  "data": null
}
```

### Error response with details:
```json
{
  "success": false,
  "message": "The given data was invalid.",
  "data": null,
  "errors": {
    "field_name": [
      "Error message"
    ]
  }
}
```

### Common Error Scenarios

- `404 Not Found`: Ø¨ÙŠØ¸Ù‡Ø± Ù„Ù…Ø§ Ø§Ù„Ù€ resource Ø§Ù„Ù…Ø·Ù„ÙˆØ¨Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø©ØŒ Ø£Ùˆ Ø®Ø§Ø±Ø¬ Ù†ÙØ³ Ø§Ù„Ù€ organization.
- `409 Conflict`: Ø¨ÙŠØ¸Ù‡Ø± ÙÙŠ Ø­Ø§Ù„Ø§Øª Ø§Ù„ØªÙƒØ±Ø§Ø± Ø£Ùˆ Ø§Ù„ØªØ¹Ø§Ø±Ø¶ØŒ Ø²ÙŠ ØªÙƒØ±Ø§Ø± email Ø£Ùˆ Ø§Ø³Ù… product Ø£Ùˆ supplier.
- `422 Validation Error`: Ø¨ÙŠØ¸Ù‡Ø± Ù„Ùˆ request body Ø£Ùˆ query params ØºÙŠØ± Ù…Ø·Ø§Ø¨Ù‚ÙŠÙ† Ù„Ù„Ù€ schema Ø£Ùˆ Ø§Ù„Ù‚ÙŠÙˆØ¯ Ø§Ù„Ù…Ø·Ù„ÙˆØ¨Ø©.
- `500 Internal Server Error`: Ø¨ÙŠØ¸Ù‡Ø± Ù„Ùˆ Ø­ØµÙ„ Ø®Ø·Ø£ ØºÙŠØ± Ù…ØªÙˆÙ‚Ø¹ ÙˆØºÙŠØ± Ù…Ø¹Ø§Ù„Ø¬ Ø¯Ø§Ø®Ù„ Ø§Ù„ØªØ·Ø¨ÙŠÙ‚.

### Validation Error Note

Ø£Ø®Ø·Ø§Ø¡ Ø§Ù„Ù€ validation ÙÙŠ Ù‡Ø°Ø§ Ø§Ù„Ù…Ø´Ø±ÙˆØ¹ Ù‚Ø¯ ØªØ¸Ù‡Ø± Ø¨Ø·Ø±ÙŠÙ‚ØªÙŠÙ† Ø­Ø³Ø¨ Ù…ØµØ¯Ø±Ù‡Ø§:

- Ù„Ùˆ Ø§Ù„Ø®Ø·Ø£ Ø·Ø§Ù„Ø¹ Ù…Ù† `AppException` Ø¯Ø§Ø®Ù„ Ø§Ù„ØªØ·Ø¨ÙŠÙ‚ØŒ Ø§Ù„Ø§Ø³ØªØ¬Ø§Ø¨Ø© Ø¨ØªÙƒÙˆÙ† ÙÙŠ Ø§Ù„Ù€ standard envelope Ø§Ù„Ù…ÙˆØ¶Ø­ ÙÙˆÙ‚.
- Ù„Ùˆ Ø§Ù„Ø®Ø·Ø£ Ø·Ø§Ù„Ø¹ Ù…Ø¨Ø§Ø´Ø±Ø© Ù…Ù† FastAPI/Pydantic Ù‚Ø¨Ù„ Ø¯Ø®ÙˆÙ„ Ø§Ù„Ù€ endpointØŒ Ø§Ù„Ø§Ø³ØªØ¬Ø§Ø¨Ø© Ù‚Ø¯ ØªØ±Ø¬Ø¹ Ø¨Ø´ÙƒÙ„ FastAPI Ø§Ù„Ø§ÙØªØ±Ø§Ø¶ÙŠ ÙˆØªØ­ØªÙˆÙŠ Ø¹Ù„Ù‰ `detail` Ø¨Ø¯Ù„ `errors`.

### Common HTTP Status Codes:
| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 204 | No Content (delete) |
| 400 | Bad Request |
| 403 | Forbidden (account inactive / action not allowed) |
| 404 | Not Found (resource missing in current organization scope) |
| 409 | Conflict (duplicate or state conflict) |
| 422 | Validation Error (body/query/path data invalid) |
| 500 | Internal Server Error |

---

## ðŸ”„ Typical Workflow

```
1. POST /files/               â†’ Ø§Ø±ÙØ¹ Ù…Ù„Ù ÙØ§ØªÙˆØ±Ø© (multipart)
   â†“ (Ø£ÙˆØªÙˆÙ…Ø§ØªÙŠÙƒ ÙÙŠ Ø§Ù„Ù€ background)
2. Celery job ÙŠØ¹Ù…Ù„ OCR/parse
3. Document + InvoiceItems + ExtractedItems Ø¨ÙŠØªØ¹Ù…Ù„ÙˆØ§ Ø£ÙˆØªÙˆÙ…Ø§ØªÙŠÙƒ
4. GET /documents/            â†’ Ø§ØªØ§Ø¨Ø¹ Ø§Ù„Ù€ status
5. GET /invoices/             â†’ Ø´ÙˆÙ Ø§Ù„ÙØ§ØªÙˆØ±Ø© Ø§Ù„Ù…Ø³ØªØ®Ù„ØµØ©
6. GET /price-estimations/    â†’ Ø´ÙˆÙ ØªÙ‚Ø¯ÙŠØ±Ø§Øª Ø§Ù„Ø£Ø³Ø¹Ø§Ø±
```

---

*Last updated: March 23, 2026*
