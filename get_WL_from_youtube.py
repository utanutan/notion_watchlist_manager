import csv
import logging
import os
from dotenv import load_dotenv

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import requests

# Load environment variables
load_dotenv()

# ------------------ 設定項目 ------------------
# 1. OAuthクライアントIDのJSONファイル
CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_FILE", "client_secret.json")

# 2. YouTube Data APIのスコープ
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# 3. CSVファイル
CSV_FILE = os.getenv("CSV_FILE", "Watchlater.csv")

# 4. NotionのAPIトークンとデータベースID
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# 5. Notionデータベースのプロパティ名
PROPERTY_TITLE = "Name"  # Title型
PROPERTY_LINK = "Link"   # URL型
# ---------------------------------------------

# ログの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def authenticate_youtube():
    """
    OAuth 2.0でYouTube Data APIにアクセスするための認証を行い、
    認証済みのYouTubeクライアントインスタンスを返す。
    """
    logger.info("Starting OAuth 2.0 authentication for YouTube...")

    creds = None
    if os.path.exists("token.json"):
        logger.info("Found existing token.json, loading credentials...")
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            logger.info("No valid credentials. Running local server flow...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)

        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())
            logger.info("Saved new credentials to token.json.")

    youtube = build("youtube", "v3", credentials=creds)
    logger.info("Successfully built YouTube client.")
    return youtube


def get_video_title(video_id: str, youtube):
    """
    YouTubeクライアントと動画IDを使ってタイトルを取得する。
    返り値: 文字列（タイトル） / 失敗時は None
    """
    logger.info(f"Fetching snippet for video_id='{video_id}'")
    try:
        response = youtube.videos().list(
            part="snippet",
            id=video_id
        ).execute()

        items = response.get("items", [])
        if not items:
            logger.warning(f"No snippet found for video_id='{video_id}'")
            return None

        snippet = items[0].get("snippet", {})
        title = snippet.get("title", "")
        logger.info(f"Success: title retrieved for video_id='{video_id}'")
        return title
    except Exception as e:
        logger.exception(f"Exception while fetching title: {str(e)}")
        return None


def create_notion_page(title: str, link: str):
    """
    Notionのデータベースに「タイトル・リンク」のページを作成する。
    ※ descriptionは扱わない。
    """
    logger.info(f"Creating a new page in Notion for title='{title}'")
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # Notion DBのプロパティをセット
    data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            PROPERTY_TITLE: {
                "title": [
                    {"text": {"content": title}}
                ]
            },
            PROPERTY_LINK: {
                "url": link
            }
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code in (200, 201):
            logger.info(f"Notion page created successfully: title='{title}'")
        else:
            logger.error(
                f"Failed to create page in Notion. Status: {resp.status_code}, "
                f"Response: {resp.text}"
            )
    except Exception as e:
        logger.exception(f"Exception while creating Notion page: {str(e)}")


def main():
    logger.info("Starting application...")

    # 1. YouTube OAuth認証 → YouTubeクライアント取得
    youtube = authenticate_youtube()

    # 2. CSVファイルを読み込み、動画IDごとにタイトル・リンクを取得 → Notionにアップロード
    try:
        with open(CSV_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # ヘッダを読み飛ばす

            index = 1
            for row in reader:
                if len(row) < 1:
                    logger.warning(f"Row {index} is empty or invalid: {row}")
                    continue

                video_id = row[0]
                timestamp = row[1] if len(row) > 1 else ""

                logger.info(f"Processing row {index} - video_id='{video_id}'")

                # タイトルを取得
                title = get_video_title(video_id, youtube)
                if title:
                    # リンクを組み立て
                    link = f"https://www.youtube.com/watch?v={video_id}"

                    # コンソール出力
                    print(f"{index}. タイトル: {title}")
                    print(f"   リンク: {link}")
                    print(f"   (追加日時: {timestamp})")
                    print()

                    # Notionへアップロード（descriptionは無し）
                    create_notion_page(title, link)
                else:
                    logger.warning(f"Failed to get title for video_id='{video_id}'")

                index += 1

        logger.info("Finished processing CSV file.")
    except FileNotFoundError:
        logger.error(f"CSV file not found: '{CSV_FILE}'")
    except Exception as e:
        logger.exception(f"An error occurred while reading the CSV file: {str(e)}")

    logger.info("Application completed successfully.")


if __name__ == "__main__":
    main()
