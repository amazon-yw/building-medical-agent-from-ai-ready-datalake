-- =====================================================
-- DDL Script - Part 5: Care Management
-- Organization: ABC Corp
-- =====================================================

-- Plan Document (CarePlan)
CREATE TABLE abc_car_cpln (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    intnt VARCHAR(50),
    ctg_sys VARCHAR(255),
    ctg_cd VARCHAR(100),
    ctg_dsp VARCHAR(255),
    ttl VARCHAR(255),
    dsc TEXT,
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    prd_st_dts TIMESTAMP,
    prd_ed_dts TIMESTAMP,
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_car_cpln_sbj ON abc_car_cpln(sbj_ref);
CREATE INDEX idx_car_cpln_evt ON abc_car_cpln(evt_ref);
CREATE INDEX idx_car_cpln_prd ON abc_car_cpln(prd_st_dts, prd_ed_dts);

-- Team Group (CareTeam)
CREATE TABLE abc_car_ctm (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    ctg_sys VARCHAR(255),
    ctg_cd VARCHAR(100),
    ctg_dsp VARCHAR(255),
    nm VARCHAR(255),
    sbj_ref VARCHAR(255),
    evt_ref VARCHAR(255),
    prd_st_dts TIMESTAMP,
    prd_ed_dts TIMESTAMP,
    mng_org_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_car_ctm_sbj ON abc_car_ctm(sbj_ref);
CREATE INDEX idx_car_ctm_evt ON abc_car_ctm(evt_ref);
CREATE INDEX idx_car_ctm_org ON abc_car_ctm(mng_org_ref);

-- Device Catalog
CREATE TABLE abc_car_devc (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    typ_sys VARCHAR(255),
    typ_cd VARCHAR(100),
    typ_dsp VARCHAR(255),
    typ_txt TEXT,
    mfr VARCHAR(255),
    mdl_num VARCHAR(100),
    vrs VARCHAR(100),
    srl_num VARCHAR(100),
    lot_num VARCHAR(100),
    exp_dt DATE,
    sbj_ref VARCHAR(255),
    loc_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_car_devc_idn ON abc_car_devc(idn_val);
CREATE INDEX idx_car_devc_sbj ON abc_car_devc(sbj_ref);
CREATE INDEX idx_car_devc_typ ON abc_car_devc(typ_cd);

-- Supply Delivery
CREATE TABLE abc_car_sdlv (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    sbj_ref VARCHAR(255),
    typ_sys VARCHAR(255),
    typ_cd VARCHAR(100),
    typ_dsp VARCHAR(255),
    sup_itm_cd_sys VARCHAR(255),
    sup_itm_cd_val VARCHAR(100),
    sup_itm_cd_dsp VARCHAR(255),
    sup_itm_ref VARCHAR(255),
    qty DECIMAL(18, 6),
    qty_unt VARCHAR(50),
    occ_st_dts TIMESTAMP,
    occ_ed_dts TIMESTAMP,
    sup_ref VARCHAR(255),
    dst_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_car_sdlv_sbj ON abc_car_sdlv(sbj_ref);
CREATE INDEX idx_car_sdlv_occ ON abc_car_sdlv(occ_st_dts);
