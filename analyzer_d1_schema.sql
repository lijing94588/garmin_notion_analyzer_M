-- Garmin Raw Activities
CREATE TABLE IF NOT EXISTS raw_activities (
    activity_id TEXT PRIMARY KEY,
    name TEXT,
    start_date TEXT,
    activity_type TEXT,
    distance_km REAL,
    duration_min REAL,
    avg_hr REAL,
    avg_pace_min_km REAL,
    raw_json_hash TEXT,
    synced_at TEXT
);

-- Garmin Raw Laps
CREATE TABLE IF NOT EXISTS raw_laps (
    lap_key TEXT PRIMARY KEY,
    activity_id TEXT,
    lap_index INTEGER,
    lap_date TEXT,
    distance_m REAL,
    duration_sec REAL,
    avg_speed_mps REAL,
    avg_hr REAL,
    cadence REAL,
    power_w REAL,
    ground_contact_ms REAL,
    stride_m REAL,
    vertical_osc_cm REAL,
    raw_json TEXT,
    synced_at TEXT
);

-- Garmin Raw Detail JSON (只存中繼資料，不存完整detail原始巨量JSON，理由見程式註解)
CREATE TABLE IF NOT EXISTS raw_detail (
    activity_id TEXT PRIMARY KEY,
    start_date TEXT,
    measurement_count INTEGER,
    metrics_count INTEGER,
    raw_json_hash TEXT,
    synced_at TEXT
);

-- Garmin Running Analysis
CREATE TABLE IF NOT EXISTS running_analysis (
    activity_id TEXT PRIMARY KEY,
    date TEXT,
    activity_type TEXT,
    duration_min REAL,
    distance_km REAL,
    pace_min_km REAL,
    pace_cv_pct REAL,
    pace_range_pct REAL,
    half_split_diff_pct REAL,
    mrs_pct REAL,
    avg_hr REAL,
    hr_drift_pct REAL,
    hr_decoupling_pct REAL,
    garmin_rpe REAL,
    trimp REAL,
    srpe_load REAL,
    load_7d REAL,
    load_28d REAL,
    cadence_change_pct REAL,
    gct_change_pct REAL,
    power_w_per_kg REAL,
    temperature_c REAL,
    training_load REAL,
    body_battery_diff REAL,
    notes TEXT,
    synced_at TEXT
);

-- Garmin Weekly Running Analysis
CREATE TABLE IF NOT EXISTS weekly_analysis (
    week_key TEXT PRIMARY KEY,
    week_start TEXT,
    week_end TEXT,
    training_sessions INTEGER,
    training_frequency_cv REAL,
    training_frequency_class TEXT,
    distance_km REAL,
    duration_min REAL,
    training_load REAL,
    srpe_load REAL,
    avg_hr REAL,
    avg_pace_min_km REAL,
    hr_efficiency_slope REAL,
    hr_efficiency_trend TEXT,
    recovery_burden_ratio REAL,
    recovery_burden_change REAL,
    recovery_resilience_trend TEXT,
    mrs_avg_pct REAL,
    hr_drift_avg_pct REAL,
    hr_decoupling_avg_pct REAL,
    temperature_avg_c REAL,
    notes TEXT,
    synced_at TEXT
);
