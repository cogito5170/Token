
BEGIN;

-- 0002_usage_extras (CMD-GC24). usage_tasks.user_id: who ran the task (NULL when the source does not say).
-- prompt_prefix_hash / content_hashes (usage_calls) and first_try_success (usage_tasks) are already in 0001.
ALTER TABLE usage_tasks ADD COLUMN user_id uuid REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX usage_tasks_user ON usage_tasks (workspace_id, user_id) WHERE user_id IS NOT NULL;

COMMIT;
