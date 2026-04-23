import sqlite3
c = sqlite3.connect('scraper_data.db')
q = "SELECT s.name, COUNT(*) total, SUM(CASE WHEN p.price>0 THEN 1 ELSE 0 END) priced, SUM(CASE WHEN p.price IS NULL OR p.price=0 THEN 1 ELSE 0 END) missing FROM scraper_products p JOIN scraper_sources s ON p.source_id=s.id GROUP BY s.name ORDER BY total DESC"
for r in c.execute(q).fetchall():
    pct = round(100*r[2]/r[1]) if r[1] else 0
    print(f'{r[0]:30} total={r[1]:6}  priced={r[2]:6} ({pct}%)  missing={r[3]}')

