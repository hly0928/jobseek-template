# Tracker

Use JSON Lines:

- `applications.jsonl`: legacy compatibility name; it contains one record per
  fully assessed role, including roles never submitted. Keep the filename for
  existing readers; new runtime truth remains in `.jobseek/batches`.
- `search_runs.jsonl`: one record per completed search batch.
- `Needs_Review/`: minimum resumable material for unresolved roles.

Tracker data records compatibility/history only and is not a lossless batch
export. It never establishes candidate facts or reusable answers.
