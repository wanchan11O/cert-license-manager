# 証明書・ライセンス管理アプリ

FastAPI + SQLite + Jinja2 による最小構成の Web アプリ。  
証明書（ドメイン/発行者/有効期限）とライセンス（製品名/キー/有効期限）を管理し、
期限切れ・30日以内・正常を色分け表示します。

## 必要環境

- Python 3.10 以上

## セットアップと起動

```bash
# 1. 依存パッケージをインストール
pip install -r requirements.txt

# 2. 環境変数ファイルを準備
cp .env.example .env
# .env を開き SECRET_KEY を任意の長い文字列に変更する

# 3. 起動（.env を読み込んで起動）
# Windows (PowerShell)
$env:SECRET_KEY="your-secret-key"; $env:DB_PATH="app.db"; uvicorn main:app --reload

# Linux / macOS
export SECRET_KEY="your-secret-key" DB_PATH="app.db"
uvicorn main:app --reload
```

起動後、ブラウザで <http://localhost:8000> を開き「新規登録」からアカウントを作成してください。

## 環境変数

| 変数 | 説明 | デフォルト値 |
|---|---|---|
| `SECRET_KEY` | セッション Cookie の署名キー（**本番では必ず変更**） | `change-this-in-production` |
| `DB_PATH` | SQLite ファイルのパス | `app.db` |

> `SECRET_KEY` を設定せずに起動するとデフォルト値が使われます。本番環境では必ず安全な値に変更してください。

## 機能

- メール + パスワード認証（セッション Cookie）
- 証明書の CRUD（ドメイン / 発行者 / 有効期限）
- ライセンスの CRUD（製品名 / ライセンスキー / 有効期限）
- 有効期限の自動判定と色分け表示
  - 正常（30日超）— 緑
  - 30日以内 — 黄
  - 期限切れ — 赤

## ファイル構成

```
main.py          # FastAPI アプリ（ルート定義）
database.py      # SQLite 初期化・接続
templates/       # Jinja2 テンプレート
  base.html
  login.html
  register.html
  dashboard.html
  cert_form.html
  license_form.html
static/
  style.css
requirements.txt
.env.example
```
