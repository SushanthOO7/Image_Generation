"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { ApiUnauthorizedError, apiUrl, authHeaders as buildAuthHeaders, parseApiResponse } from "./api-client";
import { AppHeader, ControlPanel, HistoryPanel, PageTitle, ResultPanel } from "./components/generation-workspace";
import type { ApiKey, ApiKeyCreateResponse, ApiKeyListResponse, AuthResponse, GenerationHistoryItem, GenerationHistoryResponse, GenerationResponse, GenerationStatus, LimitsResponse, SystemStatus } from "./types";

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
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [newApiKeyName, setNewApiKeyName] = useState("local script");
  const [revealedApiKey, setRevealedApiKey] = useState<string | null>(null);
  const [history, setHistory] = useState<GenerationHistoryItem[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<GenerationResponse | null>(null);
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking");
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [archivingJobId, setArchivingJobId] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingApiKeys, setIsLoadingApiKeys] = useState(false);
  const [isCreatingApiKey, setIsCreatingApiKey] = useState(false);
  const [revokingApiKeyId, setRevokingApiKeyId] = useState<string | null>(null);
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
    const data = await parseApiResponse<GenerationResponse>(response, `Polling failed with HTTP ${response.status}`);
    setJob(data);
    if (data.status === "COMPLETED" || data.status === "FAILED" || data.status === "CANCELLED") {
      refreshLimits().catch(() => undefined);
      refreshHistory().catch(() => undefined);
    }
    return data;
  }

  function authHeaders(): Record<string, string> {
    return buildAuthHeaders(accessToken);
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

      const data = await parseApiResponse<AuthResponse>(
        response,
        `${authMode === "login" ? "Login" : "Register"} failed with HTTP ${response.status}`,
      );
      window.localStorage.setItem("flux_access_token", data.access_token);
      window.localStorage.setItem("flux_user_email", data.user.email);
      setAccessToken(data.access_token);
      setUserEmail(data.user.email);
      setFeedbackMessage(`${authMode === "login" ? "Logged in" : "Registered"} as ${data.user.email}`);
      await refreshLimits(data.access_token);
      await refreshApiKeys(data.access_token);
      await refreshHistory(data.access_token);
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Authentication failed");
    }
  }

  function logout() {
    clearSession();
  }

  function clearSession(message?: string) {
    window.localStorage.removeItem("flux_access_token");
    window.localStorage.removeItem("flux_user_email");
    setAccessToken(null);
    setUserEmail(null);
    setLimits(null);
    setApiKeys([]);
    setRevealedApiKey(null);
    setHistory([]);
    setJob(null);
    setJobId(null);
    if (message) {
      setFeedbackMessage(null);
      setError(message);
    }
  }

  function handleRequestError(error: unknown, fallback: string) {
    if (error instanceof ApiUnauthorizedError) {
      clearSession(error.message);
      return;
    }
    setError(error instanceof Error ? error.message : fallback);
  }

  async function refreshLimits(tokenOverride?: string) {
    const token = tokenOverride ?? accessToken;
    if (!token) return;
    try {
      const response = await fetch(`${apiUrl}/v1/me/limits`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setLimits(await parseApiResponse<LimitsResponse>(response, `Limit refresh failed with HTTP ${response.status}`));
    } catch (limitError) {
      handleRequestError(limitError, "Unable to refresh limits");
    }
  }

  async function refreshApiKeys(tokenOverride?: string) {
    const token = tokenOverride ?? accessToken;
    if (!token) return;

    setIsLoadingApiKeys(true);
    try {
      const response = await fetch(`${apiUrl}/v1/me/api-keys`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await parseApiResponse<ApiKeyListResponse>(
        response,
        `API key refresh failed with HTTP ${response.status}`,
      );
      setApiKeys(data.api_keys.filter((apiKey) => apiKey.revoked_at === null));
    } catch (apiKeyError) {
      handleRequestError(apiKeyError, "Unable to load API keys");
    } finally {
      setIsLoadingApiKeys(false);
    }
  }

  async function createApiKey() {
    if (!accessToken || newApiKeyName.trim().length === 0) return;

    setError(null);
    setFeedbackMessage(null);
    setIsCreatingApiKey(true);
    try {
      const response = await fetch(`${apiUrl}/v1/me/api-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ name: newApiKeyName.trim() }),
      });
      const data = await parseApiResponse<ApiKeyCreateResponse>(
        response,
        `API key creation failed with HTTP ${response.status}`,
      );
      setRevealedApiKey(data.api_key);
      setNewApiKeyName("");
      await refreshApiKeys();
      setFeedbackMessage("API key created");
    } catch (apiKeyError) {
      handleRequestError(apiKeyError, "Unable to create API key");
    } finally {
      setIsCreatingApiKey(false);
    }
  }

  async function revokeApiKey(keyId: string) {
    setError(null);
    setFeedbackMessage(null);
    setRevokingApiKeyId(keyId);
    try {
      const response = await fetch(`${apiUrl}/v1/me/api-keys/${keyId}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      await parseApiResponse(response, `API key revoke failed with HTTP ${response.status}`);
      await refreshApiKeys();
      setFeedbackMessage("API key revoked");
    } catch (apiKeyError) {
      handleRequestError(apiKeyError, "Unable to revoke API key");
    } finally {
      setRevokingApiKeyId(null);
    }
  }

  async function copyRevealedApiKey() {
    if (!revealedApiKey) return;
    await navigator.clipboard.writeText(revealedApiKey);
    setFeedbackMessage("API key copied");
  }

  async function refreshHistory(tokenOverride?: string) {
    const token = tokenOverride ?? accessToken;
    if (!token) return;

    setIsLoadingHistory(true);
    try {
      const response = await fetch(`${apiUrl}/v1/generations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await parseApiResponse<GenerationHistoryResponse>(
        response,
        `History refresh failed with HTTP ${response.status}`,
      );
      setHistory(data.generations);
    } catch (historyError) {
      handleRequestError(historyError, "Unable to refresh history");
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
      handleRequestError(historyError, "Unable to open generation");
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
      await parseApiResponse(response, `Archive failed with HTTP ${response.status}`);
      if (id === jobId) {
        setJob(null);
        setJobId(null);
      }
      await refreshHistory();
      setFeedbackMessage("Generation archived");
    } catch (archiveError) {
      handleRequestError(archiveError, "Unable to archive generation");
    } finally {
      setArchivingJobId(null);
    }
  }

  async function submitGeneration(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setError(null);
    setFeedbackMessage(null);

    if (!accessToken) {
      setError("Login required");
      return;
    }

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

      const data = await parseApiResponse<{ job_id: string; status: GenerationStatus }>(
        response,
        `Submit failed with HTTP ${response.status}`,
      );
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
      handleRequestError(submitError, "Unable to submit generation");
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
      await parseApiResponse(response, `Cancel failed with HTTP ${response.status}`);
      await pollGeneration(jobId);
      await refreshLimits();
    } catch (cancelError) {
      handleRequestError(cancelError, "Unable to cancel generation");
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
      await parseApiResponse(response, `Feedback failed with HTTP ${response.status}`);
      setFeedbackMessage(liked ? "Liked feedback saved" : "Disliked feedback saved");
    } catch (feedbackError) {
      handleRequestError(feedbackError, "Unable to save feedback");
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
      await parseApiResponse(response, `Selection failed with HTTP ${response.status}`);
      await pollGeneration(jobId);
      setFeedbackMessage("Selected output updated");
      await refreshHistory();
    } catch (selectError) {
      handleRequestError(selectError, "Unable to select output");
    } finally {
      setSelectingOutputId(null);
    }
  }

  useEffect(() => {
    const storedAccessToken = window.localStorage.getItem("flux_access_token");
    const storedUserEmail = window.localStorage.getItem("flux_user_email");

    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
      setUserEmail(storedUserEmail);
      refreshLimits(storedAccessToken).catch(() => undefined);
      refreshApiKeys(storedAccessToken).catch(() => undefined);
      refreshHistory(storedAccessToken).catch(() => undefined);
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
        handleRequestError(pollError, "Unable to poll generation");
        window.clearInterval(interval);
      });
    }, 900);

    return () => window.clearInterval(interval);
  }, [canPoll, jobId]);

  return (
    <main className="appShell">
      <AppHeader health={health} gpuState={gpuState} isAuthenticated={isAuthenticated} userEmail={userEmail} />
      <PageTitle />
      <section className="workspace" aria-label="Generation workspace">
        <ControlPanel
          prompt={prompt}
          quality={quality}
          numOutputs={numOutputs}
          style={style}
          aspectRatio={aspectRatio}
          seed={seed}
          authMode={authMode}
          email={email}
          password={password}
          isAuthenticated={isAuthenticated}
          userEmail={userEmail}
          limits={limits}
          apiKeys={apiKeys}
          newApiKeyName={newApiKeyName}
          revealedApiKey={revealedApiKey}
          error={error}
          systemStatus={systemStatus}
          gpuState={gpuState}
          primaryGpu={primaryGpu}
          isSubmitting={isSubmitting}
          isCancelling={isCancelling}
          isLoadingApiKeys={isLoadingApiKeys}
          isCreatingApiKey={isCreatingApiKey}
          revokingApiKeyId={revokingApiKeyId}
          canCancel={canCancel}
          examples={examples}
          defaultCandidatesByQuality={defaultCandidatesByQuality}
          formatUptime={formatUptime}
          onSubmitGeneration={submitGeneration}
          onSubmitAuth={submitAuth}
          onLogout={logout}
          onCreateApiKey={createApiKey}
          onRevokeApiKey={revokeApiKey}
          onCopyApiKey={copyRevealedApiKey}
          onCancelGeneration={cancelGeneration}
          onCheckHealth={checkHealth}
          setPrompt={setPrompt}
          setQuality={setQuality}
          setNumOutputs={setNumOutputs}
          setStyle={setStyle}
          setAspectRatio={setAspectRatio}
          setSeed={setSeed}
          setAuthMode={setAuthMode}
          setEmail={setEmail}
          setPassword={setPassword}
          setNewApiKeyName={setNewApiKeyName}
        />
        <ResultPanel
          job={job}
          imageUrl={imageUrl}
          jobNumber={jobNumber}
          imageDimensions={imageDimensions}
          progressLabel={progressLabel}
          progressPercent={progressPercent}
          numOutputs={numOutputs}
          feedbackMessage={feedbackMessage}
          selectingOutputId={selectingOutputId}
          isSendingFeedback={isSendingFeedback}
          formatDuration={formatDuration}
          onSelectOutput={selectOutput}
          onSendFeedback={sendFeedback}
        />
      </section>
      <HistoryPanel
        isAuthenticated={isAuthenticated}
        history={history}
        jobId={jobId}
        archivingJobId={archivingJobId}
        isLoadingHistory={isLoadingHistory}
        formatUtcTimestamp={formatUtcTimestamp}
        onRefreshHistory={() => refreshHistory()}
        onOpenHistoryJob={openHistoryJob}
        onArchiveGeneration={archiveGeneration}
      />
    </main>
  );
}
