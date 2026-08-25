from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RECEIPT=ROOT/'experiments'/'akron-2026'/'r1_t21_committee_minutes_source_contract_summary.json'


def test_receipt_freezes_publisher_committee_schema_without_search() -> None:
    r=json.loads(RECEIPT.read_text(encoding='utf-8'))
    assert r['schema']=='proofline-akron-t21-committee-minutes-source-contract-receipt/v1'
    assert r['source_contract']['query']['id']=='202'
    assert r['source_contract']['query']['name']=='Committee Meeting Minutes'
    m=r['keyword_metadata']
    assert m['request_payload']=={'QueryID':202}
    assert m['keyword_ids']==['124','532','105']
    assert m['keyword_names']==['Meeting Date','Year','Committee']
    assert m['meeting_date']=={'data_type':'Date','dataset_is_null':True,'max_length':27}
    assert m['year']['dataset_count']==151 and m['year']['contains_2026'] is True
    assert m['committee']['dataset_count']==38
    assert m['committee']['planning_economic_development_value']=='PLANNING & ECONOMIC DEVELOPMENT'
    assert m['committee']['contains_planning_economic_development'] is True
    assert r['authority_boundary']['document_search_submitted'] is False
    assert r['authority_boundary']['terminal_outcome_assigned'] is False
    assert r['interpretation']['document_search_performed'] is False
    assert r['interpretation']['eastwood_outcome_status']=='Unknown'


def test_receipt_hashes_have_sha256_shape() -> None:
    r=json.loads(RECEIPT.read_text(encoding='utf-8'))
    values=[r['canonical_measurement']['raw_source_contract_sha256'], r['keyword_metadata']['raw_sha256'],
            r['keyword_metadata']['keywords_signature_sha256'], r['keyword_metadata']['committee']['dataset_signature_sha256']]
    assert all(len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in values)
