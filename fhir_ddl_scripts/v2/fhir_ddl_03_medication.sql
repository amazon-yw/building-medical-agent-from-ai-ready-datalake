-- =====================================================
-- DDL Script - Part 3: Medication Management
-- Organization: ABC Corp
-- =====================================================

-- Prescription Catalog (Medication)
CREATE TABLE abc_rx_mdcn (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    cd_sys VARCHAR(255),
    cd_val VARCHAR(100),
    cd_dsp VARCHAR(255),
    cd_txt TEXT,
    sts VARCHAR(50),
    mfr_ref VARCHAR(255),
    frm_sys VARCHAR(255),
    frm_cd VARCHAR(100),
    frm_dsp VARCHAR(255),
    amt_num DECIMAL(18, 6),
    amt_dnm DECIMAL(18, 6),
    amt_unt VARCHAR(50),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rx_mdcn_cd ON abc_rx_mdcn(cd_val);

-- Prescription Order (MedicationRequest)
CREATE TABLE abc_rx_mreq (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    sts VARCHAR(50),
    intnt VARCHAR(50),
    ctg_sys VARCHAR(255),
    ctg_cd VARCHAR(100),
    ctg_dsp VARCHAR(255),
    med_cd_sys VARCHAR(255),
    med_cd_val VARCHAR(100),
    med_cd_dsp VARCHAR(255),
    med_ref VARCHAR(255),
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    ath_dts TIMESTAMP,
    req_ref VARCHAR(255),
    rsn_cd_sys VARCHAR(255),
    rsn_cd_val VARCHAR(100),
    rsn_cd_dsp VARCHAR(255),
    dos_txt TEXT,
    dos_seq INT,
    dos_qty DECIMAL(18, 6),
    dos_unt VARCHAR(50),
    rte_sys VARCHAR(255),
    rte_cd VARCHAR(100),
    rte_dsp VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rx_mreq_sbj ON abc_rx_mreq(sbj_ref);
CREATE INDEX idx_rx_mreq_evt ON abc_rx_mreq(evt_ref);
CREATE INDEX idx_rx_mreq_med ON abc_rx_mreq(med_ref);
CREATE INDEX idx_rx_mreq_ath ON abc_rx_mreq(ath_dts);

-- Prescription Administration (MedicationAdministration)
CREATE TABLE abc_rx_madm (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    sts VARCHAR(50),
    med_cd_sys VARCHAR(255),
    med_cd_val VARCHAR(100),
    med_cd_dsp VARCHAR(255),
    med_ref VARCHAR(255),
    sbj_ref VARCHAR(255),
    ctx_ref VARCHAR(255),
    eff_st_dts TIMESTAMP,
    eff_ed_dts TIMESTAMP,
    prf_ref VARCHAR(255),
    rsn_cd_sys VARCHAR(255),
    rsn_cd_val VARCHAR(100),
    rsn_cd_dsp VARCHAR(255),
    req_ref VARCHAR(255),
    dos_txt TEXT,
    dos_qty DECIMAL(18, 6),
    dos_unt VARCHAR(50),
    rte_sys VARCHAR(255),
    rte_cd VARCHAR(100),
    rte_dsp VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rx_madm_sbj ON abc_rx_madm(sbj_ref);
CREATE INDEX idx_rx_madm_ctx ON abc_rx_madm(ctx_ref);
CREATE INDEX idx_rx_madm_med ON abc_rx_madm(med_ref);
CREATE INDEX idx_rx_madm_eff ON abc_rx_madm(eff_st_dts);
