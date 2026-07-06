// Shared UK formatting helpers.
//
// Every date and money value shown to a user goes through here so the
// whole app reads consistently: DD/MM/YYYY dates and en-GB GBP amounts.

const GBP_2DP = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const GBP_WHOLE = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

/** DD/MM/YYYY. Returns the raw input when it cannot be parsed. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return String(iso)
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  return `${day}/${month}/${d.getFullYear()}`
}

/** DD/MM/YYYY HH:mm. Returns the raw input when it cannot be parsed. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return String(iso)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${formatDate(iso)} ${hh}:${mm}`
}

/** £1,234.56 - always two decimal places. */
export function formatCurrency(n: number | string | null | undefined): string {
  const v = Number(n)
  return GBP_2DP.format(isNaN(v) ? 0 : v)
}

/** £1,235 - whole pounds, for list/summary contexts. */
export function formatCurrencyWhole(n: number | string | null | undefined): string {
  const v = Number(n)
  return GBP_WHOLE.format(isNaN(v) ? 0 : v)
}
