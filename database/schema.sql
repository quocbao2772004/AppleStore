CREATE TABLE IF NOT EXISTS crawl_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    source TEXT NOT NULL DEFAULT 'thegioididong.com',
    pages_fetched INTEGER NOT NULL DEFAULT 0,
    products_seen INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS products (
    source_product_id BIGINT PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN ('phone','laptop','headphones','tablet','smartwatch')),
    source_category_id INTEGER,
    product_code TEXT,
    name TEXT NOT NULL,
    brand TEXT,
    model TEXT,
    description TEXT,
    url TEXT NOT NULL UNIQUE,
    canonical_url TEXT,
    thumbnail_url TEXT,
    availability TEXT,
    display_status TEXT,
    rating_value NUMERIC(3,2),
    rating_count INTEGER,
    sold_count_text TEXT,
    price_vnd BIGINT,
    original_price_vnd BIGINT,
    listing_price_vnd BIGINT,
    original_listing_price_vnd BIGINT,
    detail_price_vnd BIGINT,
    original_detail_price_vnd BIGINT,
    discount_percent NUMERIC(5,2),
    price_location TEXT DEFAULT 'Thành phố Hồ Chí Minh',
    currency CHAR(3) NOT NULL DEFAULT 'VND',
    is_live_catalog BOOLEAN NOT NULL DEFAULT false,
    colors_fetched_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    detail_fetched_at TIMESTAMPTZ,
    last_run_id BIGINT REFERENCES crawl_runs(id),
    listing_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    detail_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(name,'') || ' ' || coalesce(brand,'') || ' ' || coalesce(model,'') || ' ' || coalesce(description,''))
    ) STORED
);
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_live_catalog BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE products ADD COLUMN IF NOT EXISTS colors_fetched_at TIMESTAMPTZ;
ALTER TABLE products ADD COLUMN IF NOT EXISTS listing_price_vnd BIGINT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS original_listing_price_vnd BIGINT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS detail_price_vnd BIGINT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS original_detail_price_vnd BIGINT;
CREATE INDEX IF NOT EXISTS products_category_idx ON products(category);
CREATE INDEX IF NOT EXISTS products_brand_idx ON products(category, brand);
CREATE INDEX IF NOT EXISTS products_price_idx ON products(category, price_vnd);
CREATE INDEX IF NOT EXISTS products_search_idx ON products USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS products_detail_json_idx ON products USING GIN(detail_data);

CREATE TABLE IF NOT EXISTS product_variants (
    parent_product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    variant_product_id BIGINT NOT NULL,
    label TEXT,
    variant_url TEXT,
    group_name TEXT,
    is_selected BOOLEAN NOT NULL DEFAULT false,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(parent_product_id, variant_product_id)
);
CREATE INDEX IF NOT EXISTS variants_product_idx ON product_variants(variant_product_id);

CREATE TABLE IF NOT EXISTS product_colors (
    product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    color_name TEXT NOT NULL,
    hex_color TEXT,
    source_code TEXT,
    color_id TEXT,
    option_url TEXT,
    is_selected BOOLEAN NOT NULL DEFAULT false,
    display_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(product_id, color_name)
);
CREATE INDEX IF NOT EXISTS product_colors_product_idx ON product_colors(product_id);

CREATE TABLE IF NOT EXISTS product_color_images (
    product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    color_name TEXT NOT NULL,
    image_url TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(product_id, color_name, image_url)
);

CREATE TABLE IF NOT EXISTS product_specifications (
    product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    group_name TEXT NOT NULL DEFAULT '',
    spec_name TEXT NOT NULL,
    spec_value TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(product_id, group_name, spec_name, spec_value)
);
CREATE INDEX IF NOT EXISTS specs_name_value_idx ON product_specifications(spec_name, spec_value);

CREATE TABLE IF NOT EXISTS product_images (
    product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    alt_text TEXT,
    image_role TEXT NOT NULL DEFAULT 'gallery',
    display_order INTEGER NOT NULL DEFAULT 0,
    local_path TEXT,
    download_error TEXT,
    PRIMARY KEY(product_id, image_url)
);
ALTER TABLE product_images ADD COLUMN IF NOT EXISTS local_path TEXT;
ALTER TABLE product_images ADD COLUMN IF NOT EXISTS download_error TEXT;

CREATE TABLE IF NOT EXISTS product_offers (
    product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    offer_text TEXT NOT NULL,
    offer_type TEXT NOT NULL DEFAULT 'promotion',
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(product_id, offer_type, offer_text)
);

CREATE TABLE IF NOT EXISTS product_reviews (
    product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    review_index INTEGER NOT NULL,
    author_name TEXT,
    rating_value NUMERIC(3,2),
    review_body TEXT,
    published_at_text TEXT,
    PRIMARY KEY(product_id, review_index)
);

CREATE TABLE IF NOT EXISTS price_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    price_vnd BIGINT,
    original_price_vnd BIGINT,
    location TEXT NOT NULL DEFAULT 'Thành phố Hồ Chí Minh',
    availability TEXT,
    run_id BIGINT REFERENCES crawl_runs(id),
    CHECK (price_vnd IS NOT NULL OR original_price_vnd IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS price_history_product_time_idx ON price_history(product_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS crawl_errors (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id BIGINT REFERENCES crawl_runs(id),
    url TEXT NOT NULL,
    stage TEXT NOT NULL,
    error TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS discovery_urls (
    url TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN ('phone','laptop','headphones','tablet','smartwatch')),
    source TEXT NOT NULL,
    sitemap_lastmod DATE,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fetched_at TIMESTAMPTZ,
    fetch_status TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS discovery_pending_idx ON discovery_urls(category, discovered_at) WHERE fetched_at IS NULL;

CREATE TABLE IF NOT EXISTS sitemap_pages (
    url TEXT PRIMARY KEY,
    fetched_at TIMESTAMPTZ,
    url_count INTEGER,
    error TEXT
);

CREATE TABLE IF NOT EXISTS catalog_segments (
    url TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN ('phone','laptop','headphones','tablet','smartwatch')),
    expected_count INTEGER,
    observed_count INTEGER NOT NULL,
    overflow BOOLEAN NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_id BIGINT REFERENCES crawl_runs(id)
);
CREATE INDEX IF NOT EXISTS catalog_segments_overflow_idx ON catalog_segments(category) WHERE overflow;

CREATE TABLE IF NOT EXISTS catalog_segment_products (
    segment_url TEXT NOT NULL REFERENCES catalog_segments(url) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(source_product_id) ON DELETE CASCADE,
    PRIMARY KEY(segment_url, product_id)
);
CREATE INDEX IF NOT EXISTS catalog_segment_products_product_idx ON catalog_segment_products(product_id);

DROP VIEW IF EXISTS agent_product_catalog;
CREATE VIEW agent_product_catalog AS
SELECT p.source_product_id, p.category, p.name, p.brand, p.model, p.description,
       p.price_vnd, p.original_price_vnd, p.currency, p.price_location,
       p.listing_price_vnd, p.detail_price_vnd,
       p.is_live_catalog,
       p.availability, p.display_status, p.rating_value, p.rating_count,
       p.sold_count_text, p.url, p.thumbnail_url, p.last_seen_at, p.detail_fetched_at,
       p.detail_data,
       p.listing_data #>> '{card_attributes,data-statusvalue}' AS source_status_code,
       COALESCE((SELECT jsonb_agg(jsonb_build_object('group',s.group_name,'name',s.spec_name,
                      'value',s.spec_value) ORDER BY s.display_order,s.spec_name)
                 FROM product_specifications s WHERE s.product_id=p.source_product_id),'[]'::jsonb) AS specifications,
       COALESCE((SELECT jsonb_agg(jsonb_build_object('url',i.image_url,'role',i.image_role,
                      'alt',i.alt_text,'local_path',i.local_path) ORDER BY i.display_order)
                 FROM product_images i WHERE i.product_id=p.source_product_id),'[]'::jsonb) AS images,
       COALESCE((SELECT jsonb_agg(jsonb_build_object('name',c.color_name,'hex',c.hex_color,
                      'selected',c.is_selected) ORDER BY c.display_order)
                 FROM product_colors c WHERE c.product_id=p.source_product_id),'[]'::jsonb) AS colors,
       COALESCE((SELECT jsonb_agg(jsonb_build_object('id',v.variant_product_id,'label',v.label,
                      'url',v.variant_url,'selected',v.is_selected))
                 FROM product_variants v WHERE v.parent_product_id=p.source_product_id),'[]'::jsonb) AS variants,
       COALESCE((SELECT jsonb_agg(jsonb_build_object('text',o.offer_text,'type',o.offer_type,
                      'last_seen_at',o.last_seen_at))
                 FROM product_offers o WHERE o.product_id=p.source_product_id),'[]'::jsonb) AS offers,
       COALESCE((SELECT jsonb_agg(jsonb_build_object('author',r.author_name,'rating',r.rating_value,
                      'body',r.review_body,'published_at',r.published_at_text) ORDER BY r.review_index)
                 FROM product_reviews r WHERE r.product_id=p.source_product_id),'[]'::jsonb) AS reviews
FROM products p;
