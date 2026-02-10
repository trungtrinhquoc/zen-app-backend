-- Migration: Add deleted_at column to conversations table
-- Date: 2026-02-09
-- Description: Add soft delete support for conversations

-- Add deleted_at column
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

-- Create index for better query performance on non-deleted conversations
CREATE INDEX IF NOT EXISTS idx_conversations_deleted_at 
ON conversations(deleted_at) 
WHERE deleted_at IS NULL;

-- Add comment
COMMENT ON COLUMN conversations.deleted_at IS 'Timestamp when conversation was soft-deleted. NULL means not deleted.';
