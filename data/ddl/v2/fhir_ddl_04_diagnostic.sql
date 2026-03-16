-- =====================================================
-- DDL Script - Part 4: Diagnostic & Immunization
-- Organization: ABC Corp
-- =====================================================

-- Test Report (DiagnosticReport)
CREATE TABLE abc_dgn_drpt (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
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
    prf_ref VARCHAR(255),
    cnc_txt TEXT,
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dgn_drpt_sbj ON abc_dgn_drpt(sbj_ref);
CREATE INDEX idx_dgn_drpt_evt ON abc_dgn_drpt(evt_ref);
CREATE INDEX idx_dgn_drpt_eff ON abc_dgn_drpt(eff_dts);

-- Imaging Study
CREATE TABLE abc_dgn_imgs (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    std_dts TIMESTAMP,
    modl_sys VARCHAR(255),
    modl_cd VARCHAR(100),
    modl_dsp VARCHAR(255),
    rfr_ref VARCHAR(255),
    itp_ref VARCHAR(255),
    num_srs INT,
    num_ins INT,
    prc_cd_sys VARCHAR(255),
    prc_cd_val VARCHAR(100),
    prc_cd_dsp VARCHAR(255),
    rsn_cd_sys VARCHAR(255),
    rsn_cd_val VARCHAR(100),
    rsn_cd_dsp VARCHAR(255),
    dsc TEXT,
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dgn_imgs_sbj ON abc_dgn_imgs(sbj_ref);
CREATE INDEX idx_dgn_imgs_evt ON abc_dgn_imgs(evt_ref);
CREATE INDEX idx_dgn_imgs_std ON abc_dgn_imgs(std_dts);

-- Immunization Record
CREATE TABLE abc_dgn_imzn (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    sts VARCHAR(50),
    sts_rsn_sys VARCHAR(255),
    sts_rsn_cd VARCHAR(100),
    sts_rsn_dsp VARCHAR(255),
    vac_cd_sys VARCHAR(255),
    vac_cd_val VARCHAR(100),
    vac_cd_dsp VARCHAR(255),
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    occ_dts TIMESTAMP,
    pry_src BOOLEAN,
    loc_ref VARCHAR(255),
    mfr_ref VARCHAR(255),
    lot_num VARCHAR(100),
    exp_dt DATE,
    ste_sys VARCHAR(255),
    ste_cd VARCHAR(100),
    ste_dsp VARCHAR(255),
    rte_sys VARCHAR(255),
    rte_cd VARCHAR(100),
    rte_dsp VARCHAR(255),
    dos_qty DECIMAL(18, 6),
    dos_unt VARCHAR(50),
    prf_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dgn_imzn_sbj ON abc_dgn_imzn(sbj_ref);
CREATE INDEX idx_dgn_imzn_evt ON abc_dgn_imzn(evt_ref);
CREATE INDEX idx_dgn_imzn_occ ON abc_dgn_imzn(occ_dts);

-- Allergy Record (AllergyIntolerance)
CREATE TABLE abc_dgn_algy (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    cln_sts_sys VARCHAR(255),
    cln_sts_cd VARCHAR(50),
    vrf_sts_sys VARCHAR(255),
    vrf_sts_cd VARCHAR(50),
    typ VARCHAR(50),
    ctg VARCHAR(50),
    crt VARCHAR(50),
    cd_sys VARCHAR(255),
    cd_val VARCHAR(100),
    cd_dsp VARCHAR(255),
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    ons_dts TIMESTAMP,
    rec_dts TIMESTAMP,
    rec_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dgn_algy_sbj ON abc_dgn_algy(sbj_ref);
CREATE INDEX idx_dgn_algy_cd ON abc_dgn_algy(cd_val);
