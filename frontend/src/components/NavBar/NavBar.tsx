import './NavBar.css';

export type AppView = 'upload' | 'inventory';

export interface NavBarProps {
  activeView: AppView;
  onSelectView: (view: AppView) => void;
}

export function NavBar({ activeView, onSelectView }: NavBarProps) {
  return (
    <nav className="nav-bar" data-testid="nav-bar">
      <button
        type="button"
        className={`nav-bar__tab ${activeView === 'upload' ? 'nav-bar__tab--active' : ''}`}
        onClick={() => onSelectView('upload')}
        data-testid="nav-upload-btn"
        aria-current={activeView === 'upload' ? 'page' : undefined}
      >
        Upload
      </button>
      <button
        type="button"
        className={`nav-bar__tab ${activeView === 'inventory' ? 'nav-bar__tab--active' : ''}`}
        onClick={() => onSelectView('inventory')}
        data-testid="nav-inventory-btn"
        aria-current={activeView === 'inventory' ? 'page' : undefined}
      >
        My Inventory
      </button>
    </nav>
  );
}
