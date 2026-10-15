import {
  EyeOff,
  FileUp,
  KeyRound,
  LoaderCircle,
  MessageSquareCheck,
  ScanText,
  Send,
  Sparkles,
} from "lucide-react";
import { type DragEvent, type FormEvent, useId, useRef, useState } from "react";

import { ApiError, type Submission, submitIntake } from "./api";
import { loadApiKey, saveApiKey } from "./apiKey";
import { SAMPLE_GROUPS, SAMPLES } from "./samples";

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Try again.";
  if (error.status === 0) return "Could not reach the API. Check that it is running.";
  if (error.status === 401) {
    return "The API key was rejected. Use the INTAKE_API_KEY value from the server's .env.";
  }
  if (error.status === 422) return "Both the client name and the Transcript are needed.";
  return `The API could not take this Transcript (HTTP ${error.status}). Try again.`;
}

export default function NewIntakeView({
  onSubmitted,
}: {
  onSubmitted: (submission: Submission) => void;
}) {
  const [clientName, setClientName] = useState("");
  const [transcript, setTranscript] = useState("");
  const [sampleId, setSampleId] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState(loadApiKey);
  const [editingKey, setEditingKey] = useState(() => loadApiKey() === "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const ids = { name: useId(), transcript: useId(), key: useId(), hint: useId() };

  const words = transcript.trim() ? transcript.trim().split(/\s+/).length : 0;
  const ready = clientName.trim() !== "" && transcript.trim() !== "" && apiKey !== "";

  const pickSample = (id: string) => {
    const sample = SAMPLES.find((s) => s.id === id)!;
    setClientName(sample.clientName);
    setTranscript(sample.transcript);
    setSampleId(id);
    setError(null);
  };

  const readFile = async (file: File | undefined) => {
    if (!file) return;
    setTranscript(await file.text());
    setSampleId(null);
    setError(null);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    void readFile(event.dataTransfer.files[0]);
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!ready || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const submission = await submitIntake(apiKey, {
        client_name: clientName.trim(),
        transcript,
      });
      saveApiKey(apiKey);
      onSubmitted(submission);
    } catch (caught) {
      setError(errorMessage(caught));
      if (caught instanceof ApiError && caught.status === 401) setEditingKey(true);
      setSubmitting(false);
    }
  };

  return (
    <section className="new-page">
      <div className="page-head">
        <h1>New intake</h1>
        <p className="page-lede">
          Paste a Client's first-call Transcript. Emails, phone numbers and addresses are
          redacted on the server before the agent sees a word.
        </p>
      </div>

      <div className="new-grid">
        <form
          className="panel composer"
          onSubmit={submit}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) void submit();
          }}
        >
          <div className="field">
            <label htmlFor={ids.name}>Client name</label>
            <input
              id={ids.name}
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              placeholder="Mike's Roofing"
              autoComplete="off"
            />
          </div>

          <div className="field">
            <div className="field-head">
              <label htmlFor={ids.transcript}>Transcript</label>
              <button
                type="button"
                className="button button-quiet button-small"
                onClick={() => fileInput.current?.click()}
              >
                <FileUp aria-hidden size={15} />
                Upload .txt
              </button>
              <input
                ref={fileInput}
                type="file"
                accept=".txt,text/plain"
                hidden
                onChange={(e) => void readFile(e.target.files?.[0])}
              />
            </div>
            <div
              className={`dropzone${dragging ? " dropzone-active" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <textarea
                id={ids.transcript}
                value={transcript}
                onChange={(e) => {
                  setTranscript(e.target.value);
                  setSampleId(null);
                }}
                placeholder={"Agency: Thanks for jumping on. Tell me about the business.\nClient: …"}
                rows={16}
                spellCheck={false}
              />
              {dragging && (
                <span className="dropzone-hint" aria-hidden>
                  Drop the .txt file
                </span>
              )}
            </div>
            <p className="field-meta">
              {words === 0 ? "Paste, drop a .txt file, or pick a demo Transcript." : `${words.toLocaleString()} words`}
            </p>
          </div>

          <div className="field key-field">
            {editingKey ? (
              <>
                <label htmlFor={ids.key}>API key</label>
                <input
                  id={ids.key}
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value.trim())}
                  placeholder="INTAKE_API_KEY"
                  autoComplete="off"
                  aria-describedby={ids.hint}
                />
                <p className="field-meta" id={ids.hint}>
                  The INTAKE_API_KEY from the server's .env. Kept in this browser only.
                </p>
              </>
            ) : (
              <p className="key-saved">
                <KeyRound aria-hidden size={16} />
                <span>API key saved in this browser</span>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setEditingKey(true)}
                >
                  Change
                </button>
              </p>
            )}
          </div>

          {error && (
            <div className="callout callout-error" role="alert">
              {error}
            </div>
          )}

          <div className="composer-actions">
            <button type="submit" className="button button-primary button-large" disabled={!ready || submitting}>
              {submitting ? (
                <LoaderCircle aria-hidden size={18} className="spin" />
              ) : (
                <Send aria-hidden size={18} />
              )}
              {submitting ? "Submitting…" : "Submit intake"}
            </button>
            <span className="shortcut">or Ctrl + Enter</span>
          </div>
        </form>

        <aside className="new-aside">
          <section className="panel">
            <h2>Demo Transcripts</h2>
            {SAMPLE_GROUPS.map((group) => (
              <div key={group} className="samples" role="group" aria-label={group}>
                <h3 className="samples-group">{group}</h3>
                {SAMPLES.filter((sample) => sample.group === group).map((sample) => (
                  <button
                    key={sample.id}
                    type="button"
                    className="sample"
                    aria-pressed={sampleId === sample.id}
                    onClick={() => pickSample(sample.id)}
                  >
                    <span className="sample-name">{sample.clientName}</span>
                    <span className="sample-note">{sample.note}</span>
                  </button>
                ))}
              </div>
            ))}
          </section>

          <section className="panel panel-quiet">
            <h2>What happens next</h2>
            <ul className="journey">
              <li>
                <EyeOff aria-hidden size={18} />
                <span>
                  <strong>Redacted.</strong> PII becomes placeholders like [EMAIL_1]; suspicious
                  instructions raise an Injection Flag.
                </span>
              </li>
              <li>
                <Sparkles aria-hidden size={18} />
                <span>
                  <strong>Drafted.</strong> The agent writes Current Systems, an Architecture Doc,
                  an Access Checklist and Feasibility Verdicts.
                </span>
              </li>
              <li>
                <MessageSquareCheck aria-hidden size={18} />
                <span>
                  <strong>Approved in Slack.</strong> A reviewer approves or requests changes;
                  this dashboard updates live.
                </span>
              </li>
            </ul>
            <p className="journey-foot">
              <ScanText aria-hidden size={16} />
              Re-submitting the same Transcript opens its existing Intake.
            </p>
          </section>
        </aside>
      </div>
    </section>
  );
}
