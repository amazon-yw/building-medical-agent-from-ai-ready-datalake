-- =====================================================
-- DDL Script - Part 6: Financial & Documentation
-- Organization: ABC Corp
-- =====================================================

-- Financial Claim
CREATE TABLE abc_fin_clam (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    typ_sys VARCHAR(255),
    typ_cd VARCHAR(100),
    typ_dsp VARCHAR(255),
    use_cd VARCHAR(50),
    sbj_ref VARCHAR(255),
    crt_dts TIMESTAMP,
    ins_ref VARCHAR(255),
    prv_ref VARCHAR(255),
    pry VARCHAR(50),
    prs_cd_sys VARCHAR(255),
    prs_cd_val VARCHAR(100),
    prs_cd_dsp VARCHAR(255),
    tot_amt DECIMAL(18, 2),
    tot_cur VARCHAR(10),
    sys_crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sys_upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fin_clam_sbj ON abc_fin_clam(sbj_ref);
CREATE INDEX idx_fin_clam_sts ON abc_fin_clam(sts);
CREATE INDEX idx_fin_clam_crt ON abc_fin_clam(crt_dts);

-- Financial Explanation of Benefit
CREATE TABLE abc_fin_eob (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    typ_sys VARCHAR(255),
    typ_cd VARCHAR(100),
    typ_dsp VARCHAR(255),
    use_cd VARCHAR(50),
    sbj_ref VARCHAR(255),
    crt_dts TIMESTAMP,
    ins_ref VARCHAR(255),
    prv_ref VARCHAR(255),
    clm_ref VARCHAR(255),
    outc VARCHAR(50),
    tot_amt DECIMAL(18, 2),
    tot_cur VARCHAR(10),
    pmt_amt DECIMAL(18, 2),
    pmt_cur VARCHAR(10),
    pmt_dt DATE,
    sys_crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sys_upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fin_eob_sbj ON abc_fin_eob(sbj_ref);
CREATE INDEX idx_fin_eob_clm ON abc_fin_eob(clm_ref);
CREATE INDEX idx_fin_eob_crt ON abc_fin_eob(crt_dts);

-- Document Reference
CREATE TABLE abc_doc_dref (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    doc_sts VARCHAR(50),
    typ_sys VARCHAR(255),
    typ_cd VARCHAR(100),
    typ_dsp VARCHAR(255),
    ctg_sys VARCHAR(255),
    ctg_cd VARCHAR(100),
    ctg_dsp VARCHAR(255),
    sbj_ref VARCHAR(255),
    ctx_ref VARCHAR(255),
    dt TIMESTAMP,
    ath_ref VARCHAR(255),
    cst_ref VARCHAR(255),
    dsc TEXT,
    sec_cls VARCHAR(50),
    cnt_att_typ VARCHAR(100),
    cnt_att_url TEXT,
    cnt_att_sz BIGINT,
    cnt_att_hsh VARCHAR(255),
    cnt_att_ttl VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_doc_dref_sbj ON abc_doc_dref(sbj_ref);
CREATE INDEX idx_doc_dref_ctx ON abc_doc_dref(ctx_ref);
CREATE INDEX idx_doc_dref_dt ON abc_doc_dref(dt);

-- Audit Track (Provenance)
CREATE TABLE abc_doc_prvn (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    tgt_ref VARCHAR(255),
    occ_st_dts TIMESTAMP,
    occ_ed_dts TIMESTAMP,
    rec_dts TIMESTAMP,
    act_sys VARCHAR(255),
    act_cd VARCHAR(100),
    act_dsp VARCHAR(255),
    agt_typ_sys VARCHAR(255),
    agt_typ_cd VARCHAR(100),
    agt_typ_dsp VARCHAR(255),
    agt_who_ref VARCHAR(255),
    agt_bhf_ref VARCHAR(255),
    loc_ref VARCHAR(255),
    rsn_sys VARCHAR(255),
    rsn_cd VARCHAR(100),
    rsn_dsp VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_doc_prvn_tgt ON abc_doc_prvn(tgt_ref);
CREATE INDEX idx_doc_prvn_occ ON abc_doc_prvn(occ_st_dts);
CREATE INDEX idx_doc_prvn_agt ON abc_doc_prvn(agt_who_ref);
