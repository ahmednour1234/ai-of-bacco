-- =========================================================
-- SQL Export of scraper_data.db
-- Generated: 2026-05-09 12:18:25 UTC
-- Tables: scraper_sources
-- Target: MySQL / MariaDB
-- Part: 1 / 1
-- =========================================================
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
START TRANSACTION;
INSERT INTO `scraper_sources` (`id`, `name`, `base_url`, `active`, `created_at`, `updated_at`) VALUES
  (1, 'El Buroj', 'https://elburoj.com', 1, '2026-04-21 16:17:02', '2026-04-21 16:17:02'),
  (2, 'KMCO', 'https://kmco.sa', 1, '2026-04-21 17:02:38', '2026-04-21 17:02:38'),
  (3, 'SchneiderElectric', 'https://eshop.se.com/sa', 1, '2026-04-21 17:08:43', '2026-04-21 17:08:43'),
  (4, 'ElectricHouse', 'https://electric-house.com/en', 1, '2026-04-21 18:23:36', '2026-04-21 18:23:36'),
  (5, 'Janoubco', 'https://janoubco.com', 1, '2026-04-22 15:19:37', '2026-04-22 15:19:37'),
  (6, 'Microless Saudi', 'https://saudi.microless.com', 1, '2026-04-22 15:57:54', '2026-04-22 15:57:54'),
  (7, 'Mejdaf', 'https://www.mejdaf.com', 1, '2026-04-22 15:58:12', '2026-04-22 15:58:12'),
  (8, 'Baytalebaa', 'https://baytalebaa.com', 1, '2026-04-22 15:58:48', '2026-04-22 15:58:48'),
  (9, 'Zorins Technologies', 'https://www.zorinstechnologies.sa', 1, '2026-04-22 14:33:26', '2026-04-22 14:33:26'),
  (10, 'elburoj', 'https://elburoj.com', 1, '2026-05-09T11:30:46.497908+00:00', '2026-05-09T11:30:46.497908+00:00'),
  (11, 'kmco', 'https://kmco.sa', 1, '2026-05-09T11:30:46.497908+00:00', '2026-05-09T11:30:46.497908+00:00'),
  (12, 'zorinstechnologies', 'https://www.zorinstechnologies.sa', 1, '2026-05-09T11:30:46.497908+00:00', '2026-05-09T11:30:46.497908+00:00');
COMMIT;
SET FOREIGN_KEY_CHECKS=1;
