-- Birthday registrations. One row per user; last_rewarded_year guards the yearly reward.
CREATE TABLE IF NOT EXISTS birthdays (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    birth_month INTEGER NOT NULL CHECK (birth_month BETWEEN 1 AND 12),
    birth_day INTEGER NOT NULL CHECK (birth_day BETWEEN 1 AND 31),
    last_rewarded_year INTEGER,
    PRIMARY KEY (guild_id, user_id)
);
