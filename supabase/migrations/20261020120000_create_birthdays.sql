-- Birthday registrations. One row per user; last_rewarded_year guards the yearly reward.
CREATE TABLE IF NOT EXISTS birthdays (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    birth_month INTEGER NOT NULL CHECK (birth_month BETWEEN 1 AND 12),
    birth_day INTEGER NOT NULL CHECK (birth_day BETWEEN 1 AND 31),
    last_rewarded_year INTEGER,
    PRIMARY KEY (guild_id, user_id)
);

-- The bot connects as ple_bot_app; grant the same table access as the other tables.
GRANT SELECT, INSERT, UPDATE, DELETE ON birthdays TO ple_bot_app;

-- Row-level security is on for the bot tables, so the bot role needs a policy as well.
ALTER TABLE birthdays ENABLE ROW LEVEL SECURITY;
CREATE POLICY birthdays_ple_bot_app_all ON birthdays
    FOR ALL TO ple_bot_app USING (true) WITH CHECK (true);
