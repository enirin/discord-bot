from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 全エンドポイントにCORSを許可

# モックデータ
servers_db = {
    "7dtd-server-01": {
        "name": "7dtd-server-01",
        "status": "online",
        "address": "192.168.1.10",
        "server_aliases": ["7d2d", "7days", "7dtd"],
        "stats": {
            "players": "2/8",
            "cpu": 12.5,
            "memory": 4.2
        },
        "day": 14
    },
    "palworld-server": {
        "name": "palworld-server",
        "status": "offline",
        "address": "192.168.1.11",
        "server_aliases": ["palworld", "パルワールド"],
        "stats": {
            "players": "0/32",
            "cpu": 0.0,
            "memory": 0.0
        },
        "day": 0
    },
    "valheim-server": {
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
}

@app.route('/list', methods=['GET'])
def list_servers():
    return jsonify({"servers": list(servers_db.values())})

@app.route('/start/<server_name>', methods=['POST'])
def start_server(server_name):
    if server_name in servers_db:
        if servers_db[server_name]["status"] == "online":
            return jsonify({
                "success": False,
                "message": f"Server '{server_name}' is already online.",
                "server_name": server_name
            }), 200
        
        servers_db[server_name]["status"] = "online"
        servers_db[server_name]["stats"]["cpu"] = 5.0
        servers_db[server_name]["stats"]["memory"] = 2.0
        return jsonify({
            "success": True,
            "message": f"Server '{server_name}' is starting...",
            "server_name": server_name
        }), 200
    else:
        return jsonify({
            "success": False,
            "message": f"Server '{server_name}' not found."
        }), 404

@app.route('/stop/<server_name>', methods=['POST'])
def stop_server(server_name):
    if server_name in servers_db:
        if servers_db[server_name]["status"] == "offline":
             return jsonify({
                "success": False,
                "message": f"Server '{server_name}' is already offline.",
                "server_name": server_name
            }), 200
           
        servers_db[server_name]["status"] = "offline"
        servers_db[server_name]["stats"]["players"] = "0/X"
        servers_db[server_name]["stats"]["cpu"] = 0.0
        servers_db[server_name]["stats"]["memory"] = 0.0
        return jsonify({
            "success": True,
            "message": f"Server '{server_name}' is stopping...",
            "server_name": server_name
        }), 200
    else:
        return jsonify({
            "success": False,
            "message": f"Server '{server_name}' not found."
        }), 404

if __name__ == '__main__':
    print("Starting Mock Game Server API on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
