"""Collect read-only Solr results for the typo failure analysis.

This script only sends GET requests to Solr's ``select`` endpoint. It never
calls update, delete, commit, reload, or other mutating endpoints.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
import sys
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = next(parent for parent in SCRIPT_DIR.parents if (parent / ".git").exists())
PROGRAM_DIR = next(path for path in ROOT.iterdir() if path.name.startswith("4") and path.is_dir())
WAKATI_PATH = next(
    path
    for path in ROOT.rglob("wakati.py")
    if "8-3" in str(path.parent)
)
TOOLS_DIR = WAKATI_PATH.parent

for import_dir in (PROGRAM_DIR, TOOLS_DIR):
    if str(import_dir) not in sys.path:
        sys.path.insert(0, str(import_dir))

import config  # noqa: E402
import generate_query  # noqa: E402
import wakati  # noqa: E402


SOLR_URL = f"http://127.0.0.1:8983/solr/{config.SOLR_CORE_NAME}/select"
FIELDS = [
    "doi",
    "first_author",
    "creator",
    "title",
    "journal",
    "issued",
    "volume_issue",
    "page_range",
    "score",
]
POSITIVE_RC_FIELDS = ["creator", "title", "journal", "issued", "volume_issue", "page_range"]
POSITIVE_CC_FIELDS = ["first_author", "title", "journal", "issued", "volume_issue", "page_range"]
NEGATIVE_RC_FIELDS = ["creator", "title", "journal", "issued"]
NEGATIVE_CC_FIELDS = ["first_author", "title", "journal", "issued"]
THRESHOLDS = {
    "rc": config.RC_THRESHOLD,
    "cc": config.CC_THRESHOLD,
    "mc": config.MC_THRESHOLD,
}
STYLES = ("jsai", "ipsj", "lsj")
_thread_local = threading.local()


def get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        session = requests.Session()
        session.mount("http://", HTTPAdapter(max_retries=retry))
        _thread_local.session = session
    return _thread_local.session


def solr_get(params: dict) -> dict:
    response = get_session().get(SOLR_URL, params=params, timeout=120)
    response.raise_for_status()
    return response.json()


def search_reference(reference: str) -> list[dict]:
    response = solr_get(
        {
            "q": generate_query.escape_solr_query(reference),
            "q.op": "OR",
            "fl": ",".join(FIELDS),
            "df": "jalcdata",
            "rows": 10,
            "wt": "json",
        }
    )
    return response["response"]["docs"]


def fetch_doi(doi: str) -> dict:
    escaped_doi = doi.replace("\\", "\\\\").replace('"', '\\"')
    response = solr_get(
        {
            "q": f'doi:"{escaped_doi}"',
            "fl": ",".join(FIELDS),
            "rows": 10,
            "wt": "json",
        }
    )
    docs = response["response"]["docs"]
    if not docs:
        raise RuntimeError(f"DOI not found in Solr: {doi}")
    if len(docs) > 1:
        print(f"warning: duplicate DOI in Solr: {doi} ({len(docs)} docs)", flush=True)
    return docs[0]


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def unique_reference_tokens(reference: str) -> list[str]:
    return sorted(set(wakati.get_token(reference)))


def document_rc_tokens(document: dict, field_names: list[str]) -> set[str]:
    tokens = set()
    for field_name in field_names:
        field_tokens = []
        for value in as_list(document.get(field_name)):
            field_tokens.extend(wakati.get_token(value))
        tokens.update(field_tokens)
    return tokens


def calc_rc(reference_tokens: list[str], document: dict, field_names: list[str]) -> tuple[float, list[str]]:
    candidate_tokens = document_rc_tokens(document, field_names)
    if not reference_tokens:
        return 0.0, []
    unmatched = [token for token in reference_tokens if token not in candidate_tokens]
    score = (len(reference_tokens) - len(unmatched)) / len(reference_tokens)
    return score, unmatched


def calc_cc(
    reference_tokens: list[str],
    document: dict,
    field_names: list[str],
) -> tuple[float, dict[str, float]]:
    reference_token_set = set(reference_tokens)
    components = {}
    for field_name in field_names:
        max_score = 0.0
        for value in as_list(document.get(field_name)):
            tokens = wakati.get_token(value)
            if not tokens:
                continue
            common = sum(token in reference_token_set for token in tokens)
            max_score = max(max_score, common / len(tokens))
        components[field_name] = max_score
    return sum(components.values()) / len(field_names), components


def calc_mc(rc_score: float, cc_score: float) -> float:
    beta = 0.5
    denominator = (beta**2) * cc_score + rc_score
    if denominator == 0:
        return 0.0
    return ((1 + beta**2) * rc_score * cc_score) / denominator


def score_document(reference: str, document: dict, positive: bool) -> dict:
    reference_tokens = unique_reference_tokens(reference)
    rc_fields = POSITIVE_RC_FIELDS if positive else NEGATIVE_RC_FIELDS
    cc_fields = POSITIVE_CC_FIELDS if positive else NEGATIVE_CC_FIELDS
    rc_score, unmatched = calc_rc(reference_tokens, document, rc_fields)
    cc_score, cc_components = calc_cc(reference_tokens, document, cc_fields)
    return {
        "rc": rc_score,
        "cc": cc_score,
        "mc": calc_mc(rc_score, cc_score),
        "cc_components": cc_components,
        "rc_unmatched_tokens": unmatched,
        "reference_token_count": len(reference_tokens),
    }


def score_search(reference: str, documents: list[dict], positive: bool, correct_doi: str | None) -> dict:
    scored = []
    for rank, document in enumerate(documents, start=1):
        scores = score_document(reference, document, positive)
        scored.append(
            {
                "rank": rank,
                "doi": document["doi"],
                "scores": scores,
            }
        )

    output = {
        "retrieved_dois": [document["doi"] for document in documents],
        "metrics": {},
    }
    for metric in ("rc", "cc", "mc"):
        best = max(scored, key=lambda item: item["scores"][metric])
        accepted = best["scores"][metric] >= THRESHOLDS[metric]
        metric_result = {
            "score": best["scores"][metric],
            "candidate_doi": best["doi"],
            "candidate_search_rank": best["rank"],
            "accepted": accepted,
            "rc": best["scores"]["rc"],
            "cc": best["scores"]["cc"],
            "mc": best["scores"]["mc"],
            "cc_components": best["scores"]["cc_components"],
            "rc_unmatched_tokens": best["scores"]["rc_unmatched_tokens"],
        }
        if positive:
            if accepted and best["doi"] == correct_doi:
                case = "case1"
            elif best["doi"] == correct_doi:
                case = "case2"
            elif accepted:
                case = "case3"
            else:
                case = "case4"
            correct = next((item for item in scored if item["doi"] == correct_doi), None)
            metric_result.update(
                {
                    "case": case,
                    "correct_in_top10": correct is not None,
                    "correct_search_rank": correct["rank"] if correct else None,
                    "correct_score_in_top10": correct["scores"][metric] if correct else None,
                }
            )
        else:
            metric_result["classification"] = "false_positive" if accepted else "true_negative"
        output["metrics"][metric] = metric_result
    return output


def find_data_files() -> dict:
    typo_jsai = next(ROOT.rglob("positive_reference_jsai_eval_typo_crossref.txt"))
    typo_dir = typo_jsai.parent
    no_typo_jsai = next(ROOT.rglob("positive_reference_jsai_eval_none_typo_crossref.txt"))
    no_typo_dir = no_typo_jsai.parent
    negative_ipsj = next(ROOT.rglob("negative_reference_ipsj_eval.txt"))
    negative_dir = negative_ipsj.parent
    return {
        "typo_dir": typo_dir,
        "no_typo_dir": no_typo_dir,
        "negative_dir": negative_dir,
        "manifest": typo_dir / "typo_manifest_eval.jsonl",
        "doi_list": typo_dir / "doi_list.txt",
    }


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def write_json_atomic(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def write_jsonl_atomic(path: Path, records: list[dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(path)


def fetch_correct_documents(dois: list[str], workers: int, force: bool) -> dict[str, dict]:
    cache_path = SCRIPT_DIR / "analysis_correct_documents.json"
    if cache_path.exists() and not force:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if set(cached) == set(dois):
            print(f"reuse {cache_path.name}: {len(cached)} docs", flush=True)
            return cached

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        documents = list(executor.map(fetch_doi, dois))
    cache = dict(zip(dois, documents))
    write_json_atomic(cache_path, cache)
    print(
        f"fetched correct documents: {len(cache)} docs, {time.monotonic() - started:.1f}s",
        flush=True,
    )
    return cache


def load_manifest(path: Path) -> dict[tuple[str, str], dict]:
    manifest = {}
    for line in read_lines(path):
        record = json.loads(line)
        manifest[(record["style"], record["doi"])] = record
    return manifest


def collect_positive_style(
    style: str,
    files: dict,
    dois: list[str],
    manifest: dict,
    correct_documents: dict[str, dict],
    workers: int,
    force: bool,
) -> list[dict]:
    output_path = SCRIPT_DIR / f"analysis_positive_{style}.jsonl"
    if output_path.exists() and not force:
        existing = read_lines(output_path)
        if len(existing) == len(dois):
            print(f"reuse {output_path.name}: {len(existing)} records", flush=True)
            return [json.loads(line) for line in existing]

    typo_refs = read_lines(files["typo_dir"] / f"positive_reference_{style}_eval_typo_crossref.txt")
    no_typo_refs = read_lines(
        files["no_typo_dir"] / f"positive_reference_{style}_eval_none_typo_crossref.txt"
    )
    if not (len(typo_refs) == len(no_typo_refs) == len(dois)):
        raise RuntimeError(f"positive input length mismatch: {style}")

    def collect_one(item) -> dict:
        index, doi, typo_reference, no_typo_reference = item
        manifest_record = manifest[(style, doi)]
        net_changed = typo_reference != no_typo_reference
        typo_search = score_search(
            typo_reference,
            search_reference(typo_reference),
            positive=True,
            correct_doi=doi,
        )
        no_typo_search = None
        if net_changed:
            no_typo_search = score_search(
                no_typo_reference,
                search_reference(no_typo_reference),
                positive=True,
                correct_doi=doi,
            )
        correct_document = correct_documents[doi]
        return {
            "style": style,
            "index": index,
            "doi": doi,
            "typo_reference": typo_reference,
            "no_typo_reference": no_typo_reference,
            "net_changed": net_changed,
            "manifest": manifest_record,
            "correct_document": {
                field: correct_document.get(field, [])
                for field in FIELDS
                if field != "score"
            },
            "direct_typo": score_document(typo_reference, correct_document, positive=True),
            "direct_no_typo": score_document(no_typo_reference, correct_document, positive=True),
            "typo_search": typo_search,
            "no_typo_search": no_typo_search,
        }

    items = list(enumerate(zip(dois, typo_refs, no_typo_refs)))
    items = [(index, *values) for index, values in items]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        records = list(executor.map(collect_one, items))
    write_jsonl_atomic(output_path, records)
    print(
        f"collected positive {style}: {len(records)} records, {time.monotonic() - started:.1f}s",
        flush=True,
    )
    return records


def collect_negative_style(style: str, files: dict, workers: int, force: bool) -> list[dict]:
    output_path = SCRIPT_DIR / f"analysis_negative_{style}.jsonl"
    references = read_lines(files["negative_dir"] / f"negative_reference_{style}_eval.txt")
    if output_path.exists() and not force:
        existing = read_lines(output_path)
        if len(existing) == len(references):
            print(f"reuse {output_path.name}: {len(existing)} records", flush=True)
            return [json.loads(line) for line in existing]

    def collect_one(item) -> dict:
        index, reference = item
        search = score_search(
            reference,
            search_reference(reference),
            positive=False,
            correct_doi=None,
        )
        return {
            "style": style,
            "index": index,
            "reference": reference,
            "search": search,
        }

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        records = list(executor.map(collect_one, enumerate(references)))
    write_jsonl_atomic(output_path, records)
    print(
        f"collected negative {style}: {len(records)} records, {time.monotonic() - started:.1f}s",
        flush=True,
    )
    return records


def print_validation(positive: dict[str, list[dict]], negative: dict[str, list[dict]]) -> None:
    for style, records in positive.items():
        for metric in ("rc", "cc", "mc"):
            cases = {}
            for record in records:
                case = record["typo_search"]["metrics"][metric]["case"]
                cases[case] = cases.get(case, 0) + 1
            print(f"positive {style} {metric}: {cases}")
    for style, records in negative.items():
        for metric in ("rc", "cc", "mc"):
            classifications = {}
            for record in records:
                value = record["search"]["metrics"][metric]["classification"]
                classifications[value] = classifications.get(value, 0) + 1
            print(f"negative {style} {metric}: {classifications}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("all", "positive", "negative"), default="all")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    files = find_data_files()
    dois = read_lines(files["doi_list"])
    manifest = load_manifest(files["manifest"])
    positive = {}
    negative = {}

    if args.phase in ("all", "positive"):
        correct_documents = fetch_correct_documents(dois, args.workers, args.force)
        for style in STYLES:
            positive[style] = collect_positive_style(
                style,
                files,
                dois,
                manifest,
                correct_documents,
                args.workers,
                args.force,
            )

    if args.phase in ("all", "negative"):
        for style in STYLES:
            negative[style] = collect_negative_style(style, files, args.workers, args.force)

    print_validation(positive, negative)


if __name__ == "__main__":
    main()
