import html
import re
import unicodedata
from itertools import chain


def normalize_text(t: str) -> list:
    if not t:
        return []
    # テキスト前後の空白を削除
    t = t.strip()
    # テキストの正規化（全角英数字->半角、半角カタカナ->全角）
    t = unicodedata.normalize("NFKC", t)
    # アルファベットを小文字に変換
    t = t.lower()
    # 全角スペースやタブ等を半角スペースに変換
    t = re.sub(r"　\s\t\n\r", " ", t)
    # 1つ以上の半角スペースを1つの半角スペースに変換
    t = re.sub(r"\s+", " ", t)
    # 引用文献に含まれるURLを除く
    t = re.sub(r"https?://[\w/:%#\$&\?\(\)~\.=\+\-]*", "", t)
    # 引用文献に含まれるDOIを除く
    t = re.sub("doi.org", "", t)
    t = re.sub("doi:", "", t)
    t = re.sub(r"10.\d{4,9}/[-._;()/:a-zA-Z0-9]+", "", t)
    # 数値文字参照や文字実体参照をunicodeに変換する
    t = html.unescape(t)
    # 引用文献に含まれるHTMLタグを除く
    t = re.sub("<.*?>", "", t)
    # 最終ページ番号が省略形で記載されている場合に正規化する
    # changes "1425-37" to "1425-1437"
    # https://github.com/CrossRef/reference-matching-evaluation/blob/master/matching/cr_search_validation_matcher.py
    if len(m := re.findall("[0-9]+-[0-9]+", t)) > 0:
        pages = m[-1]
        pm = re.search("([0-9]+)-([0-9]+)", pages)
        m1 = pm.group(1)
        m2 = pm.group(2)
        if (len(m1) > len(m2)) and (int(m1[-len(m2):]) <= int(m2)):
            first = m1
            last = m1[:len(m1)-len(m2)] + m2
            t = re.sub(pages, first + "-" + last, t)
    # 「ひらがな・カタカナ・漢字」の間に含まれる半角スペースを削除
    t = re.sub(r"([ぁ-んァ-ン一-龯])\s+([ぁ-んァ-ン一-龯])", r"\1\2", t)
    # 「ひらがな・カタカナ・漢字」と「半角英数字」の間に区切り文字"|"を挿入
    t = re.sub(r"([ぁ-んァ-ン一-龯])\s*([a-zA-Z0-9])", r"\1|\2", t)
    t = re.sub(r"([a-zA-Z0-9])\s*([ぁ-んァ-ン一-龯])", r"\1|\2", t)
    # 「半角英字」と「半角数字」の間に区切り文字"|"を挿入
    t = re.sub(r"([a-zA-Z])\s*([0-9])", r"\1|\2", t)
    t = re.sub(r"([0-9])\s*([a-zA-Z])", r"\1|\2", t)
    # 「半角英字」1文字、2文字または3文字だけの単語場合は周囲に区切り文字"|"を挿入
    t = re.sub(r"\b([a-z]{1,3})\b", r"|\1|", t)
    return t


# 区切り文字の正規表現のパターン
# see: mecab-ipadic-neologd のエントリを生成する際の正規化処理
# https://github.com/neologd/mecab-ipadic-neologd/wiki/Regexp
sep = r'['
# 半角の基本的な記号類 U+0020-002F, U+003A-0040, U+005B-0060, U+007B-007E
sep += r'!"#\$%&\'\(\)\*\+,\-\./:;<=>\?@\[\\\]\^_`\{\|\}~'
# ハイフンマイナス
sep += r'˗֊‐‑‒–⁃⁻₋−'
# 全角の長音記号
sep += r'﹣－ｰ—―─━'
# チルダ U+02DC, U+223C, U+223E, U+301C, U+3030, U+FF5E
sep += r'˜∼∾〜〰～'
# 全角の記号
# U+3001-3002
sep += r'、。'
# U+FF01-FF0F, U+FF1A-FF20, U+FF3B-FF40, U+FF5B-FF65, U+FFE5
sep += r'！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～￥'
# 全角の括弧 U+3008-301F, U+27E6-27EF, U+2308-230B, U+2329-232A
sep += r'〈〉《》「」『』【】〔〕〖〗〘〙〚〛⟦⟧⟨⟩⟪⟫⟬⟭⟮⟯⌈⌉⌊⌋'
# 全角の不等号
sep += r'≪≫＜＞'
# 全角の引用符 U+2018-201F, U+2032-2037, U+02DD, U+275B-275E, U+301D-301F
sep += r'‘’‚‛“”„‟′″‴‵‶‷˝〝〞〟'
# 全角の中黒 U+00B7, U+2022-2027, U+2027, U+30FB, U+FF65, U+2E31
sep += r'·•‣․‥…‧・･⸱'
sep += r']+'


# ストップワード
stopwords = [
    "", " ", "\n", "vol", "no", "pp", "p", "eds", "ed", "edn",
    "et", "al", "他", "ほか", "in", "and", "&", "lt", "gt",
    "第", "巻", "巻第", "年第", "号", "頁", "ページ",
    "年", "月", "日", "抄", "編", "編著", "等編",
]


def split_text(t: str) -> list:
    # 区切り文字（約物）で領域分割する
    segment_list = re.split(sep, t)
    # 文字列でも領域分割する
    segment_list = [re.split(r'\b(?:and|et|al)\b', e) for e in segment_list]
    # リストを平坦化する
    segment_list = sum(segment_list, [])
    # 各領域の先頭または末尾の空白を取り除く
    segment_list = [e.strip() for e in segment_list]
    # Noneとストップワードを取り除く
    segment_list = [e for e in segment_list if e is not None]
    segment_list = [e for e in segment_list if e not in stopwords]
    return segment_list


def slice_char_ngram(t: str, n: int) -> list:
    ngram_list = []
    if len(t) <= n:
        ngram_list.append(t)
        return ngram_list
    else:
        for i in range(len(t) - n + 1):
            ngram_list.append(t[i:i+n])
        return ngram_list


def slice_word_ngram(t: str, n: int) -> list:
    tokens = t.split()
    ngrams = list(chain(*[zip(*[tokens[i:] for i in range(k)])
                  for k in range(1, n+1)]))
    return [" ".join(gram) for gram in ngrams]


def get_token(t: str, n: int = 2) -> list:
    if not t:
        return []
    t = normalize_text(t)
    segment_list = split_text(t)
    token_list = []
    for segment in segment_list:
        # 日本語が含まれていれば累積文字n-gram
        if re.search(r"[ぁ-んァ-ン一-龯]", segment):
            token_list += slice_char_ngram(segment, n=n)
        # それ以外は累積単語n-gram
        else:
            token_list += slice_word_ngram(segment, n=n)
    return token_list
