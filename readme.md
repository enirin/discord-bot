# **SME Discord Bot (WSL \+ Local LLM)**

WSL2上で動作する、ローカルLLM（Ollama）と連携したAI Discord Botです。
使用モデルやキャラクタ設定（プロンプト）はconfig.yamlで変更可能です。
サーバー負荷確認（/load）や、レートリミット付きのAIチャット機能を備えています。

## **📋 前提条件**

* **OS**: Windows 10/11 (WSL2 / Ubuntu推奨)  
* **Python**: 3.10以上  
* **Ollama**: WSL上で動作していること  
* **Hardware**: メモリ 8GB以上（16GB以上推奨）

## **📖 設計思想とAPI仕様 (Contract)**

本プロジェクトでは、Bot側とサーバー管理側を疎結合にするため、\*\*「APIファースト」\*\*の設計を採用しています。管理アプリ本体が未完成の状態でも、先にインターフェースを定義することでDiscord Bot機能のみ先行実装しました。

* [API\_CONTRACT.md](https://www.google.com/search?q=./API_CONTRACT.md) : 連携APIの入出力仕様を定義した「契約」ドキュメント。

## **🛠️ Discord Botの準備と設定**

Botを動かす前に、Discord側でアプリケーションの作成とトークンの取得が必要です。

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
2. **Scopes** で bot にチェックを入れます。  
3. **Bot Permissions** で Send Messages、Read Message History、View Channels にチェックを入れます。  
4. 生成されたURLをブラウザで開き、Botを追加したいサーバーを選択して追加します。

## **🆔 チャンネルIDの取得方法**

Botが監視する特定のチャンネルIDを特定する手順です。

1. Discordアプリ左下の **\[ユーザー設定\]**（歯車アイコン）を開きます。  
2. **\[詳細設定\]** (Advanced) を選択し、**\[開発者モード\]** を **ON** にします。  
3. 設定を閉じ、監視したいチャンネル名を **右クリック** します。  
4. 一番下に表示される **\[チャンネルIDをコピー\]** をクリックします。  
   * この数字を config.yaml の channel\_ids リストに貼り付けます。

## **🚀 セットアップ手順（プログラム側）**

### **1\. リポジトリの取得**

git clone https://github.com/enirin/discord-bot.git  
cd discord-bot

### **2\. Python仮想環境の構築**

\# 仮想環境の作成  
python3 \-m venv venv

\# 仮想環境の有効化  
source venv/bin/activate

\# 依存ライブラリのインストール  
pip install \-r requirements.txt

### **3\. 設定ファイル（config.yaml）の作成**

リポジトリ直下に config.yaml を新規作成し、取得したトークン等を記述してください。

bot\_token: "取得したトークン"  
channel\_ids:  
  \- 123456789012345678 \# コピーしたチャンネルID  
bot\_name: "MySME BOTちゃん"  
\# ...その他AI設定等

### **4\. Ollamaとモデルの準備**

\# Ollamaインストール  
curl \-fsSL \[https://ollama.com/install.sh\](https://ollama.com/install.sh) | sh  
\# モデルのダウンロード  
ollama pull pakachan/elyza-llama3-8b

## **🏃 実行方法**

1. **仮想環境を有効化**  
   source venv/bin/activate

2. **Botを起動**  
   python main.py

### 💡 「時短テクニック」

毎回 `source ...` と打つのが面倒な場合、実は**「仮想環境の中にあるPython」を直接指定して実行**することもできます。

```bash
# activateしなくても、これで動きます
./venv/bin/python main.py
```

## **📂 ディレクトリ構造**

* main.py: メインスクリプト  
* config.yaml: 設定ファイル（Git管理外）  
* cogs/: 機能モジュール  
  * system.py: 負荷確認、基本コマンド  
  * chat.py: AI連携おしゃべり機能
  * game.py: ゲームサーバー管理機能

## **🎮 ゲームサーバー管理機能**
以下のコマンドで、ローカルAPI（デフォルト: localhost:5000）経由でサーバーを操作(APIアクセス)できます。

* /gs\_list: サーバー名、状態（オンライン/オフライン）、プレイヤー数、ゲーム内日数、リソース使用率の一覧を表示します。  
* /gs\_start \<サーバー名\>: 指定したサーバーを起動します。  
* /gs\_stop \<サーバー名\>: 指定したサーバーを停止します。

## **🎮 動作確認用　モックAPIサーバーの起動**
```bash
./venv/bin/python mock_api_server.py
```