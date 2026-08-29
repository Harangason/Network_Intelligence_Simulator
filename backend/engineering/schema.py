"""Versioniertes Postgres-Schema fuer das kanonische Engineering-Modell."""

from __future__ import annotations

from collections.abc import Iterable

SCHEMA_VERSION = 13
MIGRATION_LOCK_ID = 1_947_042_611


MIGRATION_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS engineering_schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_hardware_nodes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        description TEXT,
        domain TEXT,
        device_type TEXT NOT NULL DEFAULT 'GenericDevice',
        identity JSONB NOT NULL DEFAULT '{}'::jsonb,
        product_information JSONB NOT NULL DEFAULT '{}'::jsonb,
        hardware_information JSONB NOT NULL DEFAULT '{}'::jsonb,
        software_information JSONB NOT NULL DEFAULT '{}'::jsonb,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        lifecycle_state TEXT NOT NULL DEFAULT 'draft'
            CHECK (lifecycle_state IN ('draft', 'active', 'deprecated', 'superseded')),
        source TEXT NOT NULL DEFAULT 'manual'
            CHECK (source IN ('manual', 'import', 'ai_generated', 'simulation_derived')),
        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        review_state TEXT NOT NULL DEFAULT 'unreviewed'
            CHECK (review_state IN ('unreviewed', 'in_review', 'reviewed', 'rejected')),
        approval_state TEXT NOT NULL DEFAULT 'pending'
            CHECK (approval_state IN ('pending', 'approved', 'rejected')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_functions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        description TEXT,
        domain TEXT,
        hardware_node_id UUID REFERENCES engineering_hardware_nodes(id) ON DELETE SET NULL,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        lifecycle_state TEXT NOT NULL DEFAULT 'draft'
            CHECK (lifecycle_state IN ('draft', 'active', 'deprecated', 'superseded')),
        source TEXT NOT NULL DEFAULT 'manual'
            CHECK (source IN ('manual', 'import', 'ai_generated', 'simulation_derived')),
        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        review_state TEXT NOT NULL DEFAULT 'unreviewed'
            CHECK (review_state IN ('unreviewed', 'in_review', 'reviewed', 'rejected')),
        approval_state TEXT NOT NULL DEFAULT 'pending'
            CHECK (approval_state IN ('pending', 'approved', 'rejected')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_interfaces (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        description TEXT,
        domain TEXT,
        hardware_node_id UUID REFERENCES engineering_hardware_nodes(id) ON DELETE SET NULL,
        function_id UUID REFERENCES engineering_functions(id) ON DELETE SET NULL,
        interface_type TEXT NOT NULL,
        configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        lifecycle_state TEXT NOT NULL DEFAULT 'draft'
            CHECK (lifecycle_state IN ('draft', 'active', 'deprecated', 'superseded')),
        source TEXT NOT NULL DEFAULT 'manual'
            CHECK (source IN ('manual', 'import', 'ai_generated', 'simulation_derived')),
        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        review_state TEXT NOT NULL DEFAULT 'unreviewed'
            CHECK (review_state IN ('unreviewed', 'in_review', 'reviewed', 'rejected')),
        approval_state TEXT NOT NULL DEFAULT 'pending'
            CHECK (approval_state IN ('pending', 'approved', 'rejected')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        description TEXT,
        domain TEXT,
        interface_id UUID REFERENCES engineering_interfaces(id) ON DELETE SET NULL,
        message_id_hex TEXT,
        direction TEXT CHECK (direction IS NULL OR direction IN ('rx', 'tx', 'bidirectional')),
        cycle_ms DOUBLE PRECISION CHECK (cycle_ms IS NULL OR cycle_ms > 0),
        dlc INTEGER CHECK (dlc IS NULL OR dlc >= 0),
        configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        lifecycle_state TEXT NOT NULL DEFAULT 'draft'
            CHECK (lifecycle_state IN ('draft', 'active', 'deprecated', 'superseded')),
        source TEXT NOT NULL DEFAULT 'manual'
            CHECK (source IN ('manual', 'import', 'ai_generated', 'simulation_derived')),
        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        review_state TEXT NOT NULL DEFAULT 'unreviewed'
            CHECK (review_state IN ('unreviewed', 'in_review', 'reviewed', 'rejected')),
        approval_state TEXT NOT NULL DEFAULT 'pending'
            CHECK (approval_state IN ('pending', 'approved', 'rejected')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_signals (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        description TEXT,
        domain TEXT,
        message_id UUID REFERENCES engineering_messages(id) ON DELETE SET NULL,
        display_name TEXT,
        start_bit INTEGER CHECK (start_bit IS NULL OR start_bit >= 0),
        length_bits INTEGER CHECK (length_bits IS NULL OR length_bits > 0),
        byte_order TEXT CHECK (byte_order IS NULL OR byte_order IN ('little_endian', 'big_endian')),
        data_type TEXT,
        factor DOUBLE PRECISION,
        offset_value DOUBLE PRECISION,
        unit TEXT,
        min_value DOUBLE PRECISION,
        max_value DOUBLE PRECISION,
        configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
        semantic JSONB NOT NULL DEFAULT '{}'::jsonb,
        data JSONB NOT NULL DEFAULT '{}'::jsonb,
        communication JSONB NOT NULL DEFAULT '{}'::jsonb,
        quality JSONB NOT NULL DEFAULT '{}'::jsonb,
        protocol_bindings JSONB NOT NULL DEFAULT '[]'::jsonb,
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        lifecycle_state TEXT NOT NULL DEFAULT 'draft'
            CHECK (lifecycle_state IN ('draft', 'active', 'deprecated', 'superseded')),
        source TEXT NOT NULL DEFAULT 'manual'
            CHECK (source IN ('manual', 'import', 'ai_generated', 'simulation_derived')),
        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        review_state TEXT NOT NULL DEFAULT 'unreviewed'
            CHECK (review_state IN ('unreviewed', 'in_review', 'reviewed', 'rejected')),
        approval_state TEXT NOT NULL DEFAULT 'pending'
            CHECK (approval_state IN ('pending', 'approved', 'rejected')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_relations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        relation_type TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_id UUID NOT NULL,
        target_type TEXT NOT NULL,
        target_id UUID NOT NULL,
        attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
        source TEXT NOT NULL DEFAULT 'manual',
        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        review_state TEXT NOT NULL DEFAULT 'unreviewed',
        approval_state TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        UNIQUE (relation_type, source_type, source_id, target_type, target_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_object_versions (
        id BIGSERIAL PRIMARY KEY,
        project_id TEXT NOT NULL DEFAULT 'default',
        object_type TEXT NOT NULL,
        object_id UUID NOT NULL,
        version INTEGER NOT NULL,
        snapshot JSONB NOT NULL,
        change_summary TEXT,
        changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        changed_by TEXT,
        UNIQUE (object_type, object_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_ai_proposals (
        proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        proposal_type TEXT NOT NULL,
        target_object JSONB NOT NULL DEFAULT '{}'::jsonb,
        prompt TEXT NOT NULL,
        model TEXT,
        model_version TEXT,
        retrieved_context JSONB NOT NULL DEFAULT '[]'::jsonb,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        proposed_objects JSONB NOT NULL DEFAULT '[]'::jsonb,
        validation_results JSONB NOT NULL DEFAULT '[]'::jsonb,
        status TEXT NOT NULL DEFAULT 'AI_GENERATED'
            CHECK (status IN ('AI_GENERATED', 'DRAFT', 'READY_FOR_REVIEW',
                'PARTIALLY_APPROVED', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_eng_nodes_domain ON engineering_hardware_nodes(domain)",
    "CREATE INDEX IF NOT EXISTS idx_eng_functions_node ON engineering_functions(hardware_node_id)",
    "ALTER TABLE engineering_interfaces ADD COLUMN IF NOT EXISTS function_id UUID REFERENCES engineering_functions(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS idx_eng_interfaces_node ON engineering_interfaces(hardware_node_id)",
    "CREATE INDEX IF NOT EXISTS idx_eng_interfaces_function ON engineering_interfaces(function_id)",
    "CREATE INDEX IF NOT EXISTS idx_eng_messages_interface ON engineering_messages(interface_id)",
    "CREATE INDEX IF NOT EXISTS idx_eng_signals_message ON engineering_signals(message_id)",
    "CREATE INDEX IF NOT EXISTS idx_eng_relations_source ON engineering_relations(source_type, source_id)",
    "CREATE INDEX IF NOT EXISTS idx_eng_relations_target ON engineering_relations(target_type, target_id)",
    "CREATE INDEX IF NOT EXISTS idx_eng_proposals_status ON engineering_ai_proposals(status, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS engineering_routing_entries (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        route_code TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
        supersedes_id UUID REFERENCES engineering_routing_entries(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        description TEXT,
        source JSONB NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        destinations JSONB NOT NULL DEFAULT '[]'::jsonb,
        route JSONB NOT NULL DEFAULT '{}'::jsonb,
        timing JSONB NOT NULL DEFAULT '{}'::jsonb,
        routing_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
        validation JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'DRAFT'
            CHECK (status IN ('DRAFT', 'PENDING_CONFIRMATION', 'READY_FOR_REVIEW',
                'APPROVED', 'RELEASED', 'REJECTED', 'CONFLICT', 'SUPERSEDED',
                'DEPRECATED', 'OUTDATED')),
        origin TEXT NOT NULL DEFAULT 'MANUAL'
            CHECK (origin IN ('MANUAL', 'IMPORTED', 'AI_GENERATED', 'AI_MODIFIED',
                'DERIVED', 'NETWORK_EDITOR')),
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        review_state TEXT NOT NULL DEFAULT 'UNREVIEWED'
            CHECK (review_state IN ('UNREVIEWED', 'IN_REVIEW', 'REVIEWED', 'REJECTED')),
        approval_state TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (approval_state IN ('PENDING', 'APPROVED', 'REJECTED')),
        source_id TEXT,
        source_version TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT,
        approved_at TIMESTAMPTZ,
        approved_by TEXT,
        UNIQUE (route_code, revision)
    )
    """,
    "ALTER TABLE engineering_routing_entries DROP CONSTRAINT IF EXISTS engineering_routing_entries_status_check",
    """
    ALTER TABLE engineering_routing_entries
    ADD CONSTRAINT engineering_routing_entries_status_check
    CHECK (status IN ('DRAFT', 'PENDING_CONFIRMATION', 'READY_FOR_REVIEW',
        'APPROVED', 'RELEASED', 'REJECTED', 'CONFLICT', 'SUPERSEDED',
        'DEPRECATED', 'OUTDATED'))
    """,
    "ALTER TABLE engineering_routing_entries DROP CONSTRAINT IF EXISTS engineering_routing_entries_origin_check",
    """
    ALTER TABLE engineering_routing_entries
    ADD CONSTRAINT engineering_routing_entries_origin_check
    CHECK (origin IN ('MANUAL', 'IMPORTED', 'AI_GENERATED', 'AI_MODIFIED',
        'DERIVED', 'NETWORK_EDITOR'))
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_routing_proposals (
        proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        prompt TEXT NOT NULL,
        target_objects JSONB NOT NULL DEFAULT '[]'::jsonb,
        generated_routes JSONB NOT NULL DEFAULT '[]'::jsonb,
        retrieved_context JSONB NOT NULL DEFAULT '[]'::jsonb,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        validation_results JSONB NOT NULL DEFAULT '[]'::jsonb,
        model TEXT,
        model_version TEXT,
        status TEXT NOT NULL DEFAULT 'AI_GENERATED'
            CHECK (status IN ('AI_GENERATED', 'DRAFT', 'VALIDATED', 'READY_FOR_REVIEW',
                'PARTIALLY_APPROVED', 'APPROVED', 'REJECTED', 'SUPERSEDED')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_routing_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        condition JSONB NOT NULL,
        action JSONB NOT NULL,
        priority TEXT NOT NULL DEFAULT 'NORMAL',
        status TEXT NOT NULL DEFAULT 'DRAFT',
        version INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT,
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_routing_audit (
        id BIGSERIAL PRIMARY KEY,
        project_id TEXT NOT NULL DEFAULT 'default',
        route_id UUID,
        action TEXT NOT NULL,
        actor TEXT,
        agent TEXT,
        model TEXT,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        before_state JSONB,
        after_state JSONB,
        reason TEXT,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_routing_status ON engineering_routing_entries(status, approval_state, modified_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_routing_source_node ON engineering_routing_entries((source ->> 'node_id'))",
    "CREATE INDEX IF NOT EXISTS idx_routing_proposals_status ON engineering_routing_proposals(status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_routing_audit_route ON engineering_routing_audit(route_id, occurred_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS engineering_workflow_projects (
        project_id TEXT PRIMARY KEY,
        active_step TEXT NOT NULL DEFAULT 'engineering_model',
        versions JSONB NOT NULL DEFAULT '{}'::jsonb,
        statuses JSONB NOT NULL DEFAULT '{}'::jsonb,
        stale_reasons JSONB NOT NULL DEFAULT '{}'::jsonb,
        context JSONB NOT NULL DEFAULT '{}'::jsonb,
        parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
        topology JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_analysis_snapshots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL REFERENCES engineering_workflow_projects(project_id) ON DELETE CASCADE,
        analysis_type TEXT NOT NULL,
        source_versions JSONB NOT NULL,
        input_data JSONB NOT NULL DEFAULT '{}'::jsonb,
        results JSONB NOT NULL DEFAULT '{}'::jsonb,
        findings JSONB NOT NULL DEFAULT '[]'::jsonb,
        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'COMPLETE',
        is_outdated BOOLEAN NOT NULL DEFAULT FALSE,
        outdated_reason TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_simulation_snapshots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL REFERENCES engineering_workflow_projects(project_id) ON DELETE CASCADE,
        source_versions JSONB NOT NULL,
        validation_snapshot_id UUID REFERENCES engineering_analysis_snapshots(id) ON DELETE RESTRICT,
        configuration JSONB NOT NULL,
        calculated_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'READY',
        job_id TEXT,
        is_outdated BOOLEAN NOT NULL DEFAULT FALSE,
        outdated_reason TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_workflow_events (
        id BIGSERIAL PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES engineering_workflow_projects(project_id) ON DELETE CASCADE,
        step TEXT NOT NULL,
        event_type TEXT NOT NULL,
        reason TEXT,
        source_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
        actor TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_optimization_proposals (
        proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL REFERENCES engineering_workflow_projects(project_id) ON DELETE CASCADE,
        source_snapshot_id UUID REFERENCES engineering_analysis_snapshots(id) ON DELETE SET NULL,
        category TEXT NOT NULL,
        problem TEXT NOT NULL,
        affected_objects JSONB NOT NULL DEFAULT '[]'::jsonb,
        recommendation TEXT NOT NULL,
        expected_impact JSONB NOT NULL DEFAULT '{}'::jsonb,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        graph_context JSONB NOT NULL DEFAULT '[]'::jsonb,
        rag_context JSONB NOT NULL DEFAULT '[]'::jsonb,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        priority INTEGER NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
        implementation_effort TEXT NOT NULL DEFAULT 'MEDIUM',
        provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'PROPOSED'
            CHECK (status IN ('PROPOSED', 'UNDER_REVIEW', 'ACCEPTED', 'REJECTED',
                'APPLIED_AS_DRAFT', 'SUPERSEDED')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        reviewed_by TEXT,
        review_reason TEXT
    )
    """,
    "ALTER TABLE engineering_simulation_snapshots ADD COLUMN IF NOT EXISTS result JSONB NOT NULL DEFAULT '{}'::jsonb",
    "CREATE INDEX IF NOT EXISTS idx_workflow_analysis_latest ON engineering_analysis_snapshots(project_id, analysis_type, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_simulations_latest ON engineering_simulation_snapshots(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_events_project ON engineering_workflow_events(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_optimization_proposals_project ON engineering_optimization_proposals(project_id, status, priority DESC, created_at DESC)",
    "ALTER TABLE engineering_hardware_nodes ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_functions ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_interfaces ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_messages ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_signals ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_relations ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_object_versions ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_ai_proposals ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_routing_entries ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_routing_proposals ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_routing_rules ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "ALTER TABLE engineering_routing_audit ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'default'",
    "CREATE INDEX IF NOT EXISTS idx_eng_nodes_project ON engineering_hardware_nodes(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_eng_functions_project ON engineering_functions(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_eng_interfaces_project ON engineering_interfaces(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_eng_messages_project ON engineering_messages(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_eng_signals_project ON engineering_signals(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_eng_relations_project ON engineering_relations(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_eng_proposals_project ON engineering_ai_proposals(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_routing_entries_project ON engineering_routing_entries(project_id, modified_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_routing_proposals_project ON engineering_routing_proposals(project_id, modified_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_routing_rules_project ON engineering_routing_rules(project_id, modified_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_routing_audit_project ON engineering_routing_audit(project_id, occurred_at DESC)",
    "ALTER TABLE engineering_relations DROP CONSTRAINT IF EXISTS engineering_relations_relation_type_source_type_source_id_t_key",
    "ALTER TABLE engineering_object_versions DROP CONSTRAINT IF EXISTS engineering_object_versions_object_type_object_id_version_key",
    "ALTER TABLE engineering_routing_entries DROP CONSTRAINT IF EXISTS engineering_routing_entries_route_code_revision_key",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'engineering_relations'::regclass
              AND conname = 'engineering_relations_project_unique'
        ) THEN
            ALTER TABLE engineering_relations
                ADD CONSTRAINT engineering_relations_project_unique
                UNIQUE (project_id, relation_type, source_type, source_id, target_type, target_id);
        END IF;
    END $$
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'engineering_object_versions'::regclass
              AND conname = 'engineering_object_versions_project_unique'
        ) THEN
            ALTER TABLE engineering_object_versions
                ADD CONSTRAINT engineering_object_versions_project_unique
                UNIQUE (project_id, object_type, object_id, version);
        END IF;
    END $$
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'engineering_routing_entries'::regclass
              AND conname = 'engineering_routing_entries_project_unique'
        ) THEN
            ALTER TABLE engineering_routing_entries
                ADD CONSTRAINT engineering_routing_entries_project_unique
                UNIQUE (project_id, route_code, revision);
        END IF;
    END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_workloads (
        workload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        parent_workload_id UUID REFERENCES engineering_workloads(workload_id) ON DELETE SET NULL,
        workload_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        prompt TEXT NOT NULL,
        domain TEXT,
        target_object TEXT NOT NULL,
        requested_total INTEGER NOT NULL CHECK (requested_total > 0),
        constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
        dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
        validation_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
        completion_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
        status TEXT NOT NULL DEFAULT 'RECEIVED'
            CHECK (status IN ('RECEIVED', 'PLANNING', 'IN_PROGRESS', 'VALIDATING',
                'INCOMPLETE', 'READY_FOR_REVIEW', 'COMPLETED', 'FAILED', 'BLOCKED',
                'NEEDS_REVIEW', 'PAUSED', 'CANCELED')),
        requested_count INTEGER NOT NULL DEFAULT 0,
        generated_count INTEGER NOT NULL DEFAULT 0,
        valid_count INTEGER NOT NULL DEFAULT 0,
        invalid_count INTEGER NOT NULL DEFAULT 0,
        duplicate_count INTEGER NOT NULL DEFAULT 0,
        missing_count INTEGER NOT NULL DEFAULT 0,
        attempts INTEGER NOT NULL DEFAULT 0,
        max_generation_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_generation_attempts > 0),
        metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
        findings JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_objects JSONB NOT NULL DEFAULT '[]'::jsonb,
        agent TEXT,
        model TEXT,
        created_by TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_work_packages (
        work_package_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workload_id UUID NOT NULL REFERENCES engineering_workloads(workload_id) ON DELETE CASCADE,
        package_code TEXT NOT NULL,
        category TEXT NOT NULL,
        target_object TEXT NOT NULL,
        requested_count INTEGER NOT NULL CHECK (requested_count > 0),
        generated_count INTEGER NOT NULL DEFAULT 0,
        valid_count INTEGER NOT NULL DEFAULT 0,
        invalid_count INTEGER NOT NULL DEFAULT 0,
        duplicate_count INTEGER NOT NULL DEFAULT 0,
        missing_count INTEGER NOT NULL DEFAULT 0,
        attempts INTEGER NOT NULL DEFAULT 0,
        max_generation_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_generation_attempts > 0),
        status TEXT NOT NULL DEFAULT 'RECEIVED',
        configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
        findings JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_objects JSONB NOT NULL DEFAULT '[]'::jsonb,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (workload_id, package_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_workload_objects (
        workload_object_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workload_id UUID NOT NULL REFERENCES engineering_workloads(workload_id) ON DELETE CASCADE,
        work_package_id UUID NOT NULL REFERENCES engineering_work_packages(work_package_id) ON DELETE CASCADE,
        object_type TEXT NOT NULL,
        object_key TEXT NOT NULL,
        category TEXT NOT NULL,
        definition JSONB NOT NULL,
        validation_results JSONB NOT NULL DEFAULT '[]'::jsonb,
        is_valid BOOLEAN NOT NULL DEFAULT FALSE,
        is_duplicate BOOLEAN NOT NULL DEFAULT FALSE,
        duplicate_of TEXT,
        canonical_id UUID,
        proposal_id UUID REFERENCES engineering_ai_proposals(proposal_id) ON DELETE SET NULL,
        proposal_index INTEGER,
        review_state TEXT NOT NULL DEFAULT 'UNREVIEWED',
        approval_state TEXT NOT NULL DEFAULT 'PENDING',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (workload_id, object_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_workload_dependencies (
        workload_id UUID NOT NULL REFERENCES engineering_workloads(workload_id) ON DELETE CASCADE,
        dependency_workload_id UUID NOT NULL REFERENCES engineering_workloads(workload_id) ON DELETE CASCADE,
        required_status TEXT NOT NULL DEFAULT 'COMPLETED',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (workload_id, dependency_workload_id),
        CHECK (workload_id <> dependency_workload_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_workload_events (
        event_id BIGSERIAL PRIMARY KEY,
        project_id TEXT NOT NULL DEFAULT 'default',
        workload_id UUID NOT NULL REFERENCES engineering_workloads(workload_id) ON DELETE CASCADE,
        work_package_id UUID REFERENCES engineering_work_packages(work_package_id) ON DELETE SET NULL,
        event_type TEXT NOT NULL,
        actor TEXT,
        agent TEXT,
        model TEXT,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_workloads_project ON engineering_workloads(project_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_workloads_status ON engineering_workloads(project_id, status, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_work_packages_workload ON engineering_work_packages(workload_id, package_code)",
    "CREATE INDEX IF NOT EXISTS idx_workload_objects_workload ON engineering_workload_objects(workload_id, category, is_valid)",
    "CREATE INDEX IF NOT EXISTS idx_workload_objects_proposal ON engineering_workload_objects(proposal_id, proposal_index)",
    "CREATE INDEX IF NOT EXISTS idx_workload_events_workload ON engineering_workload_events(workload_id, occurred_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS engineering_signal_behaviors (
        behavior_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        signal_id UUID NOT NULL REFERENCES engineering_signals(id) ON DELETE CASCADE,
        behavior_type TEXT NOT NULL CHECK (behavior_type IN (
            'CONSTANT', 'STEP', 'RAMP', 'LINEAR', 'SINE', 'TRIANGLE',
            'SAWTOOTH', 'PULSE', 'RANDOM_WALK', 'BOUNDED_RANDOM',
            'STATE_DEPENDENT', 'FORMULA', 'LOOKUP_TABLE', 'EXTERNAL_SERIES'
        )),
        model_label TEXT NOT NULL DEFAULT 'GENERIC_ESTIMATE' CHECK (model_label IN (
            'PHYSICS_BASED', 'RULE_BASED', 'EMPIRICAL', 'SYNTHETIC', 'GENERIC_ESTIMATE'
        )),
        parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
        dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
        source TEXT NOT NULL DEFAULT 'manual',
        review_state TEXT NOT NULL DEFAULT 'reviewed',
        approval_state TEXT NOT NULL DEFAULT 'approved',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (project_id, signal_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_simulation_scenarios (
        scenario_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'NORMAL' CHECK (mode IN (
            'NORMAL', 'USER_DEFINED_FAULT', 'AI_GENERATED_FAULT', 'STRESS'
        )),
        duration_s DOUBLE PRECISION NOT NULL DEFAULT 1 CHECK (duration_s > 0),
        speed DOUBLE PRECISION NOT NULL DEFAULT 1 CHECK (speed > 0),
        seed BIGINT NOT NULL DEFAULT 42,
        trace_formats JSONB NOT NULL DEFAULT '["universal-jsonl"]'::jsonb,
        faults JSONB NOT NULL DEFAULT '[]'::jsonb,
        baseline_scenario_id UUID REFERENCES engineering_simulation_scenarios(scenario_id) ON DELETE SET NULL,
        source TEXT NOT NULL DEFAULT 'manual',
        review_state TEXT NOT NULL DEFAULT 'reviewed',
        approval_state TEXT NOT NULL DEFAULT 'approved',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_fault_proposals (
        proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        scenario_id UUID REFERENCES engineering_simulation_scenarios(scenario_id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        fault_scope TEXT NOT NULL CHECK (fault_scope IN ('SIGNAL', 'MESSAGE', 'NETWORK')),
        fault_type TEXT NOT NULL,
        target JSONB NOT NULL DEFAULT '{}'::jsonb,
        configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
        rationale TEXT NOT NULL,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        model TEXT,
        status TEXT NOT NULL DEFAULT 'READY_FOR_REVIEW' CHECK (status IN (
            'AI_GENERATED', 'READY_FOR_REVIEW', 'APPROVED', 'REJECTED', 'SUPERSEDED'
        )),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        reviewed_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_trace_metadata (
        trace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        job_id TEXT NOT NULL,
        scenario_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
        model_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
        seed BIGINT NOT NULL,
        trace_formats JSONB NOT NULL DEFAULT '[]'::jsonb,
        artifact_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
        trace_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (project_id, job_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_simulation_campaigns (
        campaign_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id TEXT NOT NULL DEFAULT 'default',
        name TEXT NOT NULL,
        configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED', 'CANCELED')),
        total_runs INTEGER NOT NULL CHECK (total_runs > 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        completed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engineering_simulation_campaign_runs (
        campaign_id UUID NOT NULL REFERENCES engineering_simulation_campaigns(campaign_id) ON DELETE CASCADE,
        job_id TEXT NOT NULL,
        seed BIGINT NOT NULL,
        scenario_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
        status TEXT NOT NULL DEFAULT 'queued',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (campaign_id, job_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_signal_behaviors_project ON engineering_signal_behaviors(project_id, signal_id)",
    "CREATE INDEX IF NOT EXISTS idx_simulation_scenarios_project ON engineering_simulation_scenarios(project_id, modified_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_fault_proposals_review ON engineering_fault_proposals(project_id, status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_trace_metadata_project ON engineering_trace_metadata(project_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_simulation_campaigns_project ON engineering_simulation_campaigns(project_id, created_at DESC)",
    "ALTER TABLE engineering_simulation_scenarios ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE engineering_simulation_scenarios ADD COLUMN IF NOT EXISTS initial_conditions JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE engineering_simulation_scenarios ADD COLUMN IF NOT EXISTS signal_profiles JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE engineering_simulation_scenarios ADD COLUMN IF NOT EXISTS expected_behavior JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE engineering_simulation_scenarios ADD COLUMN IF NOT EXISTS created_by TEXT",
    "ALTER TABLE engineering_fault_proposals ADD COLUMN IF NOT EXISTS expected_effect JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE engineering_fault_proposals ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)",
    "ALTER TABLE engineering_fault_proposals ADD COLUMN IF NOT EXISTS origin TEXT NOT NULL DEFAULT 'AI_GENERATED' CHECK (origin IN ('USER', 'AI_GENERATED', 'PREDEFINED'))",
    "ALTER TABLE engineering_trace_metadata ADD COLUMN IF NOT EXISTS simulation_id TEXT",
    "ALTER TABLE engineering_trace_metadata ADD COLUMN IF NOT EXISTS scenario_id TEXT",
    "ALTER TABLE engineering_trace_metadata ADD COLUMN IF NOT EXISTS scenario_type TEXT",
    "ALTER TABLE engineering_trace_metadata ADD COLUMN IF NOT EXISTS engineering_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE engineering_trace_metadata ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ",
    "ALTER TABLE engineering_trace_metadata ADD COLUMN IF NOT EXISTS duration_s DOUBLE PRECISION",
    "ALTER TABLE engineering_trace_metadata ADD COLUMN IF NOT EXISTS networks JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE engineering_trace_metadata ADD COLUMN IF NOT EXISTS faults JSONB NOT NULL DEFAULT '[]'::jsonb",
)


def ensure_schema(connection, statements: Iterable[str] = MIGRATION_STATEMENTS) -> None:
    """Apply the current schema exactly once per database version."""
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))
        connection.execute(MIGRATION_STATEMENTS[0])
        applied = connection.execute(
            "SELECT 1 FROM engineering_schema_migrations WHERE version = %s",
            (SCHEMA_VERSION,),
        ).fetchone()
        if applied:
            return
        for statement in tuple(statements)[1:]:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO engineering_schema_migrations (version) VALUES (%s)",
            (SCHEMA_VERSION,),
        )


def schema_status(connection) -> dict[str, int | bool]:
    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM engineering_schema_migrations"
    ).fetchone()
    version = int(row["version"] if isinstance(row, dict) else row[0])
    return {"ready": version >= SCHEMA_VERSION, "version": version, "expected_version": SCHEMA_VERSION}
