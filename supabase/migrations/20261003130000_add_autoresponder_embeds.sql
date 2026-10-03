-- Add embed response fields to base and per-server autoresponder tables.
-- Run this in the Supabase SQL Editor as a project administrator.

ALTER TABLE public.autoresponders
    ADD COLUMN IF NOT EXISTS response_type TEXT NOT NULL DEFAULT 'text'
        CHECK (response_type IN ('text', 'embed'));
ALTER TABLE public.autoresponders
    ADD COLUMN IF NOT EXISTS embed_title TEXT;
ALTER TABLE public.autoresponders
    ADD COLUMN IF NOT EXISTS embed_color INTEGER
        CHECK (embed_color IS NULL OR embed_color BETWEEN 0 AND 16777215);

DO $$
DECLARE
    accounts_table TEXT;
    responder_table TEXT;
BEGIN
    FOR accounts_table IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename ~ '^accounts_[0-9]+$'
    LOOP
        responder_table := 'autoresponders_' ||
            substring(accounts_table FROM '^accounts_([0-9]+)$');

        EXECUTE format(
            'ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS response_type TEXT NOT NULL DEFAULT ''text'' CHECK (response_type IN (''text'', ''embed''))',
            responder_table
        );
        EXECUTE format(
            'ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS embed_title TEXT',
            responder_table
        );
        EXECUTE format(
            'ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS embed_color INTEGER CHECK (embed_color IS NULL OR embed_color BETWEEN 0 AND 16777215)',
            responder_table
        );
    END LOOP;
END
$$;
