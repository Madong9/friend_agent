-- Pinned representation of the deployed CloudBase schema at Alembic 0008.
-- Deliberately excludes every 0009 addition: users personality/campus fields,
-- reports.category, partner_requests and notifications.

DO $$ BEGIN CREATE ROLE anon; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE authenticated; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE service_role; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE activities (
    id varchar(64) PRIMARY KEY,
    name varchar(128) NOT NULL,
    campus varchar(64) NOT NULL,
    location varchar(128) NOT NULL,
    time varchar(128) NOT NULL,
    tags json NOT NULL,
    capacity integer NOT NULL,
    public boolean NOT NULL
);

CREATE TABLE users (
    id varchar(64) PRIMARY KEY,
    nickname varchar(64) NOT NULL,
    school_email varchar(128),
    wechat_openid varchar(128),
    school_uid varchar(64),
    school_display_name varchar(128),
    identity_provider varchar(32) NOT NULL,
    school varchar(128) NOT NULL,
    campus varchar(64) NOT NULL,
    grade varchar(32) NOT NULL,
    major varchar(128) NOT NULL,
    bio text NOT NULL,
    social_goals json NOT NULL,
    interests json NOT NULL,
    activities json NOT NULL,
    availability json NOT NULL,
    social_style varchar(64) NOT NULL,
    avoidances json NOT NULL,
    recommendation_enabled boolean NOT NULL,
    verified boolean NOT NULL,
    password_hash varchar(512),
    token_version integer NOT NULL,
    last_token_revoked_at timestamptz,
    is_mock boolean NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz
);
CREATE UNIQUE INDEX ix_users_school_email ON users (school_email);
CREATE UNIQUE INDEX ix_users_school_uid ON users (school_uid);
CREATE UNIQUE INDEX ix_users_wechat_openid ON users (wechat_openid);

CREATE TABLE agent_sessions (
    id varchar(64) PRIMARY KEY,
    user_id varchar(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state json NOT NULL,
    version integer NOT NULL,
    active_turn_id varchar(64),
    lock_expires_at timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE INDEX ix_agent_sessions_expires_at ON agent_sessions (expires_at);
CREATE INDEX ix_agent_sessions_user_id ON agent_sessions (user_id);

CREATE TABLE agent_traces (
    session_id varchar(64) PRIMARY KEY,
    user_id varchar(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entries json NOT NULL,
    version integer NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE INDEX ix_agent_traces_expires_at ON agent_traces (expires_at);
CREATE INDEX ix_agent_traces_user_id ON agent_traces (user_id);

CREATE TABLE blocks (
    id serial PRIMARY KEY,
    blocker_id varchar(64) NOT NULL REFERENCES users(id),
    blocked_id varchar(64) NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL,
    CONSTRAINT uq_block_direction UNIQUE (blocker_id, blocked_id)
);
CREATE INDEX ix_blocks_blocked_id ON blocks (blocked_id);
CREATE INDEX ix_blocks_blocker_id ON blocks (blocker_id);

CREATE TABLE interactions (
    id serial PRIMARY KEY,
    actor_id varchar(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id varchar(64) REFERENCES users(id) ON DELETE CASCADE,
    kind varchar(32) NOT NULL,
    payload json NOT NULL,
    created_at timestamptz NOT NULL
);
CREATE INDEX ix_interactions_actor_id ON interactions (actor_id);
CREATE INDEX ix_interactions_created_at ON interactions (created_at);
CREATE INDEX ix_interactions_kind ON interactions (kind);
CREATE INDEX ix_interactions_target_id ON interactions (target_id);

CREATE TABLE matches (
    id serial PRIMARY KEY,
    user_a_id varchar(64) NOT NULL REFERENCES users(id),
    user_b_id varchar(64) NOT NULL REFERENCES users(id),
    status varchar(32) NOT NULL,
    score double precision,
    created_at timestamptz NOT NULL,
    CONSTRAINT uq_match_pair UNIQUE (user_a_id, user_b_id)
);
CREATE INDEX ix_matches_user_a_id ON matches (user_a_id);
CREATE INDEX ix_matches_user_b_id ON matches (user_b_id);

CREATE TABLE messages (
    id serial PRIMARY KEY,
    sender_id varchar(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_id varchar(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body text NOT NULL,
    safety_result json NOT NULL,
    created_at timestamptz NOT NULL,
    read_at timestamptz
);
CREATE INDEX ix_messages_created_at ON messages (created_at);
CREATE INDEX ix_messages_recipient_id ON messages (recipient_id);
CREATE INDEX ix_messages_sender_id ON messages (sender_id);

CREATE TABLE preferences (
    id serial PRIMARY KEY,
    user_id varchar(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key varchar(128) NOT NULL,
    value varchar(255) NOT NULL,
    weight double precision NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_preference_user_key UNIQUE (user_id, key)
);
CREATE INDEX ix_preferences_key ON preferences (key);
CREATE INDEX ix_preferences_user_id ON preferences (user_id);

CREATE TABLE reports (
    id serial PRIMARY KEY,
    reporter_id varchar(64) NOT NULL REFERENCES users(id),
    reported_id varchar(64) NOT NULL REFERENCES users(id),
    reason text NOT NULL,
    status varchar(32) NOT NULL,
    created_at timestamptz NOT NULL
);
CREATE INDEX ix_reports_reported_id ON reports (reported_id);
CREATE INDEX ix_reports_reporter_id ON reports (reporter_id);

CREATE TABLE alembic_version (version_num varchar(128) PRIMARY KEY);
INSERT INTO alembic_version(version_num) VALUES ('0008_add_wechat_and_mock_flags');

INSERT INTO activities(id, name, campus, location, time, tags, capacity, public)
VALUES (
    'legacy-activity', '历史羽毛球局', '西区', '风雨操场', '周六下午',
    '["羽毛球"]'::json, 12, true
);

INSERT INTO users(
    id, nickname, school_email, wechat_openid, school_uid,
    school_display_name, identity_provider, school, campus, grade, major, bio,
    social_goals, interests, activities, availability, social_style,
    avoidances, recommendation_enabled, verified, password_hash, token_version,
    last_token_revoked_at, is_mock, created_at, updated_at
) VALUES
(
    'legacy-verified', '历史认证用户', 'legacy@ustc.edu.cn', NULL, 'PB0001',
    '历史同学', 'ustc-cas', '中国科学技术大学', '西区', '研一', '计算机',
    '需要被完整保留的历史简介', '["运动搭子"]'::json,
    '["摄影"]'::json, '["羽毛球"]'::json, '["周六下午"]'::json,
    '慢热', '[]'::json, true, true, NULL, 2, NULL, false,
    '2026-08-01T00:00:00Z', '2026-08-02T00:00:00Z'
),
(
    'legacy-wechat', '历史微信用户', NULL, 'openid-legacy', NULL,
    NULL, 'wechat', '中国科学技术大学', '待验证', '待完善', '待完善',
    '微信用户历史简介', '[]'::json, '["飞盘"]'::json, '["飞盘"]'::json,
    '["周五晚上"]'::json, '随和', '[]'::json, true, true, NULL, 0,
    NULL, false, '2026-08-03T00:00:00Z', NULL
);

INSERT INTO reports(reporter_id, reported_id, reason, status, created_at)
VALUES (
    'legacy-verified', 'legacy-wechat', '历史举报原因必须保留', 'PENDING',
    '2026-08-04T00:00:00Z'
);

INSERT INTO interactions(actor_id, target_id, kind, payload, created_at)
VALUES (
    'legacy-verified', 'legacy-wechat', 'PASS', '{"legacy":true}'::json,
    '2026-08-05T00:00:00Z'
);

INSERT INTO preferences(user_id, key, value, weight, updated_at)
VALUES (
    'legacy-verified', 'activity:羽毛球', '羽毛球', 0.12,
    '2026-08-05T00:00:00Z'
);
