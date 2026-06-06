"""
Google Sheets からキーワード・URLを同期するモジュール

スプレッドシート構造:
  B列: キーワード (KW)
  S列: URL（公開済みのみ記入）

認証方法:
  環境変数 GOOGLE_CREDENTIALS_PATH にサービスアカウントJSONキーのパスを設定する。
  スプレッドシートをそのサービスアカウントのメールアドレスと共有しておくこと。
"""

import os
from typing import List, Dict, Optional

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# B列=インデックス0, S列=インデックス17（B〜Sの範囲で取得するため）
COL_KEYWORD = 0   # B列
COL_URL = 17      # S列（B=0, C=1 ... S=17）


def _build_service(credentials_path: str):
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def fetch_keywords_from_sheet(
    spreadsheet_id: str,
    credentials_path: str,
    sheet_name: str = "Sheet1"
) -> List[Dict[str, Optional[str]]]:
    """
    スプレッドシートからキーワードとURLを取得する。

    Returns:
        [{'keyword': str, 'url': str or None}, ...]
        - B列が空の行はスキップ
        - S列が空の行は url=None（未公開）として含める
    """
    if not SHEETS_AVAILABLE:
        raise ImportError(
            "google-api-python-client が未インストールです。\n"
            "pip install google-api-python-client google-auth を実行してください。"
        )

    service = _build_service(credentials_path)
    sheets = service.spreadsheets()

    # B列〜S列を一括取得（1行目はヘッダーとしてスキップ）
    # シート名に日本語や記号が含まれる場合はシングルクォートで囲む
    safe_sheet_name = f"'{sheet_name}'" if any(c in sheet_name for c in " 　()（）[]【】/\\") or not sheet_name.isascii() else sheet_name
    range_notation = f"{safe_sheet_name}!B2:S"
    print(f"[SYNC] 取得レンジ: {range_notation}")
    result = sheets.values().get(
        spreadsheetId=spreadsheet_id,
        range=range_notation,
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()

    rows = result.get("values", [])
    print(f"[SYNC] シートから{len(rows)}行取得")
    keywords: List[Dict[str, Optional[str]]] = []

    for row in rows:
        # B列（インデックス0）を取得
        keyword = str(row[COL_KEYWORD]).strip() if len(row) > COL_KEYWORD else ""
        if not keyword:
            continue

        # S列（インデックス17）を取得（列が存在しない場合はNone）
        url_raw = str(row[COL_URL]).strip() if len(row) > COL_URL else ""
        url = url_raw if url_raw else None

        keywords.append({"keyword": keyword, "url": url})

    return keywords


def sync_to_storage(
    spreadsheet_id: str,
    credentials_path: str,
    storage,
    sheet_name: str = "Sheet1"
) -> Dict[str, int]:
    """
    スプレッドシートからDBへ同期する。

    同期ルール:
    - シートに存在するKW: URLをDBへ反映（公開済み=URLあり, 未公開=URLをNULLに）
    - DBにはあるがシートにないKW: そのまま保持（削除しない）
    - シートにあるがDBにないKW: 新規登録

    Returns:
        {'inserted': int, 'updated': int, 'total': int}
    """
    print(f"[SYNC] スプレッドシートからデータ取得中...")
    keywords = fetch_keywords_from_sheet(spreadsheet_id, credentials_path, sheet_name)
    print(f"[SYNC] {len(keywords)}件取得")

    stats = storage.sync_keywords_from_sheet(keywords)
    stats['fetched'] = len(keywords)
    return stats
