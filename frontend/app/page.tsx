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
  images: GenerationImage[];
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

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const examples = [
  "A transparent violin made of ice on a black stage",
  "A polished chrome espresso machine in a moonlit kitchen",
  "A velvet armchair floating above a neon canyon",
];

function formatUtcTimestamp(value: string) {
  return value.replace("T", " ").replace(/\.\d+Z$/, " UTC").replace("Z", " UTC");
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
  const [style, setStyle] = useState("none");
  const [aspectRatio, setAspectRatio] = useState("1:1");
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

  const progressLabel = useMemo(() => {
    if (!job) return "Waiting";
    const stage = job.status_message ? ` - ${job.status_message}` : "";
    return `${job.status}${stage} - ${Math.round(job.progress * 100)}%`;
  }, [job]);

  async function checkHealth() {
    try {
      const response = await fetch(`${apiUrl}/internal/health`);
      setHealth(response.ok ? "online" : "offline");
    } catch {
      setHealth("offline");
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
          num_outputs: 1,
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
        candidate_count: 1,
        images: [],
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
        <div>
          <p className="eyebrow">FLUX.2 self-hosted platform</p>
          <h1>Generation Console</h1>
        </div>
        <div className={`healthPill ${health}`}>
          <Server size={16} />
          <span>API {health}</span>
        </div>
      </header>

      <section className="workspace">
        <form className="controlPanel" onSubmit={submitGeneration}>
          <section className="authBox">
            <div className="authHeader">
              <div>
                <p className="eyebrow">Account</p>
                <strong>{isAuthenticated ? userEmail : "Login required"}</strong>
              </div>
              <UserRound size={20} />
            </div>
            {limits && (
              <dl className="limitGrid">
                <div>
                  <dt>Active</dt>
                  <dd>
                    {limits.active_jobs}/{limits.concurrent_limit}
                  </dd>
                </div>
                <div>
                  <dt>Minute</dt>
                  <dd>{limits.rate_limit_per_minute}</dd>
                </div>
              </dl>
            )}

            {isAuthenticated ? (
              <button className="secondaryButton" type="button" onClick={logout}>
                Logout
              </button>
            ) : (
              <div className="authForm">
                <div className="authMode">
                  <button
                    type="button"
                    className={authMode === "login" ? "active" : ""}
                    onClick={() => setAuthMode("login")}
                  >
                    Login
                  </button>
                  <button
                    type="button"
                    className={authMode === "register" ? "active" : ""}
                    onClick={() => setAuthMode("register")}
                  >
                    Register
                  </button>
                </div>
                <label>
                  <span>Email</span>
                  <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" />
                </label>
                <label>
                  <span>Password</span>
                  <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" />
                </label>
                <button className="secondaryButton" type="button" onClick={submitAuth}>
                  {authMode === "login" ? "Login" : "Register"}
                </button>
              </div>
            )}
          </section>

          <div className="fieldGroup">
            <label htmlFor="prompt">Prompt</label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={6}
              minLength={1}
              maxLength={4000}
            />
          </div>

          <div className="quickPrompts">
            {examples.map((example) => (
              <button key={example} type="button" onClick={() => setPrompt(example)}>
                {example}
              </button>
            ))}
          </div>

          <div className="controlGrid">
            <label>
              <span>Quality</span>
              <select value={quality} onChange={(event) => setQuality(event.target.value)}>
                <option value="fast">Fast</option>
                <option value="standard">Standard</option>
                <option value="ultra">Ultra</option>
              </select>
            </label>

            <label>
              <span>Style</span>
              <select value={style} onChange={(event) => setStyle(event.target.value)}>
                <option value="none">None</option>
                <option value="cinematic">Cinematic</option>
                <option value="product">Product</option>
                <option value="editorial">Editorial</option>
              </select>
            </label>

            <label>
              <span>Aspect</span>
              <select value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value)}>
                <option value="1:1">1:1</option>
                <option value="16:9">16:9</option>
                <option value="9:16">9:16</option>
                <option value="4:3">4:3</option>
              </select>
            </label>
          </div>

          <div className="actions">
            <button
              className="primaryButton"
              type="submit"
              disabled={!isAuthenticated || isSubmitting || prompt.trim().length === 0}
            >
              {isSubmitting ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
              Generate
            </button>
            <button
              className="stopButton"
              type="button"
              onClick={cancelGeneration}
              title="Stop active generation"
              disabled={!canCancel || isCancelling}
            >
              {isCancelling ? <Loader2 className="spin" size={18} /> : <XCircle size={18} />}
              Stop
            </button>
            <button className="iconButton" type="button" onClick={checkHealth} title="Refresh API health">
              <RefreshCcw size={18} />
            </button>
          </div>

          {error && <p className="errorText">{error}</p>}

          {isAuthenticated && (
            <section className="historyPanel">
              <div className="historyHeader">
                <div>
                  <p className="eyebrow">History</p>
                  <strong>Recent generations</strong>
                </div>
                <button
                  className="iconButton"
                  type="button"
                  onClick={() => refreshHistory()}
                  title="Refresh generation history"
                  disabled={isLoadingHistory}
                >
                  {isLoadingHistory ? <Loader2 className="spin" size={18} /> : <History size={18} />}
                </button>
              </div>

              <div className="historyList">
                {history.length === 0 ? (
                  <p className="mutedText">No generations yet</p>
                ) : (
                  history.map((item) => {
                    const selected = item.images.find((image) => image.selected) ?? item.images[0] ?? null;
                    return (
                      <div
                        className={item.job_id === jobId ? "historyItem active" : "historyItem"}
                        key={item.job_id}
                      >
                        <button className="historyOpen" type="button" onClick={() => openHistoryJob(item.job_id)}>
                          {selected ? (
                            <img src={selected.url} alt={item.prompt} />
                          ) : (
                            <span className="historyThumb">
                              <ImageIcon size={18} />
                            </span>
                          )}
                          <span>
                            <strong>{item.prompt}</strong>
                            <small>
                              {item.status} - {item.width && item.height ? `${item.width} x ${item.height}` : "pending"} -{" "}
                              {formatUtcTimestamp(item.created_at)}
                            </small>
                          </span>
                        </button>
                        <button
                          className="historyArchive"
                          type="button"
                          onClick={() => archiveGeneration(item.job_id)}
                          title="Archive generation"
                          disabled={
                            archivingJobId !== null ||
                            item.status === "QUEUED" ||
                            item.status === "GENERATING"
                          }
                        >
                          {archivingJobId === item.job_id ? <Loader2 className="spin" size={16} /> : <Archive size={16} />}
                        </button>
                      </div>
                    );
                  })
                )}
              </div>
            </section>
          )}
        </form>

        <section className="resultPanel">
          <div className="resultHeader">
            <div>
              <p className="eyebrow">Pipeline status</p>
              <h2>{progressLabel}</h2>
            </div>
            <Activity size={22} />
          </div>

          <div className="progressTrack" aria-label="Generation progress">
            <div style={{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }} />
          </div>

          <div
            className="imageStage"
            style={{ aspectRatio: job?.width && job?.height ? `${job.width} / ${job.height}` : "1 / 1" }}
          >
            {imageUrl ? (
              <img src={imageUrl} alt={job?.prompt ?? "Generated image"} />
            ) : (
              <div className="emptyImage">
                <ImageIcon size={34} />
                <span>Generated image appears here</span>
              </div>
            )}
          </div>

          <dl className="details">
            <div>
              <dt>Job</dt>
              <dd>{jobId ?? "Not submitted"}</dd>
            </div>
            <div>
              <dt>Dimensions</dt>
              <dd>{job?.width && job?.height ? `${job.width} x ${job.height}` : "Waiting"}</dd>
            </div>
            <div>
              <dt>Candidates</dt>
              <dd>{job?.candidate_count ?? 1}</dd>
            </div>
            <div>
              <dt>Stage</dt>
              <dd>{job?.status_message ?? "Waiting"}</dd>
            </div>
          </dl>

          {job?.expanded_prompt && job.expanded_prompt !== job.prompt && (
            <div className="expandedPrompt">
              <dt>Expanded prompt</dt>
              <dd>{job.expanded_prompt}</dd>
            </div>
          )}

          {imageUrl && (
            <div className="candidateGrid">
              {job?.images.map((image, index) => (
                <button
                  key={image.id}
                  className={image.selected ? "candidateTile selected" : "candidateTile"}
                  type="button"
                  onClick={() => selectOutput(image.id)}
                  disabled={selectingOutputId !== null || image.selected}
                  title={image.selected ? "Selected final image" : `Candidate ${index}`}
                >
                  <img src={image.url} alt={image.selected ? "Selected generated image" : `Candidate ${index}`} />
                  <span>
                    {selectingOutputId === image.id ? "Selecting" : image.selected ? "Selected" : `C${index}`}
                  </span>
                </button>
              ))}
            </div>
          )}

          {imageUrl && (
            <div className="resultActions">
              <a className="openImage" href={imageUrl} target="_blank" rel="noreferrer">
                <ExternalLink size={17} />
                Open image
              </a>
              <button
                className="feedbackButton"
                type="button"
                onClick={() => sendFeedback(true)}
                disabled={isSendingFeedback}
              >
                <ThumbsUp size={17} />
                Like
              </button>
              <button
                className="feedbackButton"
                type="button"
                onClick={() => sendFeedback(false)}
                disabled={isSendingFeedback}
              >
                <ThumbsDown size={17} />
                Dislike
              </button>
            </div>
          )}
          {feedbackMessage && <p className="successText">{feedbackMessage}</p>}
        </section>
      </section>
    </main>
  );
}
