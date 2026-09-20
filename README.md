# jev_practice

Jev（TypeSafe の **System One** モデル）と LLM（Claude Haiku 4.5）に
同じテトリスを打たせて、**レイテンシ・コスト・判断の質**を並べて見るための練習台。

元ネタ: [LLM と Jev のテトリス比較検証](https://zenn.dev/yrd/articles/64d4e2f4c3e71c)

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
| `jev` | `TYPESAFE_API_KEY` — **TypeSafe の契約が要る**（https://typesafe.ai で発行） |
| `claude` | `ANTHROPIC_API_KEY`、または `ant auth login` 済みのプロファイル |

キーが無いエージェントは起動時に理由を出してスキップされる（他のエージェントは走る）。

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

盤面・ライン数・レイテンシ中央値・一致率・概算コストがリアルタイムで並ぶ。

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
