import './NavBar.css';
import { useLanguage } from '../../i18n/LanguageContext';

export type AppView = 'upload' | 'table' | 'inventory';

export interface NavBarProps {
  activeView: AppView;
  onSelectView: (view: AppView) => void;
}

export function NavBar({ activeView, onSelectView }: NavBarProps) {
  const { t, language, setLanguage } = useLanguage();

  return (
    <nav className="nav-bar" data-testid="nav-bar">
      <button
        type="button"
        className={`nav-bar__tab ${activeView === 'upload' ? 'nav-bar__tab--active' : ''}`}
        onClick={() => onSelectView('upload')}
        data-testid="nav-upload-btn"
        aria-current={activeView === 'upload' ? 'page' : undefined}
      >
        {t('navBar.upload')}
      </button>
      <button
        type="button"
        className={`nav-bar__tab ${activeView === 'table' ? 'nav-bar__tab--active' : ''}`}
        onClick={() => onSelectView('table')}
        data-testid="nav-table-btn"
        aria-current={activeView === 'table' ? 'page' : undefined}
      >
        {t('navBar.table')}
      </button>
      <button
        type="button"
        className={`nav-bar__tab ${activeView === 'inventory' ? 'nav-bar__tab--active' : ''}`}
        onClick={() => onSelectView('inventory')}
        data-testid="nav-inventory-btn"
        aria-current={activeView === 'inventory' ? 'page' : undefined}
      >
        {t('navBar.inventory')}
      </button>

      <div className="nav-bar__language-switcher" data-testid="language-switcher">
        <button
          type="button"
          className={`nav-bar__lang-btn ${language === 'es' ? 'nav-bar__lang-btn--active' : ''}`}
          onClick={() => setLanguage('es')}
          data-testid="lang-es-btn"
          aria-pressed={language === 'es'}
          aria-label="Español"
        >
          🇪🇸
        </button>
        <button
          type="button"
          className={`nav-bar__lang-btn ${language === 'en' ? 'nav-bar__lang-btn--active' : ''}`}
          onClick={() => setLanguage('en')}
          data-testid="lang-en-btn"
          aria-pressed={language === 'en'}
          aria-label="English"
        >
          🇺🇸
        </button>
      </div>
    </nav>
  );
}
