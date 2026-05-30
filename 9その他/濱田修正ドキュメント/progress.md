## 自分が作成したものと谷川さんの実装との差の分析

#### 独り言
実行ファイル単位ごとにコード量が大きすぎて修正の確認が大変...。リファクタするべきかな...？1ファイルの大きさはある程度小さくしたい

### 実装面で確認できた主な差

* `tanigawa_shoshi` は Python パッケージとして整理されており、`tokenizer.py` `jalc_extract.py` `search.py` `scoring.py` `evaluation.py` などに責務分割されている。一方で `卒業研究_谷川明英` は notebook 中心で、1ファイルあたりの責務が大きい。
* トークナイズ実装が異なる。
  `tanigawa_shoshi` は PyICU ベースで日本語 2-gram / 非日本語 1-gram + 2-gram を生成する。
  谷川さん実装は `wakati.py` ベースで、NFKC 正規化、小文字化、URL / DOI 除去、ストップワード除去、regex 分割を行った上で同様の n-gram を作る。
* Solr への登録形式が異なる。
  `tanigawa_shoshi` は `all_tokens` を主検索対象にし、保存フィールドと検索フィールドを明確に分けている。
  谷川さん実装は `creator` `first_author` `title` `journal` `issued` `volume_issue` `page_range` `publisher` を登録し、`jalcdata` copy field を検索対象にしている。
* 検索方法が異なる。
  `tanigawa_shoshi` は検索前にアプリ側でトークン化し、`all_tokens` に対して検索する。
  谷川さん実装は参考文献文字列をそのまま Solr に渡し、その後 RC / CC でリランキングする。
* MC の扱いが異なる。
  `tanigawa_shoshi` は MC を RC と CC の調和平均として実装している。
  谷川さん実装は RC + CC の和で候補選択し、RC 閾値と CC 閾値を両方満たしたときに採用する。
* 候補件数が異なる。
  `tanigawa_shoshi` の評価系は BM25 上位 100 件を前提にする。
  谷川さん実装は上位 10 件を候補論文として扱う。
* 評価データの持ち方が異なる。
  `tanigawa_shoshi` は `base_positive_examples.json` と `positive_examples.json` を分け、誤植なし正例と誤植あり正例を分離している。
  谷川さん実装は評価実験用の正例テキストが誤植あり前提で保存されている。
* 負例生成の細部も異なる。
  `tanigawa_shoshi` は雑誌名から学会名らしき文字列を推定し、年を固定値にするなど再構成している。
  谷川さん実装は学術会議協力学術研究団体一覧を使い、出版社 / 学会名抽出やタイトル書換えの流れを notebook に直接書いている。
* `tanigawa_shoshi` は再実装・再構成された別システムとして見るべきであり、谷川さん実装の完全再現ではない。
  そのため、比較時は「トークナイズ」「Solr スキーマ」「MC 定義」「評価データ母集団条件」を特に分けて考える必要がある。


## 0, インポートと参照先の修正

### 目的

谷川さん実装の notebook が、現在のリポジトリ構成でも実行できるように、インポート先と入力ファイル参照先の前提を合わせた。
評価ロジック自体は変更していない。

### 修正内容

* `from tools import wakati, generate_query` のような前提をやめ、共有フォルダ内の `wakati.py` を `sys.path` 経由で読み込む形に変更した。
* `generate_query.py` は `4プログラム` 直下にあるため、そのまま `import generate_query` する形に揃えた。
* `eval_experiment_data/...` `pre_experiment_data/...` `eval_experiment_titles_text/...` `pre_experiment_titles_text/...` といった旧前提の相対パスを、現在の `../5データ/...` 配下の実ファイル位置に合わせて修正した。
* `scj_registered_AcademicSocieties.txt` も `../5データ/5-3日本学術会議協力学術研究団体/` 配下を参照するように変更した。

### 主な修正対象

* `4プログラム/evaluation_experiment.ipynb`
* `4プログラム/preliminary_experiment.ipynb`
* `4プログラム/create_references.ipynb`
* `4プログラム/execute_proposed_method.ipynb`
* `4プログラム/get_token.ipynb`
* `4プログラム/search_solr.ipynb`
* `4プログラム/aditional_experiment.ipynb`

### 修正後の状態

* MongoDB の `jalc.restapi` は存在していることを確認済み。
* Solr は起動していることを確認済み。
* ただし notebook は `solr/jalc` core を前提にしているため、環境構築時に `jalc` という core 名で揃える必要がある。
* `wakati` の import は Python 実行時には通る想定だが、エディタ上の静的解析では未解決警告が出る可能性がある。
* `create_references.ipynb` は出力時に `'x'` モードを使っているため、既存ファイルがある状態で再生成すると別途失敗する可能性がある。


## 1, 環境構築
