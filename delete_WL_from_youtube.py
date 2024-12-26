import os
import logging
import requests
from dotenv import load_dotenv
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Load environment variables
load_dotenv()

# ----------------- Notion 設定 ------------------
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_VERSION = "2022-06-28"
DELETE_PROPERTY_NAME = "delete"    # チェックボックス型プロパティ
VIDEOID_PROPERTY_NAME = "Link"     # 動画URLを格納しているプロパティ
# ----------------------------------------------

# ----------------- YouTube 設定 -----------------
CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_FILE", "client_secret.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_FILE = "token.json"
# ----------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def authenticate_youtube():
    """YouTube Data APIにOAuth 2.0で認証し、クライアントを返す。"""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            logger.info("No valid credentials -> Running local server flow...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
            logger.info(f"Saved credentials to {TOKEN_FILE}")

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    logger.info("Successfully authenticated with YouTube.")
    return youtube

def remove_from_watch_later(youtube, video_id):
    """
    YouTubeの「あとで見る」リストから指定した動画を削除する

    Args:
        youtube: YouTube API client
        video_id (str): 削除対象の動画ID

    Returns:
        bool: 削除に成功した場合はTrue、失敗した場合はFalse
    """
    try:
        # プレイリストアイテムを検索
        request = youtube.playlistItems().list(
            part="id",
            playlistId="WL",
            videoId=video_id
        )
        response = request.execute()

        items = response.get("items", [])
        if not items:
            logger.warning(f"Video '{video_id}' not found in Watch Later playlist")
            return False

        # プレイリストアイテムを削除
        playlist_item_id = items[0]["id"]
        youtube.playlistItems().delete(
            id=playlist_item_id
        ).execute()

        logger.info(f"Successfully removed video '{video_id}' from Watch Later playlist")
        return True

    except googleapiclient.errors.HttpError as e:
        logger.error(f"Failed to delete video '{video_id}': {e}")
        return False

def update_notion_delete_flag(page_id, delete_flag=False):
    """
    Notionのページの delete フラグを更新する

    Args:
        page_id (str): 更新対象のページID
        delete_flag (bool): 設定する値（デフォルトはFalse）

    Returns:
        bool: 更新に成功した場合はTrue、失敗した場合はFalse
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    data = {
        "properties": {
            DELETE_PROPERTY_NAME: {
                "checkbox": delete_flag
            }
        }
    }

    try:
        response = requests.patch(url, headers=headers, json=data)
        if response.status_code == 200:
            logger.info(f"Successfully updated delete flag to {delete_flag} for page {page_id}")
            return True
        else:
            logger.error(f"Failed to update Notion page {page_id}: {response.status_code}, {response.text}")
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
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
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
            title_prop = props.get("Title", props.get("Name", {}))
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
    logger.info("Starting removal process from Notion to YouTube's Watch Later.")

    # 1. Notionから「delete == true」な項目を取得
    items = query_notion_delete_items()
    if not items:
        logger.info("No items found with delete == true.")
        return

    # 削除対象の動画一覧を詳細にログ出力
    logger.info(f"Found {len(items)} items to delete:")
    for i, item in enumerate(items, 1):
        logger.info(f"{i}. Title: {item['title']}")
        logger.info(f"   Video ID: {item['video_id']}")
        logger.info(f"   Page ID: {item['page_id']}")

    # 2. YouTubeにOAuth認証
    youtube = authenticate_youtube()

    # 3. 各アイテムについて「あとで見る」から削除し、Notionを更新
    for entry in items:
        vid = entry["video_id"]
        page_id = entry["page_id"]
        
        # Watch Laterから削除を試みる
        removal_result = remove_from_watch_later(youtube, vid)
        
        # 削除の成功/失敗に関わらず、deleteフラグをfalseに更新
        # （見つからない場合も、既に削除されているということなのでフラグを更新）
        update_notion_delete_flag(page_id, False)

    logger.info("Completed removal process.")

if __name__ == "__main__":
    main()
