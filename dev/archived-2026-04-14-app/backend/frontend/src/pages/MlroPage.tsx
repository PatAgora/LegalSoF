// MLRO Workbench — internal suspicion reports, SAR preparation & DAML
// timers, AML training register, and the policy repository.
//
// Route: /mlro (wired by the integration pass — this page only exports).
// Admin-gated: admin stands in for the MLRO role; the backend enforces
// the same restriction on every MLRO API. Nothing on this page is ever
// visible to the reporting fee earner or the client team (POCA 2002
// s.333A tipping off).
import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import MlroDashboardCards from '../components/Mlro/MlroDashboardCards';
import ReportsTab from '../components/Mlro/ReportsTab';
import SarsTab from '../components/Mlro/SarsTab';
import TrainingTab from '../components/Mlro/TrainingTab';
import PoliciesTab from '../components/Mlro/PoliciesTab';

type TabKey = 'reports' | 'sars' | 'training' | 'policies';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'reports', label: 'Reports' },
  { key: 'sars', label: 'SARs & DAML' },
  { key: 'training', label: 'Training' },
  { key: 'policies', label: 'Policies' },
];

export default function MlroPage() {
  const { isAuthenticated, user } = useAuthStore();
  const [tab, setTab] = useState<TabKey>('reports');
  // Bumped by child tabs after material actions so the dashboard cards refetch.
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = () => setRefreshKey((n) => n + 1);

  // Defence-in-depth: backend enforces admin on every /mlro API; this
  // guard keeps the workbench out of the non-admin UI entirely.
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (String(user?.role || '').toLowerCase() !== 'admin') return <Navigate to="/" replace />;

  return (
    <div className="space-y-6">
      <div className="border-b border-zinc-200 pb-6">
        <h1 className="font-serif text-3xl text-zinc-900">MLRO Workbench</h1>
        <p className="mt-2 text-sm text-zinc-500 max-w-3xl">
          Internal suspicion reports (POCA s.330), SAR preparation and DAML clocks, training and
          policies. Contents are restricted to the nominated officer — report status is never shown
          to the client team (s.333A). SARs are filed by a person on the NCA SAR Portal; this
          platform prepares and records.
        </p>
      </div>

      <MlroDashboardCards refreshKey={refreshKey} />

      <div className="border-b border-zinc-200">
        <nav className="flex gap-6 -mb-px">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t.key
                  ? 'border-zinc-900 text-zinc-900'
                  : 'border-transparent text-zinc-500 hover:text-zinc-800 hover:border-zinc-300'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {tab === 'reports' && <ReportsTab onChanged={bump} />}
      {tab === 'sars' && <SarsTab onChanged={bump} />}
      {tab === 'training' && <TrainingTab onChanged={bump} />}
      {tab === 'policies' && <PoliciesTab onChanged={bump} />}
    </div>
  );
}
