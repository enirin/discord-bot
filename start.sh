#!/bin/bash

# スクリプトがあるディレクトリ（リポジトリのルート）に移動
cd "$(dirname "$0")"

# '.git' ディレクトリが存在するか確認し、存在する場合のみ pull する
if [ -d ".git" ]; then
    echo "🔄 リポジトリから最新のコードを取得しています..."
    git pull origin main
else
    echo "📌 Gitリポジトリとして構成されていません。最新のコード取得をスキップします。"
fi

# config.yamlが存在するかチェック
if [ ! -f "config.yaml" ]; then
    echo "⚠️ config.yaml が存在しないため、config.yaml.sample から自動でコピーします..."
    cp config.yaml.sample config.yaml
    echo "💡 config.yaml を作成しました！"
    echo "❌ 起動する前に、必ず config.yaml を開いてDiscordのトークン(bot_token)などに書き換えてください。"
    exit 1
fi

VENV_DIR="./venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"
REQUIREMENTS_STAMP="$VENV_DIR/.requirements.txt"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "🐍 Python仮想環境が見つからないため作成します..."
    python3 -m venv "$VENV_DIR"
fi

sync_requirements=false

if [ ! -x "$VENV_PIP" ]; then
    echo "📦 pip が見つからないため、依存関係を再構成します..."
    sync_requirements=true
fi

if [ ! -f "$REQUIREMENTS_STAMP" ] || ! cmp -s requirements.txt "$REQUIREMENTS_STAMP"; then
    sync_requirements=true
fi

if ! "$VENV_PYTHON" -c "import discord, yaml" > /dev/null 2>&1; then
    sync_requirements=true
fi

if ! "$VENV_PYTHON" -c "import mcp" > /dev/null 2>&1; then
    sync_requirements=true
fi

if [ "$sync_requirements" = true ]; then
    echo "📦 Python依存関係を同期しています..."
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r requirements.txt
    cp requirements.txt "$REQUIREMENTS_STAMP"
fi

# Ollamaの起動状態を確認し、未起動であれば起動する
echo "🤖 Ollamaの起動状態を確認しています..."
if ollama list > /dev/null 2>&1; then
    echo "✅ Ollamaはすでに起動しています。"
else
    echo "⚡ Ollamaが起動していません。バックグラウンドで起動します..."
    ollama serve > /dev/null 2>&1 &
    sleep 5
    if ollama list > /dev/null 2>&1; then
        echo "✅ Ollamaを起動しました。"
    else
        echo "❌ Ollamaの起動に失敗しました。'ollama serve' を手動で実行してから再度お試しください。"
        exit 1
    fi
fi

echo "🚀 Botを起動しています..."
"$VENV_PYTHON" main.py
