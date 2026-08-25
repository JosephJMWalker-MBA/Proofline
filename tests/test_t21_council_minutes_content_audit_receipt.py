from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RECEIPT=ROOT/'experiments'/'akron-2026'/'r1_t21_council_minutes_content_audit_summary.json'
PLAN=ROOT/'experiments'/'akron-2026'/'r1_t21_council_minutes_content_audit_plan.json'

def test_frozen_content_audit_receipt_is_non_terminal_and_target_local():
    receipt=json.loads(RECEIPT.read_text())
    plan=json.loads(PLAN.read_text())
    assert receipt['schema']=='proofline-akron-t21-council-minutes-content-audit-receipt/v1'
    assert receipt['counts']=={
        'document_count':26,'documents_with_target_pages':6,'page_count':114,
        'target_page_count':6,'target_record_block_count':6,'terminal_candidate_block_count':0,
    }
    assert receipt['text_extraction']=={'engine':'PyMuPDF','ocr_used':False,'version':'1.28.2'}
    assert receipt['terminal_candidate_blocks']==[]
    assert receipt['authority_boundary']['terminal_outcome_assigned'] is False
    assert receipt['outcome']['status']=='unknown'
    assert plan['selection_rule']['procedural_phrase_must_be_in_same_target_record_block'] is True
    hearing=receipt['observations']['march_9_special_hearing_block']
    assert hearing['procedural_phrase_hits']==[
        'public_hearing_declared','public_hearing_closed','substitute_read',
        'committee_favorable_poll','committee_time_poll',
    ]
    assert hearing['favorable_report_poll']=='Ayes 3, Nays 1 (Hannah)'
    assert hearing['time_poll']=='Ayes 4, Nays 0'
