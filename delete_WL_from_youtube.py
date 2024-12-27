#!/usr/bin/env python3
import os
import logging
import agentql
from agentql.ext.playwright.sync_api import Page
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import requests

# 環境変数の読み込み
load_dotenv()

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Notion設定
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_VERSION = "2022-06-28"
DELETE_PROPERTY_NAME = "delete"    # チェックボックス型プロパティ
DELETED_PROPERTY_NAME = "deleted"  # チェックボックス型プロパティ（削除済みフラグ）
VIDEOID_PROPERTY_NAME = "Link"     # 動画URLを格納しているプロパティ
PROPERTY_TITLE = "Name"           # Title型（get_WL_from_youtubeと統一）

# 保存メニュー項目を探すクエリ
SAVE_MENU_QUERY = """
{
    menu_items[] {
        watch_later(後で見る)
    }
}
"""

def manual_login(page):
    """YouTubeに手動でログインする"""
    try:
        # ログインページにアクセス
        logger.info("Navigating to YouTube login page...")
        page.goto("https://www.youtube.com")
        
        # ログインボタンをクリック
        login_button = page.get_by_role("link", name="ログイン")
        if login_button:
            login_button.click()
            
            # ユーザーに手動ログインを促す
            logger.info("Please login manually to YouTube...")
            input("Press Enter after you have logged in...")
            
            # ログイン後のページ読み込みを待機
            page.wait_for_load_state("networkidle")
            logger.info("Login completed")
            return True
            
    except Exception as e:
        logger.error(f"Error during manual login: {str(e)}")
        return False

def delete_from_watchlist(video_url, page):
    """YouTubeの動画を後で見るリストから削除する"""
    try:
        # 動画ページにアクセス
        logger.info(f"Accessing video page: {video_url}")
        page.goto(video_url)
        
        # ページが完全にロードされるまで待機
        logger.info("Waiting for page to load...")
        page.wait_for_selector("ytd-watch-flexy")
        page.wait_for_timeout(2000)

        try:
            # メニューボタンをクリック
            logger.info("Looking for menu button...")
            menu_button = page.get_by_role("button", name="その他の操作")
            if menu_button:
                menu_button.click()
                page.wait_for_timeout(1000)
                
                # 後で見るを削除
                menu_response = page.query_elements(SAVE_MENU_QUERY)
                if hasattr(menu_response.menu_items[0], 'watch_later'):
                    menu_response.menu_items[0].watch_later.click()
                    logger.info("Removed from Watch Later")
                    return True
                    
        except Exception as e:
            logger.error(f"Error while removing from Watch Later: {str(e)}")
        
        # 操作完了後の待機
        page.wait_for_timeout(2000)
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
    
    return False

def update_notion_delete_flag(page_id, delete_flag=False, deleted_flag=False):
    """
    Notionのページの delete フラグと deleted フラグを更新する

    Args:
        page_id (str): 更新対象のページID
        delete_flag (bool): deleteプロパティの値（デフォルトはFalse）
        deleted_flag (bool): deletedプロパティの値（デフォルトはFalse）

    Returns:
        bool: 更新に成功した場合はTrue、失敗した場合はFalse
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION
    }
    data = {
        "properties": {
            DELETE_PROPERTY_NAME: {"checkbox": delete_flag},
            DELETED_PROPERTY_NAME: {"checkbox": deleted_flag}
        }
    }

    try:
        response = requests.patch(url, headers=headers, json=data)
        if response.status_code == 200:
            logger.info(f"Successfully updated delete flag to {delete_flag} and deleted flag to {deleted_flag} for page {page_id}")
            return True
        else:
            logger.error(f"Failed to update page {page_id}: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error updating Notion page {page_id}: {str(e)}")
        return False

def query_notion_delete_items():
    """
    Notionデータベースをクエリして、「delete」チェックボックスがtrueのページを取得する。
    返り値は [ {"page_id": str, "video_id": str, "title": str}, ... ] のリスト
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION
    }
    data = {
        "filter": {
            "property": DELETE_PROPERTY_NAME,
            "checkbox": {
                "equals": True
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            logger.error(f"Failed to query Notion DB: {response.status_code}, {response.text}")
            return []

        results = response.json().get("results", [])
        delete_items = []

        for page in results:
            page_id = page["id"]
            props = page["properties"]

            # デバッグ用：利用可能なプロパティ名を出力
            logger.info(f"Available properties for page {page_id}: {list(props.keys())}")

            # タイトルプロパティを取得
            title_prop = props.get(PROPERTY_TITLE, {})
            title_value = ""
            if title_prop["type"] == "title":
                title_array = title_prop.get("title", [])
                if title_array:
                    title_value = title_array[0]["text"]["content"]

            # VideoIDプロパティから動画IDを取得
            video_id_value = ""
            if VIDEOID_PROPERTY_NAME not in props:
                logger.warning(f"Link property not found in page {page_id}")
                continue

            prop_info = props[VIDEOID_PROPERTY_NAME]
            if prop_info["type"] == "url":
                url = prop_info.get("url", "")
                if "youtube.com" in url or "youtu.be" in url:
                    if "youtube.com/watch?v=" in url:
                        video_id_value = url.split("watch?v=")[1].split("&")[0]
                    elif "youtu.be/" in url:
                        video_id_value = url.split("youtu.be/")[1].split("?")[0]

            if video_id_value:
                delete_items.append({
                    "page_id": page_id,
                    "video_id": video_id_value,
                    "title": title_value
                })

        return delete_items

    except Exception as e:
        logger.error(f"Error querying Notion database: {str(e)}")
        return []

def process_videos():
    """後で見るリストから動画を削除する処理を実行"""
    with sync_playwright() as p:
        try:
            # ブラウザの設定
            browser = p.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # AgentQLでページをラップ
            page = agentql.wrap(context.new_page())
            
            # 手動ログイン
            if not manual_login(page):
                logger.error("Failed to login")
                return
            
            # 環境変数のチェック
            notion_token = os.getenv("NOTION_API_TOKEN")
            if not notion_token:
                logger.error("NOTION_API_TOKEN is not set")
                return

            # 削除対象のアイテムを取得
            delete_items = query_notion_delete_items()
            if not delete_items:
                logger.info("No items to delete")
                return

            success_count = 0
            total_count = len(delete_items)

            # 各アイテムを処理
            for item in delete_items:
                page_id = item["page_id"]
                video_id = item.get("video_id", "")
                title = item.get("title", "Unknown")
                
                logger.info(f"Processing: {title} (ID: {video_id})")
                
                # 動画を「後で見る」リストから削除
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                if delete_from_watchlist(video_url, page):
                    # 削除に成功した場合、deleteフラグをFalseに、deletedフラグをTrueに設定
                    if update_notion_delete_flag(page_id, delete_flag=False, deleted_flag=True):
                        success_count += 1
                    else:
                        logger.error(f"Failed to update Notion flags for {title}")
                else:
                    logger.error(f"Failed to remove {title} from Watch Later")

            logger.info(f"Deletion complete. Successfully deleted {success_count} out of {total_count} videos.")

        except Exception as e:
            logger.error(f"Error in process_videos: {str(e)}")

def main():
    """メイン処理"""
    try:
        logger.info("Starting video processing")
        process_videos()
        logger.info("Completed video processing")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
