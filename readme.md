# **Antigravity Discord Bot (WSL \+ Local LLM)**

WSL2上で動作する、ローカルLLM（Ollama）と連携したAI Discord Botです。

サーバー負荷確認（/load）や、レートリミット付きのAIチャット機能を備えています。

## **📋 前提条件**

* **OS**: Windows 10/11 (WSL2 / Ubuntu推奨)  
* **Python**: 3.10以上  
* **Ollama**: WSL上で動作していること  
* **Hardware**: メモリ 8GB以上（16GB以上推奨）

## **🚀 セットアップ手順**

### **1\. リポジトリの取得**

git clone \<あなたのリポジトリURL\>  
cd \<リポジトリ名\>

### **2\. Python仮想環境の構築**

\# 仮想環境の作成  
python3 \-m venv venv

\# 仮想環境の有効化  
source venv/bin/activate

\# 依存ライブラリのインストール  
pip install \-r requirements.txt

### **3\. 設定ファイル（config.yaml）の作成**

セキュリティのため config.yaml はGit管理から除外しています。

リポジトリ直下に新規作成し、以下の内容を記述してください。

\# Discord設定  
bot\_token: "YOUR\_DISCORD\_BOT\_TOKEN"  
channel\_id: 123456789012345678  \# 監視するチャンネルID  
bot\_name: "Antigravity"         \# Botの表示名  
icon\_path: "./icon.png"         \# アイコン画像のパス

\# レートリミット設定 (おしゃべり機能)  
rate\_limit\_seconds: 10          \# 判定秒数  
rate\_limit\_count: 3             \# 許可回数

\# 優先キーワード (レートリミットを無視して反応)  
priority\_keywords:  
  \- "緊急"  
  \- "ヘルプ"  
  \- "おーい"

\# AI設定 (Ollama)  
ai\_model: "pakachan/elyza-llama3-8b"  
system\_prompt: \>  
  あなたは10代の明るい女の子です。  
  「～だよ！」「～だねっ✨」といった元気な口調で、友達みたいに話してね！

\# コマンドリスト  
commands:  
  \- "/ping"  
  \- "/hello"  
  \- "/load"

### **4\. Ollamaとモデルの準備**

WSL環境にOllamaをインストールし、使用するモデルをプルします。

\# Ollamaのインストール (未導入の場合)  
curl \-fsSL \[https://ollama.com/install.sh\](https://ollama.com/install.sh) | sh

\# 日本語モデルのダウンロード  
ollama pull pakachan/elyza-llama3-8b

## **🏃 実行方法**

1. **仮想環境を有効化**  
   source venv/bin/activate

2. **Botを起動**  
   python main.py

## **📂 ディレクトリ構造**

* main.py: メインスクリプト  
* config.yaml: 設定ファイル（Git管理外）  
* requirements.txt: 必要ライブラリ  
* cogs/: 機能モジュール  
  * system.py: システム系コマンド（load, ping等）  
  * chat.py: AI連携おしゃべり機能（レートリミット込）