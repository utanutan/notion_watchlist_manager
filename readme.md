# Notion YouTube Watch Later Manager

## プロジェクトの概要
このプロジェクトは、YouTubeの「後で見る」リストをNotionのデータベースで効率的に管理するためのPythonツールです。

## ゴール・全体イメージ
### システム構成図
```mermaid
sequenceDiagram
    actor User
    participant YT as YouTube
    participant GT as Google Takeout
    participant Py1 as get_WL_from_youtube.py
    participant ND as Notion DB
    participant Py2 as delete_WL_from_youtube.py
    participant API as YouTube Data API

    %% データ取得フロー
    User->>GT: 1. 後で見るリストのエクスポート要求
    GT->>YT: 2. データ取得要求
    YT-->>GT: 3. 後で見るリスト
    GT-->>User: 4. CSVファイル

    %% Notionへの登録
    User->>Py1: 5. CSVファイル渡す
    Py1->>ND: 6. 動画情報を登録
    ND-->>User: 7. 登録完了

    %% 削除フロー
    User->>ND: 8. 不要な動画にチェック
    User->>Py2: 9. 削除実行
    Py2->>ND: 10. チェック済み動画取得
    ND-->>Py2: 11. 削除対象リスト
    Py2->>API: 12. 動画削除リクエスト
    API->>YT: 13. 動画削除実行
    YT-->>API: 14. 削除完了
    API-->>Py2: 15. 削除結果
    Py2-->>User: 16. 完了通知
```

### システム構成
このシステムは以下の要素で構成されています：

1. Google Takeout
   - YouTubeの「後で見る」リストをCSVでダウンロード

2. YouTube Data API
   - 動画の削除機能を提供

3. Notion API
   - データベースへの動画情報の登録
   - タイトルとリンクを管理
  
4. Notionのデータベース
   - 不要な動画に対してチェックをつける。

5. Pythonスクリプト
   - `get_WL_from_youtube.py`: YouTubeから動画情報を取得しNotionに登録
   - `delete_WL_from_youtube.py`: YouTubeの「後で見る」リストから動画を削除



## 準備手順

### 1. Google TakeoutでCSVをダウンロード
1. Google Takeoutを開きます。
2. 「YouTubeとYouTube Music」だけを選択します。
3. 「すべてのYouTubeデータを含む」設定から「プレイリスト」のみを選択します。
4. 指示に従いデータをエクスポートし、CSVを取得します。

### 2. Notionのデータベースを作成
1. 新しいNotionデータベースを作成します。
2. 以下のプロパティを追加します：
   - **Name**（タイトル型）
   - **Link**（URL型）
3. Notion Integrationを作成し、APIトークンを取得します。
4. データベースIDを取得します。

### 3. 環境変数の設定
1. プロジェクトのルートディレクトリに `.env` ファイルを作成します。
2. 以下の環境変数を設定します：
   ```bash
   NOTION_API_TOKEN="your_notion_api_token"
   NOTION_DATABASE_ID="your_notion_database_id"
   CLIENT_SECRET_FILE="client_secret.json"  # デフォルト値
   CSV_FILE="Watchlater.csv"               # デフォルト値
   ```
   - `NOTION_API_TOKEN`: Notion Integrationから取得したAPIトークン
   - `NOTION_DATABASE_ID`: NotionデータベースのID
   - `CLIENT_SECRET_FILE`: Google Cloud ConsoleからダウンロードしたOAuthクライアントIDのJSONファイル名
   - `CSV_FILE`: Google Takeoutからダウンロードした後で見るリストのCSVファイル名

### 4. Pythonスクリプトの準備
1. **Python 3.x**をインストールします。
2. 必要なライブラリをインストールします：
   ```bash
   pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client requests python-dotenv
   ```

### 5. Google Cloud Consoleで以下を設定します：
- プロジェクトを作成。
- YouTube Data APIを有効化。
- OAuth 2.0クライアントIDを作成し、`.env`で指定した名前（デフォルト: `client_secret.json`）として保存します。

## 使い方

### Notionに登録する
1. Google TakeoutからYouTubeの「後で見る」リストをCSVでダウンロード
2. `get_WL_from_youtube.py`: YouTubeから動画情報を取得しNotionに登録
   ```bash
   python get_WL_from_youtube.py
   ```

### Notionに登録された動画を削除する
1. Notionの画面から不要な動画にチェックをつける
2. `delete_WL_from_youtube.py`を実行しYouTubeの「後で見る」リストから動画を削除
   ```bash
   python delete_WL_from_youtube.py
   ```