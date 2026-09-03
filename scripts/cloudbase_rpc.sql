-- CloudBase HTTP API exposes RPC endpoints broadly. Every SECURITY DEFINER
-- function therefore verifies the server-only service_role claim itself.

CREATE OR REPLACE FUNCTION public.campus_require_service_role()
RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF COALESCE(
        NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role',
        ''
    ) <> 'service_role' THEN
        RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.campus_agent_session_update(
    p_session_id text,
    p_values jsonb,
    p_ttl_seconds integer
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user_id text;
    v_requested_user_id text := p_values ->> 'user_id';
    v_now timestamptz := now();
BEGIN
    PERFORM public.campus_require_service_role();
    DELETE FROM agent_sessions
    WHERE id = p_session_id AND expires_at <= v_now;

    SELECT user_id INTO v_user_id
    FROM agent_sessions WHERE id = p_session_id FOR UPDATE;
    IF NOT FOUND THEN
        IF COALESCE(v_requested_user_id, '') = '' THEN
            RETURN jsonb_build_object('status', 'missing_user_id');
        END IF;
        INSERT INTO agent_sessions(
            id, user_id, state, version, created_at, updated_at, expires_at
        ) VALUES (
            p_session_id, v_requested_user_id, p_values::json,
            1, v_now, v_now, v_now + make_interval(secs => p_ttl_seconds)
        );
        RETURN jsonb_build_object('status', 'created');
    END IF;
    IF v_requested_user_id IS NOT NULL AND v_requested_user_id <> v_user_id THEN
        RETURN jsonb_build_object('status', 'forbidden');
    END IF;
    UPDATE agent_sessions
    SET state = (COALESCE(state, '{}'::json)::jsonb || p_values)::json,
        version = version + 1,
        updated_at = v_now,
        expires_at = v_now + make_interval(secs => p_ttl_seconds)
    WHERE id = p_session_id;
    RETURN jsonb_build_object('status', 'updated');
END;
$$;

CREATE OR REPLACE FUNCTION public.campus_agent_session_acquire(
    p_session_id text,
    p_user_id text,
    p_turn_id text,
    p_lease_seconds integer
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_record agent_sessions%ROWTYPE;
    v_now timestamptz := now();
BEGIN
    PERFORM public.campus_require_service_role();
    SELECT * INTO v_record FROM agent_sessions
    WHERE id = p_session_id AND expires_at > v_now FOR UPDATE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('status', 'not_found');
    END IF;
    IF v_record.user_id <> p_user_id THEN
        RETURN jsonb_build_object('status', 'forbidden');
    END IF;
    IF v_record.active_turn_id IS NOT NULL
       AND v_record.active_turn_id <> p_turn_id
       AND (v_record.lock_expires_at IS NULL OR v_record.lock_expires_at > v_now) THEN
        RETURN jsonb_build_object('status', 'busy');
    END IF;
    UPDATE agent_sessions
    SET active_turn_id = p_turn_id,
        lock_expires_at = v_now + make_interval(secs => p_lease_seconds),
        version = version + 1,
        updated_at = v_now
    WHERE id = p_session_id;
    RETURN jsonb_build_object('status', 'acquired');
END;
$$;

CREATE OR REPLACE FUNCTION public.campus_agent_session_release(
    p_session_id text,
    p_turn_id text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_count integer;
BEGIN
    PERFORM public.campus_require_service_role();
    UPDATE agent_sessions
    SET active_turn_id = NULL,
        lock_expires_at = NULL,
        version = version + 1,
        updated_at = now()
    WHERE id = p_session_id AND active_turn_id = p_turn_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN jsonb_build_object('status', 'released', 'updated', v_count);
END;
$$;

CREATE OR REPLACE FUNCTION public.campus_agent_trace_save(
    p_session_id text,
    p_user_id text,
    p_entries jsonb,
    p_ttl_seconds integer,
    p_max_entries integer
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_record agent_traces%ROWTYPE;
    v_combined jsonb;
    v_merged jsonb;
    v_now timestamptz := now();
BEGIN
    PERFORM public.campus_require_service_role();
    DELETE FROM agent_traces
    WHERE session_id = p_session_id AND expires_at <= v_now;
    SELECT * INTO v_record FROM agent_traces
    WHERE session_id = p_session_id FOR UPDATE;
    IF FOUND AND v_record.user_id <> p_user_id THEN
        RETURN jsonb_build_object('status', 'forbidden');
    END IF;
    v_combined := COALESCE(v_record.entries, '[]'::json)::jsonb
                  || COALESCE(p_entries, '[]'::jsonb);
    WITH deduplicated AS (
        SELECT DISTINCT ON (item ->> 'event_id') item
        FROM jsonb_array_elements(v_combined) AS source(item)
        WHERE COALESCE(item ->> 'event_id', '') <> ''
        ORDER BY item ->> 'event_id', item ->> 'recorded_at' DESC
    ), limited AS (
        SELECT item FROM deduplicated
        ORDER BY item ->> 'recorded_at' DESC, item ->> 'event_id' DESC
        LIMIT GREATEST(p_max_entries, 1)
    ), ordered AS (
        SELECT item,
               row_number() OVER (
                   ORDER BY item ->> 'recorded_at', item ->> 'event_id'
               ) AS step
        FROM limited
    )
    SELECT COALESCE(
        jsonb_agg(jsonb_set(item, '{step}', to_jsonb(step), true) ORDER BY step),
        '[]'::jsonb
    ) INTO v_merged FROM ordered;
    IF v_record.session_id IS NULL THEN
        INSERT INTO agent_traces(
            session_id, user_id, entries, version, created_at, updated_at, expires_at
        ) VALUES (
            p_session_id, p_user_id, v_merged::json, 1, v_now, v_now,
            v_now + make_interval(secs => p_ttl_seconds)
        );
    ELSE
        UPDATE agent_traces
        SET entries = v_merged::json,
            version = version + 1,
            updated_at = v_now,
            expires_at = v_now + make_interval(secs => p_ttl_seconds)
        WHERE session_id = p_session_id;
    END IF;
    RETURN jsonb_build_object('status', 'saved');
END;
$$;

CREATE OR REPLACE FUNCTION public.campus_block_user(
    p_user_id text,
    p_blocked_user_id text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_block_id bigint;
    v_user_a text;
    v_user_b text;
BEGIN
    PERFORM public.campus_require_service_role();
    IF p_user_id = p_blocked_user_id THEN
        RETURN jsonb_build_object('status', 'cannot interact with self');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user_id)
       OR NOT EXISTS (SELECT 1 FROM users WHERE id = p_blocked_user_id) THEN
        RETURN jsonb_build_object('status', 'user not found');
    END IF;
    INSERT INTO blocks(blocker_id, blocked_id)
    VALUES (p_user_id, p_blocked_user_id)
    ON CONFLICT (blocker_id, blocked_id)
    DO UPDATE SET blocked_id = EXCLUDED.blocked_id
    RETURNING id INTO v_block_id;
    INSERT INTO interactions(actor_id, target_id, kind, payload)
    VALUES (p_user_id, p_blocked_user_id, 'BLOCK', '{}'::json);
    v_user_a := LEAST(p_user_id, p_blocked_user_id);
    v_user_b := GREATEST(p_user_id, p_blocked_user_id);
    UPDATE matches SET status = 'BLOCKED'
    WHERE user_a_id = v_user_a AND user_b_id = v_user_b;
    RETURN jsonb_build_object('status', 'blocked', 'block_id', v_block_id);
END;
$$;

DROP FUNCTION IF EXISTS public.campus_report_user(text,text,text);
CREATE OR REPLACE FUNCTION public.campus_report_user(
    p_user_id text,
    p_reported_user_id text,
    p_reason text,
    p_category text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_report_id bigint;
BEGIN
    PERFORM public.campus_require_service_role();
    IF p_user_id = p_reported_user_id THEN
        RETURN jsonb_build_object('status', 'cannot interact with self');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user_id)
       OR NOT EXISTS (SELECT 1 FROM users WHERE id = p_reported_user_id) THEN
        RETURN jsonb_build_object('status', 'user not found');
    END IF;
    INSERT INTO reports(reporter_id, reported_id, reason, category)
    VALUES (p_user_id, p_reported_user_id, p_reason, p_category)
    RETURNING id INTO v_report_id;
    INSERT INTO interactions(actor_id, target_id, kind, payload)
    VALUES (
        p_user_id, p_reported_user_id, 'REPORT',
        json_build_object('reason', p_reason, 'category', p_category)
    );
    RETURN jsonb_build_object('status', 'reported', 'report_id', v_report_id);
END;
$$;

CREATE OR REPLACE FUNCTION public.campus_record_feedback(
    p_user_id text,
    p_candidate_id text,
    p_feedback text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_reciprocal text;
    v_match_id bigint;
    v_new_match boolean := false;
    v_signal double precision;
    v_tag text;
    v_user_a text;
    v_user_b text;
BEGIN
    PERFORM public.campus_require_service_role();
    IF p_user_id = p_candidate_id THEN
        RETURN jsonb_build_object('status', 'cannot interact with self');
    END IF;
    IF p_feedback NOT IN ('LIKE', 'INTERESTED', 'PASS', 'NOT_RELEVANT') THEN
        RETURN jsonb_build_object('status', 'invalid feedback');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user_id)
       OR NOT EXISTS (SELECT 1 FROM users WHERE id = p_candidate_id) THEN
        RETURN jsonb_build_object('status', 'user not found');
    END IF;
    IF EXISTS (
        SELECT 1 FROM blocks
        WHERE (blocker_id = p_user_id AND blocked_id = p_candidate_id)
           OR (blocker_id = p_candidate_id AND blocked_id = p_user_id)
    ) THEN
        RETURN jsonb_build_object('status', 'blocked relation');
    END IF;
    INSERT INTO interactions(actor_id, target_id, kind, payload)
    VALUES (p_user_id, p_candidate_id, p_feedback, '{}'::json);

    v_signal := CASE p_feedback
        WHEN 'LIKE' THEN 0.08
        WHEN 'INTERESTED' THEN 0.10
        WHEN 'PASS' THEN -0.04
        WHEN 'NOT_RELEVANT' THEN -0.15
        ELSE NULL
    END;
    IF v_signal IS NOT NULL THEN
        FOR v_tag IN
            SELECT 'interest:' || lower(trim(value))
            FROM users, jsonb_array_elements_text(interests::jsonb) AS value
            WHERE id = p_candidate_id
            UNION
            SELECT 'activity:' || lower(trim(value))
            FROM users, jsonb_array_elements_text(activities::jsonb) AS value
            WHERE id = p_candidate_id
        LOOP
            IF v_tag NOT IN ('interest:', 'activity:') THEN
                INSERT INTO preferences(user_id, key, value, weight, updated_at)
                VALUES (
                    p_user_id, v_tag, split_part(v_tag, ':', 2),
                    GREATEST(-0.25, LEAST(0.25, v_signal)), now()
                )
                ON CONFLICT (user_id, key) DO UPDATE
                SET value = EXCLUDED.value,
                    weight = GREATEST(
                        -0.25,
                        LEAST(0.25, 0.8 * preferences.weight + 0.2 * v_signal)
                    ),
                    updated_at = now();
            END IF;
        END LOOP;
    END IF;

    IF p_feedback IN ('LIKE', 'INTERESTED') THEN
        SELECT kind INTO v_reciprocal
        FROM interactions
        WHERE actor_id = p_candidate_id
          AND target_id = p_user_id
          AND kind IN ('LIKE', 'INTERESTED', 'PASS', 'NOT_RELEVANT', 'BLOCK', 'REPORT')
        ORDER BY created_at DESC, id DESC LIMIT 1;
        IF v_reciprocal IN ('LIKE', 'INTERESTED') THEN
            v_user_a := LEAST(p_user_id, p_candidate_id);
            v_user_b := GREATEST(p_user_id, p_candidate_id);
            INSERT INTO matches(user_a_id, user_b_id, status)
            VALUES (v_user_a, v_user_b, 'MATCHED')
            ON CONFLICT (user_a_id, user_b_id) DO NOTHING
            RETURNING id INTO v_match_id;
            IF v_match_id IS NOT NULL THEN
                v_new_match := true;
                INSERT INTO interactions(actor_id, target_id, kind, payload)
                VALUES
                    (p_user_id, p_candidate_id, 'MATCHED', '{}'::json),
                    (p_candidate_id, p_user_id, 'MATCHED', '{}'::json);
            ELSE
                SELECT id INTO v_match_id FROM matches
                WHERE user_a_id = v_user_a AND user_b_id = v_user_b;
            END IF;
        END IF;
    END IF;
    RETURN jsonb_build_object(
        'status', 'recorded', 'match_id', v_match_id, 'new_match', v_new_match
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.campus_send_message(
    p_sender_id text,
    p_recipient_id text,
    p_body text,
    p_safety_result jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user_a text := LEAST(p_sender_id, p_recipient_id);
    v_user_b text := GREATEST(p_sender_id, p_recipient_id);
    v_message_id bigint;
BEGIN
    PERFORM public.campus_require_service_role();
    IF p_sender_id = p_recipient_id THEN
        RETURN jsonb_build_object('status', 'cannot chat with self');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM matches
        WHERE user_a_id = v_user_a AND user_b_id = v_user_b AND status = 'MATCHED'
    ) THEN
        RETURN jsonb_build_object('status', 'active mutual match required');
    END IF;
    IF EXISTS (
        SELECT 1 FROM users
        WHERE id IN (p_sender_id, p_recipient_id) AND is_mock = true
    ) THEN
        RETURN jsonb_build_object('status', 'demo match does not open contact');
    END IF;
    IF EXISTS (
        SELECT 1 FROM blocks
        WHERE (blocker_id = p_sender_id AND blocked_id = p_recipient_id)
           OR (blocker_id = p_recipient_id AND blocked_id = p_sender_id)
    ) THEN
        RETURN jsonb_build_object('status', 'active mutual match required');
    END IF;
    INSERT INTO messages(sender_id, recipient_id, body, safety_result)
    VALUES (p_sender_id, p_recipient_id, p_body, p_safety_result::json)
    RETURNING id INTO v_message_id;
    RETURN jsonb_build_object('status', 'sent', 'message_id', v_message_id);
END;
$$;

REVOKE ALL ON TABLE
    users, activities, preferences, interactions, matches, blocks, reports,
    messages, agent_sessions, agent_traces, partner_requests, notifications
FROM anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    users, activities, preferences, interactions, matches, blocks, reports,
    messages, agent_sessions, agent_traces, partner_requests, notifications
TO service_role;
GRANT USAGE, SELECT ON SEQUENCE
    preferences_id_seq, interactions_id_seq, matches_id_seq, blocks_id_seq,
    reports_id_seq, messages_id_seq, partner_requests_id_seq, notifications_id_seq
TO service_role;

REVOKE EXECUTE ON FUNCTION public.campus_require_service_role() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.campus_agent_session_update(text,jsonb,integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.campus_agent_session_acquire(text,text,text,integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.campus_agent_session_release(text,text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.campus_agent_trace_save(text,text,jsonb,integer,integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.campus_block_user(text,text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.campus_report_user(text,text,text,text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.campus_record_feedback(text,text,text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.campus_send_message(text,text,text,jsonb) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.campus_agent_session_update(text,jsonb,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.campus_agent_session_acquire(text,text,text,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.campus_agent_session_release(text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.campus_agent_trace_save(text,text,jsonb,integer,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.campus_block_user(text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.campus_report_user(text,text,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.campus_record_feedback(text,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.campus_send_message(text,text,text,jsonb) TO service_role;
