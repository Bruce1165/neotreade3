import { useCallback, useEffect, useState } from 'react';
import { Calendar, RefreshCw, AlertTriangle, X } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { getDataStatus, getTradingDay } from '../services/api';

export default function DateSelector({ onRefresh, loading = false }) {
  const { selectedDate, setSelectedDate } = useApp();
  const [tradingDayInfo, setTradingDayInfo] = useState(null);
  const [dataStatus, setDataStatus] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  const loadDataStatus = useCallback(() => {
    return getDataStatus()
      .then((payload) => {
        if (payload) setDataStatus(payload);
      })
      .catch(() => {
        return;
      });
  }, []);

  useEffect(() => {
    setDismissed(false);
    setTradingDayInfo(null);
    setDataStatus(null);
    
    getTradingDay(selectedDate)
      .then((data) => {
        if (data) setTradingDayInfo(data);
      })
      .catch(() => {
        return;
      });
    loadDataStatus();
  }, [loadDataStatus, selectedDate]);

  const now = new Date();
  const todayLocal = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

  const handleDateChange = (e) => {
    const nextValue = String(e.target.value || '').trim();
    if (!nextValue) {
      return;
    }
    if (nextValue > todayLocal) {
      setSelectedDate(todayLocal);
      return;
    }
    setSelectedDate(nextValue);
  };

  const isNonTradingDay = tradingDayInfo && tradingDayInfo.is_trading_day === false;
  const calendarCoveredUntil =
    tradingDayInfo?.calendar_covered_until || tradingDayInfo?.max_trading_day || null;
  const isCalendarStale =
    Boolean(calendarCoveredUntil && selectedDate > calendarCoveredUntil);
  const isTradingDayUnknown =
    Boolean(tradingDayInfo && tradingDayInfo.is_trading_day == null);
  const latestAvailableDate =
    dataStatus?.latest_available_date ||
    dataStatus?.latest_trade_date ||
    tradingDayInfo?.max_trading_day ||
    null;
  const isDataNotAvailable = Boolean(latestAvailableDate && selectedDate > latestAvailableDate);
  const showCalendarNotUpdated = Boolean(!dismissed && (isTradingDayUnknown || isCalendarStale));
  const showNonTradingDay = Boolean(!dismissed && !showCalendarNotUpdated && isNonTradingDay);
  const showDataNotAvailable = Boolean(
    !dismissed && !showCalendarNotUpdated && !showNonTradingDay && isDataNotAvailable
  );

  useEffect(() => {
    if (dismissed) return;
    if (!tradingDayInfo || tradingDayInfo.is_trading_day !== true) return;
    if (!latestAvailableDate) return;
    if (selectedDate <= latestAvailableDate) return;
    setSelectedDate(latestAvailableDate);
  }, [dismissed, latestAvailableDate, selectedDate, setSelectedDate, tradingDayInfo]);

  const handleSwitchToSuggested = () => {
    if (showDataNotAvailable && latestAvailableDate) {
      setSelectedDate(latestAvailableDate);
      return;
    }
    if (tradingDayInfo?.nearest_trading_day) {
      setSelectedDate(tradingDayInfo.nearest_trading_day);
    }
  };

  const handleRefresh = async () => {
    await loadDataStatus();
    if (onRefresh) {
      await onRefresh();
    }
  };

  return (
    <div className="space-y-3">
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Calendar size={20} className="text-gray-500" />
            <input
              type="date"
              value={selectedDate}
              max={todayLocal}
              onChange={handleDateChange}
              className="border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          {onRefresh && (
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
              刷新
            </button>
          )}
        </div>
      </div>

      {(showCalendarNotUpdated || showNonTradingDay || showDataNotAvailable) && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle size={20} className="text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <div className="font-medium text-amber-800">
              {showDataNotAvailable
                ? '所选日期暂无本地数据'
                : showCalendarNotUpdated
                ? '交易日历未更新'
                : '所选日期不是有效的交易日'}
            </div>
            <div className="text-sm text-amber-600 mt-1">
              {showDataNotAvailable ? (
                <>
                  本地最新数据日期为 <span className="font-semibold">{latestAvailableDate}</span>
                  ，当前选择 <span className="font-semibold">{selectedDate}</span> 暂无本地数据。可切换到最新可用日期继续使用。
                </>
              ) : showCalendarNotUpdated ? (
                <>
                  当前交易日历覆盖截至 <span className="font-semibold">{calendarCoveredUntil || '—'}</span>
                  ，无法判断 <span className="font-semibold">{selectedDate}</span> 是否为交易日。可先切换到最近交易日继续使用。
                </>
              ) : (
                <>
                  最近的一个交易日是 <span className="font-semibold">{tradingDayInfo.nearest_trading_day}</span>
                  {tradingDayInfo.max_trading_day && (
                    <span>（数据截至 {tradingDayInfo.max_trading_day}）</span>
                  )}
                </>
              )}
            </div>
            {(showDataNotAvailable && latestAvailableDate) || tradingDayInfo?.nearest_trading_day ? (
              <button
                onClick={handleSwitchToSuggested}
                className="mt-2 px-3 py-1.5 bg-amber-600 text-white text-sm rounded-lg hover:bg-amber-700 transition-colors"
              >
                切换到 {showDataNotAvailable ? latestAvailableDate : tradingDayInfo.nearest_trading_day}
              </button>
            ) : null}
          </div>
          <button
            onClick={() => setDismissed(true)}
            className="text-amber-400 hover:text-amber-600 flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>
      )}
    </div>
  );
}
