import type { FormEvent, KeyboardEvent } from "react";
import {
  Activity,
  Archive,
  Clipboard,
  ExternalLink,
  History,
  ImageIcon,
  KeyRound,
  Loader2,
  Play,
  RefreshCcw,
  Server,
  Shuffle,
  ThumbsDown,
  ThumbsUp,
  UserRound,
  XCircle,
} from "lucide-react";

import type { ApiKey, GenerationHistoryItem, GenerationResponse, GpuStatus, LimitsResponse, SystemStatus } from "../types";

type AuthMode = "login" | "register";
type Health = "checking" | "online" | "offline";

type HeaderProps = {
  health: Health;
  gpuState: string;
  isAuthenticated: boolean;
  userEmail: string | null;
};

export function AppHeader({ health, gpuState, isAuthenticated, userEmail }: HeaderProps) {
  return (
    <header className="topbar">
      <a className="brandMark" href="#generate" aria-label="FLUX.2 generate workspace">
        FLUX.2
      </a>
      <nav className="topnav" aria-label="Primary">
        <a href="#generate">GENERATE</a>
        <a href="#history">HISTORY</a>
      </nav>
      <div className="systemReadout">
        <span className={`healthPill ${health}`}>
          <Server size={15} strokeWidth={1.5} />
          API / {health.toUpperCase()}
        </span>
        <span>GPU / {gpuState}</span>
        <span>{isAuthenticated ? userEmail : "SIGNED OUT"}</span>
      </div>
    </header>
  );
}

export function PageTitle() {
  return (
    <section className="pageTitle" id="generate">
      <div>
        <p className="eyebrow">PROMPT TO GPU TO IMAGE</p>
        <h1>GENERATE</h1>
      </div>
      <p className="pageStatement">A MONOCHROME WORKSTATION FOR COMPOSING, QUEUING, AND INSPECTING FLUX.2 OUTPUTS.</p>
    </section>
  );
}

type ControlPanelProps = {
  prompt: string;
  quality: string;
  numOutputs: number;
  style: string;
  aspectRatio: string;
  seed: string;
  authMode: AuthMode;
  email: string;
  password: string;
  isAuthenticated: boolean;
  userEmail: string | null;
  limits: LimitsResponse | null;
  apiKeys: ApiKey[];
  newApiKeyName: string;
  revealedApiKey: string | null;
  error: string | null;
  systemStatus: SystemStatus | null;
  gpuState: string;
  primaryGpu: GpuStatus | null;
  isSubmitting: boolean;
  isCancelling: boolean;
  isLoadingApiKeys: boolean;
  isCreatingApiKey: boolean;
  revokingApiKeyId: string | null;
  canCancel: boolean;
  examples: string[];
  defaultCandidatesByQuality: Record<string, number>;
  formatUptime: (seconds: number | null | undefined) => string;
  onSubmitGeneration: (event?: FormEvent<HTMLFormElement>) => void;
  onSubmitAuth: () => void;
  onLogout: () => void;
  onCreateApiKey: () => void;
  onRevokeApiKey: (keyId: string) => void;
  onCopyApiKey: () => void;
  onCancelGeneration: () => void;
  onCheckHealth: () => void;
  setPrompt: (value: string) => void;
  setQuality: (value: string) => void;
  setNumOutputs: (value: number) => void;
  setStyle: (value: string) => void;
  setAspectRatio: (value: string) => void;
  setSeed: (value: string) => void;
  setAuthMode: (value: AuthMode) => void;
  setEmail: (value: string) => void;
  setPassword: (value: string) => void;
  setNewApiKeyName: (value: string) => void;
};

export function ControlPanel(props: ControlPanelProps) {
  const {
    prompt,
    quality,
    numOutputs,
    style,
    aspectRatio,
    seed,
    authMode,
    email,
    password,
    isAuthenticated,
    userEmail,
    limits,
    apiKeys,
    newApiKeyName,
    revealedApiKey,
    error,
    systemStatus,
    gpuState,
    primaryGpu,
    isSubmitting,
    isCancelling,
    isLoadingApiKeys,
    isCreatingApiKey,
    revokingApiKeyId,
    canCancel,
    examples,
    defaultCandidatesByQuality,
    formatUptime,
    onSubmitGeneration,
    onSubmitAuth,
    onLogout,
    onCreateApiKey,
    onRevokeApiKey,
    onCopyApiKey,
    onCancelGeneration,
    onCheckHealth,
    setPrompt,
    setQuality,
    setNumOutputs,
    setStyle,
    setAspectRatio,
    setSeed,
    setAuthMode,
    setEmail,
    setPassword,
    setNewApiKeyName,
  } = props;

  function handleAuthKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    onSubmitAuth();
  }

  return (
    <form className="controlPanel" onSubmit={onSubmitGeneration}>
      <section className="authBox" aria-label="Account">
        <div className="sectionHeader">
          <div>
            <p className="eyebrow">ACCOUNT</p>
            <strong>{isAuthenticated ? userEmail : "LOGIN REQUIRED"}</strong>
          </div>
          <UserRound size={19} strokeWidth={1.5} />
        </div>
        {limits && (
          <dl className="limitGrid">
            <div>
              <dt>ACTIVE</dt>
              <dd>
                {limits.active_jobs}/{limits.concurrent_limit}
              </dd>
            </div>
            <div>
              <dt>RATE</dt>
              <dd>
                {limits.rate_limit_remaining}/{limits.rate_limit_per_minute}
              </dd>
            </div>
            <div>
              <dt>MONTH</dt>
              <dd>
                {limits.monthly_quota < 0 ? "UNLIMITED" : `${limits.monthly_remaining}/${limits.monthly_quota}`}
              </dd>
            </div>
          </dl>
        )}
        {isAuthenticated ? (
          <>
            <section className="apiKeyPanel" aria-label="API keys">
              <div className="sectionHeader">
                <div>
                  <p className="eyebrow">API KEYS</p>
                  <strong>{isLoadingApiKeys ? "LOADING" : `${apiKeys.length} ACTIVE`}</strong>
                </div>
                <KeyRound size={18} strokeWidth={1.5} />
              </div>
              <div className="apiKeyCreate">
                <input value={newApiKeyName} onChange={(event) => setNewApiKeyName(event.target.value)} placeholder="Key name" maxLength={128} />
                <button className="secondaryButton" type="button" onClick={onCreateApiKey} disabled={isCreatingApiKey || newApiKeyName.trim().length === 0}>
                  {isCreatingApiKey ? <Loader2 className="spin" size={16} strokeWidth={1.5} /> : "CREATE"}
                </button>
              </div>
              {revealedApiKey && (
                <div className="apiKeySecret">
                  <code>{revealedApiKey}</code>
                  <button className="iconButton" type="button" onClick={onCopyApiKey} title="Copy API key">
                    <Clipboard size={16} strokeWidth={1.5} />
                  </button>
                </div>
              )}
              <div className="apiKeyList">
                {apiKeys.length === 0 && <p className="emptyState">NO ACTIVE KEYS</p>}
                {apiKeys.map((apiKey) => (
                  <div className="apiKeyRow" key={apiKey.id}>
                    <div>
                      <strong>{apiKey.name}</strong>
                      <span>{apiKey.key_prefix}...</span>
                    </div>
                    <button className="secondaryButton dangerButton" type="button" onClick={() => onRevokeApiKey(apiKey.id)} disabled={revokingApiKeyId === apiKey.id}>
                      {revokingApiKeyId === apiKey.id ? <Loader2 className="spin" size={16} strokeWidth={1.5} /> : "REVOKE"}
                    </button>
                  </div>
                ))}
              </div>
            </section>
            <button className="secondaryButton" type="button" onClick={onLogout}>
              LOGOUT
            </button>
          </>
        ) : (
          <div className="authForm">
            <div className="authMode" aria-label="Authentication mode">
              <button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>
                LOGIN
              </button>
              <button type="button" className={authMode === "register" ? "active" : ""} onClick={() => setAuthMode("register")}>
                REGISTER
              </button>
            </div>
            <label>
              <span>EMAIL</span>
              <input value={email} onChange={(event) => setEmail(event.target.value)} onKeyDown={handleAuthKeyDown} type="email" />
            </label>
            <label>
              <span>PASSWORD</span>
              <input value={password} onChange={(event) => setPassword(event.target.value)} onKeyDown={handleAuthKeyDown} type="password" />
            </label>
            <button className="secondaryButton" type="button" onClick={onSubmitAuth}>
              {authMode === "login" ? "LOGIN" : "REGISTER"}
            </button>
          </div>
        )}
      </section>

      <div className="fieldGroup promptComposer">
        <div className="sectionHeader">
          <label htmlFor="prompt">PROMPT</label>
          <span>{prompt.length} / 4000</span>
        </div>
        <textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={8} minLength={1} maxLength={4000} />
      </div>

      <div className="quickPrompts" aria-label="Prompt examples">
        {examples.map((example) => (
          <button key={example} type="button" onClick={() => setPrompt(example)}>
            {example}
          </button>
        ))}
      </div>

      <div className="controlGrid">
        <label>
          <span>QUALITY</span>
          <select
            value={quality}
            onChange={(event) => {
              const nextQuality = event.target.value;
              setQuality(nextQuality);
              setNumOutputs(defaultCandidatesByQuality[nextQuality] ?? 1);
            }}
          >
            <option value="fast">Fast</option>
            <option value="standard">Standard</option>
            <option value="ultra">Ultra</option>
          </select>
        </label>
        <label>
          <span>STYLE</span>
          <select value={style} onChange={(event) => setStyle(event.target.value)}>
            <option value="none">None</option>
            <option value="cinematic">Cinematic</option>
            <option value="product">Product</option>
            <option value="editorial">Editorial</option>
          </select>
        </label>
        <div className="aspectControl">
          <span>ASPECT</span>
          <div className="aspectOptions" role="group" aria-label="Aspect ratio">
            {["1:1", "16:9", "9:16", "4:3"].map((ratio) => (
              <button key={ratio} className={aspectRatio === ratio ? "aspectOption selected" : "aspectOption"} type="button" onClick={() => setAspectRatio(ratio)} aria-pressed={aspectRatio === ratio}>
                <span className={`aspectGlyph aspect-${ratio.replace(":", "-")}`} />
                <span>{ratio}</span>
              </button>
            ))}
          </div>
        </div>
        <label>
          <span>OUTPUTS</span>
          <select value={numOutputs} onChange={(event) => setNumOutputs(Number(event.target.value))}>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
            <option value={4}>4</option>
          </select>
        </label>
      </div>

      <div className="seedControl">
        <label>
          <span>SEED</span>
          <input value={seed} onChange={(event) => setSeed(event.target.value.replace(/\D/g, "").slice(0, 10))} inputMode="numeric" placeholder="Random" />
        </label>
        <button className="iconButton" type="button" onClick={() => setSeed(String(Math.floor(Math.random() * 2_147_483_647)))} title="Randomize seed">
          <Shuffle size={18} strokeWidth={1.5} />
        </button>
      </div>

      <div className="actions">
        <button className="primaryButton" type="submit" disabled={!isAuthenticated || isSubmitting || prompt.trim().length === 0}>
          {isSubmitting ? <Loader2 className="spin" size={18} strokeWidth={1.5} /> : <Play size={18} strokeWidth={1.5} />}
          GENERATE
        </button>
        <button className="stopButton" type="button" onClick={onCancelGeneration} title="Stop active generation" disabled={!canCancel || isCancelling}>
          {isCancelling ? <Loader2 className="spin" size={18} strokeWidth={1.5} /> : <XCircle size={18} strokeWidth={1.5} />}
          STOP
        </button>
        <button className="iconButton" type="button" onClick={onCheckHealth} title="Refresh API health">
          <RefreshCcw size={18} strokeWidth={1.5} />
        </button>
      </div>

      {error && (
        <p className="notice errorText" role="status">
          {error}
        </p>
      )}

      <section className="monitorPanel" aria-label="System">
        <div className="sectionHeader">
          <div>
            <p className="eyebrow">SYSTEM</p>
            <strong>GPU / {gpuState}</strong>
          </div>
          <Activity size={19} strokeWidth={1.5} />
        </div>
        <dl className="metricGrid">
          <div>
            <dt>QUEUE</dt>
            <dd>{systemStatus ? systemStatus.jobs_queued : 0}</dd>
          </div>
          <div>
            <dt>ACTIVE</dt>
            <dd>{systemStatus ? systemStatus.jobs_generating : 0}</dd>
          </div>
          <div>
            <dt>GPU</dt>
            <dd>{primaryGpu ? `${primaryGpu.utilization_gpu_percent}%` : "WAITING"}</dd>
          </div>
          <div>
            <dt>VRAM</dt>
            <dd>{primaryGpu ? `${Math.round(primaryGpu.memory_used_mib / 1024)} / ${Math.round(primaryGpu.memory_total_mib / 1024)} GB` : "WAITING"}</dd>
          </div>
          <div>
            <dt>UPTIME</dt>
            <dd>{formatUptime(systemStatus?.uptime_seconds).toUpperCase()}</dd>
          </div>
          <div>
            <dt>DONE</dt>
            <dd>{systemStatus ? systemStatus.jobs_completed : 0}</dd>
          </div>
        </dl>
      </section>
    </form>
  );
}

type ResultPanelProps = {
  job: GenerationResponse | null;
  imageUrl: string | null;
  jobNumber: string;
  imageDimensions: string;
  progressLabel: string;
  progressPercent: number;
  numOutputs: number;
  feedbackMessage: string | null;
  selectingOutputId: string | null;
  isSendingFeedback: boolean;
  formatDuration: (ms: number | null | undefined) => string;
  onSelectOutput: (outputId: string) => void;
  onSendFeedback: (liked: boolean) => void;
};

export function ResultPanel(props: ResultPanelProps) {
  const {
    job,
    imageUrl,
    jobNumber,
    imageDimensions,
    progressLabel,
    progressPercent,
    numOutputs,
    feedbackMessage,
    selectingOutputId,
    isSendingFeedback,
    formatDuration,
    onSelectOutput,
    onSendFeedback,
  } = props;

  return (
    <section className={`resultPanel ${job?.status?.toLowerCase() ?? "idle"}`} aria-label="Generation result">
      <div className="resultHeader">
        <div>
          <p className="eyebrow">PIPELINE STATUS</p>
          <h2>{job ? job.status : "READY TO GENERATE."}</h2>
        </div>
        <span>{progressLabel}</span>
      </div>
      <div className="progressTrack" aria-label="Generation progress">
        <div style={{ width: `${progressPercent}%` }} />
      </div>
      <div className="imageStage" style={{ aspectRatio: job?.width && job?.height ? `${job.width} / ${job.height}` : "1 / 1" }}>
        {imageUrl ? (
          <img src={imageUrl} alt={job?.prompt ?? "Generated image"} />
        ) : (
          <div className="emptyImage">
            <span>{job?.status === "FAILED" ? "GENERATION FAILED" : job?.status === "CANCELLED" ? "JOB CANCELLED" : job ? job.status : "YOUR IMAGE WILL APPEAR HERE."}</span>
            <small>{job?.error_message ?? job?.status_message ?? jobNumber}</small>
          </div>
        )}
      </div>
      <dl className="details">
        <div>
          <dt>JOB</dt>
          <dd>{jobNumber}</dd>
        </div>
        <div>
          <dt>MODEL</dt>
          <dd>FLUX.2</dd>
        </div>
        <div>
          <dt>SIZE</dt>
          <dd>{imageDimensions}</dd>
        </div>
        <div>
          <dt>SEED</dt>
          <dd>{job?.seed ?? "RANDOM"}</dd>
        </div>
        <div>
          <dt>OUTPUTS</dt>
          <dd>{job?.candidate_count ?? numOutputs}</dd>
        </div>
        <div>
          <dt>TIME</dt>
          <dd>{formatDuration(job?.generation_time_ms).toUpperCase()}</dd>
        </div>
      </dl>
      {job?.expanded_prompt && job.expanded_prompt !== job.prompt && (
        <div className="expandedPrompt">
          <dt>EXPANDED PROMPT</dt>
          <dd>{job.expanded_prompt}</dd>
        </div>
      )}
      {imageUrl && (
        <div className="candidateGrid" aria-label="Generated candidates">
          {job?.images.map((image, index) => (
            <button key={image.id} className={image.selected ? "candidateTile selected" : "candidateTile"} type="button" onClick={() => onSelectOutput(image.id)} disabled={selectingOutputId !== null || image.selected} title={image.selected ? "Selected final image" : `Candidate ${index + 1}`}>
              <img src={image.url} alt={image.selected ? "Selected generated image" : `Candidate ${index + 1}`} />
              <span>{selectingOutputId === image.id ? "SELECTING" : image.selected ? "SELECTED" : `C${index + 1}`}</span>
              {image.seed !== null && <small>SEED {image.seed}</small>}
              {image.score !== null && <small>SCORE {Math.round(image.score * 100)}%</small>}
            </button>
          ))}
        </div>
      )}
      {imageUrl && (
        <div className="resultActions" aria-label="Result actions">
          <a className="openImage" href={imageUrl} target="_blank" rel="noreferrer">
            <ExternalLink size={17} strokeWidth={1.5} />
            OPEN IMAGE
          </a>
          <button className="feedbackButton" type="button" onClick={() => onSendFeedback(true)} disabled={isSendingFeedback}>
            <ThumbsUp size={17} strokeWidth={1.5} />
            YES
          </button>
          <button className="feedbackButton" type="button" onClick={() => onSendFeedback(false)} disabled={isSendingFeedback}>
            <ThumbsDown size={17} strokeWidth={1.5} />
            NO
          </button>
        </div>
      )}
      {feedbackMessage && (
        <p className="notice successText" role="status">
          {feedbackMessage}
        </p>
      )}
    </section>
  );
}

type HistoryPanelProps = {
  isAuthenticated: boolean;
  history: GenerationHistoryItem[];
  jobId: string | null;
  archivingJobId: string | null;
  isLoadingHistory: boolean;
  formatUtcTimestamp: (value: string) => string;
  onRefreshHistory: () => void;
  onOpenHistoryJob: (id: string) => void;
  onArchiveGeneration: (id: string) => void;
};

export function HistoryPanel(props: HistoryPanelProps) {
  const {
    isAuthenticated,
    history,
    jobId,
    archivingJobId,
    isLoadingHistory,
    formatUtcTimestamp,
    onRefreshHistory,
    onOpenHistoryJob,
    onArchiveGeneration,
  } = props;

  if (!isAuthenticated) return null;

  return (
    <section className="historyPanel" id="history">
      <div className="historyHeader">
        <div>
          <p className="eyebrow">ARCHIVE</p>
          <h2>HISTORY</h2>
        </div>
        <button className="iconButton" type="button" onClick={onRefreshHistory} title="Refresh generation history" disabled={isLoadingHistory}>
          {isLoadingHistory ? <Loader2 className="spin" size={18} strokeWidth={1.5} /> : <History size={18} strokeWidth={1.5} />}
        </button>
      </div>
      <div className="historyList">
        {history.length === 0 ? (
          <p className="mutedText">NO GENERATIONS YET</p>
        ) : (
          history.map((item) => {
            const selected = item.images.find((image) => image.selected) ?? item.images[0] ?? null;
            return (
              <article className={item.job_id === jobId ? "historyItem active" : "historyItem"} key={item.job_id}>
                <button className="historyOpen" type="button" onClick={() => onOpenHistoryJob(item.job_id)}>
                  {selected ? (
                    <img src={selected.url} alt={item.prompt} />
                  ) : (
                    <span className="historyThumb">
                      <ImageIcon size={20} strokeWidth={1.5} />
                    </span>
                  )}
                  <span>
                    <strong>{item.prompt}</strong>
                    <small>
                      JOB #{item.job_id.slice(0, 8).toUpperCase()} / {item.status} / {item.width && item.height ? `${item.width} x ${item.height}` : "PENDING"} / {formatUtcTimestamp(item.created_at)}
                    </small>
                  </span>
                </button>
                <button className="historyArchive" type="button" onClick={() => onArchiveGeneration(item.job_id)} title="Archive generation" disabled={archivingJobId !== null || item.status === "QUEUED" || item.status === "GENERATING"}>
                  {archivingJobId === item.job_id ? <Loader2 className="spin" size={16} strokeWidth={1.5} /> : <Archive size={16} strokeWidth={1.5} />}
                </button>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
