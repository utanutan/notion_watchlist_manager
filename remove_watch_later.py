#!/usr/bin/env python3
import logging
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 削除対象の動画ID
TARGET_VIDEO_ID = "BPODklKbx5s"

def setup_driver():
    """Seleniumのドライバーをセットアップする"""
    options = webdriver.ChromeOptions()
    
    # ユーザーデータとプロファイルディレクトリを設定
    user_data_dir = os.path.abspath('./chrome_profile')
    options.add_argument(f'--user-data-dir={user_data_dir}')
    options.add_argument('--profile-directory=Profile 1')
    
    # ヘッドレスモードを有効化
    # options.add_argument('--headless=new')
    
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
            EC.element_to_be_clickable((By.CSS_SELECTOR, "ytd-menu-service-item-renderer:nth-child(2) tp-yt-paper-item"))
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

def main():
    driver = None
    try:
        # Seleniumドライバーをセットアップ
        driver = setup_driver()
        
        # 動画を「後で見る」から削除
        logger.info(f"Attempting to remove video {TARGET_VIDEO_ID} from Watch Later...")
        success = remove_from_watch_later(driver, TARGET_VIDEO_ID)
        
        if success:
            logger.info("Operation completed successfully")
        else:
            logger.error("Operation failed")
            
    finally:
        # ドライバーをクリーンアップ
        if driver:
            logger.info("Cleaning up browser...")
            driver.quit()

if __name__ == "__main__":
    main()
