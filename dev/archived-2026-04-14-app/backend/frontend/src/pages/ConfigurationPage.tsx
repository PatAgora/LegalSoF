import { useEffect, useMemo, useState } from 'react';
import { API_BASE_URL, authFetch } from '../lib/api';

// One row from the backend transaction_config table.
interface ConfigItem {
  value: string;
  type: 'string' | 'int' | 'float' | 'bool' | 'json';
  description?: string;
}
type ConfigMap = Record<string, ConfigItem>;

// Sections — each carries a key-prefix and (optional) explicit ordering
// of fields. Anything not in the ordering list falls to the end in
// natural sort order so newly-added settings appear automatically.
interface Section {
  id: string;
  title: string;
  prefix: string;
  blurb: string;
  order?: string[];
  legacyKeys?: string[]; // additional keys that don't share the prefix
}

const SECTIONS: Section[] = [
  {
    id: 'sof',
    title: 'Source of Funds Analysis',
    prefix: 'sof_',
    blurb:
      'Tolerances applied to each Source of Funds claim — how close the document evidence has to be to the declared amount, the date, and the auto-pass confidence threshold.',
  },
  {
    id: 'dv',
    title: 'Document Verification',
    prefix: 'dv_',
    blurb:
      'Scoring thresholds and weights for the document forensics pipeline, plus rules controlling when a Suspicious or Likely-Tampered document blocks downstream processing.',
  },
  {
    id: 'tr',
    title: 'Transaction Review',
    prefix: 'tr_',
    legacyKeys: [
      'cfg_high_risk_min_amount',
      'cfg_outlier_vs_median',
      'cfg_outlier_min_amount',
      'cfg_cash_threshold_deposit',
      'cfg_cash_threshold_withdrawal',
      'cfg_velocity_days',
      'cfg_velocity_count',
      'rule_high_risk_country',
      'rule_prohibited_country',
      'rule_cash_deposit',
      'rule_cash_withdrawal',
      'rule_outlier',
      'rule_velocity',
      'rule_unusual_narrative',
      'unusual_narrative_keywords',
    ],
    title: 'Transaction Review',
    blurb:
      'Rules and thresholds applied by the transaction monitoring engine — high-risk countries, cash, outliers, velocity, narrative keywords, structuring patterns.',
  },
  {
    id: 'fl',
    title: 'Funds Lineage',
    prefix: 'fl_',
    blurb:
      'Controls for the funds lineage tracer — how strict the amount match must be when linking transfers, how far back to look, and what proportion of the credit must be traced before a savings claim auto-passes.',
  },
];

// Pretty-up a setting key into a human label.
function labelFor(key: string): string {
  const parts = key.replace(/^[a-z]+_/, '').split('_');
  if (key.startsWith('rule_')) return 'Rule: ' + parts.join(' ');
  if (key.startsWith('cfg_')) return parts.join(' ');
  return parts.join(' ');
}

function parseValue(raw: string, type: ConfigItem['type']): string | number | boolean | any {
  if (raw == null) return raw;
  if (type === 'int') {
    const v = parseInt(raw, 10);
    return isNaN(v) ? 0 : v;
  }
  if (type === 'float') {
    const v = parseFloat(raw);
    return isNaN(v) ? 0 : v;
  }
  if (type === 'bool') return raw === 'true' || raw === '1';
  if (type === 'json') {
    try { return JSON.parse(raw); } catch { return raw; }
  }
  return raw;
}

function serialiseValue(value: any, type: ConfigItem['type']): string {
  if (type === 'bool') return value ? 'true' : 'false';
  if (type === 'json') {
    if (typeof value === 'string') return value; // user has typed raw JSON
    return JSON.stringify(value);
  }
  return String(value ?? '');
}

export default function ConfigurationPage() {
  const [config, setConfig] = useState<ConfigMap>({});
  const [draft, setDraft] = useState<Record<string, string>>({}); // raw string per key for the input
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const r = await authFetch(`${API_BASE_URL}/api/v1/transaction-config`);
        if (!r.ok) {
          throw new Error(`Could not load settings (${r.status})`);
        }
        const data = await r.json();
        if (cancelled) return;
        setConfig(data);
        const d: Record<string, string> = {};
        for (const k of Object.keys(data)) d[k] = data[k].value;
        setDraft(d);
      } catch (e: any) {
        setError(e?.message || 'Failed to load configuration.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const dirtyKeys = useMemo(() => {
    return Object.keys(draft).filter((k) => config[k] && draft[k] !== config[k].value);
  }, [draft, config]);

  const onSave = async () => {
    if (dirtyKeys.length === 0) return;
    setSaving(true);
    setError(null);
    setSavedNote(null);
    try {
      const payload: Record<string, string> = {};
      for (const k of dirtyKeys) payload[k] = draft[k];
      const r = await authFetch(`${API_BASE_URL}/api/v1/transaction-config`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || `Save failed (${r.status})`);
      }
      // Refresh server-side state.
      const next = { ...config };
      for (const k of dirtyKeys) next[k] = { ...config[k], value: draft[k] };
      setConfig(next);
      setSavedNote(`Saved ${dirtyKeys.length} setting${dirtyKeys.length === 1 ? '' : 's'}.`);
      setTimeout(() => setSavedNote(null), 4000);
    } catch (e: any) {
      setError(e?.message || 'Save failed.');
    } finally {
      setSaving(false);
    }
  };

  const onResetSection = (sectionKeys: string[]) => {
    setDraft((prev) => {
      const next = { ...prev };
      for (const k of sectionKeys) next[k] = config[k]?.value ?? '';
      return next;
    });
  };

  // Slot a key into its section, honouring explicit `legacyKeys` lists.
  const keysBySection = useMemo(() => {
    const all = Object.keys(config).sort();
    const out: Record<string, string[]> = {};
    for (const s of SECTIONS) out[s.id] = [];
    const claimed = new Set<string>();
    for (const s of SECTIONS) {
      const matches = all.filter((k) => k.startsWith(s.prefix) || (s.legacyKeys || []).includes(k));
      for (const m of matches) {
        if (!claimed.has(m)) {
          out[s.id].push(m);
          claimed.add(m);
        }
      }
    }
    const unclaimed = all.filter((k) => !claimed.has(k));
    if (unclaimed.length > 0) {
      out['other'] = unclaimed;
    }
    return out;
  }, [config]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-600" />
          <p className="mt-2 text-sm text-zinc-600">Loading configuration…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Page header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-serif text-3xl text-zinc-900">Configuration</h1>
          <p className="mt-2 text-sm text-zinc-600 max-w-2xl">
            Tune the platform's risk appetite. Settings are organised by the
            section of the SoF Assessment they affect. Changes take effect
            on the next assessment run — historical results stay as they were
            when the matter was scored.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <button
            type="button"
            disabled={saving || dirtyKeys.length === 0}
            onClick={onSave}
            className={`px-4 py-2 text-sm font-medium rounded transition-colors whitespace-nowrap ${
              saving || dirtyKeys.length === 0
                ? 'bg-zinc-100 text-zinc-400 cursor-not-allowed'
                : 'bg-zinc-900 text-white hover:bg-zinc-800'
            }`}
          >
            {saving
              ? 'Saving…'
              : dirtyKeys.length === 0
              ? 'No changes'
              : `Save ${dirtyKeys.length} change${dirtyKeys.length === 1 ? '' : 's'}`}
          </button>
          {savedNote && <span className="text-xs text-green-700">{savedNote}</span>}
          {error && <span className="text-xs text-red-700 max-w-xs text-right">{error}</span>}
        </div>
      </div>

      {SECTIONS.map((section) => {
        const keys = keysBySection[section.id] || [];
        if (keys.length === 0) return null;
        const sectionDirty = keys.some((k) => draft[k] !== config[k]?.value);
        return (
          <section
            key={section.id}
            className="bg-white border border-zinc-200 rounded-md overflow-hidden"
          >
            <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-zinc-900">{section.title}</h2>
                <p className="mt-1 text-xs text-zinc-600 max-w-2xl">{section.blurb}</p>
              </div>
              {sectionDirty && (
                <button
                  type="button"
                  onClick={() => onResetSection(keys)}
                  className="text-xs text-zinc-500 hover:text-zinc-900 underline whitespace-nowrap"
                >
                  Reset section
                </button>
              )}
            </div>
            <div className="divide-y divide-zinc-100">
              {keys.map((key) => {
                const item = config[key];
                const value = draft[key] ?? '';
                const isBool = item.type === 'bool';
                const dirty = value !== item.value;
                return (
                  <div key={key} className="px-6 py-4 grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
                    <div className="md:col-span-7">
                      <div className="text-sm font-medium text-zinc-900 capitalize">
                        {labelFor(key)}
                      </div>
                      {item.description && (
                        <div className="mt-1 text-xs text-zinc-500 leading-snug">{item.description}</div>
                      )}
                      <div className="mt-1 text-[10px] tracking-wider uppercase text-zinc-300 font-mono">
                        {key} · {item.type}
                      </div>
                    </div>
                    <div className="md:col-span-5">
                      {isBool ? (
                        <label className="inline-flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={value === 'true'}
                            onChange={(e) =>
                              setDraft((prev) => ({ ...prev, [key]: e.target.checked ? 'true' : 'false' }))
                            }
                            className="h-4 w-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-500"
                          />
                          <span className="text-sm text-zinc-800">{value === 'true' ? 'Enabled' : 'Disabled'}</span>
                        </label>
                      ) : item.type === 'json' ? (
                        <textarea
                          value={value}
                          onChange={(e) => setDraft((prev) => ({ ...prev, [key]: e.target.value }))}
                          rows={3}
                          className={`w-full px-3 py-2 text-xs font-mono border rounded ${
                            dirty ? 'border-amber-400 bg-amber-50/40' : 'border-zinc-200 bg-white'
                          } focus:outline-none focus:ring-2 focus:ring-zinc-300`}
                          spellCheck={false}
                        />
                      ) : (
                        <input
                          type={item.type === 'int' || item.type === 'float' ? 'number' : 'text'}
                          step={item.type === 'float' ? 'any' : item.type === 'int' ? '1' : undefined}
                          value={value}
                          onChange={(e) => setDraft((prev) => ({ ...prev, [key]: e.target.value }))}
                          className={`w-full px-3 py-2 text-sm border rounded tabular-nums ${
                            dirty ? 'border-amber-400 bg-amber-50/40' : 'border-zinc-200 bg-white'
                          } focus:outline-none focus:ring-2 focus:ring-zinc-300`}
                        />
                      )}
                      {dirty && (
                        <div className="mt-1 text-[10px] text-amber-700">
                          Current: <span className="tabular-nums">{item.value}</span> · unsaved
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}

      {keysBySection['other'] && keysBySection['other'].length > 0 && (
        <section className="bg-white border border-zinc-200 rounded-md overflow-hidden">
          <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4">
            <h2 className="text-base font-bold text-zinc-900">Other settings</h2>
            <p className="mt-1 text-xs text-zinc-600">
              Settings not yet grouped into a section. Edit with care — these are usually read by a service directly.
            </p>
          </div>
          <div className="divide-y divide-zinc-100">
            {keysBySection['other'].map((key) => {
              const item = config[key];
              return (
                <div key={key} className="px-6 py-3 text-xs flex items-start justify-between gap-4">
                  <div>
                    <code className="font-mono text-zinc-700">{key}</code>
                    {item.description && <div className="text-zinc-500 mt-0.5">{item.description}</div>}
                  </div>
                  <input
                    value={draft[key] ?? ''}
                    onChange={(e) => setDraft((prev) => ({ ...prev, [key]: e.target.value }))}
                    className="px-2 py-1 border border-zinc-200 rounded text-xs w-40 tabular-nums"
                  />
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
