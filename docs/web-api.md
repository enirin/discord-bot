# Web API

Bot 起動中は、外部システム連携用の HTTP エンドポイントを提供します。

## Base settings

ホストとポートは `config.yaml` の以下で制御します。

```yaml
web_endpoint_host: "127.0.0.1"
web_endpoint_port: 5050
web_endpoint_token:
```

`web_endpoint_token` を設定した場合、すべてのエンドポイントで `X-Send-Token` ヘッダによる認証が必要です。

## POST /tell

AI を通して Discord チャンネルへ通知したい場合に使います。

### Request body

```json
{
  "prompt": "システム情報: 監視サーバーからの通知です。現在CPU使用率が高めです。ユーザーへ案内してください。",
  "channel_id": 123456789012345678
}
```

### Fields

* `prompt`: 必須。AI に渡す文字列
* `channel_id`: 任意。Discord の送信先チャンネル ID。未指定時は `config.yaml` の `channel_ids` の先頭を使用

### Behavior

* AI 応答を生成して Discord に投稿します
* `channel_id` は JSON の整数値で渡してください

### Success response

```json
{
  "success": true,
  "response": "...AI generated response..."
}
```

### Error responses

* `400 invalid json`
* `400 prompt is required`
* `400 channel_id must be integer (JSON number)`
* `401 unauthorized`
* `404 failed to fetch channel: ...`
* `500` AI 応答生成失敗

### Example

```bash
curl -X POST "http://127.0.0.1:5050/tell" \
  -H "Content-Type: application/json" \
  -H "X-Send-Token: <token>" \
  -d '{"prompt":"システム情報: 監視通知です。サーバー負荷が高めです。案内してください。","channel_id":123456789012345678}'
```

## POST /catalog/game-servers

ゲーム管理アプリ側でサーバー構成や状態の元データが更新された直後に、Bot のゲームサーバーカタログを即時更新したい場合に使います。

このエンドポイントは Discord へ投稿しません。内部で `/list` を再取得し、catalog repository のキャッシュを更新するだけです。

### Request body

body は不要です。JSON を送らなくても利用できます。

### Behavior

* Bot がゲーム管理 API の `/list` を再取得します
* 成功時は最新 `servers` と `source: "network"` を返します
* Discord には何も送信しません

### Success response

```json
{
  "success": true,
  "servers": [
    {
      "name": "valheim-server",
      "status": "online",
      "address": "192.168.1.12",
      "server_aliases": ["valheim", "ヴァルヘイム"],
      "stats": {
        "players": "3/10",
        "cpu": 9.8,
        "memory": 3.1
      },
      "day": 42
    }
  ],
  "source": "network"
}
```

### Error responses

* `401 unauthorized`
* `500 game_server_catalog_repository is not configured`
* `500` `/list` 再取得失敗時の upstream error

### Example

```bash
curl -X POST "http://127.0.0.1:5050/catalog/game-servers" \
  -H "X-Send-Token: <token>"
```

## GET /catalog/game-servers

現在のゲームサーバーカタログキャッシュをそのまま取得したい場合に使います。

このエンドポイントは `/list` を再取得しません。現在保持しているキャッシュだけを返します。

### Behavior

* Bot 内部の catalog repository から現在のキャッシュを返します
* キャッシュが未作成なら `404` を返します
* Discord には何も送信しません

### Success response

```json
{
  "success": true,
  "servers": [
    {
      "name": "valheim-server",
      "status": "online",
      "address": "192.168.1.12",
      "server_aliases": ["valheim", "ヴァルヘイム"],
      "stats": {
        "players": "3/10",
        "cpu": 9.8,
        "memory": 3.1
      },
      "day": 42
    }
  ],
  "source": "cache"
}
```

### Error responses

* `401 unauthorized`
* `404 game server catalog cache is empty`
* `500 game_server_catalog_repository is not configured`

### Example

```bash
curl -X GET "http://127.0.0.1:5050/catalog/game-servers" \
  -H "X-Send-Token: <token>"
```