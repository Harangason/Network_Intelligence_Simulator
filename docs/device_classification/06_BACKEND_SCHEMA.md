# Backend Schema

Schema version 17 adds device classification columns to `engineering_hardware_nodes`.

Existing projects receive defaults through `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
