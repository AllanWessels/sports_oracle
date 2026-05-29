import { useCallback, useEffect, useRef, useState } from 'react'

interface PollState<T> {
  data: T | null
  error: string | null
  loading: boolean
}

/**
 * Poll an async fetcher on an interval. Keeps the last good data while
 * refetching, so the dashboards stay "continuously updated" without flicker.
 */
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 5000): PollState<T> {
  const [state, setState] = useState<PollState<T>>({ data: null, error: null, loading: true })
  // Keep the latest fetcher without re-subscribing the interval each render.
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const tick = useCallback(async () => {
    try {
      const data = await fetcherRef.current()
      setState({ data, error: null, loading: false })
    } catch (err) {
      setState((prev) => ({
        data: prev.data,
        error: err instanceof Error ? err.message : 'Failed to load',
        loading: false,
      }))
    }
  }, [])

  useEffect(() => {
    let active = true
    void tick()
    const id = setInterval(() => {
      if (active) void tick()
    }, intervalMs)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [tick, intervalMs])

  return state
}
