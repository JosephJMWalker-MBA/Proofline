#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path
import fitz

SCHEMA = "proofline-akron-t21-council-minutes-content-audit-measurement/v1"
PLAN_SCHEMA = "proofline-akron-t21-council-minutes-content-audit-plan/v1"
RECEIPT_SCHEMA = "proofline-akron-t21-council-minutes-document-retrieval-receipt/v1"

def sha256_bytes(b: bytes)->str: return hashlib.sha256(b).hexdigest()
def stable_json(v)->str: return json.dumps(v, sort_keys=True, separators=(",",":"), ensure_ascii=False)
def sha256_json(v)->str: return sha256_bytes(stable_json(v).encode())
def load(p):
    v=json.loads(Path(p).read_text())
    if not isinstance(v,dict): raise ValueError(f"{p} must contain object")
    return v

def normalize(s:str)->str:
    return " ".join(s.split())

def validate_source(retrieval:dict, receipt:dict, root:Path)->None:
    if receipt.get("schema") != RECEIPT_SCHEMA: raise ValueError("unexpected retrieval receipt schema")
    expected={(r["meeting_id"],r["stable_projection_sha256"],r["document_sha256"],r["document_byte_length"])
              for r in receipt["document_receipts"]}
    actual=set()
    for r in retrieval["retrievals"]:
        p=root/r["document_filename"]
        b=p.read_bytes()
        if sha256_bytes(b)!=r["document_sha256"] or len(b)!=r["document_byte_length"]:
            raise ValueError(f"retrieved file drift: {p}")
        actual.add((r["meeting_id"],r["stable_projection_sha256"],r["document_sha256"],r["document_byte_length"]))
    if actual != expected: raise ValueError("retrieved PDF population diverged from frozen #101 receipt")

def anchor_hits(text:str)->list[str]:
    low=normalize(text).lower()
    hits=[]
    if "1928 eastwood avenue" in low: hits.append("exact_address")
    if "defense education training facility" in low or "defence education training facility" in low: hits.append("distinctive_title_phrase")
    if re.search(r"pc\s*-?\s*2025\s*-?\s*80\s*-?\s*cu", low): hits.append("planning_case")
    if "david walker" in low: hits.append("petitioner_name")
    if "training facility" in low and "eastwood" in low: hits.append("training_eastwood_cooccurrence")
    return hits

def split_blocks(text:str, boundaries:list[str])->list[dict]:
    lines=text.splitlines()
    starts=[0]
    for i,line in enumerate(lines):
        stripped=line.strip()
        if i and any(stripped.startswith(b) for b in boundaries): starts.append(i)
    starts=sorted(set(starts)); starts.append(len(lines))
    out=[]
    for j in range(len(starts)-1):
        chunk="\n".join(lines[starts[j]:starts[j+1]]).strip()
        if chunk: out.append({"line_start":starts[j]+1,"line_end":starts[j+1],"text":chunk})
    return out

def main()->int:
    if len(sys.argv)!=6:
        raise SystemExit("usage: audit.py RETRIEVAL_JSON RETRIEVAL_DIR RECEIPT PLAN OUTPUT_DIR")
    retrieval=load(sys.argv[1]); root=Path(sys.argv[2]); receipt=load(sys.argv[3]); plan=load(sys.argv[4]); out=Path(sys.argv[5]); out.mkdir(parents=True,exist_ok=True)
    if plan.get("schema")!=PLAN_SCHEMA: raise ValueError("unexpected content audit plan schema")
    if plan["text_extraction"]["ocr_allowed"] is not False: raise ValueError("OCR must remain disabled")
    validate_source(retrieval,receipt,root)
    phrase_defs=plan["procedural_phrases"]; boundaries=plan["record_block_boundaries"]
    docs=[]; matched_pages=[]; target_blocks=[]; terminal_candidates=[]; total_pages=0
    page_dir=out/"matched-pages"; page_dir.mkdir(exist_ok=True)
    for r in sorted(retrieval["retrievals"], key=lambda x:(x["meeting_id"],x["document_sha256"])):
        p=root/r["document_filename"]
        doc=fitz.open(p); total_pages += len(doc); doc_matches=[]
        for i,page in enumerate(doc):
            text=page.get_text("text")
            hits=anchor_hits(text)
            if not hits: continue
            page_no=i+1; text_bytes=text.encode("utf-8"); page_sha=sha256_bytes(text_bytes)
            text_name=f"{r['document_sha256']}-p{page_no:03d}.txt"; (page_dir/text_name).write_bytes(text_bytes)
            blocks=[]
            for bi,b in enumerate(split_blocks(text,boundaries), start=1):
                bhits=anchor_hits(b["text"])
                if not bhits: continue
                normalized=normalize(b["text"])
                proc=[d["id"] for d in phrase_defs if d["pattern"].lower() in normalized.lower()]
                entry={"block_index":bi,"line_start":b["line_start"],"line_end":b["line_end"],"anchor_hits":bhits,
                       "procedural_phrase_hits":proc,"block_text_sha256":sha256_bytes(b["text"].encode("utf-8")),"block_text":b["text"]}
                blocks.append(entry)
                target_blocks.append({"meeting_id":r["meeting_id"],"document_sha256":r["document_sha256"],"page":page_no,**entry})
                tc=[x for x in proc if x in plan["terminal_candidate_phrase_ids"]]
                if tc: terminal_candidates.append({"meeting_id":r["meeting_id"],"document_sha256":r["document_sha256"],"page":page_no,"block_index":bi,"phrase_ids":tc})
            page_entry={"meeting_id":r["meeting_id"],"document_sha256":r["document_sha256"],"stable_projection_sha256":r["stable_projection_sha256"],
                        "page":page_no,"anchor_hits":hits,"page_text_sha256":page_sha,"page_text_byte_length":len(text_bytes),"page_text_file":f"matched-pages/{text_name}","target_blocks":blocks}
            doc_matches.append(page_entry); matched_pages.append(page_entry)
        docs.append({"meeting_id":r["meeting_id"],"document_sha256":r["document_sha256"],"page_count":len(doc),"matched_page_count":len(doc_matches),"matched_pages":doc_matches})
    stable_pages=[{k:p[k] for k in ("meeting_id","document_sha256","page","anchor_hits","page_text_sha256")} for p in matched_pages]
    stable_blocks=[{k:b[k] for k in ("meeting_id","document_sha256","page","block_index","anchor_hits","procedural_phrase_hits","block_text_sha256")} for b in target_blocks]
    measurement={
      "schema":SCHEMA,"stage":"frozen_source_bytes_text_layer_page_and_record_block_audit",
      "text_extraction":{"engine":"PyMuPDF","version":fitz.VersionBind,"ocr_used":False},
      "source_receipt":{"schema":receipt["schema"],"document_receipts_signature_sha256":receipt["document_receipts_signature_sha256"],"document_count":len(receipt["document_receipts"])},
      "plan":{"schema":plan["schema"],"sha256":sha256_json(plan)},
      "counts":{"document_count":len(docs),"page_count":total_pages,"documents_with_target_pages":sum(1 for d in docs if d["matched_page_count"]),"target_page_count":len(matched_pages),"target_record_block_count":len(target_blocks),"terminal_candidate_block_count":len(terminal_candidates)},
      "documents":docs,
      "target_record_blocks":target_blocks,
      "terminal_candidate_blocks":terminal_candidates,
      "target_page_population_signature_sha256":sha256_json(stable_pages),
      "target_record_block_population_signature_sha256":sha256_json(stable_blocks),
      "authority_boundary":{"source_pdf_population_verified":True,"ocr_used":False,"page_text_extracted":True,"procedural_phrase_hits_are_observations_only":True,"terminal_outcome_assigned":False,"absence_treated_as_disposition":False,"causality_assigned":False,"detector_authorized":False,"lead_count":None},
      "outcome":{"status":"unknown","reason":"This audit records target-local minutes text and procedural phrases only. No terminal outcome is assigned without separately governed explicit terminal semantics."}
    }
    path=out/"council-minutes-content-audit.json"; path.write_text(json.dumps(measurement,indent=2,sort_keys=True)+"\n")
    print(json.dumps(measurement["counts"],indent=2,sort_keys=True))
    return 0
if __name__=="__main__": raise SystemExit(main())
