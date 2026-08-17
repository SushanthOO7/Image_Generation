"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Archive,
  ExternalLink,
  History,
  ImageIcon,
  Loader2,
  Play,
  Shuffle,
  RefreshCcw,
  Server,
  ThumbsDown,
  ThumbsUp,
  UserRound,
  XCircle,
} from "lucide-react";

type GenerationStatus = "QUEUED" | "GENERATING" | "COMPLETED" | "FAILED" | "CANCELLED";

type GenerationImage = {
  id: string;
  url: string;
  selected: boolean;
  score: number | null;
  seed: number | null;
};

type GenerationResponse = {
  job_id: string;
  status: GenerationStatus;
  status_message: string | null;
  progress: number;
  prompt: string;
  expanded_prompt: string | null;
  width: number | null;
  height: number | null;
  candidate_count: number;
  seed: number | null;
  images: GenerationImage[];
  generation_time_ms: number | null;
  ranking_time_ms: number | null;
  upscale_time_ms: number | null;
  error_code: string | null;
  error_message: string | null;
};

type GenerationHistoryItem = GenerationResponse & {
  created_at: string;
  completed_at: string | null;
};

type GenerationHistoryResponse = {
  generations: GenerationHistoryItem[];
};

type AuthResponse = {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    role: string;
  };
};

type LimitsResponse = {
  rate_limit_per_minute: number;
  rate_limit_remaining: number;
  rate_limit_reset_seconds: number;
  concurrent_limit: number;
  active_jobs: number;
};

type SystemStatus = {
  uptime_seconds: number;
  load_1m: number;
  load_5m: number;
  load_15m: number;
  cpu_count: number;
  memory_used_percent: number;
  disk_used_percent: number;
  jobs_queued: number;
  jobs_generating: number;
  jobs_completed: number;
  jobs_failed: number;
  jobs_cancelled: number;
  worker: WorkerStatus | null;
};

type WorkerStatus = {
  status: string;
  backend: string;
  preloaded: boolean;
  gpus: GpuStatus[];
};

type GpuStatus = {
  index: number;
  name: string;
  utilization_gpu_percent: number;
  memory_used_mib: number;
  memory_total_mib: number;
  temperature_c: number;
  power_draw_w: number | null;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const examples = [
  "A transparent violin made of ice on a black stage",
  "A polished chrome espresso machine in a moonlit kitchen",
  "A velvet armchair floating above a neon canyon",
];

const defaultCandidatesByQuality: Record<string, number> = {
  fast: 1,
  standard: 2,
  ultra: 4,
};

function formatUtcTimestamp(value: string) {
  return value.replace("T", " ").replace(/\.\d+Z$/, " UTC").replace("Z", " UTC");
}

function formatDuration(ms: number | null | undefined) {
  if (ms === null || ms === undefined) return "Waiting";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatUptime(seconds: number | null | undefined) {
  if (!seconds) return "0m";
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  return `${minutes}m`;
}

async function apiErrorMessage(response: Response, fallback: string) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") {
      return data.detail;
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item: { loc?: unknown[]; msg?: string }) => {
          const location = Array.isArray(item.loc) ? item.loc.join(".") : "field";
          return `${location}: ${item.msg ?? "Invalid value"}`;
        })
        .join("; ");
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export default function Home() {
  const [prompt, setPrompt] = useState(examples[0]);
  const [quality, setQuality] = useState("fast");
  const [numOutputs, setNumOutputs] = useState(1);
  const [style, setStyle] = useState("none");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [seed, setSeed] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("password123");
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [limits, setLimits] = useState<LimitsResponse | null>(null);
  const [history, setHistory] = useState<GenerationHistoryItem[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<GenerationResponse | null>(null);
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking");
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [archivingJobId, setArchivingJobId] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSendingFeedback, setIsSendingFeedback] = useState(false);
  const [selectingOutputId, setSelectingOutputId] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedImage = job?.images.find((image) => image.selected) ?? job?.images[0] ?? null;
  const imageUrl = selectedImage?.url ?? null;
  const isTerminal = job?.status === "COMPLETED" || job?.status === "FAILED" || job?.status === "CANCELLED";
  const canPoll = jobId !== null && !isTerminal;
  const canCancel = jobId !== null && job !== null && !isTerminal;
  const isAuthenticated = accessToken !== null;
  const primaryGpu = systemStatus?.worker?.gpus?.[0] ?? null;

  const progressLabel = useMemo(() => {
    if (!job) return "Waiting";
    const stage = job.status_message ? ` - ${job.status_message}` : "";
    return `${job.status}${stage} - ${Math.round(job.progress * 100)}%`;
  }, [job]);

  const gpuState = health === "offline" || !systemStatus?.worker ? "OFFLINE" : systemStatus.jobs_generating > 0 ? "BUSY" : "READY";
  const jobNumber = jobId ? `JOB #${jobId.slice(0, 8).toUpperCase()}` : "NO JOB";
  const imageDimensions = job?.width && job?.height ? `${job.width} x ${job.height}` : "PENDING";
  const progressPercent = Math.round((job?.progress ?? 0) * 100);

  async function checkHealth() {
    try {
      const response = await fetch(`${apiUrl}/internal/health`);
      setHealth(response.ok ? "online" : "offline");
    } catch {
      setHealth("offline");
    }
  }

  async function refreshSystemStatus() {
    try {
      const response = await fetch(`${apiUrl}/internal/system`);
      if (response.ok) {
        setSystemStatus((await response.json()) as SystemStatus);
      }
    } catch {
      setSystemStatus(null);
    }
  }

  async function pollGeneration(id: string) {
    const response = await fetch(`${apiUrl}/v1/generations/${id}`, {
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error(`Polling failed with HTTP ${response.status}`);
    }
    const data = (await response.json()) as GenerationResponse;
    setJob(data);
    if (data.status === "COMPLETED" || data.status === "FAILED" || data.status === "CANCELLED") {
      refreshLimits().catch(() => undefined);
      refreshHistory().catch(() => undefined);
    }
    return data;
  }

  function authHeaders(): Record<string, string> {
    return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
  }

  async function submitAuth() {
    setError(null);
    setFeedbackMessage(null);

    try {
      const response = await fetch(`${apiUrl}/v1/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(
            response,
            `${authMode === "login" ? "Login" : "Register"} failed with HTTP ${response.status}`,
          ),
        );
      }

      const data = (await response.json()) as AuthResponse;
      window.localStorage.setItem("flux_access_token", data.access_token);
      window.localStorage.setItem("flux_user_email", data.user.email);
      setAccessToken(data.access_token);
      setUserEmail(data.user.email);
      setFeedbackMessage(`${authMode === "login" ? "Logged in" : "Registered"} as ${data.user.email}`);
      await refreshLimits(data.access_token);
      await refreshHistory(data.access_token);
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Authentication failed");
    }
  }

  function logout() {
    window.localStorage.removeItem("flux_access_token");
    window.localStorage.removeItem("flux_user_email");
    setAccessToken(null);
    setUserEmail(null);
    setLimits(null);
    setHistory([]);
    setJob(null);
    setJobId(null);
  }

  async function refreshLimits(tokenOverride?: string) {
    const token = tokenOverride ?? accessToken;
    if (!token) return;
    const response = await fetch(`${apiUrl}/v1/me/limits`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) {
      setLimits((await response.json()) as LimitsResponse);
    }
  }

  async function refreshHistory(tokenOverride?: string) {
    const token = tokenOverride ?? accessToken;
    if (!token) return;

    setIsLoadingHistory(true);
    try {
      const response = await fetch(`${apiUrl}/v1/generations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = (await response.json()) as GenerationHistoryResponse;
        setHistory(data.generations);
      }
    } finally {
      setIsLoadingHistory(false);
    }
  }

  async function openHistoryJob(id: string) {
    setError(null);
    setFeedbackMessage(null);
    setJobId(id);
    try {
      await pollGeneration(id);
    } catch (historyError) {
      setError(historyError instanceof Error ? historyError.message : "Unable to open generation");
    }
  }

  async function archiveGeneration(id: string) {
    setError(null);
    setFeedbackMessage(null);
    setArchivingJobId(id);
    try {
      const response = await fetch(`${apiUrl}/v1/generations/${id}/archive`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Archive failed with HTTP ${response.status}`);
      }
      if (id === jobId) {
        setJob(null);
        setJobId(null);
      }
      await refreshHistory();
      setFeedbackMessage("Generation archived");
    } catch (archiveError) {
      setError(archiveError instanceof Error ? archiveError.message : "Unable to archive generation");
    } finally {
      setArchivingJobId(null);
    }
  }

  async function submitGeneration(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setError(null);
    setFeedbackMessage(null);
    setIsSubmitting(true);
    setJob(null);
    setJobId(null);

    try {
      const response = await fetch(`${apiUrl}/v1/generations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          prompt,
          aspect_ratio: aspectRatio,
          quality,
          style,
          num_outputs: numOutputs,
          seed: seed.trim() === "" ? null : Number(seed),
        }),
      });

      if (!response.ok) {
        throw new Error(`Submit failed with HTTP ${response.status}`);
      }

      const data = (await response.json()) as { job_id: string; status: GenerationStatus };
      setJobId(data.job_id);
      setJob({
        job_id: data.job_id,
        status: data.status,
        status_message: data.status === "QUEUED" ? "Queued" : null,
        progress: data.status === "QUEUED" ? 0.05 : 0,
        prompt,
        expanded_prompt: null,
        width: null,
        height: null,
        candidate_count: numOutputs,
        seed: seed.trim() === "" ? null : Number(seed),
        images: [],
        generation_time_ms: null,
        ranking_time_ms: null,
        upscale_time_ms: null,
        error_code: null,
        error_message: null,
      });
      await refreshLimits();
      await refreshHistory();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to submit generation");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function cancelGeneration() {
    if (jobId === null) return;

    setError(null);
    setIsCancelling(true);
    try {
      const response = await fetch(`${apiUrl}/v1/generations/${jobId}/cancel`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Cancel failed with HTTP ${response.status}`);
      }
      await pollGeneration(jobId);
      await refreshLimits();
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Unable to cancel generation");
    } finally {
      setIsCancelling(false);
    }
  }

  async function sendFeedback(liked: boolean) {
    if (jobId === null) return;

    setError(null);
    setFeedbackMessage(null);
    setIsSendingFeedback(true);
    try {
      const response = await fetch(`${apiUrl}/v1/generations/${jobId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          output_id: selectedImage?.id ?? null,
          liked,
          rating: liked ? 5 : 1,
        }),
      });
      if (!response.ok) {
        throw new Error(`Feedback failed with HTTP ${response.status}`);
      }
      setFeedbackMessage(liked ? "Liked feedback saved" : "Disliked feedback saved");
    } catch (feedbackError) {
      setError(feedbackError instanceof Error ? feedbackError.message : "Unable to save feedback");
    } finally {
      setIsSendingFeedback(false);
    }
  }

  async function selectOutput(outputId: string) {
    if (jobId === null || selectedImage?.id === outputId) return;

    setError(null);
    setFeedbackMessage(null);
    setSelectingOutputId(outputId);
    try {
      const response = await fetch(`${apiUrl}/v1/generations/${jobId}/select-output`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ output_id: outputId }),
      });
      if (!response.ok) {
        throw new Error(`Selection failed with HTTP ${response.status}`);
      }
      await pollGeneration(jobId);
      setFeedbackMessage("Selected output updated");
      await refreshHistory();
    } catch (selectError) {
      setError(selectError instanceof Error ? selectError.message : "Unable to select output");
    } finally {
      setSelectingOutputId(null);
    }
  }

  useEffect(() => {
    const storedToken = window.localStorage.getItem("flux_access_token");
    const storedEmail = window.localStorage.getItem("flux_user_email");
    if (storedToken) {
      setAccessToken(storedToken);
      setUserEmail(storedEmail);
      refreshLimits(storedToken).catch(() => undefined);
      refreshHistory(storedToken).catch(() => undefined);
    }
    checkHealth();
    refreshSystemStatus().catch(() => undefined);
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      refreshSystemStatus().catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!canPoll || jobId === null) return;

    const interval = window.setInterval(() => {
      pollGeneration(jobId).catch((pollError) => {
        setError(pollError instanceof Error ? pollError.message : "Unable to poll generation");
        window.clearInterval(interval);
      });
    }, 900);

    return () => window.clearInterval(interval);
  }, [canPoll, jobId]);

  return (
    <main className="appShell">
      <header className="topbar">
        <a className="brandMark" href="#generate" aria-label="FLUX.2 generate workspace">FLUX.2</a>
        <nav className="topnav" aria-label="Primary"><a href="#generate">GENERATE</a><a href="#history">HISTORY</a></nav>
        <div className="systemReadout">
          <span className={`healthPill ${health}`}><Server size={15} strokeWidth={1.5} />API / {health.toUpperCase()}</span>
          <span>GPU / {gpuState}</span><span>{isAuthenticated ? userEmail : "SIGNED OUT"}</span>
        </div>
      </header>
      <section className="pageTitle" id="generate">
        <div>
          <p className="eyebrow">PROMPT TO GPU TO IMAGE</p>
          <h1>GENERATE</h1>
        </div>
        <div className="snowHero" aria-hidden="true">
          <span className="snowGlow" />
          <span className="snowBeam snowBeamOne" />
          <span className="snowBeam snowBeamTwo" />
          <span className="snowBody snowBodyBase" />
          <span className="snowBody snowBodyHead" />
          <span className="snowFace snowEye snowEyeLeft" />
          <span className="snowFace snowEye snowEyeRight" />
          <span className="snowFace snowSmile" />
          <span className="snowFrost frostOne" />
          <span className="snowFrost frostTwo" />
          <span className="snowFrost frostThree" />
        </div>
      </section>
      <section className="workspace" aria-label="Generation workspace">
        <form className="controlPanel" onSubmit={submitGeneration}>
          <section className="authBox" aria-label="Account">
            <div className="sectionHeader"><div><p className="eyebrow">ACCOUNT</p><strong>{isAuthenticated ? userEmail : "LOGIN REQUIRED"}</strong></div><UserRound size={19} strokeWidth={1.5} /></div>
            {limits && <dl className="limitGrid"><div><dt>ACTIVE</dt><dd>{limits.active_jobs}/{limits.concurrent_limit}</dd></div><div><dt>RATE</dt><dd>{limits.rate_limit_remaining}/{limits.rate_limit_per_minute}</dd></div></dl>}
            {isAuthenticated ? <button className="secondaryButton" type="button" onClick={logout}>LOGOUT</button> : <div className="authForm"><div className="authMode" aria-label="Authentication mode"><button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>LOGIN</button><button type="button" className={authMode === "register" ? "active" : ""} onClick={() => setAuthMode("register")}>REGISTER</button></div><label><span>EMAIL</span><input value={email} onChange={(event) => setEmail(event.target.value)} type="email" /></label><label><span>PASSWORD</span><input value={password} onChange={(event) => setPassword(event.target.value)} type="password" /></label><button className="secondaryButton" type="button" onClick={submitAuth}>{authMode === "login" ? "LOGIN" : "REGISTER"}</button></div>}
          </section>
          <div className="fieldGroup promptComposer"><div className="sectionHeader"><label htmlFor="prompt">PROMPT</label><span>{prompt.length} / 4000</span></div><textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={8} minLength={1} maxLength={4000} /></div>
          <div className="quickPrompts" aria-label="Prompt examples">{examples.map((example) => <button key={example} type="button" onClick={() => setPrompt(example)}>{example}</button>)}</div>
          <div className="controlGrid">
            <label><span>QUALITY</span><select value={quality} onChange={(event) => { const nextQuality = event.target.value; setQuality(nextQuality); setNumOutputs(defaultCandidatesByQuality[nextQuality] ?? 1); }}><option value="fast">Fast</option><option value="standard">Standard</option><option value="ultra">Ultra</option></select></label>
            <label><span>STYLE</span><select value={style} onChange={(event) => setStyle(event.target.value)}><option value="none">None</option><option value="cinematic">Cinematic</option><option value="product">Product</option><option value="editorial">Editorial</option></select></label>
            <label><span>ASPECT</span><select value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value)}><option value="1:1">1:1</option><option value="16:9">16:9</option><option value="9:16">9:16</option><option value="4:3">4:3</option></select></label>
            <label><span>OUTPUTS</span><select value={numOutputs} onChange={(event) => setNumOutputs(Number(event.target.value))}><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option><option value={4}>4</option></select></label>
          </div>
          <div className="seedControl"><label><span>SEED</span><input value={seed} onChange={(event) => setSeed(event.target.value.replace(/\D/g, "").slice(0, 10))} inputMode="numeric" placeholder="Random" /></label><button className="iconButton" type="button" onClick={() => setSeed(String(Math.floor(Math.random() * 2_147_483_647)))} title="Randomize seed"><Shuffle size={18} strokeWidth={1.5} /></button></div>
          <div className="actions"><button className="primaryButton" type="submit" disabled={!isAuthenticated || isSubmitting || prompt.trim().length === 0}>{isSubmitting ? <Loader2 className="spin" size={18} strokeWidth={1.5} /> : <Play size={18} strokeWidth={1.5} />}GENERATE</button><button className="stopButton" type="button" onClick={cancelGeneration} title="Stop active generation" disabled={!canCancel || isCancelling}>{isCancelling ? <Loader2 className="spin" size={18} strokeWidth={1.5} /> : <XCircle size={18} strokeWidth={1.5} />}STOP</button><button className="iconButton" type="button" onClick={checkHealth} title="Refresh API health"><RefreshCcw size={18} strokeWidth={1.5} /></button></div>
          {error && <p className="notice errorText" role="status">{error}</p>}
          <section className="monitorPanel" aria-label="System"><div className="sectionHeader"><div><p className="eyebrow">SYSTEM</p><strong>GPU / {gpuState}</strong></div><Activity size={19} strokeWidth={1.5} /></div><dl className="metricGrid"><div><dt>QUEUE</dt><dd>{systemStatus ? systemStatus.jobs_queued : 0}</dd></div><div><dt>ACTIVE</dt><dd>{systemStatus ? systemStatus.jobs_generating : 0}</dd></div><div><dt>GPU</dt><dd>{primaryGpu ? `${primaryGpu.utilization_gpu_percent}%` : "WAITING"}</dd></div><div><dt>VRAM</dt><dd>{primaryGpu ? `${Math.round(primaryGpu.memory_used_mib / 1024)} / ${Math.round(primaryGpu.memory_total_mib / 1024)} GB` : "WAITING"}</dd></div><div><dt>UPTIME</dt><dd>{formatUptime(systemStatus?.uptime_seconds).toUpperCase()}</dd></div><div><dt>DONE</dt><dd>{systemStatus ? systemStatus.jobs_completed : 0}</dd></div></dl></section>
        </form>
        <section className={`resultPanel ${job?.status?.toLowerCase() ?? "idle"}`} aria-label="Generation result"><div className="resultHeader"><div><p className="eyebrow">PIPELINE STATUS</p><h2>{job ? job.status : "READY TO GENERATE."}</h2></div><span>{progressLabel}</span></div><div className="progressTrack" aria-label="Generation progress"><div style={{ width: `${progressPercent}%` }} /></div><div className="imageStage" style={{ aspectRatio: job?.width && job?.height ? `${job.width} / ${job.height}` : "1 / 1" }}>{imageUrl ? <img src={imageUrl} alt={job?.prompt ?? "Generated image"} /> : <div className="emptyImage"><span>{job?.status === "FAILED" ? "GENERATION FAILED" : job?.status === "CANCELLED" ? "JOB CANCELLED" : job ? job.status : "YOUR IMAGE WILL APPEAR HERE."}</span><small>{job?.error_message ?? job?.status_message ?? jobNumber}</small></div>}</div><dl className="details"><div><dt>JOB</dt><dd>{jobNumber}</dd></div><div><dt>MODEL</dt><dd>FLUX.2</dd></div><div><dt>SIZE</dt><dd>{imageDimensions}</dd></div><div><dt>SEED</dt><dd>{job?.seed ?? "RANDOM"}</dd></div><div><dt>OUTPUTS</dt><dd>{job?.candidate_count ?? numOutputs}</dd></div><div><dt>TIME</dt><dd>{formatDuration(job?.generation_time_ms).toUpperCase()}</dd></div></dl>{job?.expanded_prompt && job.expanded_prompt !== job.prompt && <div className="expandedPrompt"><dt>EXPANDED PROMPT</dt><dd>{job.expanded_prompt}</dd></div>}{imageUrl && <div className="candidateGrid" aria-label="Generated candidates">{job?.images.map((image, index) => <button key={image.id} className={image.selected ? "candidateTile selected" : "candidateTile"} type="button" onClick={() => selectOutput(image.id)} disabled={selectingOutputId !== null || image.selected} title={image.selected ? "Selected final image" : `Candidate ${index + 1}`}><img src={image.url} alt={image.selected ? "Selected generated image" : `Candidate ${index + 1}`} /><span>{selectingOutputId === image.id ? "SELECTING" : image.selected ? "SELECTED" : `C${index + 1}`}</span>{image.seed !== null && <small>SEED {image.seed}</small>}{image.score !== null && <small>SCORE {Math.round(image.score * 100)}%</small>}</button>)}</div>}{imageUrl && <div className="resultActions" aria-label="Result actions"><a className="openImage" href={imageUrl} target="_blank" rel="noreferrer"><ExternalLink size={17} strokeWidth={1.5} />OPEN IMAGE</a><button className="feedbackButton" type="button" onClick={() => sendFeedback(true)} disabled={isSendingFeedback}><ThumbsUp size={17} strokeWidth={1.5} />YES</button><button className="feedbackButton" type="button" onClick={() => sendFeedback(false)} disabled={isSendingFeedback}><ThumbsDown size={17} strokeWidth={1.5} />NO</button></div>}{feedbackMessage && <p className="notice successText" role="status">{feedbackMessage}</p>}</section>
      </section>
      {isAuthenticated && <section className="historyPanel" id="history"><div className="historyHeader"><div><p className="eyebrow">ARCHIVE</p><h2>HISTORY</h2></div><button className="iconButton" type="button" onClick={() => refreshHistory()} title="Refresh generation history" disabled={isLoadingHistory}>{isLoadingHistory ? <Loader2 className="spin" size={18} strokeWidth={1.5} /> : <History size={18} strokeWidth={1.5} />}</button></div><div className="historyList">{history.length === 0 ? <p className="mutedText">NO GENERATIONS YET</p> : history.map((item) => { const selected = item.images.find((image) => image.selected) ?? item.images[0] ?? null; return <article className={item.job_id === jobId ? "historyItem active" : "historyItem"} key={item.job_id}><button className="historyOpen" type="button" onClick={() => openHistoryJob(item.job_id)}>{selected ? <img src={selected.url} alt={item.prompt} /> : <span className="historyThumb"><ImageIcon size={20} strokeWidth={1.5} /></span>}<span><strong>{item.prompt}</strong><small>JOB #{item.job_id.slice(0, 8).toUpperCase()} / {item.status} / {item.width && item.height ? `${item.width} x ${item.height}` : "PENDING"} / {formatUtcTimestamp(item.created_at)}</small></span></button><button className="historyArchive" type="button" onClick={() => archiveGeneration(item.job_id)} title="Archive generation" disabled={archivingJobId !== null || item.status === "QUEUED" || item.status === "GENERATING"}>{archivingJobId === item.job_id ? <Loader2 className="spin" size={16} strokeWidth={1.5} /> : <Archive size={16} strokeWidth={1.5} />}</button></article>; })}</div></section>}
    </main>
  );
}
