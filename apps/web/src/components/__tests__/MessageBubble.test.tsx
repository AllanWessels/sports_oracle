import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MessageBubble } from '../MessageBubble'
import type { Message, CitationEvent } from '../../types'

// Mock react-markdown to render children as plain text in tests
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}))

vi.mock('remark-gfm', () => ({ default: () => {} }))

describe('MessageBubble', () => {
  it('renders a user message as a right-aligned bubble', () => {
    const msg: Message = { role: 'user', content: 'Hello, who won last night?' }
    render(<MessageBubble message={msg} />)
    expect(screen.getByText('Hello, who won last night?')).toBeInTheDocument()
  })

  it('renders an assistant message with markdown content', () => {
    const msg: Message = { role: 'assistant', content: '**Haaland** scored 2 goals.' }
    render(<MessageBubble message={msg} />)
    expect(screen.getByTestId('message-content')).toBeInTheDocument()
    expect(screen.getByTestId('markdown')).toBeInTheDocument()
  })

  it('shows streaming dots when content is empty and isStreaming is true', () => {
    const msg: Message = { role: 'assistant', content: '' }
    render(<MessageBubble message={msg} isStreaming />)
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('renders citations list when citations are present', () => {
    const citations: CitationEvent[] = [
      {
        ref_num: 1,
        source_type: 'api',
        provider: 'ESPN',
        url: 'https://espn.com/article',
        snippet: 'Haaland scores again',
        fetched_at: '2024-01-15T12:00:00Z',
      },
    ]
    const msg: Message = {
      role: 'assistant',
      content: 'Haaland scored 2 goals [1].',
      citations,
    }
    render(<MessageBubble message={msg} />)
    expect(screen.getByText('ESPN')).toBeInTheDocument()
    expect(screen.getByText('Sources')).toBeInTheDocument()
  })

  it('renders tool chips when liveToolChips are provided', () => {
    const msg: Message = { role: 'assistant', content: '' }
    render(
      <MessageBubble
        message={msg}
        liveToolChips={[{ name: 'stats', status: 'running' }]}
        isStreaming
      />,
    )
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders intent badge for factual intent', () => {
    const msg: Message = { role: 'assistant', content: 'Some fact.', intent: 'factual' }
    render(<MessageBubble message={msg} />)
    expect(screen.getByText('Factual')).toBeInTheDocument()
  })

  it('renders prediction card when prediction is present', () => {
    const msg: Message = {
      role: 'assistant',
      content: 'My prediction:',
      prediction: {
        sport: 'Football',
        fixture_ref: 'Man City vs Liverpool',
        pick: 'Man City Win',
        win_probability: 0.58,
        confidence_num: 72,
        confidence_label: 'high',
        key_factors: [{ name: 'Home advantage', direction: 'positive', weight: 0.4 }],
        caveats: ['Recent injury concerns'],
        disclaimer: 'This is not betting advice.',
      },
    }
    render(<MessageBubble message={msg} />)
    expect(screen.getByText('Man City Win')).toBeInTheDocument()
    expect(screen.getByText('Man City vs Liverpool')).toBeInTheDocument()
  })
})
