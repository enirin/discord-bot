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

echo "🚀 Botを起動しています..."
./venv/bin/python main.py
