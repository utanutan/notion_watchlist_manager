#!/usr/bin/env python3
import os
import agentql
from agentql.ext.playwright.sync_api import Page
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# AgentQLの設定
agentql.configure(api_key=os.getenv("AGENTQL_API_KEY"))

# 保存ボタンを探すクエリ
SAVE_BUTTON_QUERY = """
{
    save_button
}
"""

# 保存メニュー項目を探すクエリ
SAVE_MENU_QUERY = """
{
    menu_items[] {
        save_option(保存)
        watch_later(後で見る)
    }
}
"""

def handle_youtube_save(video_url):
    """YouTubeの動画を後で見るリストに保存/削除する"""
    with sync_playwright() as p, p.chromium.launch(headless=False) as browser:
        try:
            # AgentQLでページをラップ
            page = agentql.wrap(browser.new_page())
            
            # 動画ページにアクセス
            print(f"Accessing video page: {video_url}")
            page.goto(video_url)
            
            # ページが完全にロードされるまで待機
            print("Waiting for page to load...")
            page.wait_for_selector("ytd-watch-flexy")
            page.wait_for_timeout(2000)

            try:
                # 保存ボタンを探す（すでに保存済みの場合）
                response = page.query_elements(SAVE_BUTTON_QUERY)
                if hasattr(response, 'save_button'):
                    print("Found save button (already saved)")
                    response.save_button.click()
                    page.wait_for_timeout(1000)
                    
                    # 後で見るを削除
                    menu_response = page.query_elements(SAVE_MENU_QUERY)
                    if hasattr(menu_response.menu_items[0], 'watch_later'):
                        menu_response.menu_items[0].watch_later.click()
                        print("Removed from Watch Later")
                
            except Exception as e:
                # 保存ボタンが見つからない場合、メニューボタンをクリック
                print("Save button not found, looking for menu button...")
                # role属性とname属性を使用して要素を特定
                menu_button = page.get_by_role("button", name="その他の操作")
                if menu_button:
                    menu_button.click()
                    page.wait_for_timeout(1000)
                    
                    # 保存オプションをクリック
                    save_response = page.query_elements(SAVE_MENU_QUERY)
                    if hasattr(save_response.menu_items[0], 'save_option'):
                        save_response.menu_items[0].save_option.click()
                        page.wait_for_timeout(1000)
                        
                        # 後で見るを選択
                        watch_later_response = page.query_elements(SAVE_MENU_QUERY)
                        if hasattr(watch_later_response.menu_items[0], 'watch_later'):
                            watch_later_response.menu_items[0].watch_later.click()
                            print("Added to Watch Later")
            
            # 操作完了後の待機
            page.wait_for_timeout(2000)
            
        except Exception as e:
            print(f"Error occurred: {str(e)}")

def main():
    video_url = "https://www.youtube.com/watch?v=rMHc-eZchG8"
    handle_youtube_save(video_url)

if __name__ == "__main__":
    main()
