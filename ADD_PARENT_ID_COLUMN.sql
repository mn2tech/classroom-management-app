-- Add parent_id column to existing users table (for linking students to parents)
-- Run this in Supabase SQL Editor if you get an error about parent_id column not existing

ALTER TABLE users ADD COLUMN IF NOT EXISTS parent_id TEXT;

-- Add foreign key constraint (optional, but recommended)
-- Note: This might fail if there are existing data issues, you can skip it if needed
-- ALTER TABLE users ADD CONSTRAINT fk_parent FOREIGN KEY (parent_id) REFERENCES users(id);


