import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { User } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

export default function ProfilePage() {
  const { user } = useAuthStore()

  if (!user) return null

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-bold text-foreground">Profile</h2>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-xl p-6"
      >
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center">
            <span className="text-2xl font-bold text-primary">
              {user.username[0].toUpperCase()}
            </span>
          </div>
          <div>
            <h3 className="font-semibold text-lg text-foreground">
              {user.full_name || user.username}
            </h3>
            <p className="text-muted-foreground">{user.email}</p>
            {user.is_admin && (
              <span className="citation-badge mt-1 inline-block">Administrator</span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Username</p>
            <p className="text-foreground">{user.username}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Account Status</p>
            <p className={user.is_active ? 'text-green-400' : 'text-red-400'}>
              {user.is_active ? 'Active' : 'Inactive'}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Member Since</p>
            <p className="text-foreground">{new Date(user.created_at).toLocaleDateString()}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Last Login</p>
            <p className="text-foreground">
              {user.last_login_at
                ? new Date(user.last_login_at).toLocaleDateString()
                : 'N/A'}
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
