-- Store per-server custom keyword responses for the bot.
-- Run this in the Supabase SQL Editor as a project administrator.

CREATE TABLE IF NOT EXISTS public.autoresponders (
    guild_id BIGINT NOT NULL,
    trigger_text TEXT NOT NULL CHECK (length(trigger_text) BETWEEN 1 AND 100),
    trigger_key TEXT NOT NULL,
    response TEXT NOT NULL CHECK (length(response) BETWEEN 1 AND 2000),
    match_mode TEXT NOT NULL DEFAULT 'exact'
        CHECK (match_mode IN ('exact', 'startswith', 'endswith', 'includes')),
    response_type TEXT NOT NULL DEFAULT 'text'
        CHECK (response_type IN ('text', 'embed')),
    embed_title TEXT,
    embed_color INTEGER CHECK (
        embed_color IS NULL OR embed_color BETWEEN 0 AND 16777215
    ),
    PRIMARY KEY (guild_id, trigger_key)
);

ALTER TABLE public.autoresponders ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.autoresponders
    FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA public TO ple_bot_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.autoresponders TO ple_bot_app;
DROP POLICY IF EXISTS autoresponders_app_all ON public.autoresponders;
CREATE POLICY autoresponders_app_all ON public.autoresponders
    FOR ALL TO ple_bot_app USING (true) WITH CHECK (true);

DO $$
DECLARE
    accounts_table TEXT;
    responder_table TEXT;
    policy_name TEXT;
BEGIN
    FOR accounts_table IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename ~ '^accounts_[0-9]+$'
    LOOP
        responder_table := 'autoresponders_' ||
            substring(accounts_table FROM '^accounts_([0-9]+)$');
        policy_name := responder_table || '_app_all';

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS public.%I (
                guild_id BIGINT NOT NULL,
                trigger_text TEXT NOT NULL CHECK (length(trigger_text) BETWEEN 1 AND 100),
                trigger_key TEXT NOT NULL,
                response TEXT NOT NULL CHECK (length(response) BETWEEN 1 AND 2000),
                match_mode TEXT NOT NULL DEFAULT ''exact''
                    CHECK (match_mode IN (''exact'', ''startswith'', ''endswith'', ''includes'')),
                response_type TEXT NOT NULL DEFAULT ''text''
                    CHECK (response_type IN (''text'', ''embed'')),
                embed_title TEXT,
                embed_color INTEGER CHECK (
                    embed_color IS NULL OR embed_color BETWEEN 0 AND 16777215
                ),
                PRIMARY KEY (guild_id, trigger_key)
            )',
            responder_table
        );
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', responder_table);
        EXECUTE format(
            'REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated, service_role',
            responder_table
        );
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO ple_bot_app',
            responder_table
        );
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy_name, responder_table);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR ALL TO ple_bot_app USING (true) WITH CHECK (true)',
            policy_name,
            responder_table
        );
    END LOOP;
END
$$;
