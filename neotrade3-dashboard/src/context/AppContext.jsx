import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';

import { getDataStatus, getTradingDay } from '../services/api';

const AppContext = createContext();

export function AppProvider({ children }) {
  const [selectedDate, setSelectedDate] = useState(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  });
  
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState({});
  const [errors, setErrors] = useState({});
  const [bootstrapped, setBootstrapped] = useState(false);
  const bootstrapDateRef = useRef(selectedDate);

  useEffect(() => {
    let alive = true;

    async function bootstrap() {
      try {
        const [dayInfo, statusInfo] = await Promise.all([
          getTradingDay(bootstrapDateRef.current),
          getDataStatus(),
        ]);
        if (!alive) return;
        if (
          dayInfo &&
          dayInfo.is_trading_day === false &&
          typeof dayInfo.nearest_trading_day === 'string' &&
          dayInfo.nearest_trading_day
        ) {
          setSelectedDate(dayInfo.nearest_trading_day);
          return;
        }

        const latestAvailableDate =
          (statusInfo && (statusInfo.latest_available_date || statusInfo.latest_trade_date)) ||
          (dayInfo && dayInfo.max_trading_day) ||
          null;
        if (
          latestAvailableDate &&
          dayInfo &&
          dayInfo.is_trading_day === true &&
          typeof latestAvailableDate === 'string' &&
          latestAvailableDate &&
          bootstrapDateRef.current > latestAvailableDate
        ) {
          setSelectedDate(latestAvailableDate);
        }
      } catch {
        if (!alive) return;
      } finally {
        if (alive) {
          setBootstrapped(true);
        }
      }
    }

    bootstrap();
    return () => {
      alive = false;
    };
  }, []);

  const setLoadingState = useCallback((key, isLoading) => {
    setLoading(prev => ({ ...prev, [key]: isLoading }));
  }, []);

  const setErrorState = useCallback((key, error) => {
    setErrors(prev => ({ ...prev, [key]: error }));
  }, []);

  const clearError = useCallback((key) => {
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[key];
      return newErrors;
    });
  }, []);

  const value = {
    selectedDate,
    setSelectedDate,
    apiKey,
    setApiKey,
    loading,
    setLoadingState,
    errors,
    setErrorState,
    clearError,
  };

  return <AppContext.Provider value={value}>{bootstrapped ? children : null}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
