"""
CSVファイルからキーワードをデータベースにインポートするスクリプト
A列: ジャンル
B列: KW（キーワード）
C列: URL
"""
import csv
import sys
from pathlib import Path
from storage import RankingStorage

def import_csv_to_db(csv_path: str, db_path: str = "rankings.db"):
    """
    CSVファイルからキーワードをデータベースにインポート
    
    Args:
        csv_path: CSVファイルのパス
        db_path: データベースファイルのパス
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"❌ エラー: CSVファイルが見つかりません: {csv_path}")
        return
    
    print(f"📂 CSVファイルを読み込み中: {csv_path}")
    
    # ストレージを初期化
    storage = RankingStorage(db_path)
    
    keywords_data = []
    skipped_rows = []
    
    # CSVファイルを読み込む
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        
        # ヘッダー行をスキップ（最初の2行）
        next(reader, None)  # 1行目をスキップ
        next(reader, None)  # 2行目（カラム名）をスキップ
        
        for row_num, row in enumerate(reader, start=3):
            # 空行をスキップ
            if not row or all(not cell.strip() for cell in row):
                continue
            
            # カラムを取得（A列=ジャンル, B列=KW, C列=URL）
            genre = row[0].strip() if len(row) > 0 else ""
            keyword = row[1].strip() if len(row) > 1 else ""
            url = row[2].strip() if len(row) > 2 else ""
            
            # キーワードが空の場合はスキップ
            if not keyword:
                skipped_rows.append(f"行{row_num}: キーワードが空")
                continue
            
            keywords_data.append({
                'keyword': keyword,
                'genre': genre if genre else None,
                'url': url if url else None,
                'priority': None,
                'notes': None
            })
    
    if not keywords_data:
        print("❌ インポートできるデータが見つかりませんでした")
        return
    
    print(f"✅ {len(keywords_data)}件のキーワードを読み込みました")
    
    if skipped_rows:
        print(f"⚠️  {len(skipped_rows)}行をスキップしました:")
        for msg in skipped_rows[:10]:  # 最初の10件のみ表示
            print(f"  - {msg}")
        if len(skipped_rows) > 10:
            print(f"  ... 他{len(skipped_rows) - 10}件")
    
    # データベースに保存
    print(f"💾 データベースに保存中...")
    storage.save_keywords_batch(keywords_data)
    
    # ジャンル別の集計
    genres = {}
    for kw in keywords_data:
        genre = kw.get('genre') or '未分類'
        genres[genre] = genres.get(genre, 0) + 1
    
    print(f"\n✅ インポート完了！")
    print(f"📊 ジャンル別集計:")
    for genre, count in sorted(genres.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {genre}: {count}件")
    
    print(f"\n合計: {len(keywords_data)}件のキーワードを保存しました")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python3 import_csv.py <CSVファイルのパス> [データベースパス]")
        print("例: python3 import_csv.py ~/Desktop/あああああ\\ -\\ 管理シート.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else "rankings.db"
    
    import_csv_to_db(csv_path, db_path)
