"""
SQLiteを使った順位履歴の保存・取得モジュール
"""
import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path


class RankingStorage:
    """順位履歴を管理するストレージ"""
    
    def __init__(self, db_path: str):
        """
        Args:
            db_path: SQLiteデータベースファイルのパス
        """
        self.db_path = db_path
        self._initialize_db()
    
    def _initialize_db(self):
        """データベースとテーブルを初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # keywords テーブル（キーワードとジャンル情報を保存）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                keyword TEXT PRIMARY KEY,
                genre TEXT,
                url TEXT,
                priority TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # rankings テーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rankings (
                keyword TEXT PRIMARY KEY,
                last_rank INTEGER,
                last_checked_at TEXT,
                last_url TEXT,
                FOREIGN KEY (keyword) REFERENCES keywords(keyword)
            )
        """)
        
        # competitors テーブル（競合情報保存用）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                url TEXT NOT NULL,
                rank INTEGER NOT NULL,
                checked_at TEXT NOT NULL,
                UNIQUE(keyword, url, checked_at),
                FOREIGN KEY (keyword) REFERENCES keywords(keyword)
            )
        """)
        
        # competitor_analysis テーブル（競合分析結果保存用）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitor_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                own_url TEXT NOT NULL,
                own_heading_count INTEGER,
                own_text_length INTEGER,
                own_image_count INTEGER,
                own_internal_link_count INTEGER,
                competitor_avg_headings REAL,
                competitor_avg_text_length REAL,
                competitor_avg_images REAL,
                competitor_avg_internal_links REAL,
                heading_diff REAL,
                text_length_diff REAL,
                image_diff REAL,
                internal_link_diff REAL,
                rank_at_analysis INTEGER,
                previous_rank INTEGER,
                checked_at TEXT NOT NULL,
                FOREIGN KEY (keyword) REFERENCES keywords(keyword)
            )
        """)
        
        # checked_atにインデックスを作成（検索高速化）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_competitors_keyword_checked_at 
            ON competitors(keyword, checked_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_competitor_analysis_keyword_checked_at 
            ON competitor_analysis(keyword, checked_at DESC)
        """)
        
        # genreにインデックスを作成（ジャンル別検索高速化）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_keywords_genre 
            ON keywords(genre)
        """)
        
        conn.commit()
        conn.close()
    
    def get_previous_rank(self, keyword: str) -> Optional[Dict[str, Any]]:
        """
        前回の順位情報を取得
        
        Args:
            keyword: キーワード
            
        Returns:
            前回情報の辞書（なければNone）
            {
                'keyword': str,
                'last_rank': int or None,
                'last_checked_at': str,
                'last_url': str or None
            }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT keyword, last_rank, last_checked_at, last_url FROM rankings WHERE keyword = ?",
            (keyword,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'keyword': row[0],
                'last_rank': row[1],
                'last_checked_at': row[2],
                'last_url': row[3]
            }
        
        return None
    
    def save_rank(
        self,
        keyword: str,
        rank: Optional[int],
        url: Optional[str],
        checked_at: Optional[str] = None
    ):
        """
        順位情報を保存（UPSERT）
        
        Args:
            keyword: キーワード
            rank: 順位（圏外の場合はNone）
            url: URL（圏外の場合はNone）
            checked_at: チェック日時（指定なしの場合は現在時刻）
        """
        if checked_at is None:
            checked_at = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO rankings (keyword, last_rank, last_checked_at, last_url)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(keyword) DO UPDATE SET
                last_rank = excluded.last_rank,
                last_checked_at = excluded.last_checked_at,
                last_url = excluded.last_url
        """, (keyword, rank, checked_at, url))
        
        conn.commit()
        conn.close()
    
    def get_all_rankings(self) -> list[Dict[str, Any]]:
        """
        全ての順位情報を取得
        
        Returns:
            順位情報のリスト
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT keyword, last_rank, last_checked_at, last_url FROM rankings")
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'keyword': row[0],
                'last_rank': row[1],
                'last_checked_at': row[2],
                'last_url': row[3]
            })
        
        return results
    
    def save_competitors(
        self,
        keyword: str,
        competitors: List[Dict[str, Any]],
        checked_at: Optional[str] = None
    ):
        """
        競合情報を保存
        
        Args:
            keyword: キーワード
            competitors: 競合情報のリスト [{'rank': int, 'url': str}, ...]
            checked_at: チェック日時（指定なしの場合は現在時刻）
        """
        if checked_at is None:
            checked_at = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for comp in competitors:
            try:
                cursor.execute("""
                    INSERT INTO competitors (keyword, url, rank, checked_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(keyword, url, checked_at) DO UPDATE SET
                        rank = excluded.rank
                """, (keyword, comp['url'], comp['rank'], checked_at))
            except Exception as e:
                print(f"[WARN] Failed to save competitor for '{keyword}': {e}")
                continue
        
        conn.commit()
        conn.close()
    
    def get_latest_competitors(
        self,
        keyword: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        最新の競合情報を取得
        
        Args:
            keyword: キーワード
            limit: 取得件数（デフォルト: 10）
            
        Returns:
            競合情報のリスト [{'url': str, 'rank': int, 'checked_at': str}, ...]
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT url, rank, checked_at
            FROM competitors
            WHERE keyword = ?
            ORDER BY checked_at DESC, rank ASC
            LIMIT ?
        """, (keyword, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'url': row[0],
                'rank': row[1],
                'checked_at': row[2]
            })
        
        return results
    
    def save_competitor_analysis(
        self,
        keyword: str,
        own_url: str,
        own_data: Dict[str, Any],
        competitor_avg: Dict[str, float],
        differences: Dict[str, float],
        rank_at_analysis: int,
        previous_rank: int,
        checked_at: Optional[str] = None
    ):
        """
        競合分析結果を保存
        
        Args:
            keyword: キーワード
            own_url: 自社URL
            own_data: 自社データ（heading_count, text_length, image_count, internal_link_count）
            competitor_avg: 競合平均値（headings, text_length, images, internal_links）
            differences: 差分（heading_diff, text_length_diff, image_diff, internal_link_diff）
            rank_at_analysis: 分析時の順位
            previous_rank: 前回順位
            checked_at: チェック日時（指定なしの場合は現在時刻）
        """
        if checked_at is None:
            checked_at = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO competitor_analysis (
                    keyword, own_url,
                    own_heading_count, own_text_length, own_image_count, own_internal_link_count,
                    competitor_avg_headings, competitor_avg_text_length, 
                    competitor_avg_images, competitor_avg_internal_links,
                    heading_diff, text_length_diff, image_diff, internal_link_diff,
                    rank_at_analysis, previous_rank, checked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                keyword, own_url,
                own_data.get('heading_count', 0),
                own_data.get('text_length', 0),
                own_data.get('image_count', 0),
                own_data.get('internal_link_count', 0),
                competitor_avg.get('headings', 0),
                competitor_avg.get('text_length', 0),
                competitor_avg.get('images', 0),
                competitor_avg.get('internal_links', 0),
                differences.get('heading_diff', 0),
                differences.get('text_length_diff', 0),
                differences.get('image_diff', 0),
                differences.get('internal_link_diff', 0),
                rank_at_analysis,
                previous_rank,
                checked_at
            ))
            
            conn.commit()
            print(f"[INFO] 競合分析結果を保存しました: {keyword}")
            
        except Exception as e:
            print(f"[ERROR] 競合分析結果の保存に失敗: {keyword} - {e}")
        finally:
            conn.close()
    
    def get_latest_competitor_analysis(
        self,
        keyword: str
    ) -> Optional[Dict[str, Any]]:
        """
        最新の競合分析結果を取得
        
        Args:
            keyword: キーワード
            
        Returns:
            競合分析結果の辞書（なければNone）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                keyword, own_url,
                own_heading_count, own_text_length, own_image_count, own_internal_link_count,
                competitor_avg_headings, competitor_avg_text_length,
                competitor_avg_images, competitor_avg_internal_links,
                heading_diff, text_length_diff, image_diff, internal_link_diff,
                rank_at_analysis, previous_rank, checked_at
            FROM competitor_analysis
            WHERE keyword = ?
            ORDER BY checked_at DESC
            LIMIT 1
        """, (keyword,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'keyword': row[0],
            'own_url': row[1],
            'own': {
                'heading_count': row[2],
                'text_length': row[3],
                'image_count': row[4],
                'internal_link_count': row[5]
            },
            'competitor_avg': {
                'headings': row[6],
                'text_length': row[7],
                'images': row[8],
                'internal_links': row[9]
            },
            'differences': {
                'heading_diff': row[10],
                'text_length_diff': row[11],
                'image_diff': row[12],
                'internal_link_diff': row[13]
            },
            'rank_at_analysis': row[14],
            'previous_rank': row[15],
            'checked_at': row[16]
        }
    
    def get_competitor_analysis_history(
        self,
        keyword: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        競合分析の履歴を取得
        
        Args:
            keyword: キーワード
            limit: 取得件数（デフォルト: 10）
            
        Returns:
            競合分析履歴のリスト
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                keyword, own_url,
                own_heading_count, own_text_length, own_image_count, own_internal_link_count,
                competitor_avg_headings, competitor_avg_text_length,
                competitor_avg_images, competitor_avg_internal_links,
                heading_diff, text_length_diff, image_diff, internal_link_diff,
                rank_at_analysis, previous_rank, checked_at
            FROM competitor_analysis
            WHERE keyword = ?
            ORDER BY checked_at DESC
            LIMIT ?
        """, (keyword, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'keyword': row[0],
                'own_url': row[1],
                'own': {
                    'heading_count': row[2],
                    'text_length': row[3],
                    'image_count': row[4],
                    'internal_link_count': row[5]
                },
                'competitor_avg': {
                    'headings': row[6],
                    'text_length': row[7],
                    'images': row[8],
                    'internal_links': row[9]
                },
                'differences': {
                    'heading_diff': row[10],
                    'text_length_diff': row[11],
                    'image_diff': row[12],
                    'internal_link_diff': row[13]
                },
                'rank_at_analysis': row[14],
                'previous_rank': row[15],
                'checked_at': row[16]
            })
        
        return results
    
    def get_connection(self):
        """
        データベース接続を取得（外部からの直接アクセス用）
        
        Returns:
            sqlite3.Connection
        """
        return sqlite3.connect(self.db_path)
    
    def save_keyword(
        self,
        keyword: str,
        genre: Optional[str] = None,
        url: Optional[str] = None,
        priority: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """
        キーワード情報を保存（UPSERT）
        
        Args:
            keyword: キーワード
            genre: ジャンル/カテゴリ
            url: 関連URL
            priority: 優先度
            notes: メモ
        """
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 既存のキーワードを確認
        cursor.execute("SELECT created_at FROM keywords WHERE keyword = ?", (keyword,))
        existing = cursor.fetchone()
        
        if existing:
            # 更新
            cursor.execute("""
                UPDATE keywords 
                SET genre = ?, url = ?, priority = ?, notes = ?, updated_at = ?
                WHERE keyword = ?
            """, (genre, url, priority, notes, now, keyword))
        else:
            # 新規作成
            cursor.execute("""
                INSERT INTO keywords (keyword, genre, url, priority, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (keyword, genre, url, priority, notes, now, now))
        
        conn.commit()
        conn.close()
    
    def save_keywords_batch(self, keywords_data: List[Dict[str, Any]]):
        """
        複数のキーワード情報をバッチで保存
        
        Args:
            keywords_data: キーワード情報のリスト
                [{'keyword': str, 'genre': str, 'url': str, 'priority': str, 'notes': str}, ...]
        """
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for kw_data in keywords_data:
            keyword = kw_data.get('keyword')
            if not keyword:
                continue
            
            genre = kw_data.get('genre')
            url = kw_data.get('url')
            priority = kw_data.get('priority')
            notes = kw_data.get('notes')
            
            # 既存のキーワードを確認
            cursor.execute("SELECT created_at FROM keywords WHERE keyword = ?", (keyword,))
            existing = cursor.fetchone()
            
            if existing:
                # 更新
                cursor.execute("""
                    UPDATE keywords 
                    SET genre = ?, url = ?, priority = ?, notes = ?, updated_at = ?
                    WHERE keyword = ?
                """, (genre, url, priority, notes, now, keyword))
            else:
                # 新規作成
                cursor.execute("""
                    INSERT INTO keywords (keyword, genre, url, priority, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (keyword, genre, url, priority, notes, now, now))
        
        conn.commit()
        conn.close()
    
    def get_keyword(self, keyword: str) -> Optional[Dict[str, Any]]:
        """
        キーワード情報を取得（ページ特徴量含む）
        
        Args:
            keyword: キーワード
            
        Returns:
            キーワード情報の辞書（なければNone）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT keyword, genre, url, priority, notes, created_at, updated_at,
                   intent_label, page_type, primary_entity, secondary_keywords, topic_embedding
            FROM keywords
            WHERE keyword = ?
        """, (keyword,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'keyword': row[0],
                'genre': row[1],
                'url': row[2],
                'priority': row[3],
                'notes': row[4],
                'created_at': row[5],
                'updated_at': row[6],
                'intent_label': row[7],
                'page_type': row[8],
                'primary_entity': row[9],
                'secondary_keywords': row[10],
                'topic_embedding': row[11]
            }
        
        return None
    
    def get_all_keywords(self) -> List[Dict[str, Any]]:
        """
        全てのキーワード情報を取得（ページ特徴量含む）
        
        Returns:
            キーワード情報のリスト
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT keyword, genre, url, priority, notes, created_at, updated_at,
                   intent_label, page_type, primary_entity, secondary_keywords, topic_embedding
            FROM keywords
            ORDER BY keyword
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'keyword': row[0],
                'genre': row[1],
                'url': row[2],
                'priority': row[3],
                'notes': row[4],
                'created_at': row[5],
                'updated_at': row[6],
                'intent_label': row[7],
                'page_type': row[8],
                'primary_entity': row[9],
                'secondary_keywords': row[10],
                'topic_embedding': row[11]
            })
        
        return results
    
    def get_keywords_by_genre(self, genre: str) -> List[Dict[str, Any]]:
        """
        ジャンル別にキーワード情報を取得（ページ特徴量含む）
        
        Args:
            genre: ジャンル名
            
        Returns:
            キーワード情報のリスト
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT keyword, genre, url, priority, notes, created_at, updated_at,
                   intent_label, page_type, primary_entity, secondary_keywords, topic_embedding
            FROM keywords
            WHERE genre = ?
            ORDER BY keyword
        """, (genre,))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'keyword': row[0],
                'genre': row[1],
                'url': row[2],
                'priority': row[3],
                'notes': row[4],
                'created_at': row[5],
                'updated_at': row[6],
                'intent_label': row[7],
                'page_type': row[8],
                'primary_entity': row[9],
                'secondary_keywords': row[10],
                'topic_embedding': row[11]
            })
        
        return results
    
    def get_all_genres(self) -> List[str]:
        """
        全てのジャンルを取得
        
        Returns:
            ジャンルのリスト（重複なし）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT genre
            FROM keywords
            WHERE genre IS NOT NULL
            ORDER BY genre
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def delete_keyword(self, keyword: str):
        """
        キーワード情報を削除
        
        Args:
            keyword: キーワード
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 関連する順位情報も削除
        cursor.execute("DELETE FROM rankings WHERE keyword = ?", (keyword,))
        cursor.execute("DELETE FROM competitors WHERE keyword = ?", (keyword,))
        cursor.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
        
        conn.commit()
        conn.close()
    
    def get_keywords_with_rankings(self) -> List[Dict[str, Any]]:
        """
        キーワード情報と最新の順位情報を結合して取得
        
        Returns:
            キーワード情報と順位情報のリスト
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                k.keyword, k.genre, k.url, k.priority, k.notes,
                r.last_rank, r.last_checked_at, r.last_url
            FROM keywords k
            LEFT JOIN rankings r ON k.keyword = r.keyword
            ORDER BY k.keyword
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'keyword': row[0],
                'genre': row[1],
                'url': row[2],
                'priority': row[3],
                'notes': row[4],
                'last_rank': row[5],
                'last_checked_at': row[6],
                'last_url': row[7]
            })
        
        return results