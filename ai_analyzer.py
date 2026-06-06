"""
Gemini AIを使用した順位変動分析モジュール
"""
import os
from typing import List, Dict, Any, Optional
import json
import warnings

# 非推奨警告を抑制
warnings.filterwarnings('ignore', category=FutureWarning)

try:
    import google.generativeai as genai
except (ImportError, PermissionError, OSError) as e:
    genai = None
    print(f"[WARN] google.generativeai のインポートに失敗しました: {e}")

# スプレッドシート機能は削除されました
SpreadsheetReader = None


class GeminiAnalyzer:
    """Gemini AIを使用した順位変動分析"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """
        Args:
            api_key: Gemini API Key
            model_name: 使用するモデル名
        """
        if genai is None:
            raise ImportError(
                "google-generativeai がインストールされていません。\n"
                "以下のコマンドでインストールしてください:\n"
                "pip install google-generativeai"
            )
        
        self.api_key = api_key
        self.model_name = model_name
        
        # Gemini APIの設定
        genai.configure(api_key=api_key)
        
        # ウェブ検索機能の有効化チェック
        enable_web_search = os.getenv('ENABLE_WEB_SEARCH', 'false').lower() == 'true'
        
        if enable_web_search:
            # Geminiモデルを初期化（Google Search有効）
            # 注: 現在のgoogle-generativeai SDKでは、Google Searchツールはまだ完全にサポートされていません
            # 代わりに、AIの知識ベースでウェブの情報を推測する方式を使用
            print(f"[INFO] Gemini モデル初期化: {model_name}")
            print(f"[INFO] ウェブ検索モード有効（AI知識ベース活用）")
            self.model = genai.GenerativeModel(model_name)
        else:
            # Geminiモデルを初期化（基本モデル、ウェブ検索なし）
            # データベースに保存された情報のみを使用
            self.model = genai.GenerativeModel(model_name)
            print(f"[INFO] Gemini モデル初期化: {model_name}")
            print(f"[INFO] データベースベースの分析モード（ウェブ検索なし）")
        
        # スプレッドシート機能は削除されました
        self.spreadsheet_reader = None
    
    def analyze_rank_drops(
        self,
        dropped_keywords: List[Dict[str, Any]],
        out_of_ranking_keywords: List[Dict[str, Any]],
        historical_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
    ) -> Dict[str, Any]:
        """
        順位下落の総合分析を実行
        
        Args:
            dropped_keywords: 下落したキーワード情報のリスト
            out_of_ranking_keywords: 圏外落ちしたキーワード情報のリスト
            historical_data: 過去の順位履歴データ（オプション）
            
        Returns:
            分析結果の辞書
            {
                'summary': str,  # 全体サマリー
                'trends': str,   # トレンド分析
                'recommendations': str,  # 改善提案
                'priority_keywords': List[str]  # 優先対応すべきキーワード
            }
        """
        if not dropped_keywords and not out_of_ranking_keywords:
            return {
                'summary': '順位下落は検出されませんでした。',
                'trends': 'トレンド分析: 該当データなし',
                'recommendations': '現状維持で問題ありません。',
                'priority_keywords': []
            }
        
        # プロンプトを構築
        prompt = self._build_analysis_prompt(
            dropped_keywords,
            out_of_ranking_keywords,
            historical_data
        )
        
        try:
            # Gemini APIで分析
            print("[INFO] Gemini AI による分析を実行中...")
            response = self.model.generate_content(prompt)
            
            # レスポンスをパース
            analysis_result = self._parse_ai_response(response.text)
            
            print("[INFO] AI分析が完了しました")
            return analysis_result
            
        except Exception as e:
            print(f"[ERROR] AI分析に失敗しました: {e}")
            return {
                'summary': 'AI分析の実行に失敗しました。',
                'trends': 'エラーのため分析できませんでした。',
                'recommendations': '手動で確認してください。',
                'priority_keywords': []
            }
    
    def _build_analysis_prompt(
        self,
        dropped_keywords: List[Dict[str, Any]],
        out_of_ranking_keywords: List[Dict[str, Any]],
        historical_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
    ) -> str:
        """AI分析用のプロンプトを構築"""
        
        prompt_parts = [
            "あなたはSEOの専門家です。以下の順位変動データを分析し、トレンドと改善提案を提供してください。",
            "",
            "## 順位下落データ",
            ""
        ]
        
        # 下落キーワード
        if dropped_keywords:
            prompt_parts.append(f"### 順位下落キーワード（{len(dropped_keywords)}件）")
            for i, kw in enumerate(dropped_keywords[:20], 1):  # 最大20件まで
                keyword = kw['keyword']
                prev = kw['previous_rank']
                curr = kw['current_rank']
                drop = curr - prev
                prompt_parts.append(f"{i}. 「{keyword}」: {prev}位 → {curr}位 (▼{drop})")
                
                # 競合情報
                competitors = kw.get('competitors_above', [])
                if competitors:
                    prompt_parts.append(f"   上位競合: {', '.join([c['url'] for c in competitors[:2]])}")
            
            prompt_parts.append("")
        
        # 圏外落ち
        if out_of_ranking_keywords:
            prompt_parts.append(f"### 圏外落ちキーワード（{len(out_of_ranking_keywords)}件）")
            for i, kw in enumerate(out_of_ranking_keywords[:20], 1):
                keyword = kw['keyword']
                prev = kw['previous_rank']
                prompt_parts.append(f"{i}. 「{keyword}」: {prev}位 → 圏外")
            
            prompt_parts.append("")
        
        # 履歴データがあれば追加
        if historical_data:
            prompt_parts.append("## 過去の順位履歴")
            prompt_parts.append("（省略: 詳細データあり）")
            prompt_parts.append("")
        
        # 分析依頼
        prompt_parts.extend([
            "## 分析依頼",
            "",
            "以下の形式で分析結果を提供してください：",
            "",
            "### 1. 全体サマリー",
            "- 今回の順位変動の全体的な傾向（2-3文で簡潔に）",
            "",
            "### 2. トレンド分析",
            "- キーワードのパターンや共通点",
            "- 業界やジャンルごとの傾向",
            "- 季節性やアルゴリズム変動の可能性",
            "",
            "### 3. 改善提案",
            "- 優先的に対応すべき施策（3-5個）",
            "- 具体的なアクションプラン",
            "",
            "### 4. 優先キーワード",
            "- 最も緊急に対応すべきキーワード（5個まで）",
            "",
            "回答は日本語で、実務的かつ具体的にお願いします。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """AI応答をパースして構造化"""
        
        # セクション分割
        sections = {
            'summary': '',
            'trends': '',
            'recommendations': '',
            'priority_keywords': []
        }
        
        lines = response_text.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # セクションの判定
            if '全体サマリー' in line or 'サマリー' in line:
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'summary'
                current_content = []
            elif 'トレンド分析' in line or 'トレンド' in line:
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'trends'
                current_content = []
            elif '改善提案' in line or '提案' in line:
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'recommendations'
                current_content = []
            elif '優先キーワード' in line or '優先' in line:
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'priority_keywords'
                current_content = []
            else:
                # 内容を追加
                if current_section and line.strip():
                    current_content.append(line)
        
        # 最後のセクションを追加
        if current_section and current_content:
            if current_section == 'priority_keywords':
                # キーワードリストを抽出
                keywords = []
                for line in current_content:
                    # 「キーワード名」や - キーワード名 の形式を抽出
                    clean_line = line.strip('- •*「」')
                    if clean_line and len(clean_line) < 100:
                        keywords.append(clean_line)
                sections[current_section] = keywords[:5]
            else:
                sections[current_section] = '\n'.join(current_content).strip()
        
        # セクションが空の場合はデフォルト値
        if not sections['summary']:
            sections['summary'] = '分析データを確認してください。'
        if not sections['trends']:
            sections['trends'] = 'トレンド情報が不十分です。'
        if not sections['recommendations']:
            sections['recommendations'] = '継続的なモニタリングを推奨します。'
        
        return sections
    
    def analyze_single_keyword(
        self,
        keyword: str,
        current_rank: Optional[int],
        previous_rank: int,
        competitors_above: List[Dict[str, Any]]
    ) -> str:
        """
        個別キーワードの詳細分析
        
        Args:
            keyword: キーワード
            current_rank: 現在順位
            previous_rank: 前回順位
            competitors_above: 上位競合情報
            
        Returns:
            分析結果テキスト
        """
        prompt = f"""
SEOキーワード「{keyword}」の順位が {previous_rank}位 から {current_rank or '圏外'}位 に変動しました。

上位競合:
{self._format_competitors(competitors_above)}

この順位変動の考えられる原因と、具体的な改善アクションを2-3文で提案してください。
"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"[ERROR] キーワード分析に失敗: {e}")
            return "分析に失敗しました。"
    
    def _format_competitors(self, competitors: List[Dict[str, Any]]) -> str:
        """競合情報をフォーマット"""
        if not competitors:
            return "情報なし"
        
        lines = []
        for comp in competitors:
            rank = comp.get('rank', '?')
            url = comp.get('url', 'N/A')
            lines.append(f"- {rank}位: {url}")
        
        return "\n".join(lines)
    
    def understand_user_intent(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        ユーザーのメッセージから意図を理解
        
        Args:
            user_message: ユーザーのメッセージ
            conversation_history: 会話履歴（オプション）
            
        Returns:
            {
                'intent': str,  # 'rank_check', 'analyze', 'status', 'question', 'greeting', 'unknown'
                'confidence': float,  # 信頼度 0.0-1.0
                'parameters': dict,  # 抽出されたパラメータ
                'response_suggestion': str  # 応答の提案
            }
        """
        # 会話履歴を含めたプロンプトを構築
        prompt_parts = [
            "あなたはSEO順位チェックボットのアシスタントです。",
            "ユーザーのメッセージから意図を理解し、JSON形式で応答してください。",
            "",
            "利用可能な機能:",
            "1. rank_check: 順位チェックを実行",
            "2. analyze: 競合分析を実行（キーワードとURLが必要）",
            "3. internal_links: 内部リンク候補を提案（キーワードが必要）",
            "4. status: 現在の設定を確認",
            "5. question: SEOに関する質問への回答",
            "6. greeting: 挨拶やチャット",
            "",
            "ユーザーメッセージ:",
            f"\"{user_message}\"",
            "",
            "以下のJSON形式で応答してください:",
            "{",
            "  \"intent\": \"<intent_type>\",",
            "  \"confidence\": <0.0-1.0>,",
            "  \"parameters\": {",
            "    \"keyword\": \"<キーワード（あれば）>\",",
            "    \"url\": \"<URL（あれば）>\",",
            "    \"limit\": <件数（あれば）>",
            "  },",
            "  \"response_suggestion\": \"<自然な日本語応答>\"",
            "}",
            "",
            "例:",
            "「順位をチェックして」 → intent: rank_check",
            "「中古車買取というキーワードの競合を調べて」 → intent: analyze, parameters.keyword: 中古車買取",
            "「設定を見せて」 → intent: status",
            "「ロレックス デイトナの内部リンク候補を教えて」 → intent: internal_links, parameters.keyword: ロレックス デイトナ",

            "「SEOって何？」 → intent: question"
        ]
        
        # 会話履歴があれば追加
        if conversation_history:
            prompt_parts.insert(7, "\n会話履歴:")
            for msg in conversation_history[-3:]:  # 直近3件のみ
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                prompt_parts.insert(8, f"{role}: {content}")
            prompt_parts.insert(8, "")
        
        prompt = "\n".join(prompt_parts)
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # JSONを抽出（マークダウンコードブロックの場合も対応）
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # JSONをパース
            intent_data = json.loads(response_text)
            
            # デフォルト値を設定
            intent_data.setdefault('intent', 'unknown')
            intent_data.setdefault('confidence', 0.5)
            intent_data.setdefault('parameters', {})
            intent_data.setdefault('response_suggestion', 'どのようなお手伝いができますか？')
            
            return intent_data
            
        except Exception as e:
            print(f"[ERROR] Intent understanding failed: {e}")
            # フォールバック：簡単なキーワードマッチング
            return self._fallback_intent_detection(user_message)
    
    def _fallback_intent_detection(self, user_message: str) -> Dict[str, Any]:
        """フォールバックの意図検出（キーワードベース）"""
        message_lower = user_message.lower()
        
        # 順位チェック
        if any(word in message_lower for word in ['順位', 'チェック', 'ランク', '確認', '調べて']):
            if any(word in message_lower for word in ['競合', '分析', 'analyze']):
                return {
                    'intent': 'analyze',
                    'confidence': 0.7,
                    'parameters': {},
                    'response_suggestion': '競合分析を実行します。キーワードとURLを教えてください。'
                }
            return {
                'intent': 'rank_check',
                'confidence': 0.8,
                'parameters': {},
                'response_suggestion': '順位チェックを開始します！'
            }
        
        # 設定確認
        if any(word in message_lower for word in ['設定', 'ステータス', 'status', '状態']):
            return {
                'intent': 'status',
                'confidence': 0.9,
                'parameters': {},
                'response_suggestion': '現在の設定を表示します。'
            }
        # 内部リンク候補
        if any(word in message_lower for word in ['内部リンク', 'リンク候補', 'リンク', '内リン', '設置']):
            return {
                'intent': 'internal_links',
                'confidence': 0.8,
                'parameters': {},
                'response_suggestion': '内部リンク候補を提案します。対策キーワードを教えてください。'
            }
        
        
        # 挨拶
        if any(word in message_lower for word in ['こんにちは', 'hello', 'hi', 'おはよう', 'こんばんは']):
            return {
                'intent': 'greeting',
                'confidence': 0.9,
                'parameters': {},
                'response_suggestion': 'こんにちは！SEO順位チェックのお手伝いをします。'
            }
        
        # ヘルプ
        if any(word in message_lower for word in ['ヘルプ', 'help', '使い方', '機能', 'できる']):
            return {
                'intent': 'help',
                'confidence': 0.9,
                'parameters': {},
                'response_suggestion': '使い方を説明します。'
            }
        
        # 不明
        return {
            'intent': 'unknown',
            'confidence': 0.3,
            'parameters': {},
            'response_suggestion': '申し訳ありませんが、理解できませんでした。「順位チェック」「競合分析」「設定確認」などができます。'
        }
    
    def chat(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        自然な会話形式でユーザーと対話
        
        Args:
            user_message: ユーザーのメッセージ
            context: コンテキスト情報（ボットの状態など）
            conversation_history: 会話履歴
            
        Returns:
            AIの応答テキスト
        """
        prompt_parts = [
            "あなたはSEO順位チェックボットのAIアシスタントです。",
            "ユーザーと自然な日本語で会話してください。",
            "",
            "ボットの機能:",
            "- データベースに保存された順位情報の分析",
            "- 競合サイトの分析",
            "- 順位変動のトレンド分析",
            "- SEO改善提案（知識ベース）",
            "",
            "【重要な注意事項】",
            "- ウェブ検索は使用しません",
            "- データベースに保存された情報のみを使用します",
            "- ユーザーが「ジャンル」と聞いた場合は、データベースに登録されているキーワードのジャンル分類のことです",
            "- 対象ドメインのビジネスジャンルを推測しないでください",
            "",
        ]
        
        # コンテキスト情報を追加
        if context:
            # デバッグログ
            print(f"[DEBUG AI] Context keys: {context.keys()}")
            if 'genres' in context:
                print(f"[DEBUG AI] Genres in context: {context['genres']}")
            
            prompt_parts.append("【データベース情報】")
            if context.get('target_domain'):
                prompt_parts.append(f"- 対象ドメイン: {context['target_domain']}")
            if context.get('keywords_count'):
                prompt_parts.append(f"- 登録キーワード数: {context['keywords_count']}件")
            
            # ジャンル情報を追加
            if context.get('genres'):
                genres_list = context['genres']
                print(f"[DEBUG AI] Adding {len(genres_list)} genres to prompt")
                prompt_parts.append("")
                prompt_parts.append("=" * 50)
                prompt_parts.append("【重要: データベースに登録されているジャンル情報】")
                prompt_parts.append(f"登録ジャンル数: {len(genres_list)}種類")
                prompt_parts.append("")
                prompt_parts.append("ジャンル一覧:")
                for i, genre in enumerate(genres_list, 1):
                    prompt_parts.append(f"  {i}. {genre}")
                prompt_parts.append("")
                prompt_parts.append("※ユーザーが「ジャンル」について質問した場合は、")
                prompt_parts.append("  上記のジャンル一覧を必ず参照して回答してください")
                prompt_parts.append("=" * 50)
            
            # キーワード情報を追加（ユーザーがキーワードについて質問している場合）
            if context.get('all_keywords'):
                keywords_data = context['all_keywords']
                
                # ジャンル別にキーワードを整理
                genre_keywords = {}
                for kw in keywords_data:
                    genre = kw.get('genre') or '未分類'
                    if genre not in genre_keywords:
                        genre_keywords[genre] = []
                    genre_keywords[genre].append(kw['keyword'])
                
                # 特定のジャンルについて聞かれている場合は、そのジャンルのキーワードを詳細に表示
                user_message_lower = user_message.lower()
                specific_genre_found = False
                for genre in context.get('genres', []):
                    if genre in user_message or genre.lower() in user_message_lower:
                        if genre in genre_keywords:
                            prompt_parts.append("")
                            prompt_parts.append("=" * 50)
                            prompt_parts.append(f"【{genre}ジャンルのキーワード一覧（全{len(genre_keywords[genre])}件）】")
                            prompt_parts.append("※これらのキーワードは確実にデータベースに存在します")
                            prompt_parts.append("")
                            for i, kw in enumerate(genre_keywords[genre], 1):
                                prompt_parts.append(f"{i}. {kw}")
                            prompt_parts.append("=" * 50)
                            prompt_parts.append("")
                            prompt_parts.append(f"【重要】ユーザーが「{genre}」のキーワードについて質問しています。")
                            prompt_parts.append("上記のキーワード一覧を必ず参照して、具体的なキーワード名を回答してください。")
                            specific_genre_found = True
                            break
                
                if not specific_genre_found:
                    # 特定ジャンルが指定されていない場合は、サマリーを表示
                    prompt_parts.append("\n【ジャンル別キーワード数】")
                    for genre in sorted(genre_keywords.keys()):
                        count = len(genre_keywords[genre])
                        prompt_parts.append(f"- {genre}: {count}件")
            
            prompt_parts.append("")
        
        # 会話履歴を追加
        if conversation_history:
            prompt_parts.append("会話履歴:")
            for msg in conversation_history[-5:]:  # 直近5件
                role = "ユーザー" if msg.get('role') == 'user' else "AI"
                prompt_parts.append(f"{role}: {msg.get('content', '')}")
            prompt_parts.append("")
        
        # ジャンル関連の質問の場合は明示的に指示
        if 'ジャンル' in user_message or 'genre' in user_message.lower():
            prompt_parts.append("")
            prompt_parts.append("【この質問への回答方法】")
            prompt_parts.append("ユーザーはデータベースに登録されているジャンルについて質問しています。")
            prompt_parts.append("上記の「データベースに登録されているジャンル情報」セクションを必ず参照して、")
            prompt_parts.append("具体的なジャンル名とその数を回答してください。")
            prompt_parts.append("")
        
        prompt_parts.extend([
            f"ユーザー: {user_message}",
            "",
            "AI: "
        ])
        
        prompt = "\n".join(prompt_parts)
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"[ERROR] Chat failed: {e}")
            return "申し訳ありません。エラーが発生しました。もう一度お試しください。"
    def chat_with_tools(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        データベース情報を基にした会話
        データベースに保存された順位情報のみを使用
        
        Args:
            user_message: ユーザーのメッセージ
            context: コンテキスト情報
            conversation_history: 会話履歴
            
        Returns:
            AIの応答テキスト
        """
        # システムプロンプト
        system_parts = [
            "あなたはSEO順位チェックボットのAIアシスタントです。",
            "ユーザーと自然な日本語で会話し、データベースに保存された情報を基に質問に答えてください。",
            "",
            "【あなたの能力】",
            "✓ データベースに保存された順位情報の分析",
            "✓ SEOに関する専門知識（2026年2月時点の知識）",
            "✓ データの集計・統計計算・トレンド分析",
            "",
            "【あなたができないこと】",
            "✗ リアルタイムのウェブ検索",
            "✗ 外部サイトへのアクセス",
            "✗ データベースに保存されていない情報の取得",
            "",
            "【重要な注意事項】",
            "- ユーザーが「ジャンル」と聞いた場合は、データベースに登録されているキーワードのジャンル分類のことです",
            "- 対象ドメインのビジネスジャンルを推測しないでください",
            "- 提供されたデータベース情報のみを使用してください",
            "",
            "【データソース】",
            "- データベースに保存されたキーワード・ジャンル情報",
            "- 過去の順位履歴データ",
            "- 競合分析結果",
            "",
        ]
        
        # コンテキスト情報を追加
        if context:
            system_parts.append("【データベース情報】")
            if context.get('target_domain'):
                system_parts.append(f"- 対象ドメイン: {context['target_domain']}")
            if context.get('keywords_count'):
                system_parts.append(f"- 登録キーワード数: {context['keywords_count']}件")
            
            # ジャンル情報を追加
            if context.get('genres'):
                genres_list = context['genres']
                system_parts.append("")
                system_parts.append("=" * 50)
                system_parts.append("【重要: データベースに登録されているジャンル情報】")
                system_parts.append(f"登録ジャンル数: {len(genres_list)}種類")
                system_parts.append("")
                system_parts.append("ジャンル一覧:")
                for i, genre in enumerate(genres_list, 1):
                    system_parts.append(f"  {i}. {genre}")
                system_parts.append("")
                system_parts.append("※ユーザーが「ジャンル」について質問した場合は、")
                system_parts.append("  上記のジャンル一覧を必ず参照して回答してください")
                system_parts.append("=" * 50)
            
            # キーワード情報を追加
            if context.get('all_keywords'):
                keywords_data = context['all_keywords']
                
                # ジャンル別にキーワードを整理
                genre_keywords = {}
                for kw in keywords_data:
                    genre = kw.get('genre') or '未分類'
                    if genre not in genre_keywords:
                        genre_keywords[genre] = []
                    genre_keywords[genre].append(kw['keyword'])
                
                # 特定のジャンルについて聞かれている場合は、そのジャンルのキーワードを詳細に表示
                user_message_lower = user_message.lower()
                specific_genre_found = False
                for genre in context.get('genres', []):
                    if genre in user_message or genre.lower() in user_message_lower:
                        if genre in genre_keywords:
                            system_parts.append("")
                            system_parts.append("=" * 50)
                            system_parts.append(f"【{genre}ジャンルのキーワード一覧（全{len(genre_keywords[genre])}件）】")
                            system_parts.append("※これらのキーワードは確実にデータベースに存在します")
                            system_parts.append("")
                            for i, kw in enumerate(genre_keywords[genre], 1):
                                system_parts.append(f"{i}. {kw}")
                            system_parts.append("=" * 50)
                            system_parts.append("")
                            system_parts.append(f"【重要】ユーザーが「{genre}」のキーワードについて質問しています。")
                            system_parts.append("上記のキーワード一覧を必ず参照して、具体的なキーワード名を回答してください。")
                            specific_genre_found = True
                            break
                
                if not specific_genre_found:
                    # 特定ジャンルが指定されていない場合は、サマリーを表示
                    system_parts.append("\n【ジャンル別キーワード数】")
                    for genre in sorted(genre_keywords.keys()):
                        count = len(genre_keywords[genre])
                        system_parts.append(f"- {genre}: {count}件")
            
            system_parts.append("")
        
        # 会話履歴を追加
        if conversation_history:
            system_parts.append("【会話履歴】")
            for msg in conversation_history[-5:]:  # 直近5件
                role = "ユーザー" if msg.get('role') == 'user' else "AI"
                system_parts.append(f"{role}: {msg.get('content', '')}")
            system_parts.append("")
        
        # ジャンル関連の質問の場合は明示的に指示
        if 'ジャンル' in user_message or 'genre' in user_message.lower():
            system_parts.append("")
            system_parts.append("【この質問への回答方法】")
            system_parts.append("ユーザーはデータベースに登録されているジャンルについて質問しています。")
            system_parts.append("上記の「データベースに登録されているジャンル情報」セクションを必ず参照して、")
            system_parts.append("具体的なジャンル名とその数を回答してください。")
            system_parts.append("")
        
        system_parts.extend([
            "【重要な指示】",
            "1. データベースに保存された情報のみを使用してください",
            "   - キーワード、ジャンル、順位履歴、競合情報はすべてデータベースから取得",
            "   - 上記に提供されたジャンル情報は確実にデータベースに存在します",
            "   - ウェブ検索や外部情報の取得は行わない",
            "",
            "2. SEOに関する質問には、あなたの知識ベースで答えてください",
            "   - 順位データの傾向分析",
            "   - SEOベストプラクティス（2026年2月時点の知識）",
            "   - コンテンツ最適化のアドバイス",
            "",
            "3. データベースにない情報を聞かれた場合:",
            "   「申し訳ありませんが、その情報はデータベースにありません。",
            "   データベースに保存されているキーワードの順位情報や、SEOの一般的な知識についてお答えできます。」",
            "   と説明してください",
            "",
            "4. 自然で親しみやすい日本語で会話してください",
            "",
            f"ユーザー: {user_message}",
            "",
            "AI: "
        ])
        
        prompt = "\n".join(system_parts)
        
        try:
            # データベース情報を基に応答生成
            response = self.model.generate_content(prompt)
            
            # 応答テキストを取得
            response_text = response.text.strip()
            
            return response_text
            
        except Exception as e:
            print(f"[ERROR] Chat with tools failed: {e}")
            import traceback
            traceback.print_exc()
            
            # フォールバック: 基本的な応答
            return (
                "申し訳ありません。エラーが発生しました。\n\n"
                "以下のようなことができます：\n"
                "• 「順位をチェックして」→ 順位チェック実行\n"
                "• 「○○について教えて」→ 情報検索\n"
                "• SEOに関する質問にも答えます！"
            )
    
    def find_related_keywords(
        self,
        target_keyword: str,
        all_keywords: List[Dict[str, Any]],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        対策キーワードに関連性の高いキーワードを検索（高精度版）
        
        Phase 2実装:
        - 同一エンティティ優先
        - Intent遷移スコア
        - カニバリ回避
        
        Args:
            target_keyword: 対策キーワード
            all_keywords: データベースの全キーワード情報
            limit: 返す件数（デフォルト: 10）
            
        Returns:
            関連キーワードのリスト
            [
                {
                    'keyword': str,
                    'url': str,
                    'genre': str,
                    'score': int,  # 関連性スコア (0-100)
                    'reason': str,  # 関連性の理由
                    'relation_type': str,  # 関係タイプ（例: 定義→詳細）
                    'anchor_suggestion': str  # アンカーテキスト提案
                },
                ...
            ]
        """
        if not all_keywords:
            return []
        
        # 対策キーワードの情報を取得
        target_info = next(
            (kw for kw in all_keywords if kw['keyword'] == target_keyword),
            None
        )
        
        if not target_info:
            print(f"[WARN] 対策キーワードがDBに見つかりません: {target_keyword}")
            return []
        
        target_entity = target_info.get('primary_entity')
        target_intent = target_info.get('intent_label', '一般')
        target_page_type = target_info.get('page_type', '記事')
        target_genre = target_info.get('genre')
        
        print(f"[INFO] ========== Phase 2: 内部リンク候補生成開始 ==========")
        print(f"[INFO] 対策KW: {target_keyword}")
        print(f"[INFO] Entity: {target_entity or 'NULL'}")
        print(f"[INFO] Intent: {target_intent}")
        print(f"[INFO] PageType: {target_page_type}")
        print(f"[INFO] Genre: {target_genre or 'NULL'}")
        
        # 候補生成（Stage 1: Recall）
        candidates = self._generate_candidates(
            target_keyword,
            target_entity,
            target_intent,
            target_page_type,
            all_keywords,
            target_genre
        )
        
        print(f"[INFO] 候補生成: {len(candidates)}件")
        
        if not candidates:
            print(f"[WARN] 候補が0件です。以下を確認してください:")
            print(f"       1. 対策キーワードのEntity/Intent/Genreが正しく設定されているか")
            print(f"       2. 他のキーワードにURLが設定されているか")
            print(f"       3. 除外理由の内訳を確認")
            return []
        
        # candidate_keywordsとして参照するための変数
        candidate_keywords = candidates
        
        # トップ5候補を表示
        print(f"[INFO] トップ5候補:")
        for i, cand in enumerate(candidates[:5], 1):
            print(f"       {i}. {cand['keyword']} (スコア={cand['recall_score']:.1f})")
        
        # AIでウェブ検索を使って検索意図を深く分析
        enable_web_search = os.getenv('ENABLE_WEB_SEARCH', 'false').lower() == 'true'
        
        if enable_web_search:
            search_intent_analysis = f"""
「{target_keyword}」について、Google検索を使って以下を調査してください:

1. このキーワードで上位表示されている記事のタイトルや内容から、ユーザーが何を求めているか
2. 関連する具体的なキーワード（モデル名、ブランド名など）
3. ユーザーの検索意図（情報収集、比較検討、購入検討など）

調査結果を基に、ユーザーの検索意図を1-2文で簡潔に説明してください。

例: 「エルメス バッグ 種類」→「ユーザーはバーキン、ケリー、ガーデンパーティーなどの具体的なモデル名とその特徴、価格を知りたい」
"""
        else:
            search_intent_analysis = f"""
あなたは検索意図の専門家です。「{target_keyword}」というキーワードで検索するユーザーの検索意図を深く分析してください。

【分析項目】
1. ユーザーの目的: このキーワードで検索する人は何を知りたいのか？
2. 求めている情報: どんな具体的な情報を期待しているか？
3. 次の行動: この情報を得た後、どんな行動を取る可能性があるか？

検索意図を1-2文で簡潔に説明してください。

例: 「エルメス バッグ 種類」の場合
「ユーザーはエルメスのバッグにどんなモデル（バーキン、ケリー、ガーデンパーティーなど）があるか具体的に知りたい。各モデルの特徴や価格帯も比較したいと考えている。」
"""
        
        try:
            if enable_web_search:
                print(f"[INFO] ウェブ検索で検索意図を分析中: {target_keyword}")
            else:
                print(f"[INFO] AIで検索意図を分析中: {target_keyword}")
            
            intent_response = self.model.generate_content(search_intent_analysis)
            search_intent = intent_response.text.strip()
            print(f"[INFO] 検索意図: {search_intent}")
        except Exception as e:
            print(f"[WARN] 検索意図分析に失敗: {e}")
            # フォールバック: キーワードベースの簡易分析
            if "種類" in target_keyword or "モデル" in target_keyword:
                search_intent = "ユーザーは具体的なモデル名や種類を知りたい"
            elif "買取" in target_keyword or "相場" in target_keyword or "価格" in target_keyword:
                search_intent = "ユーザーは買取価格や相場を知りたい"
            elif "見分け方" in target_keyword or "偽物" in target_keyword:
                search_intent = "ユーザーは真贋の見分け方を知りたい"
            else:
                search_intent = "ユーザーは一般的な情報を知りたい"
        
        # プロンプトを構築
        prompt_parts = [
            f"タスク: 「{target_keyword}」に関連性が高いキーワードを候補リストから選定してJSON配列で返してください。",
            "",
            f"【対策キーワード情報】",
            f"- キーワード: {target_keyword}",
            f"- Entity: {target_entity or '不明'}",
            f"- Intent: {target_intent}",
            f"- ページタイプ: {target_page_type}",
            "",
            f"【検索意図】{search_intent}",
            "",
            "【選定ルール（優先度順）】",
            f"1. 「{target_keyword}」の検索意図に直接応えるキーワードを最優先",
            f"2. 「{target_keyword}」に含まれる固有名詞（ブランド名・商品名）が一致するもの",
            "3. Intent遷移が自然なもの（定義→詳細、種類→個別など）",
            "4. カニバリを避ける（Intent同一 & Entity同一は既に除外済み）",
            "",
            "【例】",
            "「エルメス バッグ 種類」→ 種類を知りたい検索意図",
            "  ◯◯ エルメス バーキン、エルメス ケリー（具体的なモデル = 種類の詳細）",
            "  ◯ エルメス バッグ 買取（関連情報）",
            "  ✕ エルメス ネクタイ（カテゴリが違う）",
            "  ✕✕ Dior バッグ（ブランドが違う）",
            "",
            "【候補キーワード一覧（スコア順）】",
            "※既にEntityマッチ & Intent遷移スコアで事前フィルタ済み",
            ""
        ]
        
        # 候補キーワードをリスト化（最大50件まで、スコア情報付き）
        print(f"[DEBUG] AIプロンプト生成: 候補数={len(candidate_keywords)}")
        
        # 候補が少ない場合は警告
        if len(candidate_keywords) < 5:
            print(f"[WARN] 候補が{len(candidate_keywords)}件しかありません")
            print(f"[WARN] AIによる選定結果も少なくなる可能性があります")
        
        for i, kw in enumerate(candidate_keywords[:50], 1):
            keyword = kw['keyword']
            genre = kw.get('genre') or '未分類'
            entity = kw.get('primary_entity') or '不明'
            intent = kw.get('intent_label', '一般')
            recall_score = kw.get('recall_score', 0)
            url = kw.get('url', 'URL未設定')
            rank = kw.get('current_rank')
            rank_str = f", 順位={rank}位" if rank else ""
            prompt_parts.append(
                f"{i}. 「{keyword}」 "
                f"(Entity={entity}, Intent={intent}, スコア={recall_score:.0f}{rank_str}, URL={url})"
            )
            
            # 最初の3件は詳細表示
            if i <= 3:
                print(f"[DEBUG] 候補#{i}: {keyword} (スコア={recall_score:.0f})")
        
        print(f"[DEBUG] プロンプトに含まれる候補キーワード数: {min(len(candidate_keywords), 50)}")
        
        prompt_parts.extend([
            "",
            "【タスク】",
            f"上記の候補リストから、「{target_keyword}」に最適な内部リンク候補を選定してください。",
            "",
            "【判定手順】",
            f"ステップ1: 「{target_keyword}」の検索意図を確認",
            f"  → {search_intent}",
            "",
            "ステップ2: 検索意図に直接応えるキーワードを選定",
            "  - 「種類」を知りたい → 具体的なモデル名",
            "  - 「買取」を知りたい → 相場・価格情報",
            "  - 「定義」を知りたい → 詳細・特徴情報",
            "",
            "ステップ3: 事前スコアと検索意図を組み合わせて最終判定",
            "  - 事前スコアが高い（70以上）→ EntityとIntentが適切",
            "  - 検索意図への適合度を追加評価",
            "",
            "【厳守事項】",
            "✓✓ 検索意図に直接応える情報を最優先（最終スコア90-100）",
            "✓✓ Entity一致 & Intent遷移が自然（最終スコア85-100）",
            "✓ 関連情報として有用（最終スコア75-89）",
            "✕ 検索意図から外れた情報は選ばない",
            "✕ 最終スコアが75未満のものは選ばない",
            "",
            f"【重要】出力件数について",
            f"- 検索意図に応える候補を1〜{limit}件選定",
            f"- 質を重視（関連性が低い場合は少ない件数でOK）",
            "",
            "【最重要】出力形式",
            "説明文は一切不要です。必ずJSON配列のみを出力してください。",
            "",
            "```json",
            "[",
            "  {",
            '    "keyword": "エルメス バーキン",',
            '    "score": 95,',
            '    "reason": "種類の1つ、具体的なモデル名（Intent遷移: 種類→個別）"',
            "  },",
            "  {",
            '    "keyword": "エルメス ケリー",',
            '    "score": 95,',
            '    "reason": "種類の1つ、具体的なモデル名（Intent遷移: 種類→個別）"',
            "  },",
            "  {",
            '    "keyword": "エルメス バッグ 買取相場",',
            '    "score": 80,',
            '    "reason": "関連情報、買取を検討するユーザーに有用"',
            "  }",
            "]",
            "```",
            "",
            f"上記の形式で、検索意図に応える候補を1〜{limit}件選定してJSON配列で返してください。",
            "説明文や前置きは一切不要です。JSON配列のみを出力してください。"
        ])
        
        prompt = "\n".join(prompt_parts)
        
        try:
            print(f"[INFO] AIによる関連キーワード検索を実行中...")
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            print(f"[DEBUG] AI応答の最初の500文字: {response_text[:500]}")
            
            # JSONを抽出
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            print(f"[DEBUG] 抽出されたJSON: {response_text[:300]}")
            
            # JSONをパース
            ai_results = json.loads(response_text)
            
            print(f"[DEBUG] パース結果: {type(ai_results)}, 件数: {len(ai_results) if isinstance(ai_results, list) else 'N/A'}")
            
            if not isinstance(ai_results, list):
                print(f"[WARN] AIの応答がリスト形式ではありません")
                return []
            
            # キーワード情報とマージ
            related_keywords = []
            for result in ai_results:
                keyword = result.get('keyword', '').strip()
                score = result.get('score', 0)
                reason = result.get('reason', '')
                
                # 元のキーワード情報を検索
                kw_info = next(
                    (kw for kw in all_keywords if kw['keyword'] == keyword),
                    None
                )
                
                if kw_info and kw_info.get('url'):
                    related_keywords.append({
                        'keyword': keyword,
                        'url': kw_info['url'],
                        'genre': kw_info.get('genre', '未分類'),
                        'score': score,
                        'reason': reason,
                        'current_rank': kw_info.get('current_rank')
                    })
            
            print(f"[INFO] {len(related_keywords)}件の関連キーワードを抽出しました")
            return related_keywords[:limit]
            
        except Exception as e:
            print(f"[ERROR] 関連キーワード検索に失敗: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _generate_candidates(
        self,
        target_keyword: str,
        target_entity: Optional[str],
        target_intent: str,
        target_page_type: str,
        all_keywords: List[Dict[str, Any]],
        target_genre: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Phase 2改善版: 候補生成（Recall Stage）
        
        改善ポイント:
        1. 同一エンティティを最優先
        2. Intent遷移の自然さを考慮
        3. カニバリ回避（Intent同一 & Entity同一は除外）
        4. Entityフォールバック: NULL時はジャンル一致で代替
        
        Args:
            target_keyword: 対策キーワード
            target_entity: 対策キーワードのprimary_entity
            target_intent: 対策キーワードのIntent
            target_page_type: 対策キーワードのページタイプ
            all_keywords: データベースの全キーワード情報
            target_genre: 対策キーワードのジャンル（オプション）
            
        Returns:
            候補キーワードのリスト（フィルタ済み）
        """
        candidates = []
        excluded_reasons = {
            'self': 0,
            'no_url': 0,
            'cannibalization': 0,
            'low_score': 0
        }
        
        print(f"[DEBUG] 候補生成開始: 全{len(all_keywords)}件から候補を抽出")
        print(f"[DEBUG] ターゲット: Entity={target_entity}, Intent={target_intent}, Genre={target_genre}")
        
        for kw in all_keywords:
            # 自分自身を除外
            if kw['keyword'] == target_keyword:
                excluded_reasons['self'] += 1
                continue
            
            # URLがないものは除外
            if not kw.get('url'):
                excluded_reasons['no_url'] += 1
                continue
            
            candidate_entity = kw.get('primary_entity')
            candidate_intent = kw.get('intent_label', '一般')
            candidate_page_type = kw.get('page_type', '記事')
            candidate_genre = kw.get('genre')
            
            # カニバリ回避ルール: Intent同一 & Entity同一 → 除外
            if self._is_cannibalization(
                target_entity, target_intent,
                candidate_entity, candidate_intent
            ):
                excluded_reasons['cannibalization'] += 1
                if excluded_reasons['cannibalization'] <= 3:
                    print(f"[DEBUG] カニバリ除外: {kw['keyword']} (Intent={candidate_intent}, Entity={candidate_entity})")
                continue
            
            # 同一エンティティ優先
            entity_match_score = self._calculate_entity_match_score(
                target_entity, candidate_entity
            )
            
            # Entityフォールバック: EntityがNULLの場合はジャンル一致で代替
            genre_match_score = 0
            if entity_match_score == 0 and target_genre and candidate_genre:
                if target_genre == candidate_genre:
                    genre_match_score = 40  # ジャンル一致は中程度のスコア
            
            # Intent遷移スコア
            intent_transition_score = self._calculate_intent_transition_score(
                target_intent, candidate_intent
            )
            
            # キーワードテキスト重複スコア（Entityが欠損している場合の補完）
            keyword_text_score = self._calculate_keyword_text_score(
                target_keyword, kw['keyword']
            )

            # 総合スコア（Entityがない場合はジャンル+テキストで補完）
            if entity_match_score > 0:
                total_score = (
                    entity_match_score * 0.50
                    + intent_transition_score * 0.35
                    + keyword_text_score * 0.15
                )
            else:
                total_score = (
                    genre_match_score * 0.30
                    + intent_transition_score * 0.40
                    + keyword_text_score * 0.30
                )

            # 検索順位によるブースト（実績あるページを優先）
            rank_boost = self._calculate_rank_boost(kw)
            total_score += rank_boost

            # 閾値フィルタ（スコア20以上に緩和）
            if total_score >= 20:
                candidates.append({
                    **kw,
                    'recall_score': total_score,
                    'entity_match_score': entity_match_score,
                    'genre_match_score': genre_match_score,
                    'intent_transition_score': intent_transition_score,
                    'keyword_text_score': keyword_text_score,
                    'rank_boost': rank_boost
                })
                
                # トップ10のみ詳細ログ
                if len(candidates) <= 10:
                    print(f"[DEBUG] 候補追加 #{len(candidates)}: {kw['keyword']}")
                    print(f"        Entity={candidate_entity} (スコア={entity_match_score})")
                    if genre_match_score > 0:
                        print(f"        Genre={candidate_genre} (スコア={genre_match_score})")
                    print(f"        Intent={candidate_intent} (スコア={intent_transition_score})")
                    print(f"        TextOverlap={keyword_text_score}, RankBoost={rank_boost}")
                    print(f"        総合スコア={total_score:.1f}")
            else:
                excluded_reasons['low_score'] += 1
        
        # スコア順にソート
        candidates.sort(key=lambda x: x['recall_score'], reverse=True)

        # URL重複排除: 同一URLで複数キーワードがある場合、最高スコアのみ残す
        seen_urls: Dict[str, int] = {}  # url -> index in deduped list
        deduped: List[Dict[str, Any]] = []
        for cand in candidates:
            url = cand.get('url', '')
            if not url:
                deduped.append(cand)
                continue
            if url not in seen_urls:
                seen_urls[url] = len(deduped)
                deduped.append(cand)
            # else: 同URLの低スコア候補は破棄（既にソート済みなので先着が最高スコア）
        removed = len(candidates) - len(deduped)
        if removed > 0:
            print(f"[DEBUG] URL重複排除: {removed}件削除")
        candidates = deduped

        print(f"[DEBUG] 候補生成完了: {len(candidates)}件")
        print(f"[DEBUG] 除外内訳:")
        print(f"        自分自身: {excluded_reasons['self']}件")
        print(f"        URL無し: {excluded_reasons['no_url']}件")
        print(f"        カニバリ: {excluded_reasons['cannibalization']}件")
        print(f"        低スコア: {excluded_reasons['low_score']}件")
        
        if candidates:
            print(f"[DEBUG] トップ候補: {candidates[0]['keyword']} (スコア={candidates[0]['recall_score']:.1f})")
            print(f"[DEBUG] スコア分布: 最高={candidates[0]['recall_score']:.1f}, "
                  f"最低={candidates[-1]['recall_score']:.1f}")
        else:
            print(f"[WARN] 候補が0件です。フィルタ条件を見直す必要があります。")
        
        return candidates
    
    def _is_cannibalization(
        self,
        target_entity: Optional[str],
        target_intent: str,
        candidate_entity: Optional[str],
        candidate_intent: str
    ) -> bool:
        """
        カニバリ判定（改善版）: Intent同一 & Entity完全一致 → True（除外）
        
        重要: 部分一致はカニバリとしない
        - 「白州」と「白州18年」→ カニバリではない（異なる商品）
        - 「白州買取」と「白州買取」→ カニバリ（完全一致）
        
        Args:
            target_entity: 対策キーワードのEntity
            target_intent: 対策キーワードのIntent
            candidate_entity: 候補キーワードのEntity
            candidate_intent: 候補キーワードのIntent
            
        Returns:
            True: カニバリの可能性あり（除外すべき）
            False: カニバリなし（候補として有効）
        """
        # Intentが同一でない場合はカニバリなし
        if target_intent != candidate_intent:
            return False
        
        # Entityが両方NULLの場合はカニバリとしない（ジャンルで判定）
        if not target_entity or not candidate_entity:
            return False
        
        # Entity完全一致の場合のみカニバリ
        if target_entity == candidate_entity:
            return True
        
        # 部分一致はカニバリとしない
        # 例: 「白州」と「白州18年」は異なる商品なので候補として有効
        return False
    
    def _calculate_keyword_text_score(
        self,
        target_keyword: str,
        candidate_keyword: str
    ) -> int:
        """
        キーワードテキスト重複スコア計算

        Entityがない場合でもキーワード文字列の共通トークンで関連性を評価する。

        スコアリング:
        - Overlap係数（短い方を分母）: 部分包含に強い
        - Jaccard係数: 純粋な重複度
        - 両者の最大値 × 70 を最大スコアとする

        Returns:
            スコア (0-70)
        """
        target_tokens = set(target_keyword.split())
        candidate_tokens = set(candidate_keyword.split())

        if not target_tokens or not candidate_tokens:
            return 0

        common = target_tokens & candidate_tokens
        if not common:
            return 0

        jaccard = len(common) / len(target_tokens | candidate_tokens)
        overlap = len(common) / min(len(target_tokens), len(candidate_tokens))
        score = max(jaccard, overlap * 0.8) * 70
        return int(score)

    def _calculate_rank_boost(self, kw_info: Dict[str, Any]) -> int:
        """
        検索順位によるスコアブースト

        SEO的に評価が高いページ（上位表示中）を優先する。

        Returns:
            ブースト値 (0-15)
        """
        rank = kw_info.get('current_rank')
        if not rank:
            return 0
        try:
            rank = int(rank)
        except (TypeError, ValueError):
            return 0
        if rank <= 3:
            return 15
        elif rank <= 10:
            return 10
        elif rank <= 20:
            return 5
        return 0

    def _calculate_entity_match_score(
        self,
        target_entity: Optional[str],
        candidate_entity: Optional[str]
    ) -> int:
        """
        エンティティマッチスコア計算（強化版）
        
        スコアリング:
        - 完全一致: 100点
        - 部分一致（どちらかが含まれる）: 85点
        - トークン一致（共通ワードあり）: 60点
        - 両方NULL: 0点（ジャンルで代替）
        - 一方がNULL: 0点（ジャンルで代替）
        - 不一致: 0点
        
        Args:
            target_entity: 対策キーワードのEntity
            candidate_entity: 候補キーワードのEntity
            
        Returns:
            スコア (0-100)
        """
        # EntityがNULLの場合は0点（後でジャンルスコアで補完）
        if not target_entity or not candidate_entity:
            return 0
        
        # 完全一致
        if target_entity == candidate_entity:
            return 100
        
        # 部分一致（どちらかが含まれる）
        # 例: 「白州」と「白州18年」、「ロレックス」と「ロレックス デイトナ」
        if target_entity in candidate_entity or candidate_entity in target_entity:
            return 85
        
        # トークン一致（共通の単語がある）
        # 例: 「エルメス バーキン」と「エルメス ケリー」
        target_tokens = set(target_entity.split())
        candidate_tokens = set(candidate_entity.split())
        common_tokens = target_tokens & candidate_tokens
        
        if common_tokens and len(common_tokens) > 0:
            # 共通トークンの割合でスコアを計算
            match_ratio = len(common_tokens) / max(len(target_tokens), len(candidate_tokens))
            return int(60 * match_ratio)
        
        # 不一致
        return 0
    
    def _calculate_intent_transition_score(
        self,
        target_intent: str,
        candidate_intent: str
    ) -> int:
        """
        Intent遷移スコア計算
        
        自然な意図の流れをスコアリング:
        - 定義 → 詳細・種類・特徴: 90点
        - 定義 → 買取・相場: 70点
        - 種類 → 個別モデル: 90点
        - 買取 → 相場・価格: 80点
        - その他: 50点
        
        Args:
            target_intent: 対策キーワードのIntent
            candidate_intent: 候補キーワードのIntent
            
        Returns:
            スコア (0-100)
        """
        # Intent遷移マッピング
        transitions = {
            # 定義系 → 詳細を知りたい
            ('定義・概要', '詳細・解説'): 90,
            ('定義・概要', '種類・分類'): 90,
            ('定義・概要', '特徴・ポイント'): 90,
            ('定義・概要', '買取・査定'): 70,
            ('定義・概要', '相場・価格'): 70,
            
            # 種類 → 個別モデルを知りたい
            ('種類・分類', '詳細・解説'): 90,
            ('種類・分類', '特徴・ポイント'): 85,
            ('種類・分類', '買取・査定'): 70,
            
            # 買取 → 相場を知りたい
            ('買取・査定', '相場・価格'): 80,
            ('買取・査定', '特徴・ポイント'): 70,
            
            # 相場 → 買取を検討
            ('相場・価格', '買取・査定'): 85,
            ('相場・価格', '特徴・ポイント'): 60,
            
            # 特徴 → 詳細を知りたい
            ('特徴・ポイント', '詳細・解説'): 80,
            ('特徴・ポイント', '買取・査定'): 75,
            ('特徴・ポイント', '相場・価格'): 70,
            
            # 詳細 → 買取検討
            ('詳細・解説', '買取・査定'): 75,
            ('詳細・解説', '相場・価格'): 70,
            ('詳細・解説', '特徴・ポイント'): 65,
        }
        
        # マッピングからスコアを取得
        key = (target_intent, candidate_intent)
        if key in transitions:
            return transitions[key]
        
        # 同一Intent（カニバリ回避で除外されているはずだが念のため）
        if target_intent == candidate_intent:
            return 30
        
        # その他の組み合わせ
        return 50
    
    