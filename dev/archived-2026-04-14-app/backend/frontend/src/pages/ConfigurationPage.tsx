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
  enabledKey?: string;   // master on/off toggle for this whole module
}

const SECTIONS: Section[] = [
  {
    id: 'sof',
    title: 'Source of Funds Analysis',
    prefix: 'sof_',
    // No master on/off switch — Source of Funds Analysis is the core
    // of the platform and is always on.
    blurb:
      'Tolerances applied to each Source of Funds claim — how close the document evidence has to be to the declared amount, the date, and the auto-pass confidence threshold.',
  },
  {
    id: 'dv',
    title: 'Document Verification',
    prefix: 'dv_',
    enabledKey: 'dv_enabled',
    blurb:
      'Scoring thresholds and weights for the document forensics pipeline, plus rules controlling when a Suspicious or Likely-Tampered document blocks downstream processing.',
  },
  {
    id: 'tr',
    title: 'Transaction Review',
    prefix: 'tr_',
    enabledKey: 'tr_enabled',
    // Rules listed first (boolean toggles), then numeric thresholds,
    // then narrative keywords. Keeps the rendered ordering predictable
    // and groups the on/off switches together so a reviewer can
    // quickly enable/disable whole rule families.
    legacyKeys: [
      'rule_prohibited_country',
      'rule_high_risk_country',
      'rule_cash_deposit',
      'rule_cash_withdrawal',
      'rule_outlier',
      'rule_velocity',
      'rule_unusual_narrative',
      'cfg_high_risk_min_amount',
      'cfg_cash_threshold_deposit',
      'cfg_cash_threshold_withdrawal',
      'cfg_outlier_min_amount',
      'cfg_outlier_vs_median',
      'cfg_velocity_days',
      'cfg_velocity_count',
      'unusual_narrative_keywords',
    ],
    blurb:
      'Rules and thresholds applied by the transaction monitoring engine — high-risk countries, cash, outliers, velocity, narrative keywords, structuring patterns. Toggles control which rules fire; numeric thresholds tune their sensitivity.',
  },
  {
    id: 'fl',
    title: 'Funds Lineage',
    prefix: 'fl_',
    enabledKey: 'fl_enabled',
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
  const [reseeding, setReseeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/transaction-config`);
      if (!r.ok) {
        throw new Error(`Could not load settings (${r.status})`);
      }
      const data = await r.json();
      // Normalise tiered values to a canonical JSON string so the
      // dirty-check (string compare) isn't tripped by Python-vs-JS
      // whitespace differences in the stored JSON.
      for (const k of Object.keys(data)) {
        const t = data[k]?.type || '';
        if (t.startsWith('tiered_')) {
          try { data[k].value = JSON.stringify(JSON.parse(data[k].value)); } catch { /* leave as-is */ }
        }
      }
      setConfig(data);
      const d: Record<string, string> = {};
      for (const k of Object.keys(data)) d[k] = data[k].value;
      setDraft(d);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Failed to load configuration.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  // Backfill any missing catalogue rows from defaults. Existing values
  // stay intact. Used when a section comes back empty because the seed
  // never ran on a deploy.
  const onRestoreDefaults = async () => {
    if (!confirm(
      'Backfill missing settings from the catalogue defaults? '
      + 'Existing values are not changed — only missing rows are inserted.',
    )) return;
    setReseeding(true);
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/transaction-config/reseed`, {
        method: 'POST',
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || `Reseed failed (${r.status})`);
      }
      const result = await r.json();
      setSavedNote(`Defaults restored (${result.total_settings} settings on file).`);
      setTimeout(() => setSavedNote(null), 5000);
      await loadConfig();
    } catch (e: any) {
      setError(e?.message || 'Could not restore defaults.');
    } finally {
      setReseeding(false);
    }
  };

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
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onRestoreDefaults}
              disabled={reseeding}
              title="Backfill any missing settings from the catalogue defaults. Existing values are preserved."
              className={`px-3 py-2 text-sm font-medium rounded border transition-colors whitespace-nowrap ${
                reseeding
                  ? 'bg-zinc-100 text-zinc-400 border-zinc-200 cursor-not-allowed'
                  : 'bg-white text-zinc-900 border-zinc-300 hover:bg-zinc-50'
              }`}
            >
              {reseeding ? 'Restoring…' : 'Restore defaults'}
            </button>
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
          </div>
          {savedNote && <span className="text-xs text-green-700">{savedNote}</span>}
          {error && <span className="text-xs text-red-700 max-w-xs text-right">{error}</span>}
        </div>
      </div>

      {SECTIONS.map((section) => {
        const allKeys = keysBySection[section.id] || [];
        // The master switch is shown as the section toggle, NOT as a
        // row in the table — so we filter it out before rendering rows.
        const enabledKey = section.enabledKey;
        const enabledItem = enabledKey ? config[enabledKey] : undefined;
        const enabledDraft = enabledKey ? draft[enabledKey] : undefined;
        const moduleOn = enabledKey ? enabledDraft === 'true' : true;
        const enabledDirty = !!enabledKey && enabledDraft !== enabledItem?.value;
        const keys = allKeys.filter((k) => k !== enabledKey);
        const sectionDirty = enabledDirty || keys.some((k) => draft[k] !== config[k]?.value);

        const renderHeader = () => (
          <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-zinc-900">{section.title}</h2>
              <p className="mt-1 text-xs text-zinc-600 max-w-2xl">{section.blurb}</p>
            </div>
            <div className="flex items-center gap-4 flex-shrink-0">
              {sectionDirty && (
                <button
                  type="button"
                  onClick={() => onResetSection(allKeys)}
                  className="text-xs text-zinc-500 hover:text-zinc-900 underline whitespace-nowrap"
                >
                  Reset section
                </button>
              )}
              {enabledItem && (
                <label
                  className="inline-flex items-center gap-2 cursor-pointer select-none"
                  title="Master switch for this module. When OFF, the module is skipped on the next assessment run."
                >
                  <span className={`text-xs font-semibold tracking-wide ${moduleOn ? 'text-green-700' : 'text-zinc-400'}`}>
                    {moduleOn ? 'ON' : 'OFF'}
                  </span>
                  {/* Switch */}
                  <span
                    role="switch"
                    aria-checked={moduleOn}
                    onClick={() => enabledKey && setDraft((prev) => ({ ...prev, [enabledKey]: moduleOn ? 'false' : 'true' }))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      moduleOn ? 'bg-green-500' : 'bg-zinc-300'
                    } ${enabledDirty ? 'ring-2 ring-amber-400 ring-offset-1' : ''}`}
                  >
                    <span
                      className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                        moduleOn ? 'translate-x-5' : 'translate-x-0.5'
                      }`}
                    />
                  </span>
                </label>
              )}
            </div>
          </div>
        );

        if (allKeys.length === 0) {
          // Section has no rows yet — usually means the seed didn't run.
          // Show the section header anyway so the user can see it exists
          // and trigger a re-seed from the page header button.
          return (
            <section key={section.id} className="bg-white border border-zinc-200 rounded-md overflow-hidden">
              {renderHeader()}
              <div className="px-6 py-8 text-center text-sm text-zinc-500">
                No settings for this section yet. Click <span className="font-medium text-zinc-700">Restore defaults</span> at the top of the page to populate them.
              </div>
            </section>
          );
        }
        return (
          <section
            key={section.id}
            className={`bg-white border rounded-md overflow-hidden ${moduleOn ? 'border-zinc-200' : 'border-zinc-200 opacity-75'}`}
          >
            {renderHeader()}
            {!moduleOn && (
              <div className="px-6 py-2.5 bg-zinc-100 border-b border-zinc-200 text-xs text-zinc-700">
                <strong>This module is currently OFF.</strong> The settings below are saved but
                won't take effect until the master switch above is set to ON.
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-zinc-200 text-sm">
                <thead className="bg-zinc-50">
                  <tr>
                    <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 w-1/4">
                      Configuration Name
                    </th>
                    <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                      Description
                    </th>
                    <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 w-[24rem]">
                      Value <span className="normal-case font-normal text-zinc-300">(per risk tier where shown)</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-zinc-100">
                  {keys.map((key) => {
                    const item = config[key];
                    const value = draft[key] ?? '';
                    const isBool = item.type === 'bool';
                    const isTiered = (item.type || '').startsWith('tiered_');
                    const tieredBase = isTiered ? item.type.slice('tiered_'.length) : '';
                    const dirty = value !== item.value;

                    // Update one tier of a tiered setting and re-serialise
                    // the JSON in a fixed low/medium/high key order so the
                    // dirty-check stays consistent.
                    const setTier = (tierName: 'low' | 'medium' | 'high', raw: any) => {
                      let parsed: any = {};
                      try { parsed = JSON.parse(value || '{}'); } catch { parsed = {}; }
                      let v: any = raw;
                      if (tieredBase === 'int') { v = parseInt(raw, 10); if (isNaN(v)) v = 0; }
                      else if (tieredBase === 'float') { v = parseFloat(raw); if (isNaN(v)) v = 0; }
                      const next = {
                        low: parsed.low, medium: parsed.medium, high: parsed.high,
                        [tierName]: v,
                      };
                      setDraft((prev) => ({ ...prev, [key]: JSON.stringify(next) }));
                    };
                    let tieredVals: any = {};
                    if (isTiered) { try { tieredVals = JSON.parse(value || '{}'); } catch { tieredVals = {}; } }

                    return (
                      <tr key={key} className="align-top hover:bg-zinc-50/40">
                        <td className="px-5 py-4">
                          <div className="text-sm font-medium text-zinc-900 capitalize leading-snug">
                            {labelFor(key)}
                          </div>
                          <div className="mt-1 text-[10px] tracking-wider uppercase text-zinc-300 font-mono">
                            {key} · {item.type}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-xs text-zinc-600 leading-snug">
                          {item.description || <span className="text-zinc-300">No description.</span>}
                        </td>
                        <td className="px-5 py-4">
                          {isTiered ? (
                            <div className="flex gap-2">
                              {(['low', 'medium', 'high'] as const).map((tierName) => (
                                <div key={tierName} className="flex-1 min-w-0">
                                  <div className={`text-[9px] font-semibold uppercase tracking-wider mb-1 ${
                                    tierName === 'high' ? 'text-red-600'
                                      : tierName === 'medium' ? 'text-amber-600' : 'text-green-600'
                                  }`}>
                                    {tierName} risk
                                  </div>
                                  {tieredBase === 'bool' ? (
                                    <label className="inline-flex items-center gap-1.5 cursor-pointer">
                                      <input
                                        type="checkbox"
                                        checked={tieredVals[tierName] === true || tieredVals[tierName] === 'true'}
                                        onChange={(e) => setTier(tierName, e.target.checked)}
                                        className="h-4 w-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-500"
                                      />
                                      <span className="text-xs text-zinc-700">
                                        {(tieredVals[tierName] === true || tieredVals[tierName] === 'true') ? 'On' : 'Off'}
                                      </span>
                                    </label>
                                  ) : (
                                    <input
                                      type="number"
                                      step={tieredBase === 'float' ? 'any' : '1'}
                                      value={tieredVals[tierName] ?? ''}
                                      onChange={(e) => setTier(tierName, e.target.value)}
                                      className={`w-full px-2 py-1.5 text-sm border rounded tabular-nums ${
                                        dirty ? 'border-amber-400 bg-amber-50/40' : 'border-zinc-200 bg-white'
                                      } focus:outline-none focus:ring-2 focus:ring-zinc-300`}
                                    />
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : isBool ? (
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
                              {isTiered
                                ? 'Unsaved changes'
                                : <>Current: <span className="tabular-nums">{item.value}</span> · unsaved</>}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
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
