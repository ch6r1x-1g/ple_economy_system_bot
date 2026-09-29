-- Persist fractional voice hours and keep each guild's tracking isolated.
-- Run this in the Supabase SQL Editor as a project administrator.

CREATE TABLE IF NOT EXISTS public.voice_activity (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    accrued_units BIGINT NOT NULL DEFAULT 0 CHECK (accrued_units >= 0),
    PRIMARY KEY (guild_id, user_id)
);

ALTER TABLE public.voice_activity
    ADD COLUMN IF NOT EXISTS accrued_units BIGINT NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'voice_activity'
          AND column_name = 'accrued_seconds'
    ) THEN
        UPDATE public.voice_activity
        SET accrued_units = accrued_seconds * 100
        WHERE accrued_seconds > 0 AND accrued_units = 0;
        UPDATE public.voice_activity SET accrued_seconds = 0
        WHERE accrued_seconds > 0;
    END IF;
END
$$;

ALTER TABLE public.voice_activity ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.voice_activity
    FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA public TO ple_bot_app;
GRANT SELECT, INSERT, UPDATE ON TABLE public.voice_activity TO ple_bot_app;
DROP POLICY IF EXISTS voice_activity_app_all ON public.voice_activity;
CREATE POLICY voice_activity_app_all ON public.voice_activity
    FOR ALL TO ple_bot_app USING (true) WITH CHECK (true);

DO $$
DECLARE
    accounts_table TEXT;
    activity_table TEXT;
    policy_name TEXT;
BEGIN
    FOR accounts_table IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename ~ '^accounts_[0-9]+$'
    LOOP
        activity_table := 'voice_activity_' ||
            substring(accounts_table FROM '^accounts_([0-9]+)$');
        policy_name := activity_table || '_app_all';

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS public.%I (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                accrued_units BIGINT NOT NULL DEFAULT 0 CHECK (accrued_units >= 0),
                PRIMARY KEY (guild_id, user_id)
            )',
            activity_table
        );
        EXECUTE format(
            'ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS accrued_units BIGINT NOT NULL DEFAULT 0',
            activity_table
        );
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = activity_table
              AND column_name = 'accrued_seconds'
        ) THEN
            EXECUTE format(
                'UPDATE public.%I SET accrued_units = accrued_seconds * 100 WHERE accrued_seconds > 0 AND accrued_units = 0',
                activity_table
            );
            EXECUTE format(
                'UPDATE public.%I SET accrued_seconds = 0 WHERE accrued_seconds > 0',
                activity_table
            );
        END IF;
        EXECUTE format(
            'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',
            activity_table
        );
        EXECUTE format(
            'REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated, service_role',
            activity_table
        );
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE ON TABLE public.%I TO ple_bot_app',
            activity_table
        );
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON public.%I',
            policy_name,
            activity_table
        );
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR ALL TO ple_bot_app USING (true) WITH CHECK (true)',
            policy_name,
            activity_table
        );
    END LOOP;
END
$$;
