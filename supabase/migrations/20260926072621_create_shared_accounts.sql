CREATE TABLE public.shared_accounts (
    guild_id BIGINT PRIMARY KEY,
    balance BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0)
);

ALTER TABLE public.shared_accounts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.shared_accounts
    FROM PUBLIC, anon, authenticated, service_role;

GRANT SELECT, INSERT, UPDATE ON TABLE public.shared_accounts TO ple_bot_app;

CREATE POLICY shared_accounts_ple_bot_app_all ON public.shared_accounts
    FOR ALL TO ple_bot_app
    USING (true)
    WITH CHECK (true);
