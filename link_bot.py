"""
Link Bot - 内部リンク提案専用Discord Bot
SEO順位チェッカーから分離した、内部リンク候補提案に特化したシンプルなBot
"""
import os
import sys
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
from typing import List, Dict, Any
import yaml

# HTTPリクエスト用（Vercel API呼び出し）
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    print("[WARN] aiohttp is not installed. Vercel API integration will not work.")

# 標準出力のバッファリングを無効化
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

from storage import RankingStorage

# AI分析機能
try:
    from ai_analyzer import GeminiAnalyzer
except (ImportError, PermissionError, OSError) as e:
    GeminiAnalyzer = None
    print(f"[WARN] ai_analyzer のインポートに失敗しました: {e}")
    print("[WARN] AI分析機能は無効になりますが、Botは動作します")

# Google Sheets同期機能
try:
    from sheets_sync import sync_to_storage
    SHEETS_SYNC_AVAILABLE = True
except ImportError as e:
    sync_to_storage = None
    SHEETS_SYNC_AVAILABLE = False
    print(f"[WARN] sheets_sync のインポートに失敗しました: {e}")


class LinkBot(commands.Bot):
    """内部リンク提案専用Bot"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='/', intents=intents)
        
        # 設定読み込み
        load_dotenv()
        self.load_config()
        
        # クライアント初期化
        self.setup_clients()
        
        # 会話履歴（ユーザーIDごとに管理）
        self.conversation_history = {}
        
    def load_config(self):
        """設定ファイルを読み込む"""
        # 設定ファイルのパスを絶対パスに変換
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'settings.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 環境変数
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')

        # Google Sheets同期設定
        self.spreadsheet_id = os.getenv(
            'SPREADSHEET_ID',
            '1RZmk6tJeIpLExKQ3gAPZ-qCOOe2Pmv0BsY7GYGlBbDk'
        )
        self.google_credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        self.sheet_name = os.getenv('SHEET_NAME', '管理シート')

        # 許可するチャンネルID（オプション）
        # 特定のチャンネルでのみ動作させたい場合は、.envにチャンネルIDを設定
        allowed_channels = os.getenv('LINK_BOT_ALLOWED_CHANNELS')
        if allowed_channels:
            self.allowed_channel_ids = [int(ch.strip()) for ch in allowed_channels.split(',')]
        else:
            self.allowed_channel_ids = None  # 全チャンネルで動作
        
    def setup_clients(self):
        """各種クライアントをセットアップ"""
        # Storage（既存のデータベースを共有）
        db_path = self.config.get('db_path', 'rankings.db')
        # 相対パスの場合は絶対パスに変換
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        self.storage = RankingStorage(db_path)
        
        # AI Analyzer
        self.ai_analyzer = None
        if self.gemini_api_key and GeminiAnalyzer:
            try:
                self.ai_analyzer = GeminiAnalyzer(
                    api_key=self.gemini_api_key,
                    model_name=self.config.get('gemini_model', 'gemini-1.5-flash')
                )
                print("[INFO] AI分析機能が有効化されました")
            except Exception as e:
                print(f"[WARN] AI分析機能の初期化に失敗: {e}")
        else:
            print("[WARN] GEMINI_API_KEYが設定されていないため、フォールバック検索のみ利用可能です")
    
    async def on_ready(self):
        """ボット起動時"""
        print(f'[INFO] {self.user} としてログインしました')
        print(f'[INFO] 内部リンク提案専用Bot')
        print(f'[INFO] コマンド: /links, /search, /guide, /genres, /status, /sync')
        print('='*60)

        # 起動時にスプレッドシートから自動同期
        if SHEETS_SYNC_AVAILABLE and self.google_credentials_path:
            try:
                print("[SYNC] 起動時スプレッドシート同期を開始...")
                stats = await asyncio.to_thread(
                    sync_to_storage,
                    self.spreadsheet_id,
                    self.google_credentials_path,
                    self.storage,
                    self.sheet_name
                )
                print(f"[SYNC] 起動時同期完了: 新規={stats['inserted']}件, 更新={stats['updated']}件")
            except Exception as e:
                print(f"[WARN] 起動時スプレッドシート同期に失敗: {e}")
    
    async def on_message(self, message):
        """メッセージ受信時の処理"""
        # ボット自身のメッセージは無視
        if message.author == self.user:
            return
        
        # チャンネル制限がある場合はチェック
        is_allowed_channel = False
        if self.allowed_channel_ids and not isinstance(message.channel, discord.DMChannel):
            if message.channel.id in self.allowed_channel_ids:
                is_allowed_channel = True
            else:
                # 許可されていないチャンネルでは無視（メンションがある場合は除く）
                if self.user not in message.mentions:
                    return
        
        # コマンドの場合は通常処理
        if message.content.startswith(self.command_prefix):
            await self.process_commands(message)
            return
        
        # 許可チャンネル内、DM、またはメンションされた場合は自然言語で応答（メンション不要）
        if is_allowed_channel or isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
            await self.handle_natural_language(message)
    
    async def handle_natural_language(self, message):
        """自然言語メッセージの処理"""
        user_id = str(message.author.id)
        user_message = message.content.replace(f'<@{self.user.id}>', '').strip()
        
        print(f"[NL] Message from {message.author}: {user_message}")
        
        # AIが無効な場合
        if not self.ai_analyzer:
            await message.reply(
                "内部リンク候補を検索します。コマンドを使ってください：\n"
                "`/links [キーワード]` - 内部リンク候補を提案\n"
                "`/search [キーワード]` - キーワード検索\n"
                "`/guide` - 使い方を表示"
            )
            return
        
        try:
            async with message.channel.typing():
                # キーワード抽出
                # 「リンク」「候補」などのキーワードがある場合、それらを除外してキーワードを抽出
                # それ以外の場合は、メッセージ全体をキーワードとして扱う
                if 'リンク' in user_message or '候補' in user_message or '設置' in user_message:
                    # キーワードを抽出
                    stop_words = ['の', 'を', 'に', 'で', '内部', 'リンク', '候補', '教えて', 'ください', '提案', 'して', 'を教えて', 'の内部', '内部リンク']
                    keywords_to_check = []
                    for word in user_message.split():
                        if word not in stop_words and len(word) > 0:
                            keywords_to_check.append(word)
                    
                    if keywords_to_check:
                        target_keyword = ' '.join(keywords_to_check)
                    else:
                        # キーワードが抽出できない場合は、メッセージ全体から停止語を除外
                        target_keyword = user_message
                        for stop_word in stop_words:
                            target_keyword = target_keyword.replace(stop_word, ' ').strip()
                        target_keyword = ' '.join(target_keyword.split())
                else:
                    # その他の場合は、メッセージ全体をキーワードとして扱う
                    target_keyword = user_message.strip()
                
                # キーワードが空でない場合のみ処理
                if target_keyword and len(target_keyword) >= 2:
                    ctx = await self.get_context(message)
                    await suggest_links(ctx, target_keyword=target_keyword)
                else:
                    await message.reply(
                        "対策キーワードを教えてください。\n"
                        "例: 「ロレックス デイトナの内部リンク候補を教えて」\n"
                        "または、キーワードだけを入力: 「シャネル ポーチ ノベルティ」"
                    )
        
        except Exception as e:
            print(f"[ERROR] Natural language processing failed: {e}")
            import traceback
            traceback.print_exc()
            await message.reply("申し訳ありません。エラーが発生しました。")


# ボットインスタンス
bot = LinkBot()


@bot.command(name='sync', help='Google Sheetsからキーワード・URLを同期')
async def sync_from_sheet(ctx):
    """
    スプレッドシートからDBへキーワード・URLを同期する。

    使い方:
        /sync
    """
    if not SHEETS_SYNC_AVAILABLE:
        await ctx.send("❌ Google Sheets同期機能が利用できません（sheets_syncのインポート失敗）。")
        return

    if not bot.google_credentials_path:
        await ctx.send(
            "❌ `GOOGLE_CREDENTIALS_PATH` が設定されていません。\n"
            ".envにサービスアカウントJSONのパスを設定してください。"
        )
        return

    await ctx.send("🔄 スプレッドシートからデータを同期中...")

    try:
        stats = await asyncio.to_thread(
            sync_to_storage,
            bot.spreadsheet_id,
            bot.google_credentials_path,
            bot.storage,
            bot.sheet_name
        )
        await ctx.send(
            f"✅ 同期完了！\n"
            f"📥 新規登録: {stats['inserted']}件\n"
            f"🔄 URL更新: {stats['updated']}件\n"
            f"📊 シート取得: {stats.get('fetched', '?')}行\n"
            f"合計処理: {stats['total']}件"
        )
    except Exception as e:
        await ctx.send(f"❌ 同期に失敗しました: {str(e)[:300]}")
        print(f"[ERROR] sync_from_sheet: {e}")
        import traceback
        traceback.print_exc()


@bot.command(name='links', help='対策キーワードの内部リンク候補を提案')
async def suggest_links(ctx, *, target_keyword: str = None):
    """
    内部リンク候補提案コマンド
    
    使い方:
        /links [対策キーワード]
        
    例:
        /links ロレックス デイトナ
        /links 金 買取
    """
    if not target_keyword:
        await ctx.send(
            "❌ 使い方: `/links [対策キーワード]`\n"
            "例: `/links ロレックス デイトナ`"
        )
        return
    
    print(f"\n[BOT] Links command received from {ctx.author}")
    print(f"[BOT] Target keyword: {target_keyword}")
    
    await ctx.send(f"🔍 **「{target_keyword}」の内部リンク候補を検索中...**")
    
    try:
        # Vercel API URLが設定されている場合はVercel APIを使用
        vercel_api_url = os.getenv('VERCEL_API_URL')
        
        if vercel_api_url:
            # Vercel APIを呼び出し
            print(f"[BOT] Using Vercel API: {vercel_api_url}")
            await suggest_links_via_api(ctx, target_keyword, vercel_api_url)
        else:
            # 既存のロジックを使用（ローカルデータベース）
            print(f"[BOT] Using local database")
            await suggest_links_local(ctx, target_keyword)
        
        print(f"[BOT] Links command completed!")
        
    except Exception as e:
        error_msg = f"❌ エラーが発生しました: {str(e)}"
        await ctx.send(error_msg)
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

async def suggest_links_via_api(ctx, target_keyword: str, api_url: str):
    """Vercel API経由で内部リンク候補を取得"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{api_url}/links",
                params={'keyword': target_keyword},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get('success') and result.get('data'):
                        await send_links_result(ctx, target_keyword, result['data'])
                    else:
                        await ctx.send(f"😢 関連する内部リンク候補が見つかりませんでした。")
                else:
                    error_text = await response.text()
                    await ctx.send(f"❌ APIエラーが発生しました: {response.status}\n{error_text[:200]}")
    except aiohttp.ClientError as e:
        await ctx.send(f"❌ API接続エラー: {str(e)}")
        print(f"[ERROR] API connection error: {e}")

async def suggest_links_local(ctx, target_keyword: str):
    """ローカルデータベースを使用して内部リンク候補を取得（既存ロジック）"""
    # データベースから全キーワードを取得
    print(f"[BOT] Fetching all keywords from database")
    all_keywords = bot.storage.get_all_keywords()

    # 順位情報をマージ（rank_boostスコアリングに使用）
    try:
        all_rankings = bot.storage.get_all_rankings()
        rank_map = {r['keyword']: r.get('last_rank') for r in all_rankings if r.get('last_rank')}
        for kw in all_keywords:
            if kw['keyword'] in rank_map:
                kw['current_rank'] = rank_map[kw['keyword']]
    except Exception as e:
        print(f"[WARN] 順位情報のマージに失敗: {e}")
    
    if not all_keywords:
        await ctx.send("❌ データベースにキーワードが登録されていません。")
        return
    
    # 対策キーワードがデータベースに存在するか確認
    target_exists = any(kw['keyword'] == target_keyword for kw in all_keywords)
    
    if not target_exists:
        await ctx.send(
            f"ℹ️ 「{target_keyword}」はデータベースに未登録ですが、関連キーワードを検索します..."
        )
    
    # タイピングインジケーターを表示
    async with ctx.typing():
        if bot.ai_analyzer:
            # AIで関連キーワードを検索
            print(f"[BOT] Searching related keywords using AI")
            await ctx.send("🤖 AIで関連性を分析中... (数秒かかります)")
            
            related_keywords = await asyncio.to_thread(
                bot.ai_analyzer.find_related_keywords,
                target_keyword,
                all_keywords,
                limit=10
            )
        else:
            # フォールバック: ジャンル一致検索
            print(f"[BOT] Using fallback search (genre/keyword match)")
            await ctx.send("🔎 ジャンル/キーワード一致で検索中...")
            
            related_keywords = await asyncio.to_thread(
                bot.ai_analyzer._fallback_related_keywords if bot.ai_analyzer else _simple_search,
                target_keyword,
                all_keywords,
                10
            )
        
        if not related_keywords:
            await ctx.send(
                f"😢 「{target_keyword}」に関連する内部リンク候補が見つかりませんでした。\n"
                "別のキーワードでお試しください。"
            )
            return
        
        print(f"[BOT] Found {len(related_keywords)} related keywords")
        
        # 結果を送信
        await send_links_result(ctx, target_keyword, related_keywords)


async def send_links_result(ctx, target_keyword: str, related_keywords: List[Dict[str, Any]]):
    """
    内部リンク候補の結果を送信
    
    Args:
        ctx: Discordコンテキスト
        target_keyword: 対策キーワード
        related_keywords: 関連キーワードのリスト
    """
    # テキスト形式で送信
    result_text = f"📎 「{target_keyword}」の内部リンク候補\n"
    result_text += f"関連性の高い記事 {len(related_keywords)}件\n\n"
    
    # 全件を表示（最大10件）
    for i, kw in enumerate(related_keywords[:10], 1):
        keyword = kw['keyword']
        url = kw.get('url', 'URL未設定')
        reason = kw.get('reason', '関連性が高いキーワード')
        genre = kw.get('genre', '未分類')
        rank = kw.get('current_rank')
        rank_str = f"📊 現在順位: {rank}位\n" if rank else ""

        result_text += f"{i}. {keyword}\n"
        result_text += f"💡 {reason}\n"
        result_text += f"🏷️ {genre}\n"
        result_text += rank_str
        result_text += f"🔗 {url}\n\n"
    
    await ctx.send(result_text)


@bot.command(name='search', help='データベースからキーワードを検索')
async def search_keywords(ctx, *, query: str = None):
    """
    キーワード検索コマンド
    
    使い方:
        /search [検索キーワード]
        
    例:
        /search ロレックス
        /search 金
    """
    if not query:
        await ctx.send(
            "❌ 使い方: `/search [検索キーワード]`\n"
            "例: `/search ロレックス`"
        )
        return
    
    print(f"\n[BOT] Search command received from {ctx.author}")
    print(f"[BOT] Query: {query}")
    
    try:
        # データベースから全キーワードを取得
        all_keywords = bot.storage.get_all_keywords()
        
        if not all_keywords:
            await ctx.send("❌ データベースにキーワードが登録されていません。")
            return
        
        # 部分一致検索
        query_lower = query.lower()
        matching_keywords = [
            kw for kw in all_keywords
            if query_lower in kw['keyword'].lower()
        ]
        
        if not matching_keywords:
            await ctx.send(f"😢 「{query}」に一致するキーワードが見つかりませんでした。")
            return
        
        # 結果を表示（最大20件）
        embed = discord.Embed(
            title=f"🔍 「{query}」の検索結果",
            description=f"{len(matching_keywords)}件見つかりました",
            color=discord.Color.blue()
        )
        
        for i, kw in enumerate(matching_keywords[:20], 1):
            genre = kw.get('genre', '未分類')
            url = kw.get('url', 'URLなし')
            embed.add_field(
                name=f"{i}. {kw['keyword']}",
                value=f"🏷️ {genre}\n🔗 {url[:80]}...",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
        if len(matching_keywords) > 20:
            await ctx.send(f"... 他 {len(matching_keywords) - 20}件")
        
        print(f"[BOT] Search completed: {len(matching_keywords)} results")
        
    except Exception as e:
        error_msg = f"❌ エラーが発生しました: {str(e)}"
        await ctx.send(error_msg)
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


@bot.command(name='genres', help='登録されているジャンルを一覧表示')
async def list_genres(ctx):
    """
    ジャンル一覧表示コマンド
    
    使い方:
        /genres
    """
    print(f"\n[BOT] Genres command received from {ctx.author}")
    
    try:
        # ジャンルを取得
        all_keywords = bot.storage.get_all_keywords()
        
        if not all_keywords:
            await ctx.send("❌ データベースにキーワードが登録されていません。")
            return
        
        # ジャンル別に集計
        genre_count = {}
        for kw in all_keywords:
            genre = kw.get('genre') or '未分類'
            genre_count[genre] = genre_count.get(genre, 0) + 1
        
        # 結果を表示
        embed = discord.Embed(
            title="🏷️ 登録ジャンル一覧",
            description=f"全{len(genre_count)}ジャンル、{len(all_keywords)}キーワード",
            color=discord.Color.purple()
        )
        
        # 件数順にソート
        sorted_genres = sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
        
        genre_lines = []
        for genre, count in sorted_genres:
            genre_lines.append(f"**{genre}**: {count}件")
        
        # 10件ずつ分割
        for i in range(0, len(genre_lines), 10):
            chunk = genre_lines[i:i+10]
            embed.add_field(
                name=f"ジャンル {i+1}-{min(i+10, len(genre_lines))}",
                value="\n".join(chunk),
                inline=True
            )
        
        await ctx.send(embed=embed)
        
        print(f"[BOT] Genres listed: {len(genre_count)} genres")
        
    except Exception as e:
        error_msg = f"❌ エラーが発生しました: {str(e)}"
        await ctx.send(error_msg)
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


@bot.command(name='guide', help='使い方を表示')
async def guide_command(ctx):
    """ヘルプ表示"""
    help_text = """
**📖 Link Bot - 内部リンク提案Bot**

このBotは、対策キーワードに関連する内部リンク候補を提案します。

**コマンド:**
`/links [キーワード]` - 内部リンク候補を提案
`/search [キーワード]` - キーワードを検索
`/genres` - ジャンル一覧を表示
`/guide` - この使い方を表示
`/status` - Bot状態を確認

**使用例:**
```
/links ロレックス デイトナ  # 内部リンク候補を取得
/search ロレックス          # ロレックス関連のキーワードを検索
/genres                    # 登録されているジャンルを確認
```

**自然言語対応:**
Botをメンションすることで、自然な日本語でも使えます。
例: `@LinkBot ロレックス デイトナの内部リンク候補を教えて`
"""
    await ctx.send(help_text)


@bot.command(name='status', help='Bot の状態を表示')
async def status(ctx):
    """ステータス表示"""
    embed = discord.Embed(
        title="⚙️ Bot ステータス",
        color=discord.Color.green()
    )
    
    # データベース情報
    all_keywords = bot.storage.get_all_keywords()
    all_genres = bot.storage.get_all_genres()
    
    embed.add_field(name="データベース", value=bot.config.get('db_path', 'rankings.db'), inline=False)
    embed.add_field(name="登録キーワード数", value=f"{len(all_keywords)}件", inline=True)
    embed.add_field(name="ジャンル数", value=f"{len(all_genres)}種類", inline=True)
    embed.add_field(name="AI分析", value="有効" if bot.ai_analyzer else "無効 (フォールバックのみ)", inline=True)
    
    if bot.ai_analyzer:
        embed.add_field(name="AIモデル", value=bot.config.get('gemini_model', 'N/A'), inline=True)
    
    await ctx.send(embed=embed)


def _simple_search(target_keyword: str, all_keywords: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """
    シンプルな検索（AIが使えない場合のフォールバック）
    
    Args:
        target_keyword: 対策キーワード
        all_keywords: 全キーワード情報
        limit: 返す件数
        
    Returns:
        関連キーワードのリスト
    """
    # 対策キーワードのジャンルを取得
    target_info = next(
        (kw for kw in all_keywords if kw['keyword'] == target_keyword),
        None
    )
    
    target_genre = target_info.get('genre') if target_info else None
    
    # スコアリング
    scored_keywords = []
    for kw in all_keywords:
        if kw['keyword'] == target_keyword or not kw.get('url'):
            continue
        
        score = 0
        reason_parts = []
        
        # ジャンルが一致
        if target_genre and kw.get('genre') == target_genre:
            score += 60
            reason_parts.append(f"同じジャンル「{target_genre}」")
        
        # キーワードの一部が一致
        target_words = set(target_keyword.split())
        kw_words = set(kw['keyword'].split())
        common_words = target_words & kw_words
        
        if common_words:
            score += len(common_words) * 20
            reason_parts.append(f"共通ワード: {', '.join(common_words)}")
        
        if score > 0:
            scored_keywords.append({
                'keyword': kw['keyword'],
                'url': kw['url'],
                'genre': kw.get('genre', '未分類'),
                'score': min(score, 100),
                'reason': '、'.join(reason_parts) if reason_parts else '関連性あり'
            })
    
    # スコア順にソート
    scored_keywords.sort(key=lambda x: x['score'], reverse=True)
    
    return scored_keywords[:limit]


def main():
    """メイン処理"""
    token = os.getenv('LINK_BOT_TOKEN')
    
    if not token:
        print("[ERROR] LINK_BOT_TOKEN が設定されていません")
        print("[ERROR] .env ファイルに LINK_BOT_TOKEN を追加してください")
        return
    
    print("="*60)
    print("🔗 Link Bot - 内部リンク提案Bot 起動中...")
    print("="*60)
    
    bot.run(token)


if __name__ == '__main__':
    main()
