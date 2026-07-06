// Account settings - password management and two-factor authentication.
// Available to all authenticated roles.
import PasswordSection from '../components/Settings/PasswordSection'
import MfaSection from '../components/Settings/MfaSection'

export default function SettingsPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="font-serif text-3xl text-zinc-900">Settings</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Manage how you sign in to your account.
        </p>
      </div>

      <PasswordSection />
      <MfaSection />
    </div>
  )
}
