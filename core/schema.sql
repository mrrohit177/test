-- ===========================================================================
-- FarmConnect database schema (SQLite; written to stay PostgreSQL-compatible).
--  * TEXT UUID primary keys (uuid4 generated in Python)
--  * foreign keys with ON DELETE rules
--  * CHECK constraints guard money/quantity
--  * DECIMAL money stored as TEXT-free NUMERIC (SQLite affinity) -> use REAL-safe
--    NUMERIC; application layer uses Decimal for arithmetic.
--  * timestamps stored as ISO-8601 TEXT (sortable) via CURRENT_TIMESTAMP
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- --- sessions ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    data        TEXT NOT NULL DEFAULT '{}',
    expires_at  REAL NOT NULL,
    created_at  REAL NOT NULL
);

-- --- users (custom user model) ----------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                 TEXT PRIMARY KEY,
    role               TEXT NOT NULL DEFAULT 'buyer'
                         CHECK (role IN ('farmer','buyer','admin')),
    full_name          TEXT NOT NULL DEFAULT '',
    mobile             TEXT UNIQUE,
    email              TEXT UNIQUE,
    password_hash      TEXT NOT NULL,
    preferred_language TEXT NOT NULL DEFAULT 'en'
                         CHECK (preferred_language IN ('en','hi','mr')),
    avatar_path        TEXT,
    is_active          INTEGER NOT NULL DEFAULT 1,
    is_staff           INTEGER NOT NULL DEFAULT 0,
    mobile_verified    INTEGER NOT NULL DEFAULT 0,
    email_verified     INTEGER NOT NULL DEFAULT 0,
    last_login_at      TEXT,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile);

-- --- addresses --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS addresses (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label       TEXT,
    line1       TEXT,
    village     TEXT,
    taluka      TEXT,
    district    TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT 'Maharashtra',
    pincode     TEXT,
    is_primary  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_addresses_user ON addresses(user_id);
CREATE INDEX IF NOT EXISTS idx_addresses_district ON addresses(district);

-- --- farmer_profiles --------------------------------------------------------
CREATE TABLE IF NOT EXISTS farmer_profiles (
    id                 TEXT PRIMARY KEY,
    user_id            TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    display_name       TEXT,
    village            TEXT,
    taluka             TEXT,
    district           TEXT NOT NULL,
    state              TEXT NOT NULL DEFAULT 'Maharashtra',
    pincode            TEXT,
    farm_location      TEXT,
    total_land_acres   NUMERIC,
    main_crops         TEXT,                 -- comma-separated
    farming_methods    TEXT,                 -- comma-separated
    experience_years   INTEGER,
    bio                TEXT,
    verification_level TEXT NOT NULL DEFAULT 'basic'
                         CHECK (verification_level IN
                           ('basic','mobile_verified','identity_verified','farm_verified')),
    rating_avg         NUMERIC NOT NULL DEFAULT 0,
    rating_count       INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_farmer_district ON farmer_profiles(district);

-- --- buyer_profiles ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS buyer_profiles (
    id                 TEXT PRIMARY KEY,
    user_id            TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    buyer_type         TEXT NOT NULL DEFAULT 'individual'
                         CHECK (buyer_type IN
                           ('individual','wholesaler','retailer','trader',
                            'restaurant','hotel','food_processor','distributor','other_business')),
    business_name      TEXT,
    city               TEXT,
    village            TEXT,
    district           TEXT,
    state              TEXT NOT NULL DEFAULT 'Maharashtra',
    pincode            TEXT,
    business_address   TEXT,
    gst_number         TEXT,
    preferred_products TEXT,
    rating_avg         NUMERIC NOT NULL DEFAULT 0,
    rating_count       INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_buyer_type ON buyer_profiles(buyer_type);

-- --- product_categories -----------------------------------------------------
CREATE TABLE IF NOT EXISTS product_categories (
    id          TEXT PRIMARY KEY,
    parent_id   TEXT REFERENCES product_categories(id) ON DELETE SET NULL,
    name_en     TEXT NOT NULL,
    name_hi     TEXT,
    name_mr     TEXT,
    slug        TEXT NOT NULL UNIQUE,
    icon        TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1
);

-- --- products ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id                    TEXT PRIMARY KEY,
    farmer_id             TEXT NOT NULL REFERENCES farmer_profiles(id) ON DELETE CASCADE,
    category_id           TEXT REFERENCES product_categories(id) ON DELETE SET NULL,
    name                  TEXT NOT NULL,
    description           TEXT,
    grade                 TEXT NOT NULL DEFAULT 'ungraded'
                            CHECK (grade IN ('grade_a','grade_b','grade_c','ungraded')),
    quality_notes         TEXT,
    farming_method        TEXT NOT NULL DEFAULT 'conventional'
                            CHECK (farming_method IN ('organic','conventional','natural','mixed')),
    unit                  TEXT NOT NULL DEFAULT 'kg'
                            CHECK (unit IN
                              ('kg','quintal','metric_ton','gram','litre','dozen','piece','bag','box')),
    price                 NUMERIC NOT NULL CHECK (price >= 0),
    price_negotiable      INTEGER NOT NULL DEFAULT 1,
    min_order_qty         NUMERIC NOT NULL DEFAULT 1 CHECK (min_order_qty > 0),
    max_order_qty         NUMERIC,
    sales_channel         TEXT NOT NULL DEFAULT 'both'
                            CHECK (sales_channel IN ('retail','wholesale','both')),
    wholesale_min_qty     NUMERIC,
    listing_type          TEXT NOT NULL DEFAULT 'available'
                            CHECK (listing_type IN ('available','upcoming_harvest')),
    status                TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','paused','sold_out','draft','deleted')),
    harvest_date          TEXT,
    expected_availability TEXT,
    estimated_quantity    NUMERIC,
    expected_price        NUMERIC,
    freshness_info        TEXT,
    packaging_info        TEXT,
    pickup_available      INTEGER NOT NULL DEFAULT 1,
    delivery_available    INTEGER NOT NULL DEFAULT 0,
    village               TEXT,
    taluka                TEXT,
    district              TEXT NOT NULL,
    state                 TEXT NOT NULL DEFAULT 'Maharashtra',
    pincode               TEXT,
    view_count            INTEGER NOT NULL DEFAULT 0,
    enquiry_count         INTEGER NOT NULL DEFAULT 0,
    price_updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_products_farmer ON products(farmer_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_products_district ON products(district);
CREATE INDEX IF NOT EXISTS idx_products_listing ON products(listing_type);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);

-- --- product_images ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_images (
    id          TEXT PRIMARY KEY,
    product_id  TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    is_primary  INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_images_product ON product_images(product_id);

-- --- product_inventory ------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_inventory (
    id                  TEXT PRIMARY KEY,
    product_id          TEXT NOT NULL UNIQUE REFERENCES products(id) ON DELETE CASCADE,
    available_qty       NUMERIC NOT NULL DEFAULT 0 CHECK (available_qty >= 0),
    reserved_qty        NUMERIC NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
    sold_qty            NUMERIC NOT NULL DEFAULT 0 CHECK (sold_qty >= 0),
    low_stock_threshold NUMERIC NOT NULL DEFAULT 0,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- --- inventory_movements ----------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory_movements (
    id            TEXT PRIMARY KEY,
    product_id    TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    movement_type TEXT NOT NULL
                    CHECK (movement_type IN
                      ('add','sale','reservation','release','adjustment','spoilage')),
    quantity      NUMERIC NOT NULL,
    balance_after NUMERIC NOT NULL,
    reference_id  TEXT,
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_movements_product ON inventory_movements(product_id);

-- --- enquiries --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS enquiries (
    id                TEXT PRIMARY KEY,
    product_id        TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    buyer_id          TEXT NOT NULL REFERENCES buyer_profiles(id) ON DELETE CASCADE,
    farmer_id         TEXT NOT NULL REFERENCES farmer_profiles(id) ON DELETE CASCADE,
    required_qty      NUMERIC,
    delivery_district TEXT,
    expected_date     TEXT,
    message           TEXT,
    is_advance        INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','responded','closed','converted')),
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_enquiries_buyer ON enquiries(buyer_id);
CREATE INDEX IF NOT EXISTS idx_enquiries_farmer ON enquiries(farmer_id);
CREATE INDEX IF NOT EXISTS idx_enquiries_product ON enquiries(product_id);

-- --- negotiations -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS negotiations (
    id          TEXT PRIMARY KEY,
    enquiry_id  TEXT REFERENCES enquiries(id) ON DELETE SET NULL,
    product_id  TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    buyer_id    TEXT NOT NULL REFERENCES buyer_profiles(id) ON DELETE CASCADE,
    farmer_id   TEXT NOT NULL REFERENCES farmer_profiles(id) ON DELETE CASCADE,
    is_open     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_neg_buyer ON negotiations(buyer_id);
CREATE INDEX IF NOT EXISTS idx_neg_farmer ON negotiations(farmer_id);

-- --- negotiation_offers -----------------------------------------------------
CREATE TABLE IF NOT EXISTS negotiation_offers (
    id             TEXT PRIMARY KEY,
    negotiation_id TEXT NOT NULL REFERENCES negotiations(id) ON DELETE CASCADE,
    product_id     TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    made_by        TEXT NOT NULL CHECK (made_by IN ('buyer','farmer')),
    offered_qty    NUMERIC NOT NULL CHECK (offered_qty > 0),
    offered_price  NUMERIC NOT NULL CHECK (offered_price >= 0),
    unit           TEXT NOT NULL,
    message        TEXT,
    status         TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN
                       ('pending','countered','accepted','rejected','expired','withdrawn')),
    expires_at     TEXT,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_offers_neg ON negotiation_offers(negotiation_id);

-- --- orders -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id                   TEXT PRIMARY KEY,
    order_number         TEXT NOT NULL UNIQUE,
    parent_checkout_ref  TEXT,
    buyer_id             TEXT NOT NULL REFERENCES buyer_profiles(id) ON DELETE RESTRICT,
    farmer_id            TEXT NOT NULL REFERENCES farmer_profiles(id) ON DELETE RESTRICT,
    accepted_offer_id    TEXT REFERENCES negotiation_offers(id) ON DELETE SET NULL,
    status               TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN
                             ('draft','pending','accepted','rejected','negotiation','confirmed',
                              'ready_for_pickup','dispatched','delivered','completed','cancelled','disputed')),
    fulfilment_method    TEXT NOT NULL DEFAULT 'pickup'
                           CHECK (fulfilment_method IN ('pickup','delivery')),
    delivery_address_id  TEXT REFERENCES addresses(id) ON DELETE SET NULL,
    product_amount       NUMERIC NOT NULL DEFAULT 0,
    transport_amount     NUMERIC NOT NULL DEFAULT 0,
    platform_fee         NUMERIC NOT NULL DEFAULT 0,
    tax_amount           NUMERIC NOT NULL DEFAULT 0,
    total_amount         NUMERIC NOT NULL DEFAULT 0,
    payment_status       TEXT NOT NULL DEFAULT 'pending'
                           CHECK (payment_status IN
                             ('pending','paid','partially_paid','refunded','failed')),
    payment_method       TEXT NOT NULL DEFAULT 'cash_on_delivery',
    notes                TEXT,
    confirmed_at         TEXT,
    completed_at         TEXT,
    cancelled_at         TEXT,
    cancel_reason        TEXT,
    created_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders(buyer_id);
CREATE INDEX IF NOT EXISTS idx_orders_farmer ON orders(farmer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_parent ON orders(parent_checkout_ref);

-- --- order_items ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id           TEXT PRIMARY KEY,
    order_id     TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id   TEXT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    product_name TEXT NOT NULL,
    unit         TEXT NOT NULL,
    quantity     NUMERIC NOT NULL CHECK (quantity > 0),
    unit_price   NUMERIC NOT NULL CHECK (unit_price >= 0),
    line_total   NUMERIC NOT NULL,
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);

-- --- wishlists --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wishlists (
    id         TEXT PRIMARY KEY,
    buyer_id   TEXT NOT NULL REFERENCES buyer_profiles(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (buyer_id, product_id)
);

-- --- reviews ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reviews (
    id           TEXT PRIMARY KEY,
    order_id     TEXT REFERENCES orders(id) ON DELETE SET NULL,
    author_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type  TEXT NOT NULL CHECK (target_type IN ('farmer','buyer','product')),
    target_id    TEXT NOT NULL,
    rating       INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment      TEXT,
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reviews_target ON reviews(target_type, target_id);

-- --- complaints -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS complaints (
    id          TEXT PRIMARY KEY,
    raised_by   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id    TEXT REFERENCES orders(id) ON DELETE SET NULL,
    subject     TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open','investigating','resolved','dismissed')),
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- --- notifications ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT,
    link       TEXT,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);

-- --- market_prices ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_prices (
    id          TEXT PRIMARY KEY,
    commodity   TEXT NOT NULL,
    variety     TEXT,
    market      TEXT NOT NULL,
    district    TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT 'Maharashtra',
    min_price   NUMERIC,
    max_price   NUMERIC,
    modal_price NUMERIC,
    unit        TEXT NOT NULL DEFAULT 'quintal',
    arrival_date TEXT,
    source      TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_prices_commodity ON market_prices(commodity);
CREATE INDEX IF NOT EXISTS idx_prices_district ON market_prices(district);

-- --- transport_requests -----------------------------------------------------
CREATE TABLE IF NOT EXISTS transport_requests (
    id                  TEXT PRIMARY KEY,
    order_id            TEXT REFERENCES orders(id) ON DELETE SET NULL,
    requested_by        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pickup_district     TEXT NOT NULL,
    pickup_location     TEXT,
    delivery_district   TEXT NOT NULL,
    delivery_location   TEXT,
    product_type        TEXT,
    quantity            NUMERIC,
    unit                TEXT,
    estimated_weight_kg NUMERIC,
    vehicle_requirement TEXT,
    preferred_date      TEXT,
    status              TEXT NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','quoted','assigned','in_transit','delivered','cancelled')),
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transreq_by ON transport_requests(requested_by);

-- --- audit_logs -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id          TEXT PRIMARY KEY,
    actor_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity      TEXT,
    entity_id   TEXT,
    detail      TEXT,
    ip_address  TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id);
