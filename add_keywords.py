"""
キーワードをデータベースに追加するスクリプト
フォーマット: ジャンル<TAB>キーワード
"""
import sys
from storage import RankingStorage

def add_keywords(keywords_data: list, db_path: str = "rankings.db"):
    """
    キーワードをデータベースに追加
    
    Args:
        keywords_data: キーワードデータのリスト [{'genre': str, 'keyword': str}, ...]
        db_path: データベースファイルのパス
    """
    storage = RankingStorage(db_path)
    
    # データベースに保存
    print(f"💾 {len(keywords_data)}件のキーワードをデータベースに追加中...")
    storage.save_keywords_batch(keywords_data)
    
    # ジャンル別の集計
    genres = {}
    for kw in keywords_data:
        genre = kw.get('genre') or '未分類'
        genres[genre] = genres.get(genre, 0) + 1
    
    print(f"\n✅ 追加完了！")
    print(f"📊 ジャンル別集計:")
    for genre, count in sorted(genres.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {genre}: {count}件")
    
    print(f"\n合計: {len(keywords_data)}件のキーワードを追加しました")

if __name__ == "__main__":
    # フォーマット: KW<TAB>URL または ジャンル<TAB>KW [<TAB>URL]
    keywords_text = """ルイヴィトン 日本	https://daikichi-kaitori.jp/column/louis-vuitton-japan/
ルイヴィトン スピーディ	https://daikichi-kaitori.jp/column/louis-vuitton-speedy/
ルイヴィトン 財布 人気	https://daikichi-kaitori.jp/column/louis-vuitton-wallet-popularity/
ルイヴィトン 製造番号	https://daikichi-kaitori.jp/column/louis-vuitton-serial-number/
ヴィトン ポーチ	https://daikichi-kaitori.jp/column/louis-vuitton-pouch/
ルイヴィトン トートバッグ	https://daikichi-kaitori.jp/column/louis-vuitton-tote-bag/
エルメス 修理 断られる	https://daikichi-kaitori.jp/column/hermes-repair-refused/
エルメス ピコタン なぜ買えない	https://daikichi-kaitori.jp/column/hermes-pikotan-nazekaenai/
エルメス スカーフ 人気ランキング	https://daikichi-kaitori.jp/column/hermes-suka-hu-ninkiranking/
エルメス クリッパー ダサい	https://daikichi-kaitori.jp/%e3%82%a8%e3%83%ab%e3%83%a1%e3%82%b9/hermes-clipper-is-tacky/
エルメス ガーデンパーティー サイズ	https://daikichi-kaitori.jp/%e3%82%a8%e3%83%ab%e3%83%a1%e3%82%b9/hermes-garden-party-size/
シャネル カチューシャ	https://daikichi-kaitori.jp/%e3%82%b7%e3%83%a3%e3%83%8d%e3%83%ab/chanel-katsura/
シャネル ポーチ ノベルティ	https://daikichi-kaitori.jp/column/chanel-pouch-novelty/
シャネル トラベルライン 流行遅れ	https://daikichi-kaitori.jp/column/chanel-travel-line-out-of-style/
シャネル フラップバッグ マトラッセ 違い	https://daikichi-kaitori.jp/column/chanel-flap-bag-matelasse-difference/
シャネル スカーフ 偽物 見分け方	https://daikichi-kaitori.jp/column/chanel-scarf-fake-distinguish/
昭和39年 オリンピック記念硬貨 1000円 価値	https://daikichi-kaitori.jp/medal/1964-olympic-commemorative-1000-yen-silver-coin/
一万円札 ホログラムなし	https://daikichi-kaitori.jp/gold/10000-yen-note-without-hologram/
二千円札 消えた理由	https://daikichi-kaitori.jp/oldmny/2000-yen-bill/
プルーフ硬貨 見分け方	https://daikichi-kaitori.jp/column/proof-coin-distinguish/
造幣局 貨幣セット 価値	https://daikichi-kaitori.jp/column/mint-coin-set-value/
十銭硬貨 価値	https://daikichi-kaitori.jp/column/value-of-the-10-sen-coin/
ティファニー 婚約指輪 重ね付け	https://daikichi-kaitori.jp/column/tiffany-stackable-engagement-rings/
カルティエ オーバーホール	https://daikichi-kaitori.jp/column/cartier-overhaul/
カルティエ ネックレス 人気 50代	https://daikichi-kaitori.jp/brand/cartier/cartier-necklace-popular-50s/
ハリーウィンストン 重ね付け	https://daikichi-kaitori.jp/jewel/jewel_harrywinston/harry-winston-layered-stacking/
ティファニー 指輪 人気 50代	https://daikichi-kaitori.jp/brand/brand_tiffany/tiffany-ring-popularity-50s/
金を買うには	https://daikichi-kaitori.jp/column/kinwokauniha/
お金をきれいにする方法	https://daikichi-kaitori.jp/column/okanewokireinisuruhouhou/
金を売るならどこがいい	https://daikichi-kaitori.jp/gold/gold-urunaradokogaii/
金 鑑定 どこで	https://daikichi-kaitori.jp/column/where-to-get-gold-appraised/
金はどうやってできる	https://daikichi-kaitori.jp/column/how-is-gold-made/
金メッキとは	https://daikichi-kaitori.jp/column/gold-plating/
金 購入 証明書 なし	https://daikichi-kaitori.jp/column/no-proof-of-purchase-for-gold/
ロレックス 金無垢	https://daikichi-kaitori.jp/column/rolex-solid-gold/
未分類	金下落
未分類	金 インゴット 1kg 価格
未分類	金 手数料
未分類	金 資産
未分類	金 分割
未分類	王水とは
未分類	18kgpとは
未分類	刻印とは
未分類	14k / 750
未分類	2050年 金価格
未分類	精錬とは
未分類	金鉱脈
未分類	金標準先物
未分類	金メダル 素材
未分類	パラジウムとは
未分類	ロジウム
未分類	白金とは
未分類	ロレックス オーバーホール
未分類	ロレックス 偽物
未分類	ロレックス なぜ高い
未分類	ロレックス サンダーバード
未分類	ロレックス マラソン
未分類	カルティエ 三連リング
未分類	カルティエ 婚約指輪 相場
未分類	ヴァンクリーフ 婚約指輪
未分類	刀 種類
未分類	日本刀 種類
未分類	べっ甲
未分類	象牙 値段
未分類	江戸切子とは"""
    
    keywords_data = []
    for line in keywords_text.strip().split('\n'):
        if not line.strip():
            continue
        
        parts = [p.strip() for p in line.split('\t')]
        if len(parts) >= 3:
            # ジャンル, KW, URL
            genre, keyword, url = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            if parts[1].startswith('http://') or parts[1].startswith('https://'):
                # KW, URL（ジャンルなし）
                keyword, url = parts[0], parts[1]
                genre = None
            else:
                # ジャンル, KW
                genre, keyword = parts[0], parts[1]
                url = None
        else:
            continue
            
        if keyword:
            keywords_data.append({
                'keyword': keyword,
                'genre': genre if genre else None,
                'url': url if url else None,
                'priority': None,
                'notes': None
            })
    
    if not keywords_data:
        print("❌ キーワードデータが見つかりませんでした")
        sys.exit(1)
    
    add_keywords(keywords_data)
