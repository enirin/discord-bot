# Game Server Management MCP 連携ハンドオフ

## 背景

Game-Server-Management-API 側で、ゲームサーバー管理用 MCP server の運用契約と IF 仕様が更新されています。

- transport: streamable HTTP
- 既定接続先: http://127.0.0.1:8000/mcp
- 読み取り系 tool は自動実行可
- IP プレイヤー名マッピング tool が追加済み
- start_server / stop_server は確認必須
- /tell 通知は当面そのまま維持

Discord bot 側は、専用 HTTP client ではなく MCP host として実装してください。

## このフェーズで bot 側がやること

1. MCP server に streamable HTTP で接続する
2. 読み取り系 tool を AI エージェントから利用可能にする
3. start_server / stop_server は確認フローを挟んでから実行する
4. IP プレイヤー名参照・一覧・登録を利用可能にする
5. 将来の Discord role 制御を差し込める構造にしておく

## 接続先

- 既定 URL: http://127.0.0.1:8000/mcp
- transport: streamable HTTP

接続先 URL は bot 側設定として外出ししてください。

## 初期公開 tool

- list_servers
- get_server_status
- get_server_maintenance_notes
- get_ip_player_name
- list_ip_player_names
- register_ip_player_name
- start_server
- stop_server

## 初期公開 resource

- servers://catalog
- servers://status
- servers://status/{server_id}
- games://maintenance/{game}

## bot 側の必須運用ルール

- list_servers / get_server_status / get_server_maintenance_notes は自動実行可
- get_ip_player_name / list_ip_player_names / register_ip_player_name も自動実行可
- start_server / stop_server は即実行しない
- 操作対象と操作内容を明示して確認を返す
- 明示的な肯定応答後のみ実行する
- 否定応答またはタイムアウト時は実行しない
- タイムアウト後は「もう一度依頼してください」と案内する

推奨確認文面:

- `craftopia` を起動します。実行しますか？
- `craftopia` を停止します。実行しますか？

## 参照先の正本

接続契約:

- https://github.com/enirin/Game-Server-Management-API/blob/66c4915c7bf1d090605de7a84a2718da4b150933/docs/mcp-bot-connection-contract.md

IF 仕様:

- https://github.com/enirin/Game-Server-Management-API/blob/66c4915c7bf1d090605de7a84a2718da4b150933/docs/mcp-interface-spec.md

移行計画:

- https://github.com/enirin/Game-Server-Management-API/blob/2932683f37076e31b6a69c50d2ec76a79dc66bb1/docs/mcp-migration-plan.md

ADR:

- https://github.com/enirin/Game-Server-Management-API/blob/2932683f37076e31b6a69c50d2ec76a79dc66bb1/docs/adr/0001-mcp-based-game-server-management.md

API 側の詳細設計:

- https://github.com/enirin/Game-Server-Management-API/blob/2932683f37076e31b6a69c50d2ec76a79dc66bb1/docs/mcp-phase1-detailed-design.md

API 側の起動と設定:

- https://github.com/enirin/Game-Server-Management-API/blob/2932683f37076e31b6a69c50d2ec76a79dc66bb1/README.md

## API 側の確認済み事項

- MCP server は起動確認済み
- streamable HTTP で initialize 成功済み
- list_tools 成功済み
- list_resources 成功済み
- list_servers 呼び出し成功済み

## bot 側の実装順序

1. MCP 接続設定を追加する
2. list_servers / get_server_status を呼べるようにする
3. get_server_maintenance_notes を参照できるようにする
4. get_ip_player_name / list_ip_player_names / register_ip_player_name を利用できるようにする
5. start_server / stop_server の確認フローを実装する

## 補足

- GitHub リンクは commit 固定 permalink を使っています
- 仕様変更時はブランチ先頭リンクではなく permalink を更新してください