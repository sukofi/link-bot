"""
既存キーワードからページ特徴量を自動抽出してDBを更新
- Intent分類（とは/方法/比較/買取/価格など）
- Primary Entity抽出（商品名/ブランド名など）
- Gemini APIでembedding生成
"""
import sqlite3
import os
import json
import re
from typing import Dict, Any, List, Optional

try:
    import google.generativeai as genai
except (ImportError, PermissionError, OSError) as e:
    genai = None

def classify_intent(keyword: str) -> str:
    """
    キーワードから検索意図を分類
    
    Args:
        keyword: キーワード
        
    Returns:
        Intent分類（とは/方法/比較/おすすめ/買取/価格など）
    """
    # ルールベースで分類
    if any(x in keyword for x in ['とは', '意味', '定義']):
        return '定義'
    elif any(x in keyword for x in ['方法', 'やり方', '手順', '使い方']):
        return '方法'
    elif any(x in keyword for x in ['比較', 'どっち', 'どちら', '違い']):
        return '比較'
    elif any(x in keyword for x in ['おすすめ', 'ランキング', '人気', 'まとめ']):
        return 'おすすめ'
    elif any(x in keyword for x in ['買取', '売る', '査定']):
        return '買取'
    elif any(x in keyword for x in ['価格', '値段', '相場', '料金', '費用', '定価']):
        return '価格'
    elif any(x in keyword for x in ['種類', 'モデル', '一覧', 'バリエーション']):
        return '種類'
    elif any(x in keyword for x in ['偽物', '見分け方', '本物', '真贋']):
        return '真贋'
    elif any(x in keyword for x in ['原因', '理由', 'なぜ']):
        return '原因'
    elif any(x in keyword for x in ['症状', '状態', 'サイン']):
        return '症状'
    elif any(x in keyword for x in ['対策', '解決', '治療', '改善']):
        return '対策'
    else:
        return '一般'

def classify_page_type(keyword: str, intent: str) -> str:
    """
    ページタイプを分類
    
    Args:
        keyword: キーワード
        intent: Intent分類
        
    Returns:
        ページタイプ（ハブ/カテゴリ/詳細/LP/記事）
    """
    # ブランド名や商品名が含まれる場合は「詳細」
    if any(x in keyword for x in ['ロレックス', 'シャネル', 'エルメス', 'ティファニー', 'カルティエ', 'オメガ']):
        return '詳細'
    elif intent in ['買取', '価格', '真贋']:
        return '詳細'
    elif intent in ['種類', '比較', 'おすすめ']:
        return 'カテゴリ'
    elif intent in ['定義', '方法']:
        return '記事'
    else:
        return '記事'

def extract_primary_entity(keyword: str) -> Optional[str]:
    """
    主要エンティティを抽出（商品名/ブランド名など）
    
    Args:
        keyword: キーワード
        
    Returns:
        主要エンティティ（抽出できない場合はNone）
    """
    # ブランド名リスト
    brands = ['ロレックス', 'シャネル', 'エルメス', 'ティファニー', 'カルティエ', 'オメガ', 
              'パテックフィリップ', 'オーデマピゲ', 'ブレゲ', 'ヴァシュロン', 'ランゲ',
              'グランドセイコー', 'セイコー', 'シチズン', 'カシオ', 'ガガミラノ']
    
    # ブランド名を検索
    for brand in brands:
        if brand in keyword:
            # ブランド名 + 商品名のパターンを抽出
            parts = keyword.split()
            brand_idx = -1
            for i, part in enumerate(parts):
                if brand in part:
                    brand_idx = i
                    break
            
            if brand_idx >= 0:
                # ブランド名とその後の単語を結合
                entity_parts = parts[brand_idx:brand_idx+3]  # 最大3単語
                return ' '.join(entity_parts)
    
    # ブランド名がない場合、最初の2-3単語をエンティティとして扱う
    parts = keyword.split()
    if len(parts) >= 2:
        return ' '.join(parts[:2])
    elif len(parts) == 1:
        return parts[0]
    
    return None

def generate_embedding_with_gemini(keyword: str, api_key: str) -> Optional[List[float]]:
    """
    Gemini APIでembeddingを生成
    
    Args:
        keyword: キーワード
        api_key: Gemini API Key
        
    Returns:
        Embeddingベクトル（失敗時はNone）
    """
    if not genai:
        return None
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('models/embedding-001')
        result = model.embed_content(keyword)
        return result['embedding']
    except Exception as e:
        print(f"  ⚠️  Embedding生成失敗: {e}")
        return None

def process_keywords(db_path: str = "rankings.db"):
    """
    既存キーワードの特徴量を抽出してDBを更新
    
    Args:
        db_path: データベースファイルのパス
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 全キーワードを取得
    cursor.execute("SELECT keyword, genre FROM keywords")
    keywords = cursor.fetchall()
    
    print(f"📊 処理対象: {len(keywords)}件のキーワード\n")
    
    # Gemini API Key取得
    api_key = os.getenv('GEMINI_API_KEY')
    use_embedding = api_key is not None and genai is not None
    
    if use_embedding:
        print("✅ Gemini Embedding有効\n")
    else:
        print("⚠️  Gemini Embedding無効（embeddingはスキップ）\n")
    
    updated_count = 0
    
    for keyword, genre in keywords:
        try:
            # Intent分類
            intent = classify_intent(keyword)
            
            # Page Type分類
            page_type = classify_page_type(keyword, intent)
            
            # Primary Entity抽出
            entity = extract_primary_entity(keyword)
            
            # Secondary Keywords（同じエンティティを持つ他のKW）
            # 後でバッチ処理で計算するため、ここでは空配列
            secondary_kws = []
            
            # Topic Embedding生成
            embedding = None
            if use_embedding:
                embedding = generate_embedding_with_gemini(keyword, api_key)
            
            # DBを更新
            cursor.execute("""
                UPDATE keywords 
                SET intent_label = ?,
                    page_type = ?,
                    primary_entity = ?,
                    secondary_keywords = ?,
                    topic_embedding = ?,
                    updated_at = datetime('now')
                WHERE keyword = ?
            """, (
                intent,
                page_type,
                entity,
                json.dumps(secondary_kws, ensure_ascii=False),
                json.dumps(embedding, ensure_ascii=False) if embedding else None,
                keyword
            ))
            
            updated_count += 1
            
            if updated_count % 10 == 0:
                print(f"処理済み: {updated_count}/{len(keywords)}")
            
            # デバッグ出力（最初の5件）
            if updated_count <= 5:
                print(f"  KW: {keyword}")
                print(f"    Intent: {intent}, Type: {page_type}, Entity: {entity}")
                print()
        
        except Exception as e:
            print(f"  ❌ エラー: {keyword} - {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 完了: {updated_count}件のキーワードを更新しました")

if __name__ == "__main__":
    import sys
    db_path = "rankings.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print("=" * 60)
    print("ページ特徴量の自動抽出")
    print("=" * 60)
    print()
    
    process_keywords(db_path)
