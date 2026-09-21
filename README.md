# jev_practice

Jev（TypeSafe の **System One** モデル）と LLM（Claude Haiku 4.5）に
**同じゲームの同じ局面**を打たせて、レイテンシ・コスト・判断の質を並べて見る練習台。

元ネタ: [LLM と Jev のテトリス比較検証](https://zenn.dev/yrd/articles/64d4e2f4c3e71c)

![jev と Haiku 4.5 を同時に走らせた画面](docs/jev_vs_haiku.gif)

GitHub の README は mp4 を再生できない（`<video>` はサニタイズで消える）ので、
ここは GIF を貼っている。実時間の動画は
**[docs/jev_vs_haiku.mp4](docs/jev_vs_haiku.mp4)** をダウンロードするか、
[jsDelivr 経由](https://cdn.jsdelivr.net/gh/ryuchan00/jev_practice@00a2e286fb2de61520d1e8fab9b19e7cc4b25ebe/docs/jev_vs_haiku.mp4)
で直接再生できる。静止画は [開始時点](docs/jev_vs_haiku_start.png) /
[終了時点](docs/jev_vs_haiku.png)。

**左が jev（System One）、右が claude（Haiku 4.5）。**

- **同じパズル** — 同じ seed から作った同一の盤面。開始ボタンを押した時点で
  左右に同じ盤面が出るので、目で確認できる
- **同じ候補手・同じラベル** — 評価も上位 12 手の絞り込みもシャッフルも共通コード
- **同じ手数** — 30 手固定。先に目標へ着いた方が止まる、という不公平をなくしている
- **同じ経路** — 同じゲートウェイ・同じコード・同じ計測系
- **同時スタート** — 別スレッドで並走。GIF は 7 倍速だが
  [mp4 は実時間](docs/jev_vs_haiku.mp4)

違うのは「どれが最善か」を誰に聞くかだけ。

30 手を終えた時点で **jev レベル 3・スコア 3,810・$0.0048 / 855 ms、
Haiku レベル 2・スコア 2,840・$0.0488 / 2,927 ms**。どちらも fallbacks 0 の実測。
（これは動画 1 本の値。5 seed で平均すると次章の「実測」の通り、スコア自体には
有意差がない。速度とコストの差は seed をまたいで一貫している。）

盤面の下にレベル・スコア・タイマー・動物ごとのノルマ・使用トークン・累計コスト・
レイテンシ中央値・フォールバック数が並ぶ。1 手は **入れ替え（青枠）→ 消える 3 匹が
黄色く弾ける → 上から落ちてくる** の順に見せる。

「候補手を列挙 → 上位 12 手に絞る → どれが最善か 1 回だけ聞く」という形に
落としてあるので、エージェントから見た違いは state の中身だけになる。

## ズーキーパー

よくある 3 マッチパズル。ルールは次のとおり。

- 8×8 に **7 種の動物**（ゾウ・キリン・ワニ・パンダ・カバ・サル・ライオン）
- 隣り合う 2 匹を入れ替え、縦か横に 3 匹以上並ぶと消える
- **入れ替えても消せない手はそもそも打てない**（候補手に出てこない）
- 消えると上から落ちてきて連鎖する
- 動物を捕獲すると**タイマーが回復**し、1 手ごとに減る。0 でゲームオーバー
- **全種**のノルマを満たすとレベルアップ。レベルが上がるほどタイマーの減りが速くなる
- どう動かしても消せなくなったら盤面を総入れ替え（ボーナス点とタイマー回復つき）

### なぜこれをベンチにするか

ノルマが「全種いくつずつ」なので、**一番多く消える手が正解とは限らない**。
ライオンのノルマは終わっていてワニが残っているなら、6 匹のライオンより
3 匹のワニを消す手の方が価値がある。素点だけでは候補の順位が決まらないので、
盤面を読んで選ぶ余地が残る。

候補手の評価式:

```
score = 2.0*(まだ足りない動物を消す数)   # ノルマに効く分
      + 0.4*(ノルマ達成済みの動物を消す数) # 余剰はおまけ
      + 3.0*(連鎖 - 1)
      + 2.0*(最長の直線 - 3)
      + 0.3*(打てる手の増減)              # 総入れ替えに追い込まれる手は少し嫌う
```

> 候補の評価だけは**補充なし**で計算している。補充は乱数なので、
> 入れてしまうと同じ盤面でも候補の順位が毎回変わり、`agreement` や
> `mean_regret` が指標として使えなくなる。実際に打つときは補充あり・連鎖ありで解決する。

### 動物アイコン

[Twemoji](https://github.com/jdecked/twemoji)（CC-BY 4.0, © Twitter, Inc and other
contributors）を丸く敷いている。ファイルと対応は
[`jevbench/static/animals/LICENSE.md`](jevbench/static/animals/LICENSE.md)。

## Haiku 4.5 と Jev の比較

### 何が違うのか

| | **Jev**（System One） | **Claude Haiku 4.5**（LLM） |
|---|---|---|
| 出力の形 | テキストを生成しない。型付きの質問に**確率つきの答え**を返す | トークンを生成する。JSON Schema で形だけ縛る |
| 質問の型 | `choice`（択一） / `score`（段階評価） / `noul`（真偽の確率） | 任意。スキーマ次第 |
| 付いてくる情報 | `confidence`、候補ごとの `probabilities` | なし（logprobs は非公開） |
| 向く仕事 | 分類・選択・判定を高頻度で回す | 生成・説明・自由形式の推論 |
| 向かない仕事 | 文章を書く、手順を考える | 1 手 200ms 以内の選択をゲームループで回す |

1 手は「12 個の候補から 1 個選ぶ」だけで、**文章を作る能力は要らない**。
System One が向くのはこの形の仕事。

### 実測（2026-09-21, ズーキーパー, **30 手固定**, seed 0〜4）

手数を 30 に固定して、同じ局面から何点取れるかで比べた。
全エージェントが同じゲートウェイ・同じコード経路・同じ計測系を通っている。

> 以前このセクションに載っていた数値（jev 2,644 / Haiku 2,578）は、
> jev 側だけ別のゲーム向けの指示文が渡ったままのバグ入り計測値だった。
> 以下は目的文をゲーム側に一本化し、両エージェントへ**一字一句同じ**文字列を
> 渡すよう直したあとに取り直した値。

| エージェント | score 平均 | score 範囲 (min〜max) | 標準偏差 | レイテンシ / 手 | コスト / 局 | fallbacks |
|---|---|---|---|---|---|---|
| `jev`（System One） | 2,494 | 2,180〜2,700 | 179 | **905 ms** | **$0.0045** | 0 |
| `claude`（Haiku 4.5） | 2,676 | 2,190〜3,310 | 370 | 2,834 ms | $0.0478 | 0 |
| `heuristic`（基準線） | 2,552 | 1,890〜3,150 | 440 | 0 ms | $0 | 0 |

**スコアは 3 者とも標準偏差の範囲で重なっており、この 5 seed からは有意差は言えない**
（seed によって jev が勝つ回・Haiku が勝つ回の両方がある）。
一方で **jev は Haiku より 3.1 倍速く、10.7 倍安い**。ここは seed をまたいで一貫している。

元記事の報告（約 4 倍速・約 1/24 のコスト・判断品質はほぼ同等）と、
「速度・コストは大差、判断の質は互角」という結論の方向は一致した
（倍率はゲーム・モデル構成が異なるため単純比較はできない）。

#### agreement と mean_regret は品質の指標ではない

`mean_regret` は「選んだ手とヒューリスティック最善手の**評価値の差**」であって、
「最善からどれだけ離れたか」ではない。評価式そのものが正解ではないので、
そこから離れた手が悪いとは限らない。実際 `heuristic` は定義上 regret 0・一致率 100%
だが、30 手スコア平均は 3 者中 **真ん中**（jev 2,494 < heuristic 2,552 < claude 2,676）で、
一致率 100% が最高スコアに直結してはいない。`agreement` も同じで、**どちらも「評価式への
追従度」であって、独立した品質指標ではない。**

#### fallbacks は必ず先に見ること

API が失敗した手はヒューリスティック最善手に逃がして局を止めない。
全手フォールバックすると `agreement` 1.0 / `mean_regret` 0.0 の「満点」に見えるが、
それはヒューリスティックの成績であってそのエージェントの成績ではない。
実際このリポジトリでは、それで 2 回誤ったデータを作りかけている
（ゲートウェイが構造化出力を無視していた件と、サブエージェントがレート制限で
落ちていた件）。

### このリポジトリで測れる指標

`heuristic` エージェント（評価式の最善手をそのまま打つ、API を叩かない基準線）を
同じ seed で走らせて、そこからのズレを見る。

| 指標 | 意味 |
|---|---|
| `progress` / `turns` | 到達したレベル / 打った手数 |
| `median_latency_ms` | 1 手あたり API 往復の中央値 |
| `in_tok` / `out_tok` | 使用トークン（累計） |
| `cost_usd` | 単価からの概算（Haiku はキャッシュ読み書きの割引・割増込み） |
| `agreement` | ヒューリスティック最善手と一致した割合 |
| `mean_regret` | 選んだ手と最善手の評価値の差の平均。0 に近いほど良い |
| `fallbacks` | API が失敗してヒューリスティックに落ちた手数 |

**`fallbacks` が 0 でない行は、そのエージェントを測れていない。**
API が落ちた手はヒューリスティック最善手に逃がして局を止めない作りなので、
全手フォールバックすると `agreement` は 1.0、`mean_regret` は 0.0 になり、
一見すると満点に見えてしまう。必ずここを先に見ること。

## 仕組み

1. seed から初期状態を作る（同じ seed なら全エージェントに同じ局）
2. 現在の局面で打てる手を全部並べる
3. 評価式で上位 12 手に絞る
4. **順番をシャッフルしてから** `A`..`L` のラベルを振る
   （しないとラベル `A` が常に最善になり、盤面を読まずに A と答えるだけで当たる）
5. 各エージェントに「どれが最善か」を 1 回だけ聞く
6. 選ばれた手を打ち、1 手ごとに WebSocket / stdout へ流す

ゲーム側は `games.Game` の形（`start` / `candidates` / `apply` / `progress` /
`rows` / `view`）だけを満たせばよく、ループもエージェントも中身を知らない。

## セットアップ

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
cp .env.example .env   # キーを書く
```

### API キー

| エージェント | 必要なもの |
|---|---|
| `heuristic` | 不要。キーが 1 つも無くてもこれは動く |
| `jev` | `TYPESAFE_API_KEY` |
| `claude` | `ANTHROPIC_API_KEY`、または `ant auth login` 済みのプロファイル |

キーが無いエージェントは起動時に理由を出してスキップされる（他は走る）。

#### ロリポップ！AI ゲートウェイ経由で両方まかなう

[ロリポップ！AI ゲートウェイ](https://ai-gateway.lolipop.jp/) は
OpenAI 互換 / Anthropic 互換に加えて、Jev と同じ `POST /v1/systemone`
（型付き確率的判断）を提供している。**キー 1 本で jev と claude の両方**を通せる。

```bash
# .env
TYPESAFE_API_KEY=sk-...            # ゲートウェイの推論用 API キー
TYPESAFE_BASE_URL=https://ai-gateway.lolipop.jp
TYPESAFE_DEFAULT_MODEL=typesafe/jev-latest

ANTHROPIC_API_KEY=sk-...           # 同じキーでよい
ANTHROPIC_BASE_URL=https://ai-gateway.lolipop.jp
JEV_LLM_MODEL=claude-haiku-4-5     # ゲートウェイ上の Haiku の ID（prefix 無し）
```

どちらの SDK も `*_BASE_URL` を自分で読むので、コード側の変更は要らない。

**推論キーの発行**（`mgmt_` で始まるマネジメントトークンが要る。
マネジメントトークンは推論には使えない）:

```bash
ACC=<accountId>; PRJ=<projectId>
BASE=https://ai-gateway.lolipop.jp/console/v1/accounts/$ACC/projects/$PRJ
OP=$(uuidgen); AT=$(uuidgen)

# 1. 発行（この時点では blocked:true で、まだ一覧にも出ない）
curl -s -X POST -H "Authorization: Bearer $MGMT" -H 'Content-Type: application/json' \
  -d "{\"keyAlias\":\"jev-practice\",\"expiresInDays\":30,
       \"operationId\":\"$OP\",\"attemptId\":\"$AT\",\"recovery\":false}" "$BASE/keys"

# 2. 確定（これを忘れるとキーは有効にならない）
curl -s -X POST -H "Authorization: Bearer $MGMT" -H 'Content-Type: application/json' \
  -d "{\"attemptId\":\"$AT\"}" "$BASE/keys/provisioning/$OP/confirm"
```

平文のキーは 1. のレスポンスの `key.key` に**一度だけ**返る。

**前提となるアカウント設定**（どちらも足りないと全手フォールバックになる）:

- **`typesafe/jev-latest` の利用許可**: 組織レベルで許可が要る。無いと
  `403 permission_error / model_not_allowed`（キーやルールでは開けられない）。
  **2026-09-20 に許可済みで、jev は動いている**
- **残高**: prepaid なので、チャージが無いと `402 billing_error / Insufficient balance`。
  チャージ後は Haiku も動いている

## 実測する

```bash
# API 不要の基準線
.venv/bin/jev-bench --agent heuristic --games 10

# jev と claude を同じ seed で 10 局ずつ
.venv/bin/jev-bench --agent jev --agent claude --games 10

# 1 手ずつ JSON で見る
.venv/bin/jev-bench --agent jev --verbose

# API を使わず、自分（or 別プロセスの LLM）が 1 手ずつ選ぶ
.venv/bin/jev-bench --agent operator --goal 2 --seed 7
#   .operator/turn.json   <- 盤面と候補手が書き出される
#   .operator/answer.txt  -> ラベルを 1 文字書き戻すと次の手へ進む
```

### ブラウザで 2 つの盤面を並べる

```bash
.venv/bin/uvicorn jevbench.server:app --reload
# http://127.0.0.1:8000
```

左右に 1 枚ずつパネルが出て、盤面・レベル・スコア・タイマー・動物ごとのノルマ・
**使用トークン（in / out）・累計コスト**・レイテンシ中央値・一致率・
フォールバック数がリアルタイムで並ぶ。

`step delay (ms)` は 1 手ごとの待ち時間。`heuristic` は API を叩かないので
既定の 0 だと一瞬で終わる。目で追いたいときや録画するときに 100〜300 にする
（CLI なら `--step-delay-ms`）。

## 構成

```
jevbench/
├── core.py                 候補手・決定・1 手の記録・エージェント基底
├── match.py                1 局を回してイベントを吐くループ（ゲーム非依存）
├── cli.py                  CLI
├── server.py               FastAPI + WebSocket
├── static/index.html       Vanilla JS のビューア
├── static/animals/         動物アイコン（Twemoji, CC-BY 4.0）
├── games/
│   ├── base.py             Game プロトコル
│   └── zookeeper.py        8x8・動物 7 種・ノルマ・タイマー・連鎖
└── agents/
    ├── heuristic_agent.py  API を叩かない基準線
    ├── jev_agent.py        System One に choice + noul を 1 往復で聞く
    ├── claude_agent.py     Haiku 4.5 に json_schema の enum で答えさせる
    └── operator_agent.py   API を使わず、人 / 別プロセスの LLM にファイル越しに聞く
```

## コスト計算について

Haiku 4.5 は公表単価（入力 $1.00 / 出力 $5.00 per MTok）に、
キャッシュ書き込み ×1.25・キャッシュ読み出し ×0.10 を掛けて積算している。

Jev 側の単価は `JEV_INPUT_PRICE` / `JEV_OUTPUT_PRICE` で差し替えられる
（既定値は暫定なので、契約した単価に合わせること）。

## テスト

```bash
.venv/bin/python -m pytest tests -q
```

両ゲームのエンジンとループを見る。API は叩かないので課金されない。
