import { useState, type ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import brandLogo from '../assets/logo.jpeg';

interface AppNavbarProps {
  actions?: ReactNode;
  activeAlertCount?: number;
}

interface NavItem {
  to: string;
  label: string;
  badge?: number;
  icon: React.ReactNode;
}

export default function AppNavbar({ actions, activeAlertCount = 0 }: AppNavbarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { isDark, toggleTheme } = useTheme();

  const navItems: NavItem[] = [
    {
      to: '/',
      label: 'Overview',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      ),
    },
    {
      to: '/map',
      label: 'Thermal Map',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
      ),
    },
    {
      to: '/alerts',
      label: 'Alerts',
      badge: activeAlertCount,
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
      ),
    },
    {
      to: '/events',
      label: 'Events Queue',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
      ),
    },
    {
      to: '/analytics',
      label: 'Analytics',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
    {
      to: '/system',
      label: 'System Health',
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
        </svg>
      ),
    },
  ];

  return (
    <nav className="relative bg-white/90 dark:bg-slate-900/75 backdrop-blur-xl border-b border-slate-200/80 dark:border-white/[0.06] transition-colors duration-200 flex-shrink-0 z-30 sticky top-0">
      {/* Hairline accent inspired by the brand palette (navy → ember) */}
      <span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-blue-600/25 via-transparent to-orange-500/30 dark:from-blue-400/30 dark:to-orange-400/25" />
      <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6">
        <div className="flex items-center justify-between h-13">
          {/* Left: Brand Identity — command-center lockup: FLAREX logo plate +
              THERMALWATCH wordmark + descriptor. The logo artwork carries its
              own white background, so it sits on a crisp white plate (the
              visual focal point) inside a translucent panel with a restrained
              ember→cyan hairline echoing the FLAREX palette. */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <NavLink
              to="/"
              title="ThermalWatch"
              aria-label="ThermalWatch — home"
              className="group relative flex items-center gap-2 lg:gap-3 rounded-lg lg:rounded-xl bg-white/70 dark:bg-white/[0.04] pl-1.5 pr-2 sm:pl-2 sm:pr-2.5 lg:pr-3 py-1 ring-1 ring-slate-200/90 dark:ring-white/10 shadow-xs backdrop-blur-md overflow-hidden hover:ring-slate-300 dark:hover:ring-white/20 transition-all flex-shrink-0"
            >
              {/* Restrained ember → cyan hairline accent (FLAREX palette echo) */}
              <span
                aria-hidden
                className="pointer-events-none absolute inset-x-1 top-0 h-px bg-gradient-to-r from-orange-500/40 via-orange-500/5 to-cyan-500/40 dark:from-orange-400/45 dark:via-orange-400/10 dark:to-cyan-400/45"
              />

              {/* FLAREX logo plate — the visual focal point */}
              <span className="relative flex items-center rounded-md bg-white px-1 py-0.5 ring-1 ring-slate-200/90 dark:ring-white/15 shadow-2xs">
                <img
                  src={brandLogo}
                  alt="ThermalWatch"
                  draggable={false}
                  className="h-6 lg:h-8 w-auto object-contain select-none"
                />
              </span>

              {/* Lockup divider */}
              <span aria-hidden className="hidden lg:block h-8 w-px bg-slate-200/90 dark:bg-white/10" />

              {/* Product wordmark stack */}
              <span className="flex flex-col justify-center leading-none pr-0.5">
                <span className="text-[11px] lg:text-sm font-bold tracking-[0.11em] lg:tracking-[0.13em] text-navy-900 dark:text-white">
                  THERMALWATCH
                </span>
                <span className="hidden lg:block mt-1 text-[9px] font-semibold tracking-[0.26em] text-slate-500 dark:text-slate-400">
                  AI FIRE INTELLIGENCE
                </span>
              </span>
            </NavLink>
          </div>

          {/* Center: Desktop Navigation Links. flex-1 keeps the links centered
              and lets them absorb horizontal squeeze at tablet widths so the
              right-side controls (bell, theme) are never pushed off-screen. */}
          <div className="hidden md:flex flex-1 min-w-0 justify-center items-center space-x-1 lg:space-x-1.5">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-navy-900 text-white dark:bg-blue-600 dark:text-white shadow-2xs'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`
                }
              >
                {item.icon}
                <span>{item.label}</span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="ml-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-600 text-white animate-pulse">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </div>

          {/* Right: Actions, Theme Switcher & Mobile Hamburger */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            {actions}

            {/* Dark/Light Theme Button */}
            <button
              type="button"
              onClick={toggleTheme}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors shadow-2xs"
              title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {isDark ? (
                <>
                  <svg className="w-3.5 h-3.5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                  <span className="hidden lg:inline">LIGHT</span>
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                  <span className="hidden lg:inline">DARK</span>
                </>
              )}
            </button>

            {/* Mobile Menu Hamburger Button */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-1.5 rounded-md text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 focus:outline-none"
              aria-label="Toggle Navigation Menu"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Navigation Drawer / Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200/80 dark:border-white/[0.06] bg-white/95 dark:bg-slate-900/90 backdrop-blur-xl px-3 pt-2 pb-3 space-y-1 animate-fadeIn">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-navy-900 text-white dark:bg-blue-600 dark:text-white shadow-2xs'
                    : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`
              }
            >
              <div className="flex items-center gap-2">
                {item.icon}
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-600 text-white">
                  {item.badge} ACTIVE
                </span>
              )}
            </NavLink>
          ))}
        </div>
      )}
    </nav>
  );
}
