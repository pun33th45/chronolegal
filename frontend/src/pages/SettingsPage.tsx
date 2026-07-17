import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Loader2, Lock, Save } from 'lucide-react'
import { authApi } from '@/services/api'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const [passwords, setPasswords] = useState({
    current: '',
    new: '',
    confirm: '',
  })

  const changePwMutation = useMutation({
    mutationFn: () => authApi.changePassword(passwords.current, passwords.new),
    onSuccess: () => {
      toast.success('Password changed successfully')
      setPasswords({ current: '', new: '', confirm: '' })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Password change failed')
    },
  })

  function handleChangePw(e: React.FormEvent) {
    e.preventDefault()
    if (passwords.new !== passwords.confirm) {
      toast.error('Passwords do not match')
      return
    }
    changePwMutation.mutate()
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-bold text-foreground">Settings</h2>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-xl p-6"
      >
        <h3 className="font-semibold text-foreground mb-4 flex items-center gap-2">
          <Lock className="w-4 h-4 text-primary" />
          Change Password
        </h3>
        <form onSubmit={handleChangePw} className="space-y-4">
          {['current', 'new', 'confirm'].map((field) => (
            <div key={field}>
              <label className="block text-sm font-medium text-foreground mb-1.5 capitalize">
                {field === 'current' ? 'Current Password' : field === 'new' ? 'New Password' : 'Confirm New Password'}
              </label>
              <input
                type="password"
                value={passwords[field as keyof typeof passwords]}
                onChange={(e) => setPasswords({ ...passwords, [field]: e.target.value })}
                required
                className="w-full px-4 py-2.5 bg-card border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
          ))}
          <button
            type="submit"
            disabled={changePwMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {changePwMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Update Password
          </button>
        </form>
      </motion.div>
    </div>
  )
}
