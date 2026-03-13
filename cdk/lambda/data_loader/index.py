import json
import boto3
import psycopg2
import os

s3 = boto3.client('s3')
secrets = boto3.client('secretsmanager')

# FHIR resource to table mapping
TABLE_MAPPING = {
    'Patient': 'abc_reg_ptnt',
    'Practitioner': 'abc_reg_prct',
    'Organization': 'abc_reg_orgz',
    'Location': 'abc_reg_lctn',
    'PractitionerRole': 'abc_reg_prol',
    'Encounter': 'abc_cln_enct',
    'Condition': 'abc_cln_cond',
    'Procedure': 'abc_cln_prcd',
    'Observation': 'abc_cln_obsv',
    'Medication': 'abc_rx_mdcn',
    'MedicationRequest': 'abc_rx_mreq',
    'MedicationAdministration': 'abc_rx_madm',
    'DiagnosticReport': 'abc_dgn_drpt',
    'ImagingStudy': 'abc_dgn_imgs',
    'Immunization': 'abc_dgn_imzn',
    'AllergyIntolerance': 'abc_dgn_algy',
    'CarePlan': 'abc_car_cpln',
    'CareTeam': 'abc_car_ctm',
    'Device': 'abc_car_devc',
    'SupplyDelivery': 'abc_car_sdlv',
    'Claim': 'abc_fin_clam',
    'ExplanationOfBenefit': 'abc_fin_eob',
    'DocumentReference': 'abc_doc_dref',
    'Provenance': 'abc_doc_prvn'
}

# Code value mappings: FHIR original value -> abbreviated code
CODE_MAPS = {
    'sts': {'active': 'A', 'completed': 'C', 'final': 'F', 'inactive': 'I',
            'superseded': 'S', 'available': 'V', 'current': 'A', 'finished': 'C'},
    'gndr': {'male': 'M', 'female': 'F', 'other': 'O', 'unknown': 'U'},
    'cln_sts_cd': {'active': 'A', 'recurrence': 'R', 'relapse': 'RL',
                   'inactive': 'IA', 'remission': 'RE', 'resolved': 'RS'},
    'vrf_sts_cd': {'unconfirmed': 'U', 'provisional': 'P', 'differential': 'D',
                   'confirmed': 'C', 'refuted': 'R', 'entered-in-error': 'E'},
    'typ_algy': {'allergy': 'AL', 'intolerance': 'IT'},
    'crt': {'low': 'L', 'high': 'H', 'unable-to-assess': 'UC'},
    'ctg_algy': {'food': 'FD', 'medication': 'MD', 'environment': 'EN', 'biologic': 'BL'},
    'intnt': {'order': 'O', 'plan': 'P', 'proposal': 'PR'},
    'use_cd': {'claim': 'CL', 'preauthorization': 'PA', 'predetermination': 'PD'},
    'outc': {'queued': 'Q', 'complete': 'CP', 'partial': 'PE', 'error': 'ER'},
    'doc_sts': {'preliminary': 'P', 'final': 'F', 'amended': 'A', 'entered-in-error': 'EE'},
    'cls_cd': {'AMB': 'AMB', 'EMER': 'EMER', 'IMP': 'IMP', 'VR': 'VR', 'HH': 'HH'},
    'pry_src': {True: 'Y', False: 'N', 'true': 'Y', 'false': 'N'},
}

def codify(field, value):
    """Convert a FHIR value to its code using CODE_MAPS."""
    if value is None:
        return None
    m = CODE_MAPS.get(field)
    if not m:
        return value
    v = value.lower() if isinstance(value, str) else value
    return m.get(v, value)

def extract_reference_id(reference):
    """Extract ID from FHIR reference (e.g., 'Patient/123' -> '123')"""
    if not reference:
        return None
    ref = reference.get('reference', '') if isinstance(reference, dict) else reference
    if '/' in ref:
        return ref.split('/')[-1]
    return ref if ref else None
    """Extract ID from FHIR reference (e.g., 'Patient/123' -> '123')"""
    if not reference:
        return None
    ref = reference.get('reference', '') if isinstance(reference, dict) else reference
    if '/' in ref:
        return ref.split('/')[-1]
    return ref if ref else None

def extract_patient_fields(resource):
    """Extract Patient fields"""
    data = {
        'rid': resource.get('id'),
        'rtp': resource.get('resourceType'),
        'gndr': codify('gndr', resource.get('gender')),
        'bth_dt': resource.get('birthDate'),
        'mlt_bth_ind': resource.get('multipleBirthBoolean')
    }
    
    # Identifier
    identifiers = resource.get('identifier', [])
    for idn in identifiers:
        if idn.get('system') == 'http://hl7.org/fhir/sid/us-ssn':
            data['idn_sys'] = idn.get('system')
            data['idn_val'] = idn.get('value')
            break
    
    # Name
    names = resource.get('name', [])
    if names:
        name = names[0]
        given = name.get('given', [])
        data['nm_gvn'] = given[0] if given else None
        data['nm_fam'] = name.get('family')
    
    # Address
    addresses = resource.get('address', [])
    if addresses:
        addr = addresses[0]
        lines = addr.get('line', [])
        data['addr_ln1'] = lines[0] if lines else None
        data['addr_cty'] = addr.get('city')
        data['addr_st'] = addr.get('state')
        data['addr_zip'] = addr.get('postalCode')
        data['addr_ctr'] = addr.get('country')
    
    # Telecom
    telecoms = resource.get('telecom', [])
    if telecoms:
        tel = telecoms[0]
        data['tlc_sys'] = tel.get('system')
        data['tlc_val'] = tel.get('value')
    
    # Marital status
    marital = resource.get('maritalStatus')
    if marital:
        coding = marital.get('coding', [])
        if coding:
            data['mrt_sts'] = coding[0].get('code')
    
    return data

def extract_practitioner_fields(resource):
    """Extract Practitioner fields"""
    data = {
        'rid': resource.get('id'),
        'rtp': resource.get('resourceType'),
        'actv_ind': resource.get('active'),
        'gndr': codify('gndr', resource.get('gender'))
    }
    
    # Identifier
    identifiers = resource.get('identifier', [])
    if identifiers:
        idn = identifiers[0]
        data['idn_sys'] = idn.get('system')
        data['idn_val'] = idn.get('value')
    
    # Name
    names = resource.get('name', [])
    if names:
        name = names[0]
        given = name.get('given', [])
        data['nm_gvn'] = given[0] if given else None
        data['nm_fam'] = name.get('family')
        data['nm_pfx'] = name.get('prefix', [None])[0]
        data['nm_sfx'] = name.get('suffix', [None])[0]
    
    # Address
    addresses = resource.get('address', [])
    if addresses:
        addr = addresses[0]
        lines = addr.get('line', [])
        data['addr_ln1'] = lines[0] if lines else None
        data['addr_cty'] = addr.get('city')
        data['addr_st'] = addr.get('state')
        data['addr_zip'] = addr.get('postalCode')
    
    # Telecom
    telecoms = resource.get('telecom', [])
    if telecoms:
        tel = telecoms[0]
        data['tlc_sys'] = tel.get('system')
        data['tlc_val'] = tel.get('value')
    
    return data

def extract_organization_fields(resource):
    """Extract Organization fields"""
    data = {
        'rid': resource.get('id'),
        'rtp': resource.get('resourceType'),
        'actv_ind': resource.get('active'),
        'nm': resource.get('name')
    }
    
    # Identifier
    identifiers = resource.get('identifier', [])
    if identifiers:
        idn = identifiers[0]
        data['idn_sys'] = idn.get('system')
        data['idn_val'] = idn.get('value')
    
    # Type
    types = resource.get('type', [])
    if types:
        typ = types[0]
        coding = typ.get('coding', [])
        if coding:
            data['typ_cd'] = coding[0].get('code')
            data['typ_dsp'] = coding[0].get('display')
    
    # Address
    addresses = resource.get('address', [])
    if addresses:
        addr = addresses[0]
        lines = addr.get('line', [])
        data['addr_ln1'] = lines[0] if lines else None
        data['addr_cty'] = addr.get('city')
        data['addr_st'] = addr.get('state')
        data['addr_zip'] = addr.get('postalCode')
    
    # Telecom
    telecoms = resource.get('telecom', [])
    if telecoms:
        tel = telecoms[0]
        data['tlc_sys'] = tel.get('system')
        data['tlc_val'] = tel.get('value')
    
    return data

def extract_location_fields(resource):
    """Extract Location fields"""
    data = {
        'rid': resource.get('id'),
        'rtp': resource.get('resourceType'),
        'sts': resource.get('status'),
        'nm': resource.get('name'),
        'dsc': resource.get('description'),
        'modl': resource.get('mode')
    }
    
    # Type
    types = resource.get('type', [])
    if types:
        typ = types[0]
        coding = typ.get('coding', [])
        if coding:
            data['typ_cd'] = coding[0].get('code')
            data['typ_dsp'] = coding[0].get('display')
    
    # Address
    address = resource.get('address')
    if address:
        lines = address.get('line', [])
        data['addr_ln1'] = lines[0] if lines else None
        data['addr_cty'] = address.get('city')
        data['addr_st'] = address.get('state')
        data['addr_zip'] = address.get('postalCode')
    
    # Managing organization
    org = resource.get('managingOrganization')
    if org:
        data['mng_org_ref'] = extract_reference_id(org)
    
    return data

def extract_medication_fields(resource):
    """Extract Medication fields"""
    data = {
        'rid': resource.get('id'),
        'rtp': resource.get('resourceType'),
        'sts': resource.get('status')
    }
    code = resource.get('code')
    if code:
        coding = code.get('coding', [])
        if coding:
            data['cd_sys'] = coding[0].get('system')
            data['cd_val'] = coding[0].get('code')
            data['cd_dsp'] = coding[0].get('display')
        data['cd_txt'] = code.get('text')
    return data


def _coding(obj):
    """Helper: extract first coding from a CodeableConcept"""
    if not obj:
        return {}
    coding = obj.get('coding', [])
    if coding:
        return coding[0]
    return {}


def extract_practitioner_role_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['actv_ind'] = resource.get('active')
    data['prf_ref'] = extract_reference_id(resource.get('practitioner'))
    data['org_ref'] = extract_reference_id(resource.get('organization'))
    c = _coding(resource.get('code', [{}])[0] if resource.get('code') else None)
    data['cd_sys'] = c.get('system')
    data['cd_val'] = c.get('code')
    data['cd_dsp'] = c.get('display')
    spec = resource.get('specialty', [])
    if spec:
        sc = _coding(spec[0])
        data['spc_sys'] = sc.get('system')
        data['spc_val'] = sc.get('code')
        data['spc_dsp'] = sc.get('display')
    locs = resource.get('location', [])
    if locs:
        data['loc_ref'] = extract_reference_id(locs[0])
    return data


def extract_encounter_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    cls_ = resource.get('class', {})
    data['cls_sys'] = cls_.get('system')
    data['cls_cd'] = codify('cls_cd', cls_.get('code'))
    types = resource.get('type', [])
    if types:
        tc = _coding(types[0])
        data['typ_sys'] = tc.get('system')
        data['typ_cd'] = tc.get('code')
        data['typ_dsp'] = tc.get('display')
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    period = resource.get('period', {})
    data['prd_st_dts'] = period.get('start')
    data['prd_ed_dts'] = period.get('end')
    reasons = resource.get('reasonCode', [])
    if reasons:
        rc = _coding(reasons[0])
        data['rsn_cd_sys'] = rc.get('system')
        data['rsn_cd_val'] = rc.get('code')
        data['rsn_cd_dsp'] = rc.get('display')
    participants = resource.get('participant', [])
    if participants:
        for p in participants:
            ind = p.get('individual')
            if ind:
                data['svc_prf_ref'] = extract_reference_id(ind)
                break
    locs = resource.get('location', [])
    if locs:
        data['loc_ref'] = extract_reference_id(locs[0].get('location'))
    data['org_ref'] = extract_reference_id(resource.get('serviceProvider'))
    return data


def extract_condition_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    cs = _coding(resource.get('clinicalStatus'))
    data['cln_sts_sys'] = cs.get('system')
    data['cln_sts_cd'] = codify('cln_sts_cd', cs.get('code'))
    vs = _coding(resource.get('verificationStatus'))
    data['vrf_sts_sys'] = vs.get('system')
    data['vrf_sts_cd'] = codify('vrf_sts_cd', vs.get('code'))
    cats = resource.get('category', [])
    if cats:
        cc = _coding(cats[0])
        data['ctg_sys'] = cc.get('system')
        data['ctg_cd'] = cc.get('code')
        data['ctg_dsp'] = cc.get('display')
    c = _coding(resource.get('code'))
    data['cd_sys'] = c.get('system')
    data['cd_val'] = c.get('code')
    data['cd_dsp'] = c.get('display')
    data['cd_txt'] = resource.get('code', {}).get('text')
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    data['ons_dts'] = resource.get('onsetDateTime')
    data['abd_dts'] = resource.get('abatementDateTime')
    data['rec_dts'] = resource.get('recordedDate')
    return data


def extract_procedure_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    data['sts'] = codify('sts', resource.get('status'))
    c = _coding(resource.get('code'))
    data['cd_sys'] = c.get('system')
    data['cd_val'] = c.get('code')
    data['cd_dsp'] = c.get('display')
    data['cd_txt'] = resource.get('code', {}).get('text')
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    period = resource.get('performedPeriod', {})
    data['prf_st_dts'] = period.get('start')
    data['prf_ed_dts'] = period.get('end')
    performers = resource.get('performer', [])
    if performers:
        data['prf_ref'] = extract_reference_id(performers[0].get('actor'))
    data['loc_ref'] = extract_reference_id(resource.get('location'))
    reasons = resource.get('reasonReference', [])
    if reasons:
        data['rsn_ref'] = extract_reference_id(reasons[0])
    return data


def extract_observation_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    data['sts'] = codify('sts', resource.get('status'))
    cats = resource.get('category', [])
    if cats:
        cc = _coding(cats[0])
        data['ctg_sys'] = cc.get('system')
        data['ctg_cd'] = cc.get('code')
        data['ctg_dsp'] = cc.get('display')
    c = _coding(resource.get('code'))
    data['cd_sys'] = c.get('system')
    data['cd_val'] = c.get('code')
    data['cd_dsp'] = c.get('display')
    data['cd_txt'] = resource.get('code', {}).get('text')
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    data['eff_dts'] = resource.get('effectiveDateTime')
    data['iss_dts'] = resource.get('issued')
    vq = resource.get('valueQuantity', {})
    if vq:
        data['val_qty'] = vq.get('value')
        data['val_unt'] = vq.get('unit')
        data['val_sys'] = vq.get('system')
        data['val_cd'] = vq.get('code')
    data['val_str'] = resource.get('valueString')
    data['val_bool'] = resource.get('valueBoolean')
    itp = resource.get('interpretation', [])
    if itp:
        data['itp_txt'] = itp[0].get('text')
    return data


def extract_medication_request_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    data['sts'] = codify('sts', resource.get('status'))
    data['intnt'] = codify('intnt', resource.get('intent'))
    cats = resource.get('category', [])
    if cats:
        cc = _coding(cats[0])
        data['ctg_sys'] = cc.get('system')
        data['ctg_cd'] = cc.get('code')
        data['ctg_dsp'] = cc.get('display')
    mc = _coding(resource.get('medicationCodeableConcept'))
    data['med_cd_sys'] = mc.get('system')
    data['med_cd_val'] = mc.get('code')
    data['med_cd_dsp'] = mc.get('display')
    data['med_ref'] = extract_reference_id(resource.get('medicationReference'))
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    data['ath_dts'] = resource.get('authoredOn')
    data['req_ref'] = extract_reference_id(resource.get('requester'))
    reasons = resource.get('reasonReference', [])
    if reasons:
        data['rsn_cd_sys'] = None
        data['rsn_cd_val'] = None
        data['rsn_cd_dsp'] = None
    reason_codes = resource.get('reasonCode', [])
    if reason_codes:
        rc = _coding(reason_codes[0])
        data['rsn_cd_sys'] = rc.get('system')
        data['rsn_cd_val'] = rc.get('code')
        data['rsn_cd_dsp'] = rc.get('display')
    dosage = resource.get('dosageInstruction', [])
    if dosage:
        d = dosage[0]
        data['dos_txt'] = d.get('text')
        data['dos_seq'] = d.get('sequence')
        dd = d.get('doseAndRate', [{}])
        if dd:
            dq = dd[0].get('doseQuantity', {})
            data['dos_qty'] = dq.get('value')
            data['dos_unt'] = dq.get('unit')
        route = d.get('route')
        if route:
            rc = _coding(route)
            data['rte_sys'] = rc.get('system')
            data['rte_cd'] = rc.get('code')
            data['rte_dsp'] = rc.get('display')
    return data


def extract_medication_admin_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    data['sts'] = codify('sts', resource.get('status'))
    mc = _coding(resource.get('medicationCodeableConcept'))
    data['med_cd_sys'] = mc.get('system')
    data['med_cd_val'] = mc.get('code')
    data['med_cd_dsp'] = mc.get('display')
    data['med_ref'] = extract_reference_id(resource.get('medicationReference'))
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['ctx_ref'] = extract_reference_id(resource.get('context'))
    ep = resource.get('effectivePeriod', {})
    if ep:
        data['eff_st_dts'] = ep.get('start')
        data['eff_ed_dts'] = ep.get('end')
    else:
        data['eff_st_dts'] = resource.get('effectiveDateTime')
    performers = resource.get('performer', [])
    if performers:
        data['prf_ref'] = extract_reference_id(performers[0].get('actor'))
    reasons = resource.get('reasonCode', [])
    if reasons:
        rc = _coding(reasons[0])
        data['rsn_cd_sys'] = rc.get('system')
        data['rsn_cd_val'] = rc.get('code')
        data['rsn_cd_dsp'] = rc.get('display')
    data['req_ref'] = extract_reference_id(resource.get('request'))
    dosage = resource.get('dosage', {})
    if dosage:
        data['dos_txt'] = dosage.get('text')
        dq = dosage.get('dose', {})
        data['dos_qty'] = dq.get('value')
        data['dos_unt'] = dq.get('unit')
        route = dosage.get('route')
        if route:
            rc = _coding(route)
            data['rte_sys'] = rc.get('system')
            data['rte_cd'] = rc.get('code')
            data['rte_dsp'] = rc.get('display')
    return data


def extract_diagnostic_report_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    cats = resource.get('category', [])
    if cats:
        cc = _coding(cats[0])
        data['ctg_sys'] = cc.get('system')
        data['ctg_cd'] = cc.get('code')
        data['ctg_dsp'] = cc.get('display')
    c = _coding(resource.get('code'))
    data['cd_sys'] = c.get('system')
    data['cd_val'] = c.get('code')
    data['cd_dsp'] = c.get('display')
    data['cd_txt'] = resource.get('code', {}).get('text')
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    data['eff_dts'] = resource.get('effectiveDateTime')
    data['iss_dts'] = resource.get('issued')
    performers = resource.get('performer', [])
    if performers:
        data['prf_ref'] = extract_reference_id(performers[0])
    data['cnc_txt'] = resource.get('conclusion')
    return data


def extract_imaging_study_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    data['std_dts'] = resource.get('started')
    series = resource.get('series', [])
    if series:
        mod = series[0].get('modality', {})
        data['modl_sys'] = mod.get('system')
        data['modl_cd'] = mod.get('code')
        data['modl_dsp'] = mod.get('display')
    data['num_srs'] = resource.get('numberOfSeries')
    data['num_ins'] = resource.get('numberOfInstances')
    procs = resource.get('procedureCode', [])
    if procs:
        pc = _coding(procs[0])
        data['prc_cd_sys'] = pc.get('system')
        data['prc_cd_val'] = pc.get('code')
        data['prc_cd_dsp'] = pc.get('display')
    reasons = resource.get('reasonCode', [])
    if reasons:
        rc = _coding(reasons[0])
        data['rsn_cd_sys'] = rc.get('system')
        data['rsn_cd_val'] = rc.get('code')
        data['rsn_cd_dsp'] = rc.get('display')
    data['dsc'] = resource.get('description')
    return data


def extract_immunization_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    data['sts'] = codify('sts', resource.get('status'))
    sr = resource.get('statusReason')
    if sr:
        sc = _coding(sr)
        data['sts_rsn_sys'] = sc.get('system')
        data['sts_rsn_cd'] = sc.get('code')
        data['sts_rsn_dsp'] = sc.get('display')
    vc = _coding(resource.get('vaccineCode'))
    data['vac_cd_sys'] = vc.get('system')
    data['vac_cd_val'] = vc.get('code')
    data['vac_cd_dsp'] = vc.get('display')
    data['sbj_ref'] = extract_reference_id(resource.get('patient'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    data['occ_dts'] = resource.get('occurrenceDateTime')
    data['pry_src'] = codify('pry_src', resource.get('primarySource'))
    data['loc_ref'] = extract_reference_id(resource.get('location'))
    data['lot_num'] = resource.get('lotNumber')
    data['exp_dt'] = resource.get('expirationDate')
    site = resource.get('site')
    if site:
        sc = _coding(site)
        data['ste_sys'] = sc.get('system')
        data['ste_cd'] = sc.get('code')
        data['ste_dsp'] = sc.get('display')
    route = resource.get('route')
    if route:
        rc = _coding(route)
        data['rte_sys'] = rc.get('system')
        data['rte_cd'] = rc.get('code')
        data['rte_dsp'] = rc.get('display')
    dq = resource.get('doseQuantity', {})
    if dq:
        data['dos_qty'] = dq.get('value')
        data['dos_unt'] = dq.get('unit')
    performers = resource.get('performer', [])
    if performers:
        data['prf_ref'] = extract_reference_id(performers[0].get('actor'))
    return data


def extract_allergy_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    cs = _coding(resource.get('clinicalStatus'))
    data['cln_sts_sys'] = cs.get('system')
    data['cln_sts_cd'] = codify('cln_sts_cd', cs.get('code'))
    vs = _coding(resource.get('verificationStatus'))
    data['vrf_sts_sys'] = vs.get('system')
    data['vrf_sts_cd'] = codify('vrf_sts_cd', vs.get('code'))
    data['typ'] = codify('typ_algy', resource.get('type'))
    cats = resource.get('category', [])
    data['ctg'] = codify('ctg_algy', cats[0] if cats else None)
    data['crt'] = codify('crt', resource.get('criticality'))
    c = _coding(resource.get('code'))
    data['cd_sys'] = c.get('system')
    data['cd_val'] = c.get('code')
    data['cd_dsp'] = c.get('display')
    data['sbj_ref'] = extract_reference_id(resource.get('patient'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    data['ons_dts'] = resource.get('onsetDateTime')
    data['rec_dts'] = resource.get('recordedDate')
    data['rec_ref'] = extract_reference_id(resource.get('recorder'))
    return data


def extract_careplan_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    data['intnt'] = codify('intnt', resource.get('intent'))
    cats = resource.get('category', [])
    if cats:
        cc = _coding(cats[0])
        data['ctg_sys'] = cc.get('system')
        data['ctg_cd'] = cc.get('code')
        data['ctg_dsp'] = cc.get('display')
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    period = resource.get('period', {})
    data['prd_st_dts'] = period.get('start')
    data['prd_ed_dts'] = period.get('end')
    return data


def extract_careteam_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    cats = resource.get('category', [])
    if cats:
        cc = _coding(cats[0])
        data['ctg_sys'] = cc.get('system')
        data['ctg_cd'] = cc.get('code')
        data['ctg_dsp'] = cc.get('display')
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    data['evt_ref'] = extract_reference_id(resource.get('encounter'))
    period = resource.get('period', {})
    data['prd_st_dts'] = period.get('start')
    data['prd_ed_dts'] = period.get('end')
    orgs = resource.get('managingOrganization', [])
    if orgs:
        data['mng_org_ref'] = extract_reference_id(orgs[0])
    return data


def extract_device_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    udis = resource.get('udiCarrier', [])
    if udis:
        data['idn_sys'] = udis[0].get('jurisdiction')
        data['idn_val'] = udis[0].get('deviceIdentifier')
    data['sts'] = codify('sts', resource.get('status'))
    tc = _coding(resource.get('type'))
    data['typ_sys'] = tc.get('system')
    data['typ_cd'] = tc.get('code')
    data['typ_dsp'] = tc.get('display')
    data['typ_txt'] = resource.get('type', {}).get('text')
    data['mfr'] = resource.get('manufacturer')
    data['mdl_num'] = resource.get('modelNumber')
    data['vrs'] = resource.get('version')
    data['srl_num'] = resource.get('serialNumber')
    data['lot_num'] = resource.get('lotNumber')
    data['exp_dt'] = resource.get('expirationDate')
    data['sbj_ref'] = extract_reference_id(resource.get('patient'))
    data['loc_ref'] = extract_reference_id(resource.get('location'))
    return data


def extract_supply_delivery_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    data['sbj_ref'] = extract_reference_id(resource.get('patient'))
    tc = _coding(resource.get('type'))
    data['typ_sys'] = tc.get('system')
    data['typ_cd'] = tc.get('code')
    data['typ_dsp'] = tc.get('display')
    si = resource.get('suppliedItem', {})
    if si:
        ic = _coding(si.get('itemCodeableConcept'))
        data['sup_itm_cd_sys'] = ic.get('system')
        data['sup_itm_cd_val'] = ic.get('code')
        data['sup_itm_cd_dsp'] = ic.get('display')
        data['sup_itm_ref'] = extract_reference_id(si.get('itemReference'))
        q = si.get('quantity', {})
        data['qty'] = q.get('value')
        data['qty_unt'] = q.get('unit')
    data['occ_st_dts'] = resource.get('occurrenceDateTime')
    op = resource.get('occurrencePeriod', {})
    if op:
        data['occ_st_dts'] = op.get('start')
        data['occ_ed_dts'] = op.get('end')
    data['sup_ref'] = extract_reference_id(resource.get('supplier'))
    data['dst_ref'] = extract_reference_id(resource.get('destination'))
    return data


def extract_claim_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    tc = _coding(resource.get('type'))
    data['typ_sys'] = tc.get('system')
    data['typ_cd'] = tc.get('code')
    data['typ_dsp'] = tc.get('display')
    data['use_cd'] = codify('use_cd', resource.get('use'))
    data['sbj_ref'] = extract_reference_id(resource.get('patient'))
    data['crt_dts'] = resource.get('created')
    ins = resource.get('insurance', [])
    if ins:
        data['ins_ref'] = extract_reference_id(ins[0].get('coverage'))
    data['prv_ref'] = extract_reference_id(resource.get('provider'))
    pri = resource.get('priority')
    if pri:
        data['pry'] = _coding(pri).get('code')
    prs = resource.get('prescription')
    if prs:
        data['prs_cd_sys'] = None
        data['prs_cd_val'] = None
        data['prs_cd_dsp'] = None
    total = resource.get('total', {})
    data['tot_amt'] = total.get('value')
    data['tot_cur'] = total.get('currency')
    return data


def extract_eob_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    tc = _coding(resource.get('type'))
    data['typ_sys'] = tc.get('system')
    data['typ_cd'] = tc.get('code')
    data['typ_dsp'] = tc.get('display')
    data['use_cd'] = codify('use_cd', resource.get('use'))
    data['sbj_ref'] = extract_reference_id(resource.get('patient'))
    data['crt_dts'] = resource.get('created')
    data['ins_ref'] = extract_reference_id(resource.get('insurer'))
    data['prv_ref'] = extract_reference_id(resource.get('provider'))
    data['clm_ref'] = extract_reference_id(resource.get('claim'))
    data['outc'] = codify('outc', resource.get('outcome'))
    totals = resource.get('total', [])
    if totals:
        data['tot_amt'] = totals[0].get('amount', {}).get('value')
        data['tot_cur'] = totals[0].get('amount', {}).get('currency')
    payment = resource.get('payment', {})
    if payment:
        data['pmt_amt'] = payment.get('amount', {}).get('value')
        data['pmt_cur'] = payment.get('amount', {}).get('currency')
        data['pmt_dt'] = payment.get('date')
    return data


def extract_document_ref_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    ids = resource.get('identifier', [])
    if ids:
        data['idn_sys'] = ids[0].get('system')
        data['idn_val'] = ids[0].get('value')
    data['sts'] = codify('sts', resource.get('status'))
    data['doc_sts'] = codify('doc_sts', resource.get('docStatus'))
    tc = _coding(resource.get('type'))
    data['typ_sys'] = tc.get('system')
    data['typ_cd'] = tc.get('code')
    data['typ_dsp'] = tc.get('display')
    cats = resource.get('category', [])
    if cats:
        cc = _coding(cats[0])
        data['ctg_sys'] = cc.get('system')
        data['ctg_cd'] = cc.get('code')
        data['ctg_dsp'] = cc.get('display')
    data['sbj_ref'] = extract_reference_id(resource.get('subject'))
    ctx = resource.get('context', {})
    evts = ctx.get('encounter', [])
    if evts:
        data['ctx_ref'] = extract_reference_id(evts[0])
    data['dt'] = resource.get('date')
    authors = resource.get('author', [])
    if authors:
        data['ath_ref'] = extract_reference_id(authors[0])
    data['cst_ref'] = extract_reference_id(resource.get('custodian'))
    data['dsc'] = resource.get('description')
    sc = resource.get('securityLabel', [])
    if sc:
        data['sec_cls'] = _coding(sc[0]).get('code')
    contents = resource.get('content', [])
    if contents:
        att = contents[0].get('attachment', {})
        data['cnt_att_typ'] = att.get('contentType')
        data['cnt_att_url'] = att.get('url')
        data['cnt_att_sz'] = att.get('size')
        data['cnt_att_hsh'] = att.get('hash')
        data['cnt_att_ttl'] = att.get('title')
    return data


def extract_provenance_fields(resource):
    data = {'rid': resource.get('id'), 'rtp': resource.get('resourceType')}
    targets = resource.get('target', [])
    if targets:
        data['tgt_ref'] = extract_reference_id(targets[0])
    op = resource.get('occurredPeriod', {})
    if op:
        data['occ_st_dts'] = op.get('start')
        data['occ_ed_dts'] = op.get('end')
    data['rec_dts'] = resource.get('recorded')
    act = resource.get('activity')
    if act:
        ac = _coding(act)
        data['act_sys'] = ac.get('system')
        data['act_cd'] = ac.get('code')
        data['act_dsp'] = ac.get('display')
    agents = resource.get('agent', [])
    if agents:
        a = agents[0]
        at = a.get('type')
        if at:
            atc = _coding(at)
            data['agt_typ_sys'] = atc.get('system')
            data['agt_typ_cd'] = atc.get('code')
            data['agt_typ_dsp'] = atc.get('display')
        data['agt_who_ref'] = extract_reference_id(a.get('who'))
        data['agt_bhf_ref'] = extract_reference_id(a.get('onBehalfOf'))
    data['loc_ref'] = extract_reference_id(resource.get('location'))
    reasons = resource.get('reason', [])
    if reasons:
        rc = _coding(reasons[0])
        data['rsn_sys'] = rc.get('system')
        data['rsn_cd'] = rc.get('code')
        data['rsn_dsp'] = rc.get('display')
    return data

def extract_fields(resource):
    """Extract fields based on resource type"""
    resource_type = resource.get('resourceType')
    
    extractors = {
        'Patient': extract_patient_fields,
        'Practitioner': extract_practitioner_fields,
        'Organization': extract_organization_fields,
        'Location': extract_location_fields,
        'Medication': extract_medication_fields,
        'PractitionerRole': extract_practitioner_role_fields,
        'Encounter': extract_encounter_fields,
        'Condition': extract_condition_fields,
        'Procedure': extract_procedure_fields,
        'Observation': extract_observation_fields,
        'MedicationRequest': extract_medication_request_fields,
        'MedicationAdministration': extract_medication_admin_fields,
        'DiagnosticReport': extract_diagnostic_report_fields,
        'ImagingStudy': extract_imaging_study_fields,
        'Immunization': extract_immunization_fields,
        'AllergyIntolerance': extract_allergy_fields,
        'CarePlan': extract_careplan_fields,
        'CareTeam': extract_careteam_fields,
        'Device': extract_device_fields,
        'SupplyDelivery': extract_supply_delivery_fields,
        'Claim': extract_claim_fields,
        'ExplanationOfBenefit': extract_eob_fields,
        'DocumentReference': extract_document_ref_fields,
        'Provenance': extract_provenance_fields,
    }
    
    extractor = extractors.get(resource_type)
    if extractor:
        return extractor(resource)
    
    # Fallback for other resources
    data = {
        'rid': resource.get('id'),
        'rtp': resource.get('resourceType')
    }
    patient_ref = resource.get('patient') or resource.get('subject')
    if patient_ref:
        data['sbj_ref'] = extract_reference_id(patient_ref)
    return data

def handler(event, context):
    try:
        # Get DB credentials
        secret_arn = os.environ['DB_SECRET_ARN']
        secret = json.loads(secrets.get_secret_value(SecretId=secret_arn)['SecretString'])
        
        print(f"Secret keys: {list(secret.keys())}")
        
        # Connect to database
        conn = psycopg2.connect(
            host=secret.get('host'),
            port=secret.get('port', 5432),
            database=secret.get('dbname') or secret.get('database'),
            user=secret.get('username') or secret.get('user'),
            password=secret.get('password')
        )
        print("Database connection successful")
        conn.autocommit = False
        cursor = conn.cursor()
        
        # Get NDJSON files from S3
        bucket = os.environ['BUCKET_NAME']
        prefix = os.environ['DATA_PREFIX']
        
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        ndjson_files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.ndjson')]
        
        # Get resource filter from environment (comma-separated list)
        resource_filter = os.environ.get('RESOURCE_FILTER', '')
        allowed_resources = set(resource_filter.split(',')) if resource_filter else set(TABLE_MAPPING.keys())
        
        print(f"Resource filter: {allowed_resources if resource_filter else 'ALL'}")
        
        # Define loading order: base entities first, then clinical data
        LOAD_ORDER = [
            # Base entities (no dependencies)
            'Patient', 'Practitioner', 'Organization', 'Location', 'Medication',
            # Intermediate entities
            'PractitionerRole',
            # Clinical events and data (depend on base entities)
            'Encounter', 'Condition', 'Procedure', 'Observation',
            'MedicationRequest', 'MedicationAdministration',
            'DiagnosticReport', 'ImagingStudy', 'Immunization', 'AllergyIntolerance',
            'CarePlan', 'CareTeam', 'Device', 'SupplyDelivery',
            'Claim', 'ExplanationOfBenefit', 'DocumentReference', 'Provenance'
        ]
        
        # Group files by resource type
        files_by_type = {}
        for ndjson_file in ndjson_files:
            filename = ndjson_file.split('/')[-1]
            resource_type = filename.split('.')[0]
            if resource_type in TABLE_MAPPING and resource_type in allowed_resources:
                files_by_type[resource_type] = ndjson_file
        
        # Process files in defined order
        for resource_type in LOAD_ORDER:
            if resource_type not in files_by_type:
                continue
            
            ndjson_file = files_by_type[resource_type]
            filename = ndjson_file.split('/')[-1]
            
            table_name = TABLE_MAPPING[resource_type]
            print(f"Loading {resource_type} from {filename} into {table_name}")
            
            # Stream file line by line to avoid memory issues
            obj = s3.get_object(Bucket=bucket, Key=ndjson_file)
            
            count = 0
            batch = []
            for line in obj['Body'].iter_lines():
                if not line:
                    continue
                
                line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                if not line_str.strip():
                    continue
                    
                resource = json.loads(line_str)
                data = extract_fields(resource)
                
                # Truncate long string values to avoid VARCHAR overflow (skip TEXT columns)
                _text_cols = {'cd_txt','cnc_txt','cnt_att_url','dos_txt','dsc','itp_txt','typ_txt','val_str'}
                for k, v in data.items():
                    if isinstance(v, str) and len(v) > 255 and k not in _text_cols:
                        data[k] = v[:255]

                # Insert basic data
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['%s'] * len(data))
                query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) ON CONFLICT (rid) DO NOTHING"
                
                cursor.execute(query, list(data.values()))
                count += 1
                
                if count % 5000 == 0:
                    conn.commit()
                    print(f"Loaded {count} records for {resource_type}")
            
            conn.commit()
            print(f"Completed {resource_type}: {count} records")
        
        # Add foreign key constraints after all data loaded
        print("\nAdding foreign key constraints...")
        fk_script_key = os.environ['DDL_PREFIX'] + 'fhir_ddl_07_add_foreign_keys.sql'
        try:
            fk_obj = s3.get_object(Bucket=bucket, Key=fk_script_key)
            fk_sql = fk_obj['Body'].read().decode('utf-8')
            
            # Execute each ALTER TABLE statement individually
            success_count = 0
            fail_count = 0
            for statement in fk_sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        cursor.execute(statement)
                        conn.commit()
                        success_count += 1
                    except Exception as stmt_error:
                        print(f"Warning: FK constraint failed: {stmt_error}")
                        conn.rollback()
                        fail_count += 1
            
            print(f"Foreign key constraints: {success_count} added, {fail_count} failed")
        except Exception as fk_error:
            print(f"Warning: Could not load FK script: {fk_error}")
        
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'body': json.dumps('Data loaded successfully')
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if conn:
            conn.rollback()
        raise e
