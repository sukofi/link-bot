#!/bin/bash
# Link Bot 起動スクリプト

echo "============================================================"
echo "🔗 Link Bot - 内部リンク提案Bot"
echo "============================================================"
echo ""

# 環境変数チェック
if [ ! -f .env ]; then
    echo "❌ エラー: .env ファイルが見つかりません"
    echo ""
    echo "セットアップ手順:"
    echo "1. env.link_bot.example を参考に .env ファイルを作成"
    echo "2. LINK_BOT_TOKEN を設定"
    echo "3. GEMINI_API_KEY を設定（オプション）"
    echo ""
    echo "詳細は LINK_BOT_SETUP.md をご覧ください"
    exit 1
fi

# Python バージョンチェック
python3 --version > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ エラー: Python 3 がインストールされていません"
    exit 1
fi

echo "✅ 環境チェック: OK"
echo ""
echo "Bot を起動します..."
echo "終了するには Ctrl+C を押してください"
echo ""

# Bot 起動
python3 link_bot.py
