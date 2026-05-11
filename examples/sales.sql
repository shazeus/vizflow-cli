CREATE TABLE sales (
  date TEXT NOT NULL,
  region TEXT NOT NULL,
  category TEXT NOT NULL,
  revenue INTEGER NOT NULL,
  orders INTEGER NOT NULL,
  margin REAL NOT NULL
);

INSERT INTO sales (date, region, category, revenue, orders, margin) VALUES
('2026-01-01', 'North', 'Hardware', 12400, 82, 0.31),
('2026-01-02', 'North', 'Software', 18350, 97, 0.54),
('2026-01-03', 'South', 'Hardware', 9700, 61, 0.27),
('2026-01-04', 'South', 'Services', 14200, 74, 0.43),
('2026-01-05', 'East', 'Software', 21100, 118, 0.57),
('2026-01-06', 'East', 'Services', 15650, 88, 0.46),
('2026-01-07', 'West', 'Hardware', 13200, 76, 0.29),
('2026-01-08', 'West', 'Software', 22400, 126, 0.59);

