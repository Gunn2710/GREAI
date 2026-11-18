import type { WordListEntry } from './types'

/** A printable word list: each word on the left, its meaning on the right. A set
 * of 20-30 words fits on one or two Letter pages. */
export async function downloadWordList(title: string, subtitle: string, words: WordListEntry[]) {
  // Only loaded when someone downloads, so it stays out of the main bundle.
  const { jsPDF } = await import('jspdf')
  const doc = new jsPDF({ unit: 'pt', format: 'letter' })

  const W = doc.internal.pageSize.getWidth()
  const H = doc.internal.pageSize.getHeight()
  const M = 54 // 0.75in margins
  const WORD_W = 135
  const GAP = 16
  const MEANING_X = M + WORD_W + GAP
  const MEANING_W = W - M - MEANING_X
  const SIZE = 10.5
  const POS_SIZE = 9
  const LINE = SIZE * 1.35
  const PAD = 6
  const INK = 20
  const MUTED = 110
  const RULE = 215

  let y = M
  let page = 1

  const footer = () => {
    doc.setFont('helvetica', 'normal').setFontSize(8.5).setTextColor(MUTED)
    doc.text(`${title} · GRE Prep`, M, H - 30)
    doc.text(String(page), W - M, H - 30, { align: 'right' })
  }

  const columns = () => {
    doc.setFont('helvetica', 'bold').setFontSize(8.5).setTextColor(MUTED)
    doc.text('WORD', M, y)
    doc.text('MEANING', MEANING_X, y)
    y += 6
    doc.setDrawColor(MUTED).setLineWidth(0.75)
    doc.line(M, y, W - M, y)
    y += PAD + SIZE
  }

  doc.setFont('helvetica', 'bold').setFontSize(18).setTextColor(INK)
  doc.text(title, M, y + 14)
  doc.setFont('helvetica', 'normal').setFontSize(10).setTextColor(MUTED)
  doc.text(subtitle, M, y + 32)
  y += 54
  columns()

  for (const w of words) {
    doc.setFont('helvetica', 'normal').setFontSize(SIZE)
    const meaning: string[] = doc.splitTextToSize(w.definition, MEANING_W)
    // The part of speech follows the word, or goes under it when there's no room.
    doc.setFont('helvetica', 'bold')
    const lemmaW = doc.getTextWidth(w.lemma)
    doc.setFont('helvetica', 'italic').setFontSize(POS_SIZE)
    const posW = w.pos ? doc.getTextWidth(w.pos) : 0
    const posBelow = lemmaW + 6 + posW > WORD_W
    const height = Math.max(posBelow ? 2 : 1, meaning.length) * LINE

    if (y + height > H - M) {
      footer()
      doc.addPage()
      page += 1
      y = M
      columns()
    }

    doc.setFont('helvetica', 'bold').setFontSize(SIZE).setTextColor(INK)
    doc.text(w.lemma, M, y)
    if (w.pos) {
      doc.setFont('helvetica', 'italic').setFontSize(POS_SIZE).setTextColor(MUTED)
      doc.text(w.pos, posBelow ? M : M + lemmaW + 6, posBelow ? y + LINE : y)
    }
    doc.setFont('helvetica', 'normal').setFontSize(SIZE).setTextColor(INK)
    doc.text(meaning, MEANING_X, y, { lineHeightFactor: 1.35 })

    y += height - SIZE + PAD
    doc.setDrawColor(RULE).setLineWidth(0.5)
    doc.line(M, y, W - M, y)
    y += PAD + SIZE
  }
  footer()

  doc.save(`${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-words.pdf`)
}
