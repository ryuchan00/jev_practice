# jev_practice

Jev（TypeSafe の **System One** モデル）と LLM（Claude Haiku 4.5）に
同じテトリスを打たせて、**レイテンシ・コスト・判断の質**を並べて見るための練習台。

元ネタ: [LLM と Jev のテトリス比較検証](https://zenn.dev/yrd/articles/64d4e2f4c3e71c)

![ゲーム画面](docs/demo.gif)

1 手ごとに盤面・使用トークン・累計コスト・レイテンシ中央値が更新される
（[mp4 版](docs/demo.mp4)）。上の録画は `heuristic` を `step delay 110ms` で
流したもの。jev / claude はまだアカウント側が通っていないので映っていない
（下の「前提となるアカウント設定」を参照）。

## Haiku 4.5 と Jev の比較

### 何が違うのか

| | **Jev**（System One） | **Claude Haiku 4.5**（LLM） |
|---|---|---|
| 出力の形 | テキストを生成しない。型付きの質問に**確率つきの答え**を返す | トークンを生成する。JSON Schema で形だけ縛る |
| 質問の型 | `choice`（択一） / `score`（段階評価） / `noul`（真偽の確率） | 任意。スキーマ次第 |
| 1 往復で聞ける数 | 複数の質問をまとめて 1 リクエスト | 同上（ただし生成トークンとして出る） |
| 付いてくる情報 | `confidence`、候補ごとの `probabilities` | なし（logprobs は非公開） |
| 向く仕事 | 分類・選択・判定を高頻度で回す | 生成・説明・自由形式の推論 |
| 向かない仕事 | 文章を書く、手順を考える | 1 手 200ms 以内の選択をゲームループで回す |

テトリスの 1 手選択は「12 個の候補から 1 個選ぶ」だけなので、
**文章を作る能力は 1 ミリも要らない**。Jev が効くのはそういう形の仕事。

### 記事で報告されている数値

> 以下は元記事の計測値であって、このリポジトリで測った値ではない。
> 自分で測る手順は下の「実測する」を参照。

| 指標 | Jev | Haiku 4.5 |
|---|---|---|
| API レイテンシ（中央値） | 239 ms | 1,011 ms |
| 1 局あたりの推定費用 | $0.006 | $0.15 |
| 20 ライン到達 | 8/10 局 | 9/10 局 |

判断の質はほぼ互角のまま、**約 4 倍速く、約 1/24 のコスト**。

### このリポジトリで測れる指標

`heuristic` エージェント（評価式の最善手をそのまま打つ、API を叩かない基準線）を
同じ seed で走らせて、そこからのズレを見る。

| 指標 | 意味 |
|---|---|
| `lines` / `pieces` | 消したライン数 / 置いたミノ数 |
| `median_latency_ms` | 1 手あたり API 往復の中央値 |
| `cost_usd` | トークン使用量からの概算（Haiku はキャッシュ読み書きの割引・割増込み） |
| `agreement` | ヒューリスティック最善手と一致した割合 |
| `mean_regret` | 選んだ手と最善手の評価値の差の平均。0 に近いほど良い |
| `fallbacks` | API が失敗してヒューリスティックに落ちた手数 |

`fallbacks` が 0 でない行は**そのエージェントを測れていない**。
全手フォールバックすると `agreement` は 1.0、`mean_regret` は 0.0 になり、
一見すると完璧な成績に見えてしまうので、必ずここを先に見ること。

`agreement` と `mean_regret` があるので、**ライン数だけでは見えない判断の質**を
1 局でも比べられる。

## 仕組み

1. 10×20 の盤面と 7-bag 乱数でミノを配る（seed 固定 = 全エージェントに同じ列）
2. 現在のミノについて、全回転 × 全列のハードドロップ結果を列挙する
3. 記事の評価式で上位 12 手に絞る
   `score = -4*holes + 3*cleared - 0.5*max_height - 0.2*bumpiness`
4. **順番をシャッフルしてから** `A`..`L` のラベルを振る
   （しないとラベル `A` が常に最善になり、位置バイアスだけで当たってしまう）
5. 各エージェントに「どれが最善か」を 1 回だけ聞く
6. 選ばれた手を打ち、1 手ごとに WebSocket / stdout へ流す

API が失敗した手は、局を止めずにヒューリスティック最善手へフォールバックする
（`note` に `fallback: ...` が残る）。

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

キーが無いエージェントは起動時に理由を出してスキップされる（他のエージェントは走る）。

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

# 1. 発行（この時点では blocked:true で、まだ一覧に出ない）
curl -s -X POST -H "Authorization: Bearer $MGMT" -H 'Content-Type: application/json' \
  -d "{\"keyAlias\":\"jev-practice\",\"expiresInDays\":30,
       \"operationId\":\"$OP\",\"attemptId\":\"$AT\",\"recovery\":false}" "$BASE/keys"

# 2. 確定（これを忘れるとキーは有効にならない）
curl -s -X POST -H "Authorization: Bearer $MGMT" -H 'Content-Type: application/json' \
  -d "{\"attemptId\":\"$AT\"}" "$BASE/keys/provisioning/$OP/confirm"
```

平文のキーは 1. のレスポンスの `key.key` に**一度だけ**返る。

**前提となるアカウント設定**（どちらも足りないと全手フォールバックになる）:

- **残高**: prepaid なので、チャージが無いと推論は `402 billing_error / Insufficient balance`
- **`typesafe/jev-latest` の利用許可**: 既定では
  `403 permission_error / model_not_allowed`。ダッシュボードで許可が要る

## 実測する

```bash
# API 不要の基準線
.venv/bin/jev-tetris --agent heuristic --games 10

# 3 者を同じ seed で 10 局ずつ
.venv/bin/jev-tetris --agent heuristic --agent jev --agent claude --games 10 --target-lines 20

# 1 手ずつ JSON で見る
.venv/bin/jev-tetris --agent jev --verbose
```

### ブラウザで 2 つの盤面を並べる

```bash
.venv/bin/uvicorn jevtetris.server:app --reload
# http://127.0.0.1:8000
```

盤面・ライン数・**使用トークン（in / out）・累計コスト**・レイテンシ中央値・
一致率・フォールバック数がリアルタイムで並ぶ。

`step delay (ms)` は 1 手ごとの待ち時間。`heuristic` は API を叩かないので
既定の 0 だと一瞬で終わる。目で追いたいときや録画するときに 100 前後にする
（CLI なら `--step-delay-ms`）。

## 構成

```
jevtetris/
├── tetris.py               盤面・7 種ミノ・7-bag・ハードドロップ
├── heuristic.py            評価式と上位 12 手の絞り込み
├── match.py                1 局を回してイベントを吐くループ
├── cli.py                  CLI
├── server.py               FastAPI + WebSocket
├── static/index.html       Vanilla JS のビューア
└── agents/
    ├── base.py             共通インタフェース・レイテンシ / コスト集計
    ├── heuristic_agent.py  API を叩かない基準線
    ├── jev_agent.py        System One に choice + noul を 1 往復で聞く
    └── claude_agent.py     Haiku 4.5 に json_schema の enum で答えさせる
```

## コスト計算について

Haiku 4.5 は公表単価（入力 $1.00 / 出力 $5.00 per MTok）に、
キャッシュ書き込み ×1.25・キャッシュ読み出し ×0.10 を掛けて積算している。

Jev 側の単価は環境変数 `JEV_INPUT_PRICE` / `JEV_OUTPUT_PRICE` で差し替えられる
（既定値は暫定なので、契約した単価に合わせること）。

## テスト

```bash
.venv/bin/python -m pytest tests -q
```

エンジンとヒューリスティックだけを見る。API は叩かないので課金されない。
