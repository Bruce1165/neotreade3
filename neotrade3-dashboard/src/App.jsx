import { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { 
  AlertTriangle,
  LayoutDashboard, 
  Filter, 
  Search, 
  TrendingUp,
  Target,
} from 'lucide-react';
import Overview from './pages/Overview';
import Screeners from './pages/Screeners';
import StockCheck from './pages/StockCheck';
import Lowfreq from './pages/Lowfreq';
import LowfreqBacktestReport from './pages/LowfreqBacktestReport';
import MarketIntelligence from './pages/MarketIntelligence';
import { AppProvider } from './context/AppContext';
import { getDataStatus } from './services/api';

function Sidebar() {
  const location = useLocation();
  
  const navItems = [
    { path: '/', icon: LayoutDashboard, label: '今日总览' },
    { path: '/market-intelligence', icon: Target, label: '主线审阅' },
    { path: '/lowfreq', icon: TrendingUp, label: '低频交易' },
    { path: '/screeners', icon: Filter, label: '筛选器' },
    { path: '/stock-check', icon: Search, label: '单股核验' },
  ];

  return (
    <aside className="w-64 bg-white border-r border-gray-200 min-h-screen fixed left-0 top-0">
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-[25px] font-bold text-gray-900">NeoTrade3</h1>
        <p className="text-sm text-gray-500 mt-1">量化选股控制台</p>
      </div>
      
      <nav className="p-4">
        <div className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive 
                    ? 'bg-blue-50 text-blue-700' 
                    : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <Icon size={20} />
                <span className="font-medium">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}

function Header() {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">量化选股控制台</h2>
          <p className="text-sm text-gray-500">团队控制台：审阅 / 监控 / 复盘</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-500">
            API: <span className="text-gray-700 font-medium">本地模式</span>
          </div>
        </div>
      </div>
    </header>
  );
}

function isEnvironmentUnavailable(apiError) {
  const code = String(apiError?.code || '').trim();
  const message = String(apiError?.message || '').trim();
  return (
    code === 'api_unreachable' ||
    code === 'api_timeout' ||
    message.includes('后端不可达') ||
    message.includes('请求超时')
  );
}

function GlobalBanner() {
  const [tushare, setTushare] = useState(null);

  useEffect(() => {
    let alive = true;
    let timerId = null;

    async function tick() {
      try {
        const status = await getDataStatus();
        if (!alive) return;
        setTushare(status && status.tushare ? status.tushare : null);
      } catch {
        if (!alive) return;
        setTushare(null);
      } finally {
        if (alive) {
          timerId = setTimeout(tick, 60000);
        }
      }
    }

    tick();
    return () => {
      alive = false;
      if (timerId) clearTimeout(timerId);
    };
  }, []);

  const creditInsufficient =
    tushare && typeof tushare.credit_insufficient === 'boolean' ? tushare.credit_insufficient : false;

  if (!creditInsufficient) return null;

  const lastAt = tushare.last_credit_insufficient_at || 'unknown';
  const lastApi = tushare.last_credit_insufficient_api || 'unknown';
  const lastOkAt = tushare.last_tushare_ok_at || null;
  const lastOkApi = tushare.last_tushare_ok_api || null;

  return (
    <div className="bg-yellow-50 border-b border-yellow-200 px-6 py-3">
      <div className="text-sm text-yellow-900">
        <span className="font-semibold">Tushare 黄旗：</span>
        <span>检测到 Tushare 积分不足，日线主源可能受影响。</span>
        <span className="ml-3">last_insufficient={lastAt}</span>
        <span className="ml-3">api={lastApi}</span>
        {lastOkAt ? <span className="ml-3">last_ok={lastOkAt}</span> : null}
        {lastOkApi ? <span className="ml-3">last_ok_api={lastOkApi}</span> : null}
      </div>
    </div>
  );
}

function GlobalApiErrorBanner() {
  const [apiError, setApiError] = useState(null);

  useEffect(() => {
    function handleApiError(event) {
      const detail = event?.detail || {};
      const message = String(detail.message || '').trim() || '请求失败';
      const endpoint = String(detail.endpoint || '').trim();
      const status = detail.status == null ? null : String(detail.status);
      const code = String(detail.code || '').trim();
      const happenedAt = String(detail.happenedAt || '').trim();
      setApiError({
        message,
        endpoint,
        status,
        code,
        happenedAt,
      });
    }

    window.addEventListener('neotrade3:api-error', handleApiError);
    return () => window.removeEventListener('neotrade3:api-error', handleApiError);
  }, []);

  if (!apiError) return null;

  const environmentUnavailable = isEnvironmentUnavailable(apiError);

  return (
    <div className={`${environmentUnavailable ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200'} border-b px-6 py-3`}>
      <div className="flex items-start justify-between gap-4">
        <div className={`flex items-start gap-3 text-sm ${environmentUnavailable ? 'text-amber-900' : 'text-red-900'}`}>
          <AlertTriangle size={18} className="mt-0.5 flex-shrink-0" />
          <div className="space-y-1">
            <div>
              <span className="font-semibold">{environmentUnavailable ? '开发环境未连接：' : '接口失败告警：'}</span>
              <span>
                {environmentUnavailable
                  ? '本地 API 服务暂未连接，页面会先展示占位信息。'
                  : apiError.message}
              </span>
            </div>
            {environmentUnavailable ? (
              <div className="text-xs text-amber-800">
                请先启动后端服务或检查本地代理配置。
                {(apiError.endpoint || apiError.status || apiError.code || apiError.happenedAt) ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-amber-900 font-medium">查看详细信息</summary>
                    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
                      {apiError.endpoint ? <span>最近请求：{apiError.endpoint}</span> : null}
                      {apiError.status ? <span>状态码：{apiError.status}</span> : null}
                      {apiError.code ? <span>错误编码：{apiError.code}</span> : null}
                      {apiError.happenedAt ? <span>记录时间：{apiError.happenedAt}</span> : null}
                    </div>
                  </details>
                ) : null}
              </div>
            ) : (
              (apiError.endpoint || apiError.status || apiError.code || apiError.happenedAt) ? (
                <details className="text-xs text-red-800">
                  <summary className="cursor-pointer text-red-900 font-medium">查看详细信息</summary>
                  <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
                    {apiError.endpoint ? <span>最近请求：{apiError.endpoint}</span> : null}
                    {apiError.status ? <span>状态码：{apiError.status}</span> : null}
                    {apiError.code ? <span>错误编码：{apiError.code}</span> : null}
                    {apiError.happenedAt ? <span>记录时间：{apiError.happenedAt}</span> : null}
                  </div>
                </details>
              ) : null
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setApiError(null)}
          className={`text-xs font-medium ${environmentUnavailable ? 'text-amber-800 hover:text-amber-900' : 'text-red-800 hover:text-red-900'}`}
        >
          关闭
        </button>
      </div>
    </div>
  );
}

function App() {
  return (
    <AppProvider>
      <Router>
        <div className="flex min-h-screen bg-gray-50">
          <Sidebar />
          <div className="flex-1 ml-64">
            <Header />
            <GlobalBanner />
            <GlobalApiErrorBanner />
            <main className="p-6">
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/market-intelligence" element={<MarketIntelligence />} />
                <Route path="/screeners" element={<Screeners />} />
                <Route path="/stock-check" element={<StockCheck />} />
                <Route path="/lowfreq" element={<Lowfreq />} />
                <Route path="/lowfreq/backtest-reports/:reportId" element={<LowfreqBacktestReport />} />
              </Routes>
            </main>
          </div>
        </div>
      </Router>
    </AppProvider>
  );
}

export default App;
