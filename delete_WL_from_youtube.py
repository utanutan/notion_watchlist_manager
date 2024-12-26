#!/usr/bin/env python3
import os
import time
import logging
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Load environment variables
load_dotenv()

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ----------------- Notion 設定 ------------------
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_VERSION = "2022-06-28"
DELETE_PROPERTY_NAME = "delete"    # チェックボックス型プロパティ
DELETED_PROPERTY_NAME = "deleted"  # チェックボックス型プロパティ（削除済みフラグ）
VIDEOID_PROPERTY_NAME = "Link"     # 動画URLを格納しているプロパティ
PROPERTY_TITLE = "Name"           # Title型（get_WL_from_youtubeと統一）
# ----------------------------------------------

def setup_driver():
    """Seleniumのドライバーをセットアップする"""
    options = webdriver.ChromeOptions()
    
    # ユーザーデータとプロファイルディレクトリを設定
    user_data_dir = os.path.abspath('./chrome_profile')
    options.add_argument(f'--user-data-dir={user_data_dir}')
    options.add_argument('--profile-directory=Profile 1')
    
    # セキュリティ関連の設定
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # その他の設定
    options.add_argument('--start-maximized')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--window-size=1920,1080')  # ヘッドレスモード用のウィンドウサイズ
    
    driver = webdriver.Chrome(options=options)
    
    # JavaScriptを実行してWebDriverフラグを削除
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    driver.implicitly_wait(10)
    return driver

def remove_from_watch_later(driver, video_id):
    """
    YouTubeの「後で見る」リストから指定した動画を削除する

    Args:
        driver: Seleniumのドライバー
        video_id (str): 削除対象の動画ID

    Returns:
        bool: 削除に成功した場合はTrue、失敗した場合はFalse
    """
    try:
        # 動画ページにアクセス
        url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"Accessing video page: {url}")
        driver.get(url)
        
        # ページが完全にロードされるまで少し待機
        logger.info("Waiting for page to load...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "ytd-watch-flexy"))
        )
        
        # 少し待機してページの読み込みを確実にする
        time.sleep(5)
        
        # メタデータセクションが読み込まれるまで待機
        logger.info("Waiting for metadata section...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "ytd-watch-metadata"))
        )
        
        # 3点ボタンを待機してクリック
        logger.info("Waiting for threedot button...")
        threedot_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#button-shape button"))
        )
        logger.info("Found threedot button, clicking...")
        driver.execute_script("arguments[0].click();", threedot_button)
        logger.info("Clicked threedot button")
        
        # メニューが表示されるまで待機
        time.sleep(2)
        
        # 保存ボタンをクリック
        logger.info("Waiting for save button...")
        save_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='items']/ytd-menu-service-item-renderer[2]/tp-yt-paper-item/yt-formatted-string"))
        )
        logger.info("Found save button, clicking...")
        driver.execute_script("arguments[0].click();", save_button)
        logger.info("Clicked save button")
        
        # プレイリストメニューが表示されるまで待機
        time.sleep(2)
        
        # 「後で見る」のチェックボックスを待機して見つける
        logger.info("Looking for Watch Later checkbox...")
        watch_later_checkbox = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/ytd-app/ytd-popup-container/tp-yt-paper-dialog/ytd-add-to-playlist-renderer/div[2]/ytd-playlist-add-to-option-renderer[1]/tp-yt-paper-checkbox/div[1]/div"))
        )
        
        # チェックボックスの状態を確認
        logger.info("Checking Watch Later checkbox state...")
        parent_element = watch_later_checkbox.find_element(By.XPATH, "./../..")
        checkbox_state = parent_element.get_attribute("aria-checked")
        logger.info(f"Checkbox state: {checkbox_state}")
        
        if checkbox_state == "true":
            logger.info("Found checked Watch Later item, unchecking...")
            driver.execute_script("arguments[0].click();", watch_later_checkbox)
            logger.info(f"Successfully removed video '{video_id}' from Watch Later playlist")
            # 変更が反映されるまで少し待機
            time.sleep(2)
            return True
        else:
            logger.info(f"Video '{video_id}' is not in Watch Later playlist")
            return True

    except TimeoutException as e:
        logger.error(f"Timeout waiting for elements: {e}")
        return False
    except NoSuchElementException as e:
        logger.error(f"Element not found: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to remove video '{video_id}' from Watch Later: {e}")
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

def main():
    # Seleniumドライバーをセットアップ
    driver = None
    try:
        # 削除対象のアイテムを取得
        delete_items = query_notion_delete_items()
        if not delete_items:
            logger.info("No items found with delete flag set to true")
            return

        driver = setup_driver()
        success_count = 0
        total_count = len(delete_items)

        for item in delete_items:
            page_id = item["page_id"]
            video_id = item["video_id"]
            title = item["title"]

            logger.info(f"Processing: {title} (ID: {video_id})")
            
            # 動画を「後で見る」リストから削除
            if remove_from_watch_later(driver, video_id):
                # 削除に成功した場合、deleteフラグをFalseに、deletedフラグをTrueに設定
                if update_notion_delete_flag(page_id, delete_flag=False, deleted_flag=True):
                    success_count += 1
                    logger.info(f"Successfully processed: {title}")
            else:
                # 削除に失敗した場合、deleteフラグのみFalseに設定
                if update_notion_delete_flag(page_id, delete_flag=False, deleted_flag=False):
                    logger.info(f"Failed to remove video but updated delete flag: {title}")

        logger.info(f"Deletion complete. Successfully deleted {success_count} out of {total_count} videos.")

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
