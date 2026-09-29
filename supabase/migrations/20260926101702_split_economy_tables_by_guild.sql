-- Create one isolated set of economy tables for each configured Discord server.
-- Run this in the Supabase SQL Editor as a project administrator.

DO $$
BEGIN
    IF to_regclass('public.accounts') IS NULL
       OR to_regclass('public.shop_items') IS NULL
       OR to_regclass('public.inventory') IS NULL
       OR to_regclass('public.shared_accounts') IS NULL THEN
        RAISE EXCEPTION
            'Base economy tables are missing. Apply the economy and shared-account migrations first.';
    END IF;
END
$$;

CREATE TABLE public.accounts_1352691962817548360
    (LIKE public.accounts INCLUDING ALL);
CREATE TABLE public.shop_items_1352691962817548360
    (LIKE public.shop_items INCLUDING ALL);
CREATE TABLE public.inventory_1352691962817548360
    (LIKE public.inventory INCLUDING ALL);
CREATE TABLE public.shared_accounts_1352691962817548360
    (LIKE public.shared_accounts INCLUDING ALL);

CREATE TABLE public.accounts_1358747276754817074
    (LIKE public.accounts INCLUDING ALL);
CREATE TABLE public.shop_items_1358747276754817074
    (LIKE public.shop_items INCLUDING ALL);
CREATE TABLE public.inventory_1358747276754817074
    (LIKE public.inventory INCLUDING ALL);
CREATE TABLE public.shared_accounts_1358747276754817074
    (LIKE public.shared_accounts INCLUDING ALL);

ALTER TABLE public.accounts_1352691962817548360 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shop_items_1352691962817548360 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_1352691962817548360 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shared_accounts_1352691962817548360 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounts_1358747276754817074 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shop_items_1358747276754817074 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_1358747276754817074 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shared_accounts_1358747276754817074 ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE
    public.accounts_1352691962817548360,
    public.shop_items_1352691962817548360,
    public.inventory_1352691962817548360,
    public.shared_accounts_1352691962817548360,
    public.accounts_1358747276754817074,
    public.shop_items_1358747276754817074,
    public.inventory_1358747276754817074,
    public.shared_accounts_1358747276754817074
FROM PUBLIC, anon, authenticated, service_role;

GRANT USAGE ON SCHEMA public TO ple_bot_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.accounts_1352691962817548360,
    public.shop_items_1352691962817548360,
    public.inventory_1352691962817548360,
    public.accounts_1358747276754817074,
    public.shop_items_1358747276754817074,
    public.inventory_1358747276754817074
TO ple_bot_app;
GRANT SELECT, INSERT, UPDATE ON TABLE
    public.shared_accounts_1352691962817548360,
    public.shared_accounts_1358747276754817074
TO ple_bot_app;

DROP POLICY IF EXISTS accounts_1352691962817548360_app_all
    ON public.accounts_1352691962817548360;
CREATE POLICY accounts_1352691962817548360_app_all
    ON public.accounts_1352691962817548360 FOR ALL TO ple_bot_app
    USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS shop_items_1352691962817548360_app_all
    ON public.shop_items_1352691962817548360;
CREATE POLICY shop_items_1352691962817548360_app_all
    ON public.shop_items_1352691962817548360 FOR ALL TO ple_bot_app
    USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS inventory_1352691962817548360_app_all
    ON public.inventory_1352691962817548360;
CREATE POLICY inventory_1352691962817548360_app_all
    ON public.inventory_1352691962817548360 FOR ALL TO ple_bot_app
    USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS shared_accounts_1352691962817548360_app_all
    ON public.shared_accounts_1352691962817548360;
CREATE POLICY shared_accounts_1352691962817548360_app_all
    ON public.shared_accounts_1352691962817548360 FOR ALL TO ple_bot_app
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS accounts_1358747276754817074_app_all
    ON public.accounts_1358747276754817074;
CREATE POLICY accounts_1358747276754817074_app_all
    ON public.accounts_1358747276754817074 FOR ALL TO ple_bot_app
    USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS shop_items_1358747276754817074_app_all
    ON public.shop_items_1358747276754817074;
CREATE POLICY shop_items_1358747276754817074_app_all
    ON public.shop_items_1358747276754817074 FOR ALL TO ple_bot_app
    USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS inventory_1358747276754817074_app_all
    ON public.inventory_1358747276754817074;
CREATE POLICY inventory_1358747276754817074_app_all
    ON public.inventory_1358747276754817074 FOR ALL TO ple_bot_app
    USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS shared_accounts_1358747276754817074_app_all
    ON public.shared_accounts_1358747276754817074;
CREATE POLICY shared_accounts_1358747276754817074_app_all
    ON public.shared_accounts_1358747276754817074 FOR ALL TO ple_bot_app
    USING (true) WITH CHECK (true);
