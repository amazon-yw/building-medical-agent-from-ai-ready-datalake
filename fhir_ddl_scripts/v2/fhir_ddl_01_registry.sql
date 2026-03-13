-- =====================================================
-- DDL Script - Part 1: Registry (Core Entities)
-- Organization: ABC Corp
-- =====================================================

-- Subject Registry (Patient)
CREATE TABLE abc_reg_ptnt (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    nm_fam VARCHAR(100),
    nm_gvn VARCHAR(100),
    gndr VARCHAR(20),
    bth_dt DATE,
    dcd_dt TIMESTAMP,
    mlt_bth_ind BOOLEAN,
    mlt_bth_num INT,
    addr_ln1 VARCHAR(255),
    addr_ln2 VARCHAR(255),
    addr_cty VARCHAR(100),
    addr_st VARCHAR(50),
    addr_zip VARCHAR(20),
    addr_ctr VARCHAR(50),
    tlc_sys VARCHAR(50),
    tlc_val VARCHAR(100),
    lng_cd VARCHAR(10),
    mrt_sts VARCHAR(50),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reg_ptnt_idn ON abc_reg_ptnt(idn_val);
CREATE INDEX idx_reg_ptnt_bth ON abc_reg_ptnt(bth_dt);

-- Professional Registry (Practitioner)
CREATE TABLE abc_reg_prct (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    actv_ind BOOLEAN,
    nm_fam VARCHAR(100),
    nm_gvn VARCHAR(100),
    nm_pfx VARCHAR(20),
    nm_sfx VARCHAR(20),
    tlc_sys VARCHAR(50),
    tlc_val VARCHAR(100),
    gndr VARCHAR(20),
    bth_dt DATE,
    addr_ln1 VARCHAR(255),
    addr_cty VARCHAR(100),
    addr_st VARCHAR(50),
    addr_zip VARCHAR(20),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reg_prct_idn ON abc_reg_prct(idn_val);
CREATE INDEX idx_reg_prct_nm ON abc_reg_prct(nm_fam, nm_gvn);

-- Organization Registry
CREATE TABLE abc_reg_orgz (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    actv_ind BOOLEAN,
    typ_cd VARCHAR(50),
    typ_dsp VARCHAR(255),
    nm VARCHAR(255),
    tlc_sys VARCHAR(50),
    tlc_val VARCHAR(100),
    addr_ln1 VARCHAR(255),
    addr_cty VARCHAR(100),
    addr_st VARCHAR(50),
    addr_zip VARCHAR(20),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reg_orgz_idn ON abc_reg_orgz(idn_val);
CREATE INDEX idx_reg_orgz_nm ON abc_reg_orgz(nm);

-- Location Registry
CREATE TABLE abc_reg_lctn (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    sts VARCHAR(50),
    nm VARCHAR(255),
    dsc TEXT,
    modl VARCHAR(50),
    typ_cd VARCHAR(50),
    typ_dsp VARCHAR(255),
    tlc_sys VARCHAR(50),
    tlc_val VARCHAR(100),
    addr_ln1 VARCHAR(255),
    addr_cty VARCHAR(100),
    addr_st VARCHAR(50),
    addr_zip VARCHAR(20),
    pos_lng DECIMAL(10, 7),
    pos_lat DECIMAL(10, 7),
    mng_org_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mng_org_ref) REFERENCES abc_reg_orgz(rid)
);

CREATE INDEX idx_reg_lctn_idn ON abc_reg_lctn(idn_val);
CREATE INDEX idx_reg_lctn_org ON abc_reg_lctn(mng_org_ref);

-- Professional Role (PractitionerRole)
CREATE TABLE abc_reg_prol (
    rid VARCHAR(255) PRIMARY KEY,
    rtp VARCHAR(50) NOT NULL,
    idn_sys VARCHAR(255),
    idn_val VARCHAR(255),
    actv_ind BOOLEAN,
    prf_ref VARCHAR(255),
    org_ref VARCHAR(255),
    cd_sys VARCHAR(255),
    cd_val VARCHAR(100),
    cd_dsp VARCHAR(255),
    spc_sys VARCHAR(255),
    spc_val VARCHAR(100),
    spc_dsp VARCHAR(255),
    loc_ref VARCHAR(255),
    crt_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upd_dts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prf_ref) REFERENCES abc_reg_prct(rid),
    FOREIGN KEY (org_ref) REFERENCES abc_reg_orgz(rid),
    FOREIGN KEY (loc_ref) REFERENCES abc_reg_lctn(rid)
);

CREATE INDEX idx_reg_prol_prf ON abc_reg_prol(prf_ref);
CREATE INDEX idx_reg_prol_org ON abc_reg_prol(org_ref);
