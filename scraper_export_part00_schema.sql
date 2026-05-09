-- =========================================================
-- SQL Export of scraper_data.db
-- Generated: 2026-05-09 12:18:25 UTC
-- Tables: scraper_sources, scraper_brands, scraper_categories, scraper_products, scraper_sync_logs
-- Target: MySQL / MariaDB
-- =========================================================
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
START TRANSACTION;

DROP TABLE IF EXISTS `scraper_sources`;
CREATE TABLE `scraper_sources` (
	id BIGINT NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	base_url VARCHAR(2048) NOT NULL, 
	active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `scraper_brands`;
CREATE TABLE `scraper_brands` (
	id BIGINT NOT NULL, 
	source_id BIGINT NOT NULL, 
	external_id VARCHAR(255), 
	name VARCHAR(500) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES scraper_sources (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `scraper_categories`;
CREATE TABLE `scraper_categories` (
	id BIGINT NOT NULL, 
	source_id BIGINT NOT NULL, 
	external_id VARCHAR(255), 
	name VARCHAR(500) NOT NULL, 
	url VARCHAR(2048), 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES scraper_sources (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `scraper_products`;
CREATE TABLE `scraper_products` (
	id BIGINT NOT NULL, 
	source_id BIGINT NOT NULL, 
	scraper_category_id BIGINT, 
	scraper_brand_id BIGINT, 
	external_id VARCHAR(255), 
	source_url VARCHAR(2048) NOT NULL, 
	sku VARCHAR(255), 
	name VARCHAR(1000) NOT NULL, 
	description LONGTEXT, 
	specifications LONGTEXT, 
	price NUMERIC(12, 2), 
	raw_data LONGTEXT, 
	hash VARCHAR(255), 
	is_synced BOOLEAN DEFAULT 'false' NOT NULL, 
	synced_at DATETIME, 
	last_scraped_at DATETIME, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES scraper_sources (id) ON DELETE CASCADE, 
	FOREIGN KEY(scraper_category_id) REFERENCES scraper_categories (id) ON DELETE SET NULL, 
	FOREIGN KEY(scraper_brand_id) REFERENCES scraper_brands (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `scraper_sync_logs`;
CREATE TABLE `scraper_sync_logs` (
	id BIGINT NOT NULL, 
	scraper_product_id BIGINT NOT NULL, 
	sync_status VARCHAR(50) NOT NULL, 
	request_payload LONGTEXT, 
	response_body LONGTEXT, 
	synced_at DATETIME, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(scraper_product_id) REFERENCES scraper_products (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
COMMIT;
SET FOREIGN_KEY_CHECKS=1;
