import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, CheckCircle2, FileUp, Loader2, XCircle } from 'lucide-react'
import { documentsApi, type UploadStatus } from '@/services/api'

const STAGES: { key: UploadStatus['status']; emoji: string; label: string }[] = [
  { key: 'extracting', emoji: '📄', label: 'Extracting judgment' },
  { key: 'chunking', emoji: '✂️', label: 'Legal structure-aware chunking' },
  { key: 'extracting_entities', emoji: '⚖️', label: 'Extracting legal entities' },
  { key: 'embedding', emoji: '🧠', label: 'Generating LegalBERT embeddings' },
  { key: 'indexing', emoji: '🔎', label: 'Indexing into the legal knowledge base' },
  { key: 'done', emoji: '✅', label: 'Ready for research' },
]

const PIPELINE_STEPS = ['Judgment', 'LegalBERT', 'Vector Search', 'Reranking', 'Groq', 'Cited Answer']

function stageState(stageKey: UploadStatus['status'], currentStatus: UploadStatus['status']) {
  const order = STAGES.map((s) => s.key)
  const stageIdx = order.indexOf(stageKey)
  const currentIdx = order.indexOf(currentStatus)
  if (currentStatus === 'failed') return stageIdx < currentIdx ? 'done' : 'pending'
  if (stageIdx < currentIdx) return 'done'
  if (stageIdx === currentIdx) return 'active'
  return 'pending'
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState<UploadStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
    setStatus(null)
    try {
      const { task_id } = await documentsApi.upload(file)
      pollRef.current = setInterval(async () => {
        try {
          const s = await documentsApi.status(task_id)
          setStatus(s)
          if (s.status === 'done' || s.status === 'failed') {
            stopPolling()
            setUploading(false)
          }
        } catch {
          stopPolling()
          setUploading(false)
          setError('Lost connection while checking processing status.')
        }
      }, 2000)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Upload failed')
      setUploading(false)
    }
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
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold text-foreground mb-1">Upload Judgment</h2>
        <p className="text-sm text-muted-foreground">
          Upload a real judgment (PDF, DOCX, or TXT). It is extracted, chunked, embedded with
          LegalBERT, and indexed — then immediately searchable in Chat and Search Cases.
        </p>
      </div>

      {!status && (
        <div className="legal-card space-y-4">
          <label
            className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-border rounded-xl py-12 cursor-pointer hover:border-primary/50 hover:bg-accent/50 transition-colors"
          >
            <FileUp className="w-8 h-8 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              {file ? file.name : 'Click to choose a PDF, DOCX, or TXT file'}
            </span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>

          {error && (
            <p className="text-sm text-destructive flex items-center gap-2">
              <XCircle className="w-4 h-4" /> {error}
            </p>
          )}

          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="w-full py-2.5 bg-primary text-primary-foreground font-semibold rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {uploading && <Loader2 className="w-4 h-4 animate-spin" />}
            Process Judgment
          </button>
        </div>
      )}

      {status && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="legal-card space-y-4"
        >
          <p className="text-sm font-medium text-foreground">{status.filename}</p>

          <div className="space-y-3">
            {STAGES.map((stage) => {
              const state = stageState(stage.key, status.status)
              return (
                <div key={stage.key} className="flex items-center gap-3 text-sm">
                  {state === 'done' && <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0" />}
                  {state === 'active' && (
                    <Loader2 className="w-4 h-4 text-primary animate-spin flex-shrink-0" />
                  )}
                  {state === 'pending' && (
                    <div className="w-4 h-4 rounded-full border border-border flex-shrink-0" />
                  )}
                  <span aria-hidden="true">{stage.emoji}</span>
                  <span
                    className={
                      state === 'pending' ? 'text-muted-foreground' : 'text-foreground'
                    }
                  >
                    {stage.label}
                  </span>
                </div>
              )
            })}
          </div>

          {status.status === 'failed' && (
            <p className="text-sm text-destructive flex items-center gap-2">
              <XCircle className="w-4 h-4" /> {status.error || 'Processing failed'}
            </p>
          )}

          {status.status === 'done' && (
            <div className="pt-2 space-y-3">
              <p className="text-sm text-primary">
                Indexed {status.chunk_count ?? status.chunks} passages successfully.
              </p>
              {status.case_id && (
                <Link
                  to={`/cases/${status.case_id}`}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
                >
                  Research this Judgment
                  <ArrowRight className="w-4 h-4" />
                </Link>
              )}
            </div>
          )}

          {(status.status === 'done' || status.status === 'failed') && (
            <button
              onClick={reset}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Upload another document
            </button>
          )}
        </motion.div>
      )}

      <div className="legal-card">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
          How ChronoLegal works
        </p>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={step} className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-lg bg-accent text-foreground">{step}</span>
              {i < PIPELINE_STEPS.length - 1 && (
                <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
