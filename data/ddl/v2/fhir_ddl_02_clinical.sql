-- =====================================================
-- DDL Script - Part 2: Clinical Events
-- Organization: ABC Corp
-- =====================================================

-- Event Log (Encounter)
CREATE TABLE abc_cln_enct (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    cls_sys VARCHAR(255),
    cls_cd VARCHAR(50),
    typ_sys VARCHAR(255),
    typ_cd VARCHAR(100),
    typ_dsp VARCHAR(255),
    sbj_ref VARCHAR(255),
    prd_st_dts TIMESTAMP,
    prd_ed_dts TIMESTAMP,
    rsn_cd_sys VARCHAR(255),
    rsn_cd_val VARCHAR(100),
    rsn_cd_dsp VARCHAR(255),
    svc_prf_ref VARCHAR(255),
    loc_ref VARCHAR(255),
    org_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cln_enct_sbj ON abc_cln_enct(sbj_ref);
CREATE INDEX idx_cln_enct_prd ON abc_cln_enct(prd_st_dts, prd_ed_dts);
CREATE INDEX idx_cln_enct_sts ON abc_cln_enct(sts);

-- Diagnosis Record (Condition)
CREATE TABLE abc_cln_cond (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    cln_sts_sys VARCHAR(255),
    cln_sts_cd VARCHAR(50),
    vrf_sts_sys VARCHAR(255),
    vrf_sts_cd VARCHAR(50),
    ctg_sys VARCHAR(255),
    ctg_cd VARCHAR(100),
    ctg_dsp VARCHAR(255),
    cd_sys VARCHAR(255),
    cd_val VARCHAR(100),
    cd_dsp VARCHAR(255),
    cd_txt TEXT,
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    ons_dts TIMESTAMP,
    abd_dts TIMESTAMP,
    rec_dts DATE,
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cln_cond_sbj ON abc_cln_cond(sbj_ref);
CREATE INDEX idx_cln_cond_evt ON abc_cln_cond(evt_ref);
CREATE INDEX idx_cln_cond_cd ON abc_cln_cond(cd_val);

-- Activity Performance (Procedure)
CREATE TABLE abc_cln_prcd (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    sts VARCHAR(50),
    cd_sys VARCHAR(255),
    cd_val VARCHAR(100),
    cd_dsp VARCHAR(255),
    cd_txt TEXT,
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    prf_st_dts TIMESTAMP,
    prf_ed_dts TIMESTAMP,
    prf_ref VARCHAR(255),
    loc_ref VARCHAR(255),
    rsn_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cln_prcd_sbj ON abc_cln_prcd(sbj_ref);
CREATE INDEX idx_cln_prcd_evt ON abc_cln_prcd(evt_ref);
CREATE INDEX idx_cln_prcd_prf ON abc_cln_prcd(prf_st_dts, prf_ed_dts);

-- Measurement Data (Observation)
CREATE TABLE abc_cln_obsv (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    sts VARCHAR(50),
    ctg_sys VARCHAR(255),
    ctg_cd VARCHAR(100),
    ctg_dsp VARCHAR(255),
    cd_sys VARCHAR(255),
    cd_val VARCHAR(100),
    cd_dsp VARCHAR(255),
    cd_txt TEXT,
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    eff_dts TIMESTAMP,
    iss_dts TIMESTAMP,
    val_qty DECIMAL(18, 6),
    val_unt VARCHAR(50),
    val_sys VARCHAR(255),
    val_cd VARCHAR(100),
    val_str TEXT,
    val_bool BOOLEAN,
    itp_txt TEXT,
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cln_obsv_sbj ON abc_cln_obsv(sbj_ref);
CREATE INDEX idx_cln_obsv_evt ON abc_cln_obsv(evt_ref);
CREATE INDEX idx_cln_obsv_cd ON abc_cln_obsv(cd_val);
CREATE INDEX idx_cln_obsv_eff ON abc_cln_obsv(eff_dts);
