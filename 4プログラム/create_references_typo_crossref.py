"""Generate reproducible positive-reference data containing typographical errors."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import random
import re
import unicodedata

import config


DATASET_CONFIG = {
    "pre": {
        "source_dir": Path(
            "../5データ/5-1予備実験用データ/"
            "5-1-1参考文献文字列_誤植なし（実在）"
        ),
        "output_dir": Path(
            "../5データ/5-1予備実験用データ/"
            "5-1-1参考文献文字列_誤植あり_Crossrefなし（実在）"
        ),
        "baseline_files": {
            "jsai": "positive_reference_jsai_pre_none_typo.txt",
            "ipsj": "positive_reference_ipsj_pre_none_typo.txt",
            "lsj": "positive_reference_lsj_pre_none_typo.txt",
        },
        "output_files": {
            "jsai": "positive_reference_jsai_pre_typo_crossref.txt",
            "ipsj": "positive_reference_ipsj_pre_typo_crossref.txt",
            "lsj": "positive_reference_lsj_pre_typo_crossref.txt",
        },
        "manifest_file": "typo_manifest_pre.jsonl",
    },
    "eval": {
        "source_dir": Path(
            "../5データ/5-2評価実験用データ/"
            "5-2-1参考文献文字列_誤植なし_Crossrefなし（実在）"
        ),
        "output_dir": Path(
            "../5データ/5-2評価実験用データ/"
            "5-2-1参考文献文字列_誤植あり_Crossrefなし（実在）"
        ),
        "baseline_files": {
            "jsai": "positive_reference_jsai_eval_none_typo_crossref.txt",
            "ipsj": "positive_reference_ipsj_eval_none_typo_crossref.txt",
            "lsj": "positive_reference_lsj_eval_none_typo_crossref.txt",
        },
        "output_files": {
            "jsai": "positive_reference_jsai_eval_typo_crossref.txt",
            "ipsj": "positive_reference_ipsj_eval_typo_crossref.txt",
            "lsj": "positive_reference_lsj_eval_typo_crossref.txt",
        },
        "manifest_file": "typo_manifest_eval.jsonl",
    },
}

SCJ_FILE = Path(
    "../5データ/5-3日本学術会議協力学術研究団体/"
    "scj_registered_AcademicSocieties.txt"
)
STYLES = ("jsai", "ipsj", "lsj")


def has_japanese(text):
    text = unicodedata.normalize("NFKC", text or "")
    return bool(
        re.search(
            r"[\u3040-\u309F\u30A0-\u30FF\uFF66-\uFF9F\u4E00-\u9FFF]",
            text,
        )
    )


def check_lang(doc):
    title_lang, creator_lang, journal_lang = "", "", ""

    for title in doc["title_list"]:
        lang = title.get("lang", "")
        if lang == "" and has_japanese(title.get("title", "")):
            lang = "ja"
        if lang == "ja":
            title_lang = "ja"
            break

    for creator in doc["creator_list"]:
        for creator_name in creator["names"]:
            lang = creator_name.get("lang", "")
            if lang == "" and has_japanese(creator_name.get("first_name", "")):
                lang = "ja"
            if lang == "ja":
                creator_lang = "ja"
                break

    for journal in doc["journal_title_name_list"]:
        lang = journal.get("lang", "")
        if lang == "" and has_japanese(journal.get("journal_title_name", "")):
            lang = "ja"
        if lang == "ja":
            journal_lang = "ja"
            break

    return title_lang == "ja" and creator_lang == "ja" and journal_lang == "ja"


def check_publisher(doc, scj_registered_academic_societies):
    for academic_society in scj_registered_academic_societies:
        for publisher in doc["publisher_list"]:
            if academic_society in publisher.get("publisher_name", ""):
                return True
    return False


def get_title(doc):
    title_text = ""
    for value in doc["title_list"]:
        lang = value.get("lang", "")
        title = value.get("title", "")
        subtitle = value.get("subtitle", "")
        if lang == "" and has_japanese(title):
            lang = "ja"
        if lang == "ja":
            title_text = title
            if subtitle != "":
                title_text = title_text + " " + subtitle
    return title_text


def get_journal(doc):
    journal_text = ""
    for value in doc["journal_title_name_list"]:
        journal_title = value.get("journal_title_name", "")
        journal_type = value.get("type", "")
        lang = value.get("lang", "")
        if lang == "" and has_japanese(journal_title):
            lang = "ja"
        if lang == "ja":
            journal_text = journal_title
            if journal_type == "full":
                break
    return journal_text


def get_creator(doc):
    creator_list = []
    for creator in doc["creator_list"]:
        if len(creator["names"]) == 1:
            name = creator["names"][0]
            creator_list.append(
                [name.get("last_name", ""), name.get("first_name", "")]
            )
            continue

        for name in creator["names"]:
            last_name = name.get("last_name", "")
            first_name = name.get("first_name", "")
            lang = name.get("lang", "")
            if has_japanese(first_name):
                lang = "ja"
            if lang == "ja":
                creator_list.append([last_name, first_name])
                break
    return creator_list


def format_lsj_creator_name(name):
    last_name, first_name = name[0], name[1]
    if last_name and first_name and not has_japanese(last_name):
        return last_name + " " + first_name
    return last_name + first_name


def create_style_authors(style, creator_list):
    authors = []
    if style == "jsai":
        for last_name, first_name in creator_list:
            if last_name != "":
                if has_japanese(last_name):
                    authors.append(last_name)
                else:
                    authors.append(last_name + ", " + first_name[0] + ".")
            else:
                authors.append(first_name)
        return authors

    if style == "ipsj":
        for last_name, first_name in creator_list[:3]:
            if last_name != "":
                if has_japanese(last_name):
                    authors.append(last_name + first_name)
                else:
                    authors.append(last_name + ", " + first_name[0] + ".")
            else:
                authors.append(first_name)
        return authors

    if style == "lsj":
        return [format_lsj_creator_name(name) for name in creator_list]

    raise ValueError(f"未対応の引用スタイルです: {style}")


def create_reference(style, authors, fields):
    title = fields["title"]
    journal = fields["journal"]
    volume = fields["volume"]
    issue = fields["issue"]
    first_page, last_page = fields["pages"]
    year = fields["year"]

    if style == "jsai":
        creator_text = "，".join(authors)
        return (
            creator_text
            + "："
            + title
            + "，"
            + journal
            + "，Vol."
            + volume
            + ", No."
            + issue
            + ", pp."
            + first_page
            + "-"
            + last_page
            + " ("
            + year
            + ")."
        )

    if style == "ipsj":
        creator_text = "，".join(authors)
        return (
            creator_text
            + "："
            + title
            + "，"
            + journal
            + "，Vol."
            + volume
            + "，No."
            + issue
            + "，pp."
            + first_page
            + "-"
            + last_page
            + "（"
            + year
            + "）．"
        )

    if style == "lsj":
        return (
            "・".join(authors)
            + "（"
            + year
            + "）「"
            + title
            + "」『"
            + journal
            + "』"
            + volume
            + "（"
            + issue
            + "）: "
            + first_page
            + "–"
            + last_page
            + "."
        )

    raise ValueError(f"未対応の引用スタイルです: {style}")


def _remove_random_char(value, rng):
    if not value:
        return value, None
    index = rng.randint(0, len(value) - 1)
    return value[:index] + value[index + 1 :], index


def _change_numeric_value(value, rng):
    delta = rng.choice([1, -1])
    return str(int(value) + delta), delta


def _apply_one_typo(fields, authors, rng):
    roll = rng.randint(0, 99)
    operation = {"selection_roll": roll, "changed": False}

    if roll < 40:
        operation["type"] = "title_char_deletion"
        before = fields["title"]
        fields["title"], index = _remove_random_char(before, rng)
        operation.update(
            {
                "changed": fields["title"] != before,
                "character_index": index,
            }
        )
        return operation

    if roll < 60:
        operation["type"] = "author_omission"
        if len(authors) > 1:
            operation["removed_author"] = authors.pop()
            operation["changed"] = True
        return operation

    if roll < 75:
        operation["type"] = "journal_char_deletion"
        before = fields["journal"]
        fields["journal"], index = _remove_random_char(before, rng)
        operation.update(
            {
                "changed": fields["journal"] != before,
                "character_index": index,
            }
        )
        return operation

    if roll < 80 and fields["year"].isdigit():
        operation["type"] = "year_shift"
        fields["year"], operation["delta"] = _change_numeric_value(
            fields["year"], rng
        )
        operation["changed"] = True
        return operation

    if roll < 85 and fields["volume"].isdigit():
        operation["type"] = "volume_shift"
        fields["volume"], operation["delta"] = _change_numeric_value(
            fields["volume"], rng
        )
        operation["changed"] = True
        return operation

    if roll < 90 and fields["issue"].isdigit():
        operation["type"] = "issue_shift"
        fields["issue"], operation["delta"] = _change_numeric_value(
            fields["issue"], rng
        )
        operation["changed"] = True
        return operation

    operation["type"] = "page_shift"
    page_index = rng.choice([0, 1])
    operation["page_index"] = page_index
    if fields["pages"][page_index].isdigit():
        fields["pages"][page_index], operation["delta"] = _change_numeric_value(
            fields["pages"][page_index], rng
        )
        operation["changed"] = True
    return operation


def apply_typos(fields, authors, rng):
    typo_roll = rng.randint(0, 99)
    audit = {
        "typo_selection_roll": typo_roll,
        "selected_for_typo": typo_roll < 35,
        "requested_typo_count": 0,
        "applied_typo_count": 0,
        "operations": [],
    }
    if typo_roll >= 35:
        return fields, authors, audit

    error_count_roll = rng.randint(0, 99)
    requested_typo_count = 2 if error_count_roll < 20 else 1
    audit["error_count_roll"] = error_count_roll
    audit["requested_typo_count"] = requested_typo_count

    for _ in range(requested_typo_count):
        operation = _apply_one_typo(fields, authors, rng)
        audit["operations"].append(operation)

    audit["applied_typo_count"] = sum(
        operation["changed"] for operation in audit["operations"]
    )
    return fields, authors, audit


def _stable_rng(base_seed, dataset_name, style, doi):
    key = f"{base_seed}:{dataset_name}:{style}:{doi}".encode("utf-8")
    seed = int.from_bytes(sha256(key).digest()[:8], "big")
    return random.Random(seed)


def _read_lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def _read_scj_societies():
    societies = []
    with SCJ_FILE.open(encoding="utf-8") as file:
        for line in file:
            societies += line.split(",")
    return societies


def _metadata_fields(doc):
    return {
        "title": get_title(doc),
        "journal": get_journal(doc),
        "volume": doc["volume"],
        "issue": doc["issue"],
        "pages": [doc["first_page"], doc["last_page"]],
        "year": doc["publication_date"]["publication_year"],
    }


def _verify_baseline(config, generated_baselines):
    for style in STYLES:
        expected_path = config["source_dir"] / config["baseline_files"][style]
        expected = _read_lines(expected_path)
        actual = generated_baselines[style]
        if expected == actual:
            print(f"{style.upper()} 誤植なし既存データとの一致確認：OK")
            continue

        mismatch_index = next(
            (
                index
                for index, (expected_line, actual_line) in enumerate(
                    zip(expected, actual), start=1
                )
                if expected_line != actual_line
            ),
            min(len(expected), len(actual)) + 1,
        )
        raise ValueError(
            f"{style.upper()} の誤植なしデータが既存ファイルと一致しません。"
            f"最初の不一致行: {mismatch_index}, "
            f"既存件数: {len(expected)}, 生成件数: {len(actual)}"
        )


def _print_skip_log(skipped):
    labels = {
        "missing_doi": "DOI未登録",
        "non_japanese": "日本語条件を満たさない",
        "non_scj": "学術会議登録団体条件を満たさない",
    }
    for reason, label in labels.items():
        values = skipped[reason]
        print(f"{label}ためスキップ：{len(values)}件")
        if values:
            print(f"{label}ためスキップしたDOI一覧")
            for doi in values:
                print(doi)


def _print_typo_summary(manifest):
    for style in STYLES:
        rows = [row for row in manifest if row["style"] == style]
        selected = sum(row["selected_for_typo"] for row in rows)
        changed_references = sum(row["applied_typo_count"] > 0 for row in rows)
        requested = Counter()
        applied = Counter()
        for row in rows:
            for operation in row["operations"]:
                requested[operation["type"]] += 1
                if operation["changed"]:
                    applied[operation["type"]] += 1

        print(f"--- {style.upper()} 誤植付与結果 ---")
        print(f"全件数：{len(rows)}件")
        print(f"誤植付与対象：{selected}件")
        print(f"実際に1箇所以上変化した参考文献：{changed_references}件")
        print(f"要求された誤植操作数：{sum(requested.values())}件")
        print(f"実際に変化した誤植操作数：{sum(applied.values())}件")
        for operation_type in sorted(requested):
            print(
                f"{operation_type}: "
                f"要求={requested[operation_type]}件, "
                f"変化={applied[operation_type]}件"
            )


def generate_typo_dataset(collection, dataset_name, base_seed=None):
    if dataset_name not in DATASET_CONFIG:
        raise ValueError(f"未対応のデータセットです: {dataset_name}")
    if base_seed is None:
        base_seed = config.REFERENCE_TYPO_SEED

    dataset_config = DATASET_CONFIG[dataset_name]
    doi_list = _read_lines(dataset_config["source_dir"] / "doi_list.txt")
    societies = _read_scj_societies()
    generated_dois = []
    generated_baselines = {style: [] for style in STYLES}
    generated_typo = {style: [] for style in STYLES}
    manifest = []
    skipped = {
        "missing_doi": [],
        "non_japanese": [],
        "non_scj": [],
    }

    for doi in doi_list:
        doc = collection.find_one({"doi": doi}, {"_id": 0})
        if doc is None:
            skipped["missing_doi"].append(doi)
            continue
        if not check_lang(doc):
            skipped["non_japanese"].append(doi)
            continue
        if not check_publisher(doc, societies):
            skipped["non_scj"].append(doi)
            continue

        fields = _metadata_fields(doc)
        creator_list = get_creator(doc)
        generated_dois.append(doi)

        for style in STYLES:
            baseline_authors = create_style_authors(style, creator_list)
            baseline = create_reference(style, baseline_authors, fields)
            generated_baselines[style].append(baseline)

            typo_fields = {
                **fields,
                "pages": fields["pages"].copy(),
            }
            typo_authors = baseline_authors.copy()
            rng = _stable_rng(base_seed, dataset_name, style, doi)
            typo_fields, typo_authors, audit = apply_typos(
                typo_fields, typo_authors, rng
            )
            generated_typo[style].append(
                create_reference(style, typo_authors, typo_fields)
            )
            manifest.append(
                {
                    "dataset": dataset_name,
                    "doi": doi,
                    "style": style,
                    "base_seed": base_seed,
                    **audit,
                }
            )

    print(f"入力DOI数：{len(doi_list)}件")
    print(f"該当論文数：{len(generated_dois)}件")
    _print_skip_log(skipped)
    total_skipped = sum(len(values) for values in skipped.values())
    print(f"総スキップ件数：{total_skipped}件")

    if total_skipped:
        raise RuntimeError(
            "比較対象のDOI集合を維持できないため、ファイルは出力しません。"
        )
    if generated_dois != doi_list:
        raise ValueError("生成されたDOIの行順が入力DOIリストと一致しません。")

    _verify_baseline(dataset_config, generated_baselines)
    _print_typo_summary(manifest)

    output_dir = dataset_config["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "doi_list.txt").write_text(
        "\n".join(generated_dois), encoding="utf-8"
    )
    for style in STYLES:
        (output_dir / dataset_config["output_files"][style]).write_text(
            "\n".join(generated_typo[style]), encoding="utf-8"
        )
    (output_dir / dataset_config["manifest_file"]).write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True)
            for row in manifest
        ),
        encoding="utf-8",
    )

    print(f"出力先：{output_dir}")
    print("誤植あり正例データ、DOIリスト、誤植ログの作成完了")
    return {
        "dataset": dataset_name,
        "input_count": len(doi_list),
        "output_count": len(generated_dois),
        "output_dir": output_dir,
        "manifest": manifest,
    }
