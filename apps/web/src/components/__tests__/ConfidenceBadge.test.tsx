import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConfidenceBadge } from '../ConfidenceBadge'

describe('ConfidenceBadge', () => {
  it('renders low confidence with amber color class', () => {
    const { container } = render(<ConfidenceBadge label="low" num={30} />)
    expect(screen.getByText('Low Confidence')).toBeInTheDocument()
    expect(screen.getByText('30%')).toBeInTheDocument()
    // Check amber color is applied
    const badge = container.firstChild as HTMLElement
    expect(badge.className).toContain('amber')
  })

  it('renders medium confidence with sky color class', () => {
    const { container } = render(<ConfidenceBadge label="medium" num={55} />)
    expect(screen.getByText('Medium Confidence')).toBeInTheDocument()
    expect(screen.getByText('55%')).toBeInTheDocument()
    const badge = container.firstChild as HTMLElement
    expect(badge.className).toContain('sky')
  })

  it('renders high confidence with emerald color class', () => {
    const { container } = render(<ConfidenceBadge label="high" num={82} />)
    expect(screen.getByText('High Confidence')).toBeInTheDocument()
    expect(screen.getByText('82%')).toBeInTheDocument()
    const badge = container.firstChild as HTMLElement
    expect(badge.className).toContain('emerald')
  })

  it('clamps percentage value to 0–100', () => {
    render(<ConfidenceBadge label="high" num={150} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('renders progress bar when showBar is true', () => {
    render(<ConfidenceBadge label="high" num={75} showBar />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toBeInTheDocument()
    expect(bar).toHaveAttribute('aria-valuenow', '75')
    expect(bar).toHaveAttribute('aria-valuemax', '100')
  })

  it('does not render progress bar by default', () => {
    render(<ConfidenceBadge label="medium" num={60} />)
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })
})
