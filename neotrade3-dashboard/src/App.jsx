import { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { 
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

function App() {
  return (
    <AppProvider>
      <Router>
        <div className="flex min-h-screen bg-gray-50">
          <Sidebar />
          <div className="flex-1 ml-64">
            <Header />
            <GlobalBanner />
            <main className="p-6">
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/market-intelligence" element={<MarketIntelligence />} />
                <Route path="/screeners" element={<Screeners />} />
                <Route path="/stock-check" element={<StockCheck />} />
                <Route path="/lowfreq" element={<Lowfreq />} />
              </Routes>
            </main>
          </div>
        </div>
      </Router>
    </AppProvider>
  );
}

export default App;
