CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA extensions;

CREATE TABLE public.accounts (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    balance BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0),
    last_daily TEXT,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE public.shop_items (
    guild_id BIGINT NOT NULL,
    item_name extensions.citext NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price BIGINT NOT NULL CHECK (price > 0),
    stock BIGINT CHECK (stock IS NULL OR stock >= 0),
    role_id BIGINT,
    PRIMARY KEY (guild_id, item_name)
);

CREATE TABLE public.inventory (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    item_name extensions.citext NOT NULL,
    quantity BIGINT NOT NULL CHECK (quantity > 0),
    cost_basis BIGINT NOT NULL DEFAULT 0 CHECK (cost_basis >= 0),
    PRIMARY KEY (guild_id, user_id, item_name)
);

ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shop_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.accounts, public.shop_items, public.inventory
    FROM anon, authenticated, service_role;

GRANT USAGE ON SCHEMA public TO ple_bot_app;
GRANT USAGE ON SCHEMA extensions TO ple_bot_app;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE public.accounts, public.shop_items, public.inventory
    TO ple_bot_app;

CREATE POLICY accounts_ple_bot_app_all ON public.accounts
    FOR ALL TO ple_bot_app USING (true) WITH CHECK (true);
CREATE POLICY shop_items_ple_bot_app_all ON public.shop_items
    FOR ALL TO ple_bot_app USING (true) WITH CHECK (true);
CREATE POLICY inventory_ple_bot_app_all ON public.inventory
    FOR ALL TO ple_bot_app USING (true) WITH CHECK (true);
