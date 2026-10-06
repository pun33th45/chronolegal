import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ArrowRight, CheckCircle2, FileText, FileUp, Loader2, X, XCircle } from 'lucide-react'
import { casesApi, documentsApi, type UploadStatus } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { displayCaseName, courtLabel, formatCount, yearOf } from '@/lib/caseMeta'
import { cn } from '@/utils/cn'

// The real backend processing stages, in order (document_processor.py).
const STAGES: { key: UploadStatus['status']; label: string; detail: string }[] = [
  { key: 'extracting', label: 'Extracting text', detail: 'Reading the judgment' },
  { key: 'chunking', label: 'Understanding legal structure', detail: 'Splitting by sections and paragraphs' },
  { key: 'extracting_entities', label: 'Extracting entities', detail: 'Court, judges, statutes and dates' },
  { key: 'embedding', label: 'Creating semantic embeddings', detail: 'LegalBERT vectors for every passage' },
  { key: 'indexing', label: 'Building knowledge index', detail: 'Making passages searchable' },
]

// 'queued' is a real backend status (set the instant the upload is accepted,
// before the background task even starts) — it just isn't one of the
// pipeline stages shown above, since nothing has actually started yet.
function isQueued(status: UploadStatus['status'] | undefined) {
  return status === 'queued'
}

// Mirrors the backend: documents.py ALLOWED_TYPES and settings.MAX_UPLOAD_SIZE_MB.
// Legacy .doc is accepted by the API but python-docx can only read .docx, so a
// .doc upload would always fail at extraction — it is not offered here.
const MAX_UPLOAD_MB = 50
const ACCEPTED_EXTENSIONS = ['pdf', 'docx', 'txt']
const ACCEPT = ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(',')

const WHAT_HAPPENS = [
  { title: 'Extract', text: 'The text of the judgment is read from your file.' },
  { title: 'Understand', text: 'It is split along its legal structure, and the court, judges, statutes and dates are identified.' },
  { title: 'Index', text: 'Each passage is embedded with LegalBERT and added to the search index.' },
  { title: 'Research', text: 'The judgment becomes available for grounded, cited legal research.' },
]

function fileKind(name: string): string {
  return (name.split('.').pop() ?? 'file').toUpperCase()
}

function validateFile(file: File): string | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  if (!ACCEPTED_EXTENSIONS.includes(ext)) return 'Unsupported file type. Upload a PDF, DOCX or TXT file.'
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `This file is larger than ${MAX_UPLOAD_MB} MB.`
  if (file.size === 0) return 'This file is empty.'
  return null
}

type StageState = 'done' | 'active' | 'failed' | 'pending'

function stageState(stageKey: UploadStatus['status'], status: UploadStatus): StageState {
  const order = STAGES.map((s) => s.key)
  const stageIdx = order.indexOf(stageKey)
  if (status.status === 'done') return 'done'
  if (status.status === 'failed') {
    const failedIdx = order.indexOf((status.failed_stage ?? '') as UploadStatus['status'])
    if (failedIdx < 0) return 'pending'
    return stageIdx < failedIdx ? 'done' : stageIdx === failedIdx ? 'failed' : 'pending'
  }
  const currentIdx = order.indexOf(status.status)
  if (stageIdx < currentIdx) return 'done'
  if (stageIdx === currentIdx) return 'active'
  return 'pending'
}

/** Completed stages out of the five real ones (stage-based, not a fake %). */
function completedStages(status: UploadStatus): number {
  if (status.status === 'done') return STAGES.length
  return STAGES.filter((s) => stageState(s.key, status) === 'done').length
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState<UploadStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isDone = status?.status === 'done'
  const { data: newCase, isLoading: isLoadingCase } = useQuery({
    queryKey: ['case', status?.case_id],
    queryFn: () => casesApi.get(status!.case_id!),
    enabled: isDone && !!status?.case_id,
  })

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setError(null)
    // The upload POST itself (auth + file read, before the backend even
    // accepts the job) can take several seconds — without this, the panel
    // below stays on the pre-upload file-picker view for that whole time,
    // the one real gap where nothing visibly happens after clicking.
    // "queued" is the real status this request is genuinely in transit
    // toward, not a fabricated one.
    setStatus({ status: 'queued', filename: file.name })
    try {
      const { task_id } = await documentsApi.upload(file)

      /** Returns true once processing has reached a terminal state. */
      async function poll(): Promise<boolean> {
        try {
          const s = await documentsApi.status(task_id)
          setStatus(s)
          if (s.status === 'done' || s.status === 'failed') {
            stopPolling()
            setUploading(false)
            return true
          }
          return false
        } catch {
          stopPolling()
          setUploading(false)
          setError('Lost connection while checking processing status.')
          return true
        }
      }

      // Poll once immediately (the backend already has a real "queued"
      // status waiting) instead of leaving the user looking at nothing for
      // up to 2 seconds until the first interval tick. Only start the
      // repeating poll if that first check didn't already finish — a tiny
      // document can complete before this line runs.
      const finished = await poll()
      if (!finished) {
        pollRef.current = setInterval(poll, 2000)
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : "We couldn't upload this file. Please try again.")
      setUploading(false)
      setStatus(null)
    }
  }

  function selectFile(next: File | null) {
    if (!next) return
    const problem = validateFile(next)
    setError(problem)
    setFile(problem ? null : next)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function clearFile() {
    setFile(null)
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function reset() {
    stopPolling()
    setFile(null)
    setStatus(null)
    setError(null)
    setUploading(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-2xl mx-auto space-y-6">
      <PageHeader
        eyebrow="Documents"
        title="Add a Judgment"
        description="Add a judgment to your ChronoLegal knowledge base. ChronoLegal extracts its legal structure, identifies entities, creates semantic embeddings and makes it searchable for research."
      />

      {!status && (
        <div className="space-y-4">
          <div className="legal-card space-y-4">
            {!file ? (
              <label
                htmlFor="judgment-file"
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragOver(true)
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragOver(false)
                  selectFile(e.dataTransfer.files?.[0] ?? null)
                }}
                className={cn(
                  'flex flex-col items-center justify-center text-center gap-2 rounded-xl border px-6 py-12 sm:py-14 cursor-pointer transition-colors',
                  'focus-within:ring-2 focus-within:ring-primary/40',
                  dragOver
                    ? 'border-legal-gold bg-accent'
                    : 'border-dashed border-legal-gold/40 bg-accent/40 hover:bg-accent/70 hover:border-legal-gold/70',
                )}
              >
                <span className="w-11 h-11 rounded-full bg-card border border-legal-gold/30 flex items-center justify-center mb-1">
                  <FileUp className="w-5 h-5 text-primary" />
                </span>
                <span className="font-serif text-base font-semibold text-foreground">
                  {dragOver ? 'Drop to add this judgment' : 'Upload your judgment'}
                </span>
                <span className="text-sm text-muted-foreground">
                  Drag &amp; drop your file here, or <span className="font-medium text-primary underline-offset-2 hover:underline">browse files</span>
                </span>
                <span className="text-xs text-muted-foreground mt-1">
                  PDF, DOCX or TXT · up to {MAX_UPLOAD_MB} MB
                </span>
                <input
                  id="judgment-file"
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPT}
                  className="sr-only"
                  onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
                />
              </label>
            ) : (
              <div className="rounded-xl border border-legal-gold/40 bg-accent/40 p-4 sm:p-5">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-card border border-border flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-primary" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground break-all">{file.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {fileKind(file.name)} · {formatBytes(file.size)}
                    </p>
                    <p className="text-xs text-primary font-medium mt-2 flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Ready to process
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={clearFile}
                    aria-label="Remove file"
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors shrink-0"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-3 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  Change file
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPT}
                  className="sr-only"
                  tabIndex={-1}
                  onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
                />
              </div>
            )}

            {error && (
              <p role="alert" className="text-sm text-destructive flex items-start gap-2">
                <XCircle className="w-4 h-4 mt-0.5 shrink-0" /> {error}
              </p>
            )}

            <Button
              onClick={handleUpload}
              disabled={!file || uploading}
              loading={uploading}
              size="lg"
              className="w-full gap-2"
            >
              {uploading ? 'Processing…' : 'Process Judgment'}
              {!uploading && file && <ArrowRight className="w-4 h-4" />}
            </Button>
          </div>

          <div className="rounded-xl border border-border bg-card/60 p-4 sm:p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
              What happens to your judgment
            </p>
            <ol className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
              {WHAT_HAPPENS.map((step, i) => (
                <li key={step.title} className="flex gap-3">
                  <span className="font-serif text-sm font-semibold text-legal-gold tabular-nums pt-px">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-foreground">{step.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {status && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="legal-card space-y-5"
          aria-live="polite"
        >
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <FileText className="w-4 h-4 text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-muted-foreground">
                {isDone ? 'Judgment added' : status.status === 'failed' ? 'Processing stopped' : 'Adding judgment'}
              </p>
              <p className="text-sm font-medium text-foreground truncate">{status.filename}</p>
            </div>
            {!isDone && status.status !== 'failed' && !error && (
              <span className="text-xs text-muted-foreground tabular-nums shrink-0 pt-0.5">
                {isQueued(status.status)
                  ? 'Uploading…'
                  : `Step ${Math.min(completedStages(status) + 1, STAGES.length)} of ${STAGES.length}`}
              </span>
            )}
          </div>

          {/* Stage-based progress: one segment per real backend stage. */}
          <div className="flex gap-1" aria-hidden="true">
            {STAGES.map((stage) => {
              const state = stageState(stage.key, status)
              return (
                <div
                  key={stage.key}
                  className={cn(
                    'h-1.5 flex-1 rounded-full transition-colors duration-300',
                    state === 'done' && 'bg-primary',
                    state === 'active' && 'bg-primary/40 animate-pulse',
                    state === 'failed' && 'bg-destructive',
                    state === 'pending' && 'bg-muted',
                  )}
                />
              )
            })}
          </div>

          <ol className="space-y-2.5">
            {STAGES.map((stage) => {
              const state = stageState(stage.key, status)
              return (
                <li key={stage.key} className="flex items-start gap-3 text-sm">
                  <span className="mt-0.5 shrink-0">
                    {state === 'done' && <CheckCircle2 className="w-4 h-4 text-primary" />}
                    {state === 'active' && <Loader2 className="w-4 h-4 text-primary animate-spin" />}
                    {state === 'failed' && <XCircle className="w-4 h-4 text-destructive" />}
                    {state === 'pending' && <span className="block w-4 h-4 rounded-full border border-border" />}
                  </span>
                  <div className="min-w-0">
                    <p
                      className={cn(
                        state === 'pending' ? 'text-muted-foreground' : 'text-foreground',
                        state === 'active' && 'font-medium',
                      )}
                    >
                      {stage.label}
                    </p>
                    {state === 'active' && <p className="text-xs text-muted-foreground mt-0.5">{stage.detail}</p>}
                  </div>
                </li>
              )
            })}
          </ol>

          {(status.status === 'failed' || error) && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 space-y-3">
              <div className="flex items-start gap-2.5">
                <XCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-foreground">Something went wrong</p>
                  <p className="text-sm text-foreground/90">We couldn&apos;t process this judgment.</p>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {error || status.error || 'Please try again in a moment.'}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {file && (
                  <Button
                    size="sm"
                    onClick={() => {
                      stopPolling()
                      handleUpload()
                    }}
                  >
                    Try again
                  </Button>
                )}
                <Button size="sm" variant="secondary" onClick={reset}>
                  Choose another file
                </Button>
              </div>
            </div>
          )}

          {isDone && (
            <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 space-y-4">
              <div>
                <p className="text-sm font-medium text-foreground flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary" />
                  Judgment added successfully
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  It has been added to your ChronoLegal knowledge base and is ready for research.
                </p>
              </div>

              {isLoadingCase ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Finalizing case details…
                </p>
              ) : (
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-muted-foreground">Case</dt>
                    <dd className="text-foreground font-medium break-words">
                      {displayCaseName(newCase?.case_name ?? status.filename)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Court</dt>
                    <dd className="text-foreground">{courtLabel(newCase?.court) ?? 'Not recorded'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Year</dt>
                    <dd className="text-foreground">{yearOf(newCase?.judgment_date) ?? 'Not recorded'}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-muted-foreground">Indexed</dt>
                    <dd className="text-foreground">
                      {formatCount(status.chunk_count ?? status.chunks)} chunks ready for research
                    </dd>
                  </div>
                </dl>
              )}

              {status.case_id && (
                <div className="flex flex-wrap items-center gap-2">
                  <Link to={`/cases/${status.case_id}`}>
                    <Button variant="secondary" size="sm">View Judgment</Button>
                  </Link>
                  <Link
                    to={`/chat?case=${status.case_id}&name=${encodeURIComponent(displayCaseName(newCase?.case_name ?? status.filename))}`}
                  >
                    <Button size="sm" className="gap-1.5">
                      Start Research
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                  </Link>
                  <button
                    onClick={reset}
                    className="text-sm text-muted-foreground hover:text-foreground transition-colors px-2"
                  >
                    Upload another
                  </button>
                </div>
              )}
            </div>
          )}
        </motion.div>
      )}

    </div>
  )
}
