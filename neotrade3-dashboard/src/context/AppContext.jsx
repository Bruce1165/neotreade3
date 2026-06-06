import { createContext, useContext, useState, useCallback, useEffect } from 'react';

import { getTradingDay } from '../services/api';

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

  useEffect(() => {
    let alive = true;

    async function bootstrap() {
      try {
        const info = await getTradingDay(selectedDate);
        if (!alive) return;
        if (info && info.is_trading_day === false && typeof info.nearest_trading_day === 'string' && info.nearest_trading_day) {
          setSelectedDate(info.nearest_trading_day);
        }
      } catch {
        if (!alive) return;
      } finally {
        if (!alive) return;
        setBootstrapped(true);
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
