import { ChevronDown, Sparkles } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { api } from '../lib/api'
import type { StudyItem } from '../lib/types'
import { ChatBox } from './TutorChat'

const BEFORE = ['Give me a hint', 'What is this question asking?', 'Break the word into parts']
const BEFORE_FLASHCARD = ['What does it mean?', 'Give me a memory trick', 'Use it in a GRE-style sentence']
const AFTER = ['Explain the answer', 'How do I tell these options apart?', 'Have I mixed this word up before?']

/**
 * Chat with Claude about the question on screen. Mount it with key={item.id}
 * so the thread carries over from the question to its result, then resets.
 */
export function StudyTutor({
  item,
  answered,
  open,
  onToggle,
}: {
  item: StudyItem
  answered: boolean
  open: boolean
  onToggle: () => void
}) {
  const flashcard = item.item_type === 'flashcard'
  return (
    <Card className="gap-0 py-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex items-center gap-2 rounded-xl px-6 py-4 text-left text-sm font-medium hover:bg-accent/50 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <Sparkles className="size-4 text-primary" />
        Ask the tutor about this question
        <ChevronDown className={cn('ml-auto size-4 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <CardContent className="flex flex-col gap-3 pb-6">
          {!answered && !flashcard && (
            <p className="text-xs text-muted-foreground">
              The tutor won't give the answer away until you answer. Asking before you answer counts as using a hint.
            </p>
          )}
          <ChatBox
            ask={async (history) => (await api.studyChat(item.id, history)).reply}
            starters={answered ? AFTER : flashcard ? BEFORE_FLASHCARD : BEFORE}
            placeholder={answered ? 'Ask about this question…' : 'Ask for a hint…'}
          />
        </CardContent>
      )}
    </Card>
  )
}
