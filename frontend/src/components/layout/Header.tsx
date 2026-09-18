import { useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { Avatar } from '@/components/ui/Avatar'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/chat': 'Legal AI Chat',
  '/search': 'Search Cases',
  '/upload': 'Upload Judgment',
  '/analytics': 'Analytics',
  '/cases': 'Case Viewer',
  '/admin': 'Admin Panel',
  '/settings': 'Settings',
  '/profile': 'Profile',
}

interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  const location = useLocation()
  const { user } = useAuthStore()

  const title = Object.entries(PAGE_TITLES).find(([path]) =>
    location.pathname.startsWith(path),
  )?.[1] ?? 'ChronoLegal'

  return (
    <header className="h-14 border-b border-border flex items-center justify-between px-4 md:px-6 bg-card/50 backdrop-blur-sm flex-shrink-0">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          aria-label="Open navigation menu"
          className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
        >
          <Menu className="w-4 h-4" />
        </button>
        <h1 className="text-sm font-semibold text-foreground">{title}</h1>
      </div>
      <Avatar name={user?.full_name || user?.username} />
    </header>
  )
}
