#!/usr/bin/env python3
import os
import logging
import requests
from dotenv import load_dotenv
from delete_WL_from_youtube import query_notion_delete_items, NOTION_VERSION

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def test_notion_connection():
    """Notionの接続をテストする"""
    notion_token = os.getenv("NOTION_API_TOKEN")
    notion_db_id = os.getenv("NOTION_DATABASE_ID")
    
    # トークンとデータベースIDの存在確認
    logger.info(f"Notion Token: {notion_token[:4]}...{notion_token[-4:]}")
    logger.info(f"Notion DB ID: {notion_db_id}")
    
    # データベースへの直接アクセスをテスト
    url = f"https://api.notion.com/v1/databases/{notion_db_id}"
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
    }
    
    try:
        response = requests.get(url, headers=headers)
        logger.info(f"Database test response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        logger.info(f"Response body: {response.text[:500]}...")  # 最初の500文字のみ表示
    except Exception as e:
        logger.error(f"Error testing database connection: {e}")

def main():
    # 環境変数を読み込む
    load_dotenv()
    
    # Notion接続テスト
    logger.info("Testing Notion connection...")
    test_notion_connection()
    
    # 削除対象のアイテムを取得
    logger.info("\nQuerying Notion for items to delete...")
    items = query_notion_delete_items()
    
    if not items:
        logger.info("No items found with delete flag set to true")
        return
        
    # 取得したアイテムの詳細を表示
    logger.info(f"Found {len(items)} items to delete:")
    for i, item in enumerate(items, 1):
        logger.info(f"\nItem {i}:")
        logger.info(f"Title: {item['title']}")
        logger.info(f"Video ID: {item['video_id']}")
        logger.info(f"Page ID: {item['page_id']}")

if __name__ == "__main__":
    main()
