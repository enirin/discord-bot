import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  Play,
  Square,
  RefreshCw,
  Server,
  Users,
  Cpu,
  HardDrive,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  Settings,
  Globe,
  ShieldAlert,
  Info
} from 'lucide-react';

/**
 * ゲームサーバー管理ダッシュボード
 * フェーズ2: デバッグ機能とCORS対策ガイド付き
 */

const App = () => {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [actionLoading, setActionLoading] = useState({});
  const [notification, setNotification] = useState(null);

  // API接続先の設定
  const [apiUrl, setApiUrl] = useState('http://localhost:5000');
  const [showSettings, setShowSettings] = useState(false);

  // 通知を表示
  const showNotification = useCallback((message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  }, []);

  // サーバー一覧の取得
  const fetchServers = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000); // 3秒でタイムアウト

      const response = await fetch(`${apiUrl}/list`, {
        mode: 'cors',
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) throw new Error(`HTTPエラー: ${response.status}`);
      const data = await response.json();
      setServers(data.servers || []);
      setLastUpdated(new Date());
    } catch (err) {
      if (err.name === 'AbortError') {
        setError("接続タイムアウト: サーバーが応答していません。");
      } else {
        setError(`Failed to fetch: ${apiUrl} への接続に失敗しました。CORS設定またはMixed Content制限の可能性があります。`);
      }
      console.error('Fetch error details:', err);
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  // 定期更新
  useEffect(() => {
    fetchServers();
    const interval = setInterval(fetchServers, 15000); // 少し間隔を広げる
    return () => clearInterval(interval);
  }, [fetchServers]);

  // サーバー操作
  const handleAction = async (serverName, action) => {
    setActionLoading(prev => ({ ...prev, [serverName]: true }));
    try {
      const response = await fetch(`${apiUrl}/${action}/${serverName}`, {
        method: 'POST',
        mode: 'cors'
      });
      const data = await response.json();

      if (response.ok && data.success) {
        showNotification(data.message, 'success');
        setTimeout(fetchServers, 2000);
      } else {
        showNotification(data.message || '操作に失敗しました', 'error');
      }
    } catch (err) {
      showNotification('操作に失敗しました。ブラウザのコンソール(F12)を確認してください。', 'error');
    } finally {
      setActionLoading(prev => ({ ...prev, [serverName]: false }));
    }
  };

  const isHttps = window.location.protocol === 'https:';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-4 md:p-8">
      {/* Header */}
      <header className="max-w-6xl mx-auto mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500 flex items-center gap-3">
            <Server className="text-cyan-400" />
            Dedicated Game Server Dashboard
          </h1>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1">
            <p className="text-slate-400 flex items-center gap-2 text-sm">
              <Clock size={14} />
              最終更新: {lastUpdated.toLocaleTimeString()}
            </p>
            <p className="text-slate-500 flex items-center gap-2 text-sm">
              <Globe size={14} />
              URL: <span className="text-cyan-800 font-mono">{apiUrl}</span>
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-lg border transition-colors ${showSettings ? 'bg-cyan-600 border-cyan-400' : 'bg-slate-800 border-slate-700 hover:bg-slate-700'}`}
          >
            <Settings size={20} />
          </button>
          <button
            onClick={() => fetchServers()}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors border border-slate-700"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
            手動更新
          </button>
        </div>
      </header>

      {/* Connection Troubleshooting Guide */}
      {showSettings && (
        <div className="max-w-6xl mx-auto mb-8 p-6 bg-slate-900 border border-cyan-500/30 rounded-2xl animate-in fade-in slide-in-from-top-4">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Settings size={18} className="text-cyan-400" /> API接続設定とトラブルシュート
            </h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm text-slate-400">APIベースURL (Flaskサーバーのアドレス)</label>
                <input
                  type="text"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  placeholder="http://localhost:5000"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 focus:border-cyan-500 outline-none transition-colors font-mono"
                />
              </div>

              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
                  <ShieldAlert size={14} className="text-amber-500" /> ブラウザの制限を解除する
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  このダッシュボードはHTTPSで動いているため、HTTPのローカルAPIへの通信がブロックされる場合があります。
                </p>
                <div className="text-xs space-y-1 text-amber-200/80">
                  <p>1. ブラウザのアドレスバー右端の<strong>盾アイコン</strong>または<strong>鍵アイコン</strong>をクリック</p>
                  <p>2. 「サイトの設定」から<strong>「安全でないコンテンツ」を「許可」</strong>に変更</p>
                  <p>3. ページを再読み込みしてください</p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-cyan-950/20 border border-cyan-900/50 rounded-xl space-y-3">
                <h3 className="text-sm font-bold text-cyan-300 flex items-center gap-2">
                  <Info size={14} /> Flask側のCORS設定 (必須)
                </h3>
                <p className="text-xs text-slate-400">WSLターミナルで以下を実行し、コードを更新してください。</p>
                <pre className="text-[10px] bg-black/50 p-2 rounded border border-slate-800 text-cyan-400 overflow-x-auto">
                  {`pip install flask-cors\n\n# Python code:\nfrom flask_cors import CORS\napp = Flask(__name__)\nCORS(app)`}
                </pre>
              </div>
              <button
                onClick={() => { setShowSettings(false); fetchServers(); }}
                className="w-full bg-cyan-600 hover:bg-cyan-500 py-3 rounded-xl font-bold transition-all shadow-lg shadow-cyan-900/20"
              >
                保存して接続テスト
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && !showSettings && (
        <div className="max-w-6xl mx-auto mb-8 p-4 bg-red-900/20 border border-red-500/30 rounded-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 text-red-200">
          <div className="flex items-center gap-3">
            <AlertCircle className="flex-shrink-0 text-red-500" />
            <p className="text-sm font-medium">{error}</p>
          </div>
          <button
            onClick={() => setShowSettings(true)}
            className="text-xs bg-red-500/20 hover:bg-red-500/40 border border-red-500/50 px-4 py-1.5 rounded-full transition-colors font-bold whitespace-nowrap"
          >
            解決方法を確認
          </button>
        </div>
      )}

      {/* Notification Toast */}
      {notification && (
        <div className={`fixed bottom-8 right-8 z-50 p-4 rounded-xl shadow-2xl border flex items-center gap-3 animate-in slide-in-from-right duration-300 ${notification.type === 'success' ? 'bg-emerald-900 border-emerald-500 text-emerald-100' :
          notification.type === 'error' ? 'bg-red-900 border-red-500 text-red-100' : 'bg-blue-900 border-blue-500 text-blue-100'
          }`}>
          {notification.type === 'success' ? <CheckCircle2 /> : <AlertCircle />}
          <p className="font-medium">{notification.message}</p>
        </div>
      )}

      {/* Server Grid */}
      <main className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading && servers.length === 0 ? (
          Array(3).fill(0).map((_, i) => (
            <div key={i} className="h-64 bg-slate-900/50 rounded-2xl border border-slate-800 animate-pulse" />
          ))
        ) : (
          servers.map((server) => (
            <div key={server.name} className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden hover:border-slate-600 transition-all shadow-xl group">
              <div className="p-5 border-b border-slate-800 flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-white group-hover:text-cyan-400 transition-colors">{server.name}</h2>
                  <p className="text-slate-500 text-sm font-mono mt-1">{server.address}</p>
                </div>
                <div className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${server.status === 'online' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                  server.status === 'offline' ? 'bg-slate-500/10 text-slate-400 border border-slate-500/20' :
                    'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}>
                  <span className={`w-2 h-2 rounded-full ${server.status === 'online' ? 'bg-emerald-500 animate-pulse' :
                    server.status === 'offline' ? 'bg-slate-500' : 'bg-amber-500'
                    }`} />
                  {server.status}
                </div>
              </div>

              <div className="p-5 space-y-5">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-800/50 p-3 rounded-xl">
                    <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                      <Users size={14} /> プレイヤー
                    </div>
                    <div className="text-lg font-semibold text-white">{server.stats?.players || '0/0'}</div>
                  </div>
                  <div className="bg-slate-800/50 p-3 rounded-xl">
                    <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                      <Calendar size={14} /> ゲーム内日数
                    </div>
                    <div className="text-lg font-semibold text-white">Day {server.day || 0}</div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs px-1">
                      <span className="text-slate-400 flex items-center gap-1"><Cpu size={12} /> CPU</span>
                      <span className={(server.stats?.cpu || 0) > 80 ? 'text-red-400 font-bold' : 'text-slate-300'}>{server.stats?.cpu || 0}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ${(server.stats?.cpu || 0) > 80 ? 'bg-red-500' : 'bg-cyan-500'}`}
                        style={{ width: `${server.stats?.cpu || 0}%` }}
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs px-1">
                      <span className="text-slate-400 flex items-center gap-1"><HardDrive size={12} /> Memory</span>
                      <span className="text-slate-300">{server.stats?.memory || 0} GB</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 transition-all duration-500"
                        style={{ width: `${((server.stats?.memory || 0) / 16) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-4 bg-slate-800/30 flex gap-3">
                {server.status === 'offline' ? (
                  <button
                    onClick={() => handleAction(server.name, 'start')}
                    disabled={actionLoading[server.name]}
                    className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-xl font-bold transition-all shadow-lg shadow-emerald-900/20"
                  >
                    {actionLoading[server.name] ? <RefreshCw className="animate-spin" size={18} /> : <Play size={18} />}
                    サーバー起動
                  </button>
                ) : (
                  <button
                    onClick={() => handleAction(server.name, 'stop')}
                    disabled={actionLoading[server.name]}
                    className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-red-600 hover:bg-red-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-xl font-bold transition-all shadow-lg shadow-red-900/20"
                  >
                    {actionLoading[server.name] ? <RefreshCw className="animate-spin" size={18} /> : <Square size={18} />}
                    サーバー停止
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </main>

      <footer className="max-w-6xl mx-auto mt-12 pt-8 border-t border-slate-900 text-center text-slate-600 text-sm">
        <p>© 2026 Game Server Control Panel - Antigravity Phase 2</p>
      </footer>
    </div>
  );
};

export default App;