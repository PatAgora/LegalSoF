// Companies House company search: search box → results table → run check.
import { FormEvent, useState } from 'react'
import { Badge, Button, Table, Tbody, Td, Th, Thead, Tr } from '../ui'
import { CompanySearchItem, searchCompanies } from './kybApi'

interface CompanySearchProps {
  onRunCheck: (companyNumber: string) => Promise<void>
  running: boolean
}

export default function CompanySearch({ onRunCheck, running }: CompanySearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<CompanySearchItem[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [runningNumber, setRunningNumber] = useState<string | null>(null)

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault()
    const q = query.trim()
    if (q.length < 2) {
      setError('Enter at least 2 characters (company name or number).')
      return
    }
    setSearching(true)
    setError(null)
    try {
      const data = await searchCompanies(q)
      setResults(data.items)
    } catch (err: any) {
      setResults(null)
      setError(err?.message || 'Search failed.')
    } finally {
      setSearching(false)
    }
  }

  const handleRun = async (companyNumber: string) => {
    setRunningNumber(companyNumber)
    try {
      await onRunCheck(companyNumber)
    } finally {
      setRunningNumber(null)
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Company name or registered number…"
          className="flex-1 rounded border border-zinc-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400"
          aria-label="Search Companies House"
        />
        <Button type="submit" loading={searching}>
          Search Companies House
        </Button>
      </form>

      {error && (
        <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </div>
      )}

      {results && results.length === 0 && (
        <p className="text-sm text-zinc-500">No companies found for “{query.trim()}”.</p>
      )}

      {results && results.length > 0 && (
        <Table>
          <Thead>
            <Tr>
              <Th>Company</Th>
              <Th>Number</Th>
              <Th>Status</Th>
              <Th>Incorporated</Th>
              <Th>Registered office</Th>
              <Th className="text-right">Action</Th>
            </Tr>
          </Thead>
          <Tbody>
            {results.map((item) => (
              <Tr key={item.company_number}>
                <Td className="font-medium text-zinc-900">{item.title}</Td>
                <Td className="font-mono text-xs">{item.company_number}</Td>
                <Td>
                  <Badge variant={item.company_status === 'active' ? 'success' : 'warning'}>
                    {(item.company_status || 'unknown').toUpperCase()}
                  </Badge>
                </Td>
                <Td>{item.date_of_creation || '-'}</Td>
                <Td className="text-xs text-zinc-500">{item.address_snippet || '-'}</Td>
                <Td className="text-right">
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={running && runningNumber === item.company_number}
                    disabled={running}
                    onClick={() => handleRun(item.company_number)}
                  >
                    Run KYB check
                  </Button>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}
    </div>
  )
}
