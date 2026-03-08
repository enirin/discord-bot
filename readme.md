# **SME Discord Bot (WSL \+ Local LLM)**

WSL2上で動作する、ローカルLLM（Ollama）と連携したAI Discord Botです。
使用モデルやキャラクタ設定（プロンプト）はconfig.yamlの編集で変更可能になってます。

サーバー負荷確認や、AIチャット機能を備えています。荒らし対策としてレートリミット設定可能にしてます。

## **📋 本プログラムの前提条件**

* **OS**: Windows 10/11 (WSL2 / Ubuntu推奨)  
* **Python**: 3.10以上  
* **Ollama**: WSL上で動作していること  
* **Hardware**: メモリ 8GB以上（16GB以上推奨）

このreadmeではWindowsにはWSL2/Ubuntuがインストールされていること、読者がWSL上のLinuxをコンソールで操作することができるのを前提にインストールガイドを記載しています。

## **📖 設計思想と利用用途**

Discordへの投稿コマンドに連動させてゲームサーバーを管理したい！というご要望の為にDiscord BotをデザインしたついでにAIとのお喋りというお遊びを追加しています。AIchat機能はおまけなので制限レートがあったり従量課金が発生する高機能なＡＰＩ利用は採用せず、無料のローカルＬＬＭを利用して気兼ねなく個人で存分に楽しめるようにしています。

サーバー管理側の機能についてもまとめて盛り込むことは可能ですが、chatBot側とサーバー管理側を疎結合にするため、\*\*「APIファースト」\*\*の設計を採用しています。ゲームサーバーの管理アプリ本体が未完成/未導入の状態でも、先にインターフェースのみを定義しDiscord Botの機能に特化させて先行リリースしました。

副産物としてゲームサーバー管理に興味なくても、当アプリケーションのみを導入すればAIチャットボットのみの用途でご自身のDiscordサーバーに参加させて楽しむことも可能です。

* [API\_CONTRACT.md](https://www.google.com/search?q=./API_CONTRACT.md) : 連携APIの入出力仕様を定義した「契約」ドキュメント。

## **🛠️ Discord Botの準備と設定**
Botを動かす前に、Discord側でアプリケーション（Bot名義で任意のサーバーに参加させるためのアカウント）の作成とトークンの取得が必要です。

### **1\. Botの作成とトークン取得**
1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセスし、ログインします。  
2. **\[New Application\]** をクリックし、任意の名前を入力して作成します。  
3. 左メニューの **\[Bot\]** を選択します。  
4. **\[Reset Token\]**（または Copy Token）をクリックし、表示された文字列をコピーします。  
   * **重要**: このトークンは config.yaml の bot\_token に使用します。他人に教えないでください。

### **2\. 特権インテント（Privileged Gateway Intents）の設定**
メッセージの中身を読み取るために必須の設定です。

1. 同じく **\[Bot\]** ページ内の **Privileged Gateway Intents** セクションを探します。  
2. **MESSAGE CONTENT INTENT** を **ON** に切り替え、\[Save Changes\] をクリックします。

### **3\. Botの招待（サーバーへの追加）**
1. 左メニューの **OAuth2** を選択します。  
2. **Scopes** で `bot` と `applications.commands` にチェックを入れます。（※ `/` コマンド、通称 Slash Commands をDiscord上で表示させるために必要です）
3. **Bot Permissions** で Send Messages、Read Message History、View Channels にチェックを入れます。  
4. 生成されたURLをブラウザで開き、Botを追加したいサーバーを選択して追加します。

## **🆔 チャンネルIDの取得方法**

Botが監視する特定のチャンネルIDを特定する手順です。

1. Discordアプリ左下の **\[ユーザー設定\]**（歯車アイコン）を開きます。  
2. **\[詳細設定\]** (Advanced) を選択し、**\[開発者モード\]** を **ON** にします。  
3. 設定を閉じ、監視したいチャンネル名を **右クリック** します。  
4. 一番下に表示される **\[チャンネルIDをコピー\]** をクリックします。  
   * この数字を config.yaml の channel\_ids リストに貼り付けます。

## **🚀 セットアップ/インストール手順（本プログラム側）**

### **1\. リポジトリ（本プログラム）の取得**
以下、ご自身のbotを稼働させるPC端末のwsl2にログインし、
任意の作業ディレクトリに移動してからインストール操作を行ってください。

git clone https://github.com/enirin/discord-bot.git  
cd discord-bot

### 会話履歴の要約圧縮について

おしゃべり機能では、`conversation_history_limit` を超えた古い履歴を単純に捨てるのではなく、過去ログを要約した上で追加のsystemメッセージとして保持します。これにより、直近の発話はそのまま残しつつ、古い文脈もある程度引き継げます。

`conversation_summary_keep_recent` は、要約せずにそのまま残す直近メッセージ件数です。小さすぎると直近の会話の細部が失われやすくなり、大きすぎると毎回の送信トークン量が増えて返信速度が低下します。

複数人が参加するチャンネルでは、会話履歴に発言者名を含めてAIへ渡します。また、Botは全発言に毎回反応するのではなく、メンション・Botへの返信・Bot名の呼びかけ・優先キーワードをきっかけに会話へ入り、その後は一定時間だけ質問に追従しやすくなります。

```yaml
conversation_history_limit: 20

# 会話履歴が上限を超えた際に、直近として保持するメッセージ件数
# 古い会話は要約され、追加のsystemメッセージとして文脈に再利用されます
conversation_summary_keep_recent: 8

# Botが会話に呼び込まれた後、追従しやすい状態を維持する秒数
conversation_session_timeout_seconds: 90

# Botが連続で割り込みすぎないための、チャンネル単位の最小返信間隔（秒）
conversation_reply_cooldown_seconds: 20
```

### **2\. Python仮想環境の構築**
本プログラムを実行するために必要な前提環境を整えます。

\# 仮想環境の作成  
python3 \-m venv venv

\# 仮想環境の有効化  
source venv/bin/activate

\# 依存ライブラリのインストール  
pip install \-r requirements.txt

### **3\. 設定ファイル（config.yaml）の作成**
リポジトリ直下に config.yaml を新規作成し、取得したトークン等を記述してください。(config.yaml.sampleをコピーしてファイル名や中身を更新するのが簡単です。)

bot\_token: "取得したトークン"  
channel\_ids:  
  \- 123456789012345678 \# コピーしたチャンネルID  
bot\_name: "MySME BOTちゃん"  
\# ...その他AI設定等

### **4\. Ollamaとモデルの準備**
こちらはAI機能を利用する場合に必要です。同じ環境に任意の言語モデルをダウンロードし、自前のPC内でAIを動かせるようになります。必要なのはそこそこのスペックと電気代だけです。

```bash
# Ollamaインストール  
curl -fsSL https://ollama.com/install.sh | sh  
# モデルのダウンロード  
ollama pull pakachan/elyza-llama3-8b
```

## **🏃 実行方法**

全ての準備が整ったら、後は本プログラムを実行するだけです。configで指定したチャンネルをDiscord Botが監視し始めます。

> [!IMPORTANT]
> **Bot起動前にOllamaサービスが起動していること**を確認してください。
> Ollamaはインストールしただけではサービスとして動いていないことがあります。
>
> ```bash
> # Ollamaサービスをバックグラウンドで起動
> ollama serve &
>
> # または、起動中かどうかを確認（モデル一覧が表示されればOK）
> ollama list
> ```
>
> Ollamaが起動していない状態でBotを動かすと、AIが応答できずエラーになります。

### 🕊️ おすすめの起動方法（自動更新付き）
本プログラムの最新化とOllamaの起動確認やBotの起動を1コマンドで行ってくれる起動スクリプトを用意しています。一番簡単でおすすめです。

```bash
./start.sh
```

### 🐢 手動での起動方法
もしプログラムの最新化が不要等の理由で手動で実行したい場合は、以下の手順になります。

1. **仮想環境を有効化**  
   source venv/bin/activate

2. **Botを起動**  
   python main.py

サーバーに参加させたBotの名前がログイン状態になっていたら、監視が成功しています。

### 💡 「時短テクニック」
毎回端末の起動時に`source ...` と打つのが面倒な場合、実は以下のコマンドで**「仮想環境の中にあるPython」を直接指定して**１行で実行することもできます。

```bash
# activateしなくても、これで動きます
./venv/bin/python main.py
```

## **📂 ディレクトリ構造**

* main.py: メインスクリプト  
* config.yaml: 設定ファイル（Git管理外）  
* API_CONTRACT.md: 連携APIの仕様書
* cogs/: 機能モジュール  
  * system.py: 負荷確認、基本コマンド  
  * chat.py: AI連携おしゃべり機能
  * game.py: ゲームサーバー管理機能
* web/: 管理ダッシュボード用Reactサーバー  
* mock_api_server.py: 動作確認証FlaskMockサーバー

## **🎮 ゲームサーバー管理機能**

ゲームサーバー管理用のAPIサーバーアプリケーションと連携させることで、Discordへのコマンド入力でゲームサーバーを管理することができるようになります。APIサーバーアプリケーションは別途作成予定ですが、mock_api_server.pyという動作確認用の偽物サーバーだけ同梱しています。
以下のコマンドで、ローカルAPI（デフォルト: localhost:5000）経由でサーバーを操作(APIアクセス)できます。

* /gs\_list: サーバー名、状態（オンライン/オフライン）、プレイヤー数、ゲーム内日数、リソース使用率の一覧を表示します。  
* /gs\_start \<サーバー名\>: 指定したサーバーを起動します。  
* /gs\_stop \<サーバー名\>: 指定したサーバーを停止します。

## **🎮 動作確認用　モックAPIサーバーの起動**

```bash
./venv/bin/python mock_api_server.py
```

## **🎮 Webダッシュボードサーバーの起動**

### 事前準備

1. Web Dashboard (React) の起動に必要なNode環境のセットアップ

```bash
# Node.js 20系をインストール (Ubuntu)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# インストール確認
node -v
npm -v
```

### Web Dashboard (React) の起動

```bash
cd web
npm install
npm run dev -- --host
```
