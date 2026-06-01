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

### 確認したこと

* MongoDB 側は `localhost:27017 > jalc > restapi` を前提にしており、`卒業研究_谷川明英` 側で独自の別登録実装は確認できなかった。
  `4プログラム/jalc-to-solr.ipynb` は既存の `jalc.restapi` を読む前提であり、MongoDB 登録処理そのものは `jalc` 側の notebook 群を使っていると見てよい。
* JaLC データの年版について、`卒業研究_谷川明英` 側の資料では「JaLC のメタデータ」としか書かれておらず、MongoDB に入れる年版は固定されていなかった。
  そのため、2024 年版 JaLC データを `jalc.restapi` に入れている現状は実装前提として問題ないと判断した。
  ただし論文本文にある登録件数や再現値と完全一致するとは限らない。
* Solr 側の `text_ja` は谷川さん独自実装ではなく、Solr 9.7.0 の標準 configset に含まれる fieldType であることを確認した。
  `tanigawa_jalc` の `managed-schema.xml` にある `text_ja` も、標準 `_default` の日本語アナライザ設定と同等だった。
  そのため、今回の環境構築では Solr の日本語アナライザを独自に追加実装する必要はない。

### `jalc` 側との比較

* Solr 登録本体である `jalc/jalc-to-solr.ipynb` と `卒業研究_谷川明英/4プログラム/jalc-to-solr.ipynb` を比較したところ、登録ロジック・helper 関数・登録フィールド・copy field は一致していた。
* 差分は実質 core 名だけだった。
  `jalc` 側は Python の接続先が `tanigawa_jalc`、`卒業研究_谷川明英` 側は `jalc` を向いていた。
* MongoDB 登録についても、`卒業研究_谷川明英` 側に別の整形処理は見当たらず、`jalc` 側の `restapi` 登録結果を利用する前提で矛盾しなかった。
* 以上から、今回は `tanigawa_jalc` を流用して進める方針にした。
  「論文どおりの core 名に完全一致させる」ことより、「登録ロジックとスキーマ構成が同じであること」を優先した。

### 実施した修正

* notebook 側の Solr 参照先を `http://localhost:8983/solr/tanigawa_jalc` に揃えた。
* `jalc-to-solr.ipynb` の raw セルにある schema API の送信先も `tanigawa_jalc` に合わせた。
* 主な修正対象は以下。
  * `4プログラム/evaluation_experiment.ipynb`
  * `4プログラム/preliminary_experiment.ipynb`
  * `4プログラム/execute_proposed_method.ipynb`
  * `4プログラム/search_solr.ipynb`
  * `4プログラム/jalc-to-solr.ipynb`
  * `4プログラム/aditional_experiment.ipynb`
  * `4プログラム/get_token.ipynb`

### 補足

* まだ `solr/jalc` の文字列が残っている箇所は、保存済み実行出力のログだけであり、現在の notebook ソース参照先ではない。
* したがって、以後の実行では `tanigawa_jalc` を参照する前提で進めてよい。


## 2, 誤植ありの既存評価を再現

### 方針

* `evaluation_experiment.ipynb` は `Run All` ではなく、`test_set` を切り替えながら必要セルだけ実行する。
* 理由は、同一 notebook 内に「正例用セル」「負例用セル」「確認用セル」「追加分析セル」が混在しているため。
* 特に `Cell 4` の `test_set` は手動で対象ファイルを切り替える前提になっている。

### 使用 notebook

* `4プログラム/evaluation_experiment.ipynb`

### 事前実行

* `Cell 2`
  * import
  * `wakati`, `generate_query`, `pysolr` の読み込み
  * Solr 接続
* これは notebook 起動後、最初に 1 回だけ実行すればよい。

### 入力ファイル

#### 正例（誤植あり）

* `../5データ/5-2評価実験用データ/5-2-1参考文献文字列（実在）/positive_reference_ipsj_eval.txt`
* `../5データ/5-2評価実験用データ/5-2-1参考文献文字列（実在）/positive_reference_jsai_eval.txt`
* `../5データ/5-2評価実験用データ/5-2-1参考文献文字列（実在）/positive_reference_lsj_eval.txt`

#### 負例

* `../5データ/5-2評価実験用データ/5-2-2参考文献文字列（架空）/negative_reference_ipsj_eval.txt`
* `../5データ/5-2評価実験用データ/5-2-2参考文献文字列（架空）/negative_reference_jsai_eval.txt`
* `../5データ/5-2評価実験用データ/5-2-2参考文献文字列（架空）/negative_reference_lsj_eval.txt`

### 実行セル

#### 正例評価で使うセル

* `Cell 12`
  * DOI リストの読み込み
* `Cell 15`
  * BM25（非正規化）
* `Cell 24`
  * BM25（正規化）
* `Cell 35`
  * Reference Coverage（sim_r）
* `Cell 41`
  * Candidate Coverage（sim_p）
* `Cell 46`
  * Mutual Coverage

#### 負例評価で使うセル

* `Cell 17`
  * BM25（非正規化）
* `Cell 29`
  * BM25（正規化）
* `Cell 38`
  * Reference Coverage（sim_r）
* `Cell 43`
  * Candidate Coverage（sim_p）
* `Cell 48`
  * Mutual Coverage

#### 今回の再現確認では必須ではないセル

* `Cell 6`
* `Cell 8`
* `Cell 10`
* `Cell 20` 以降の単語頻度・追加分析用セル

### 実行手順

#### 1. 初期化

* `Cell 2` を実行する。
* `Cell 12` を実行する。

#### 2. 正例（誤植あり）を 3 スタイル分評価

##### 2-1. IPSJ スタイル

* `Cell 4` の `test_set` を `positive_reference_ipsj_eval.txt` に変更して実行する。
* 次のセルを順に実行する。
  * `Cell 15`
  * `Cell 24`
  * `Cell 35`
  * `Cell 41`
  * `Cell 46`
* 上記セルの実行が終わったタイミングで、下の `#### 正例 IPSJ` にログを追記する。
  * `実行日時`
  * `使用ファイル`
    * `positive_reference_ipsj_eval.txt`
    * 必要なら `doi_list.txt` も併記
  * `実行セル`
    * `Cell 4, 15, 24, 35, 41, 46`
  * `主な出力`
    * 各手法の件数サマリ
    * 必要なら代表的な詳細出力
  * `備考`
    * エラー有無、論文値との差、気づいた点など

##### 2-2. JSAI スタイル

* `Cell 4` の `test_set` を `positive_reference_jsai_eval.txt` に変更して実行する。
* 次のセルを順に実行する。
  * `Cell 15`
  * `Cell 24`
  * `Cell 35`
  * `Cell 41`
  * `Cell 46`
* 上記セルの実行が終わったタイミングで、下の `#### 正例 JSAI` にログを追記する。
  * `実行日時`
  * `使用ファイル`
    * `positive_reference_jsai_eval.txt`
    * 必要なら `doi_list.txt` も併記
  * `実行セル`
    * `Cell 4, 15, 24, 35, 41, 46`
  * `主な出力`
    * 各手法の件数サマリ
    * 必要なら代表的な詳細出力
  * `備考`
    * エラー有無、論文値との差、気づいた点など

##### 2-3. LSJ スタイル

* `Cell 4` の `test_set` を `positive_reference_lsj_eval.txt` に変更して実行する。
* 次のセルを順に実行する。
  * `Cell 15`
  * `Cell 24`
  * `Cell 35`
  * `Cell 41`
  * `Cell 46`
* 上記セルの実行が終わったタイミングで、下の `#### 正例 LSJ` にログを追記する。
  * `実行日時`
  * `使用ファイル`
    * `positive_reference_lsj_eval.txt`
    * 必要なら `doi_list.txt` も併記
  * `実行セル`
    * `Cell 4, 15, 24, 35, 41, 46`
  * `主な出力`
    * 各手法の件数サマリ
    * 必要なら代表的な詳細出力
  * `備考`
    * エラー有無、論文値との差、気づいた点など

#### 3. 負例を 3 スタイル分評価

##### 3-1. IPSJ スタイル

* `Cell 4` の `test_set` を `negative_reference_ipsj_eval.txt` に変更して実行する。
* 次のセルを順に実行する。
  * `Cell 17`
  * `Cell 29`
  * `Cell 38`
  * `Cell 43`
  * `Cell 48`
* 上記セルの実行が終わったタイミングで、下の `#### 負例 IPSJ` にログを追記する。
  * `実行日時`
  * `使用ファイル`
    * `negative_reference_ipsj_eval.txt`
  * `実行セル`
    * `Cell 4, 17, 29, 38, 43, 48`
  * `主な出力`
    * 各手法の `True Negative` / `False Positive`
    * 必要なら代表的な詳細出力
  * `備考`
    * エラー有無、論文値との差、気づいた点など

##### 3-2. JSAI スタイル

* `Cell 4` の `test_set` を `negative_reference_jsai_eval.txt` に変更して実行する。
* 次のセルを順に実行する。
  * `Cell 17`
  * `Cell 29`
  * `Cell 38`
  * `Cell 43`
  * `Cell 48`
* 上記セルの実行が終わったタイミングで、下の `#### 負例 JSAI` にログを追記する。
  * `実行日時`
  * `使用ファイル`
    * `negative_reference_jsai_eval.txt`
  * `実行セル`
    * `Cell 4, 17, 29, 38, 43, 48`
  * `主な出力`
    * 各手法の `True Negative` / `False Positive`
    * 必要なら代表的な詳細出力
  * `備考`
    * エラー有無、論文値との差、気づいた点など

##### 3-3. LSJ スタイル

* `Cell 4` の `test_set` を `negative_reference_lsj_eval.txt` に変更して実行する。
* 次のセルを順に実行する。
  * `Cell 17`
  * `Cell 29`
  * `Cell 38`
  * `Cell 43`
  * `Cell 48`
* 上記セルの実行が終わったタイミングで、下の `#### 負例 LSJ` にログを追記する。
  * `実行日時`
  * `使用ファイル`
    * `negative_reference_lsj_eval.txt`
  * `実行セル`
    * `Cell 4, 17, 29, 38, 43, 48`
  * `主な出力`
    * 各手法の `True Negative` / `False Positive`
    * 必要なら代表的な詳細出力
  * `備考`
    * エラー有無、論文値との差、気づいた点など

### 注意点

* `Cell 4` の `test_set` を切り替えたら、そのたびに `Cell 4` 自体を再実行する。
* 正例用セルと負例用セルを混ぜて `Run All` しない。
* notebook 内に保存済み出力が残っていても、再実行時は現在の `tanigawa_jalc` と手元データで結果が上書きされる。

### 実行ログ記録欄

#### 正例 IPSJ
====================== 2024データ
* 実行日時: 5/30, 16:30
* 使用ファイル:positive_reference_ipsj_eval.txt
* 総実行セル：Cell 4, 15, 24, 35, 41, 46

* 実行セル: Cell15(BM25)
* 主な出力: case1 = 854件，case2 =8件，case3 = 1件，case4 = 0件

* 実行セル: Cell24(BM25長さ補正)
* 主な出力: case1 = 845件，case2 =17件，case3 = 1件，case4 = 0件

* 実行セル: Cell35(RC)
* 主な出力: case1 = 857件，case2 =6件，case3 = 0件，case4 = 0件

* 実行セル: Cell 41(CC)
* 主な出力: case1 = 835件，case2 =28件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46(MC)
* 主な出力: case1 = 830件，case2 =33件，case3 = 0件，case4 = 0件
* 備考:
====================== 2023データ
* 実行日時: 6/1 14:00
* 使用ファイル:positive_reference_ipsj_eval.txt
* 総実行セル：Cell 4, 15, 24, 35, 41, 46

* 実行セル: Cell15(BM25)
* 主な出力: case1 = 838件，case2 =24件，case3 = 1件，case4 = 0件

* 実行セル: Cell24(BM25長さ補正)
* 主な出力: case1 = 838件，case2 =24件，case3 = 1件，case4 = 0件

* 実行セル: Cell35(RC)
* 主な出力: case1 = 857件，case2 =6件，case3 = 0件，case4 = 0件

* 実行セル: Cell 41(CC)
* 主な出力: case1 = 836件，case2 =27件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46(MC)
* 主な出力: case1 = 831件，case2 =32件，case3 = 0件，case4 = 0件
* 備考:
====================== 2023データ(MC修正)
* 実行日時: 6/1 18:00
* 使用ファイル:positive_reference_ipsj_eval.txt
* 総実行セル：Cell 4, 15, 24, 35, 41, 46

* 実行セル: Cell15(BM25)
* 主な出力: case1 = 854件，case2 =8件，case3 = 1件，case4 = 0件

* 実行セル: Cell24(BM25長さ補正)
* 主な出力: case1 = 838件，case2 =24件，case3 = 1件，case4 = 0件

* 実行セル: Cell35(RC)
* 主な出力: case1 = 857件，case2 =6件，case3 = 0件，case4 = 0件

* 実行セル: Cell 41(CC)
* 主な出力: case1 = 836件，case2 =27件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46(MC)
* 主な出力: case1 = 863件，case2 =0件，case3 = 0件，case4 = 0件
* 備考:

#### 正例 JSAI
====================== 2024データ
* 実行日時:5/30 17:00
* 使用ファイル: positive_reference_jsai_eval.txt`
* 総実行セル: Cell 4, 15, 24, 35, 41, 46

* 実行セル: Cell 15
* 主な出力: case1 = 842件，case2 =20件，case3 = 1件，case4 = 0件

* 実行セル: Cell24
* 主な出力: case1 = 831件，case2 =31件，case3 = 1件，case4 = 0件

* 実行セル: Cell 35
* 主な出力: case1 = 853件，case2 =9件，case3 = 1件，case4 = 0件

* 実行セル: Cell 41
* 主な出力: case1 = 840件，case2 =23件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46
* 主な出力: case1 = 831件，case2 =32件，case3 = 0件，case4 = 0件
* 備考:
====================== 2023データ
* 実行日時: 6/1 14:00
* 使用ファイル: positive_reference_jsai_eval.txt`
* 総実行セル: Cell 4, 15, 24, 35, 41, 46

* 実行セル: Cell 15
* 主な出力: case1 = 842件，case2 =20件，case3 = 1件，case4 = 0件

* 実行セル: Cell24
* 主な出力: case1 = 823件，case2 =39件，case3 = 1件，case4 = 0件

* 実行セル: Cell 35
* 主な出力: case1 = 853件，case2 =9件，case3 = 1件，case4 = 0件

* 実行セル: Cell 41
* 主な出力: case1 = 841件，case2 =22件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46
* 主な出力: case1 = 832件，case2 =31件，case3 = 0件，case4 = 0件
* 備考:
====================== 2023データ(MC修正)
* 実行日時: 6/1 18:00
* 使用ファイル: positive_reference_jsai_eval.txt`
* 総実行セル: Cell 4, 15, 24, 35, 41, 46

* 実行セル: Cell 15
* 主な出力: case1 = 842件，case2 =20件，case3 = 0件，case4 = 1件

* 実行セル: Cell24
* 主な出力: case1 = 823件，case2 =39件，case3 = 1件，case4 = 0件

* 実行セル: Cell 35
* 主な出力: case1 = 853件，case2 =9件，case3 = 1件，case4 = 0件

* 実行セル: Cell 41
* 主な出力: case1 = 841件，case2 =22件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46
* 主な出力: case1 = 863件，case2 =0件，case3 = 0件，case4 = 0件
* 備考:

#### 正例 LSJ
====================== 2024データ
* 実行日時:5/30 17:00
* 使用ファイル: positive_reference_lsj_eval.txt
総実行セル: Cell 4, 15, 24, 35, 41, 46

* 実行セル:  Cell 15
* 主な出力: case1 = 853件，case2 =9件，case3 = 1件，case4 = 0件

* 実行セル: Cell24
* 主な出力: case1 = 861件，case2 =1件，case3 = 1件，case4 = 0件

* 実行セル:  Cell 35
* 主な出力: case1 = 859件，case2 =4件，case3 = 0件，case4 = 0件

* 実行セル: Cell 41
* 主な出力: case1 = 837件，case2 =26件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46
* 主な出力: case1 = 833件，case2 =30件，case3 = 0件，case4 = 0件
* 備考:
====================== 2023データ
* 実行日時: 6/1 14:00
* 使用ファイル: positive_reference_lsj_eval.txt
総実行セル: Cell 4, 15, 24, 35, 41, 46

* 実行セル:  Cell 15
* 主な出力: case1 = 853件，case2 =9件，case3 = 1件，case4 = 0件

* 実行セル: Cell24
* 主な出力: case1 = 860件，case2 =2件，case3 = 1件，case4 = 0件

* 実行セル:  Cell 35
* 主な出力: case1 = 859件，case2 =4件，case3 = 0件，case4 = 0件

* 実行セル: Cell 41
* 主な出力: case1 = 838件，case2 =25件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46
* 主な出力: case1 = 834件，case2 =29件，case3 = 0件，case4 = 0件
* 備考:
====================== 2023データ(MC修正)
* 実行日時: 6/1 18:00
* 使用ファイル: positive_reference_lsj_eval.txt
総実行セル: Cell 4, 15, 24, 35, 41, 46

* 実行セル:  Cell 15
* 主な出力: case1 = 853件，case2 =9件，case3 = 1件，case4 = 0件

* 実行セル: Cell24
* 主な出力: case1 = 860件，case2 =2件，case3 = 1件，case4 = 0件

* 実行セル:  Cell 35
* 主な出力: case1 = 859件，case2 =4件，case3 = 0件，case4 = 0件

* 実行セル: Cell 41
* 主な出力: case1 = 838件，case2 =25件，case3 = 0件，case4 = 0件

* 実行セル: Cell 46
* 主な出力: case1 = 863件，case2 =0件，case3 = 0件，case4 = 0件
* 備考:

#### 負例 IPSJ

* 実行日時:
* 使用ファイル:
* 実行セル:
* 主な出力:
* 備考:

#### 負例 JSAI

* 実行日時:
* 使用ファイル:
* 実行セル:
* 主な出力:
* 備考:

#### 負例 LSJ

* 実行日時:
* 使用ファイル:
* 実行セル:
* 主な出力:
* 備考:

### Step2 実行結果まとめ

#### 正例 3 スタイル合計

* case の解釈
  * `case1`: 正しい DOI を同定できた
  * `case2`: 正しい候補論文は見つけているが、閾値を超えず `No registration` 扱いになった
  * `case3`: 閾値を超えたが、誤った DOI を同定した
  * `case4`: 正しい DOI も取れず、閾値も超えなかった
* 論文表との対応
  * `正常検出 = case1`
  * `検出漏れ = case2 + case4`
  * `誤検出 = case3`

#### 集計結果

* BM25（Cell 15）
  * `2549 / 37 / 3`
  * `98.46% / 1.43% / 0.12%`
* BM25 長さ補正（Cell 24）
  * `2537 / 49 / 3`
  * `97.99% / 1.89% / 0.12%`
* RC（Cell 35）
  * `2569 / 19 / 1`
  * `99.23% / 0.73% / 0.04%`
* CC（Cell 41）
  * `2512 / 77 / 0`
  * `97.03% / 2.97% / 0.00%`
* MC（Cell 46）
  * `2494 / 95 / 0`
  * `96.33% / 3.67% / 0.00%`

#### 論文値との比較

* 論文記載値
  * BM25: `2549 / 38 / 2`
  * RC: `2569 / 19 / 1`
  * CC: `2515 / 74 / 0`
  * MC: `2589 / 0 / 0`
* 比較結果
  * BM25 はかなり近い。正常検出数は一致している。
  * RC は論文値と完全一致した。
  * CC は 3 件差でかなり近い。
  * MC は大きく不一致であり、論文の `100%` 再現にはならなかった。

#### 現時点の見立て

* notebook の実行手順や基本ロジックが大きく間違っているなら RC まで完全一致するのは不自然である。
* そのため、現在の主な差分要因は実装ミスよりも、MongoDB / Solr に入っている JaLC メタデータの年版差である可能性が高い。
* 今回は 2024 年版 JaLC データを利用しているが、論文時点では 2023 年版またはそれ以前のスナップショットを使っていた可能性がある。
* 特に MC は top10 候補集合とその順位の微妙な差に弱いため、JaLC データ更新の影響を最も受けやすいと考えられる。

#### Step2 の結論

* 誤植あり既存評価の再現は、BM25 / RC / CC については概ね成功した。
* 一方で MC は未再現である。
* 次の Step3 では、誤植なし正例データを用いた評価に進む前に、「現在の環境では MC のみ論文値とずれる」という前提を明記して扱う必要がある。
