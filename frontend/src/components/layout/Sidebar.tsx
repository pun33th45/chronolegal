import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarChart3,
  BookOpen,
  Bot,
  FileUp,
  Home,
  LogOut,
  Search,
  Settings,
  Shield,
  User,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { useAuthStore } from '@/store/authStore'
import { Avatar } from '@/components/ui/Avatar'

const NAV_ITEMS = [
  { to: '/dashboard', icon: Home, label: 'Dashboard' },
  { to: '/chat', icon: Bot, label: 'Legal AI Chat' },
  { to: '/search', icon: Search, label: 'Search Cases' },
  { to: '/upload', icon: FileUp, label: 'Upload Judgment' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
]

const BOTTOM_ITEMS = [
  { to: '/settings', icon: Settings, label: 'Settings' },
  { to: '/profile', icon: User, label: 'Profile' },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <>
      {/* Mobile backdrop */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 md:hidden"
          />
        )}
      </AnimatePresence>

      <aside
        className={cn(
          'flex flex-col w-64 flex-shrink-0 bg-card border-r border-border',
          'fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-out',
          'md:static md:z-auto md:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Logo */}
        <div className="p-6 border-b border-border">
          <Link to="/dashboard" className="flex items-center gap-3" onClick={onClose}>
            <div className="w-9 h-9 rounded-lg bg-legal-gradient flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-serif font-bold text-base gold-text">ChronoLegal</p>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Legal AI Platform
              </p>
            </div>
          </Link>
        </div>

        {/* Main nav */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto no-scrollbar">
          {NAV_ITEMS.map((item) => (
            <NavItem
              key={item.to}
              to={item.to}
              icon={item.icon}
              label={item.label}
              active={location.pathname.startsWith(item.to)}
              onClick={onClose}
            />
          ))}

          {user?.is_admin && (
            <NavItem
              to="/admin"
              icon={Shield}
              label="Admin"
              active={location.pathname.startsWith('/admin')}
              onClick={onClose}
            />
          )}
        </nav>

        {/* Bottom */}
        <div className="p-3 border-t border-border space-y-1">
          {BOTTOM_ITEMS.map((item) => (
            <NavItem
              key={item.to}
              to={item.to}
              icon={item.icon}
              label={item.label}
              active={location.pathname === item.to}
              onClick={onClose}
            />
          ))}
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>

        {/* User info */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-3">
            <Avatar name={user?.full_name || user?.username} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.full_name || user?.username}</p>
              <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}

function NavItem({
  to,
  icon: Icon,
  label,
  active,
  onClick,
}: {
  to: string
  icon: React.ElementType
  label: string
  active: boolean
  onClick?: () => void
}) {
  return (
    <Link to={to} onClick={onClick}>
      <div
        className={cn(
          'relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60',
          active
            ? 'bg-primary/15 text-primary font-medium'
            : 'text-muted-foreground hover:text-foreground hover:bg-accent',
        )}
      >
        {active && (
          <motion.div
            layoutId="sidebar-active"
            className="absolute left-0 w-0.5 h-6 bg-primary rounded-r-full"
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          />
        )}
        <Icon className="w-4 h-4 flex-shrink-0" />
        {label}
      </div>
    </Link>
  )
}
