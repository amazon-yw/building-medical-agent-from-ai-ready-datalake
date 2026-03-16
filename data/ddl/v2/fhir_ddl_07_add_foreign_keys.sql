-- =====================================================
-- Add Foreign Key Constraints After Data Loading
-- Organization: ABC Corp
-- =====================================================

-- Clinical Events -> Subject
ALTER TABLE abc_cln_enct ADD CONSTRAINT fk_cln_evt_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_cln_cond ADD CONSTRAINT fk_cln_dgs_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_cln_prcd ADD CONSTRAINT fk_cln_act_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_cln_obsv ADD CONSTRAINT fk_cln_msr_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);

-- Medication -> Subject
ALTER TABLE abc_rx_mreq ADD CONSTRAINT fk_rx_ord_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_rx_madm ADD CONSTRAINT fk_rx_adm_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);

-- Diagnostic -> Subject
ALTER TABLE abc_dgn_drpt ADD CONSTRAINT fk_dgn_rpt_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_dgn_imgs ADD CONSTRAINT fk_dgn_img_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_dgn_imzn ADD CONSTRAINT fk_dgn_imz_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_dgn_algy ADD CONSTRAINT fk_dgn_alg_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);

-- Care Management -> Subject
ALTER TABLE abc_car_cpln ADD CONSTRAINT fk_car_pln_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_car_ctm ADD CONSTRAINT fk_car_tm_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_car_devc ADD CONSTRAINT fk_car_dev_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_car_sdlv ADD CONSTRAINT fk_car_sup_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);

-- Financial & Document -> Subject
ALTER TABLE abc_fin_clam ADD CONSTRAINT fk_fin_clm_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_fin_eob ADD CONSTRAINT fk_fin_eob_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
ALTER TABLE abc_doc_dref ADD CONSTRAINT fk_doc_ref_sbj FOREIGN KEY (sbj_ref) REFERENCES abc_reg_ptnt(rid);
