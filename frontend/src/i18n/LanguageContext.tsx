import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { translations } from './translations';

export type Language = 'es' | 'en';

interface LanguageContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const STORAGE_KEY = 'pantryvision_language';
const DEFAULT_LANGUAGE: Language = 'en';

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

/** Reads the persisted language preference from localStorage, falling back to the default. */
function getInitialLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'es' || stored === 'en') {
      return stored;
    }
  } catch {
    // localStorage unavailable (e.g. private browsing) — fall back to default
  }
  return DEFAULT_LANGUAGE;
}

/** Resolves a dot-notation key path (e.g. "navBar.upload") against a nested object. */
function resolveKey(source: unknown, key: string): string | undefined {
  const parts = key.split('.');
  let current: unknown = source;

  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = (current as Record<string, unknown>)[part];
    } else {
      return undefined;
    }
  }

  return typeof current === 'string' ? current : undefined;
}

/** Substitutes `{placeholder}` tokens in a string with values from params. */
function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, token) => {
    const value = params[token];
    return value !== undefined ? String(value) : match;
  });
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {
      // Ignore persistence failures — language switch still works for the session
    }
  }, [language]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
  };

  const t = (key: string, params?: Record<string, string | number>): string => {
    const resolved = resolveKey(translations[language], key);
    if (resolved === undefined) {
      // Never crash on a missing key — fall back to the key itself for visibility
      return key;
    }
    return interpolate(resolved, params);
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
