"""
データベースにページ特徴量カラムを追加するマイグレーションスクリプト
"""
import sqlite3
import sys

def migrate_db(db_path: str):
    """
    keywordsテーブルにページ特徴量カラムを追加
    
    Args:
        db_path: データベースファイルのパス
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 新しいカラムを追加
        columns_to_add = [
            ("intent_label", "TEXT"),  # 検索意図（とは/方法/比較/おすすめ/料金/症状/原因）
            ("page_type", "TEXT"),     # ページタイプ（ハブ/カテゴリ/詳細/LP/記事）
            ("primary_entity", "TEXT"), # 主要エンティティ（商品名/ブランド名など）
            ("secondary_keywords", "TEXT"), # 関連KW群（JSON配列）
            ("topic_embedding", "TEXT"),    # トピックベクトル（JSON配列）
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE keywords ADD COLUMN {column_name} {column_type}")
                print(f"✅ カラム追加成功: {column_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    print(f"⚠️  カラムは既に存在します: {column_name}")
                else:
                    raise
        
        # インデックスを作成（検索高速化）
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_keywords_intent_label ON keywords(intent_label)")
            print("✅ インデックス作成成功: intent_label")
        except sqlite3.OperationalError:
            print("⚠️  インデックスは既に存在します: intent_label")
        
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_keywords_primary_entity ON keywords(primary_entity)")
            print("✅ インデックス作成成功: primary_entity")
        except sqlite3.OperationalError:
            print("⚠️  インデックスは既に存在します: primary_entity")
        
        conn.commit()
        print("\n✅ マイグレーション完了！")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ マイグレーション失敗: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    db_path = "rankings.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"データベースをマイグレーション中: {db_path}\n")
    migrate_db(db_path)
