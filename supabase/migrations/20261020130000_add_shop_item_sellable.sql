-- Whether a shop item can be sold back to the shop. Existing items stay sellable.
ALTER TABLE shop_items
    ADD COLUMN IF NOT EXISTS sellable INTEGER NOT NULL DEFAULT 1 CHECK (sellable IN (0, 1));
