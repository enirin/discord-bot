# **Game Server Management API Specification (v1.0.0)**

このドキュメントは、Discord Bot（SME Bot）がゲームサーバーを操作するために通信する、ローカルFlask APIの仕様書です。

## **🌐 サーバー情報**

* **Base URL**: http://localhost:5000 (デフォルト)

## **📍 エンドポイント**

### **1\. サーバー一覧の取得**

管理下にあるすべてのゲームサーバーの状態を取得します。

* **URL**: /list  
* **Method**: GET  
* **Response (200 OK)**:  
  {  
    "servers": \[  
      {  
        "name": "7dtd-server-01",  
        "status": "online",  
        "address": "192.168.1.10",  
        "stats": {  
          "players": "2/8",  
          "cpu": 12.5,  
          "memory": 4.2  
        },  
        "day": 14  
      }  
    \]  
  }

### **2\. サーバーの起動**

指定した識別名のサーバーを起動します。

* **URL**: /start/{server\_name}  
* **Method**: POST  
* **Parameters**:  
  * server\_name (string): 起動したいサーバーの名前  
* **Response (200 OK)**:  
  {  
    "success": true,  
    "message": "Server '7dtd-server-01' is starting...",  
    "server\_name": "7dtd-server-01"  
  }

* **Response (404 Not Found)**: サーバー名が存在しない場合

### **3\. サーバーの停止**

指定した識別名のサーバーに停止コマンドを送信します。

* **URL**: /stop/{server\_name}  
* **Method**: POST  
* **Parameters**:  
  * server\_name (string): 停止したいサーバーの名前  
* **Response (200 OK)**:  
  {  
    "success": true,  
    "message": "Server '7dtd-server-01' is stopping...",  
    "server\_name": "7dtd-server-01"  
  }

## **📋 データ構造 (Schemas)**

### **ServerStatus**

| フィールド | 型 | 説明 |
| :---- | :---- | :---- |
| name | string | サーバーの識別名 |
| status | string | online, offline, busy のいずれか |
| address | string | 接続用IPアドレス |
| day | integer | ゲーム内の経過日数 |
| stats.players | string | 現在のプレイヤー数 (例: "2/8") |
| stats.cpu | number | CPU使用率 (%) |
| stats.memory | number | メモリ使用量 (GB) |

