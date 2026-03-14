-- Add support_blocked column to users table
-- Run this in Supabase SQL Editor

ALTER TABLE users ADD COLUMN IF NOT EXISTS support_blocked BOOLEAN DEFAULT FALSE;

-- Add comment for documentation
COMMENT ON COLUMN users.support_blocked IS 'Blocks second admin access to support system';
