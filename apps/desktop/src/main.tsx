import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  Database,
  FolderOpen,
  HardDrive,
  ListChecks,
  Plus,
  Play,
  RefreshCw,
  Save,
  ShieldAlert,
  Trash2,
  X
} from "lucide-react";
import { confirm as confirmDialog, open } from "@tauri-apps/plugin-dialog";
import {
  fillTemplate,
  isLanguage,
  LANGUAGE_OPTIONS,
  LANGUAGE_STORAGE_KEY,
  TRANSLATIONS,
  type Language,
  type Translation
} from "./i18n";
import "./styles.css";

type Profile = {
  id: number;
  name: string;
  local_path: string;
  external_path: string;
  strict_verification: boolean;
};

type AnalyzeAction = {
  type: string;
  relative_path: string;
  size: number;
};

type AnalyzePlan = {
  plan_id: string | null;
  profile: Profile;
  summary: {
    total_actions: number;
    total_bytes: number;
    ignored_count: number;
  };
  actions: AnalyzeAction[];
};

type SyncResult = {
  session_id: number;
  status: string;
  copied_count: number;
  updated_count: number;
  skipped_count: number;
  conflict_count: number;
  conflicts_resolved_count: number;
  error_count: number;
  total_bytes: number;
  events: string[];
};

type SyncJob = {
  job_id: string;
  profile_id: number;
  plan_id: string | null;
  uses_prepared_plan: boolean;
  status: string;
  stage: string;
  message: string;
  current_path: string | null;
  processed_actions: number;
  total_actions: number;
  bytes_done: number;
  elapsed_seconds: number;
  result: SyncResult | null;
  error: string | null;
  cancel_requested: boolean;
};

type AnalyzeJob = {
  job_id: string;
  profile_id: number;
  status: string;
  stage: string;
  message: string;
  current_path?: string | null;
  elapsed_seconds: number;
  result: AnalyzePlan | null;
  error: string | null;
  cancel_requested: boolean;
};

type ApiError = {
  error: string;
};

const API_BASE_CANDIDATES = [8765, 18765, 28765, 38765, 48765].map((port) => `http://127.0.0.1:${port}`);
const TERMINAL_JOB_STATUSES = new Set(["completed", "completed_with_errors", "failed", "cancelled"]);
const TERMINAL_ANALYZE_STATUSES = new Set(["completed", "failed", "cancelled"]);

const EMPTY_PROFILE_FORM = {
  name: "",
  local_path: "",
  external_path: "",
  strict_verification: false
};

function App() {
  const [language, setLanguage] = useState<Language>(() => {
    const storedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return isLanguage(storedLanguage) ? storedLanguage : "uk";
  });
  const [backendOnline, setBackendOnline] = useState(false);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [plan, setPlan] = useState<AnalyzePlan | null>(null);
  const [analyzeJob, setAnalyzeJob] = useState<AnalyzeJob | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [syncJob, setSyncJob] = useState<SyncJob | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isCreatingProfile, setIsCreatingProfile] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState(EMPTY_PROFILE_FORM);
  const [apiBase, setApiBase] = useState(API_BASE_CANDIDATES[0]);
  const [logLines, setLogLines] = useState<string[]>([TRANSLATIONS.uk.logs.waitingBackend]);
  const text = TRANSLATIONS[language];

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [profiles, selectedProfileId]
  );

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  }, [language]);

  useEffect(() => {
    void loadProfiles();
  }, []);

  async function loadProfiles() {
    try {
      const detectedApiBase = await discoverBackend(apiBase);
      setApiBase(detectedApiBase);
      const health = await fetch(`${detectedApiBase}/health`);
      setBackendOnline(health.ok);
      const response = await fetch(`${detectedApiBase}/profiles`);
      const payload = (await response.json()) as { profiles: Profile[] };
      setProfiles(payload.profiles);
      setSelectedProfileId((current) => current ?? payload.profiles[0]?.id ?? null);
      setAnalyzeJob(null);
      setSyncResult(null);
      setSyncJob(null);
      setLogLines([fillTemplate(text.logs.backendConnectedAt, { url: detectedApiBase })]);
    } catch {
      setBackendOnline(false);
      setLogLines([text.logs.backendOffline]);
    }
  }

  function selectProfile(profileId: number) {
    setSelectedProfileId(profileId);
    setPlan(null);
    setAnalyzeJob(null);
    setSyncResult(null);
    setSyncJob(null);
  }

  async function createProfile() {
    const trimmedForm = {
      ...profileForm,
      name: profileForm.name.trim(),
      local_path: profileForm.local_path.trim(),
      external_path: profileForm.external_path.trim()
    };
    if (!trimmedForm.name || !trimmedForm.local_path || !trimmedForm.external_path) {
      setLogLines((lines) => [text.logs.profileRequired, ...lines]);
      return;
    }
    setIsSavingProfile(true);
    try {
      const response = await fetch(`${apiBase}/profiles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(trimmedForm)
      });
      const payload = (await response.json()) as { profile: Profile } | { error: string };
      if ("error" in payload) {
        setLogLines((lines) => [payload.error, ...lines]);
        return;
      }
      setProfiles((current) => [...current, payload.profile].sort((a, b) => a.name.localeCompare(b.name)));
      setSelectedProfileId(payload.profile.id);
      setPlan(null);
      setAnalyzeJob(null);
      setSyncResult(null);
      setSyncJob(null);
      setProfileForm(EMPTY_PROFILE_FORM);
      setIsCreatingProfile(false);
      setLogLines((lines) => [fillTemplate(text.logs.profileCreated, { name: payload.profile.name }), ...lines]);
    } catch {
      setLogLines((lines) => [text.logs.profileCreateFailed, ...lines]);
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function deleteProfile(profile: Profile) {
    if (isSyncing || isAnalyzing) {
      setLogLines((lines) => [text.logs.cannotDeleteWhileRunning, ...lines]);
      return;
    }
    let shouldDelete = false;
    try {
      shouldDelete = await confirmDialog(
        fillTemplate(text.deleteProfileMessage, { name: profile.name }),
        {
          title: text.deleteProfileTitle,
          kind: "warning",
          okLabel: text.deleteProfileButton,
          cancelLabel: text.cancel
        }
      );
    } catch {
      setLogLines((lines) => [text.logs.deleteConfirmationFailed, ...lines]);
      return;
    }
    if (!shouldDelete) {
      return;
    }

    try {
      const response = await fetch(`${apiBase}/profiles/${profile.id}`, { method: "DELETE" });
      const payload = (await response.json()) as { deleted: true; profile_id: number } | { error: string };
      if ("error" in payload) {
        setLogLines((lines) => [payload.error, ...lines]);
        return;
      }
      const nextProfiles = profiles.filter((current) => current.id !== profile.id);
      setProfiles(nextProfiles);
      if (selectedProfileId === profile.id) {
        setSelectedProfileId(nextProfiles[0]?.id ?? null);
        setPlan(null);
        setAnalyzeJob(null);
        setSyncResult(null);
        setSyncJob(null);
      }
      setLogLines((lines) => [fillTemplate(text.logs.profileDeleted, { name: profile.name }), ...lines]);
    } catch {
      setLogLines((lines) => [text.logs.profileDeleteFailed, ...lines]);
    }
  }

  async function chooseFolder(field: "local_path" | "external_path") {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: field === "local_path" ? text.selectComputerFolder : text.selectExternalFolder
      });
      if (typeof selected === "string") {
        setProfileForm((form) => ({ ...form, [field]: selected }));
      }
    } catch {
      setLogLines((lines) => [text.logs.folderPickerFailed, ...lines]);
    }
  }

  async function analyzeSelectedProfile() {
    if (!selectedProfileId) {
      setLogLines((lines) => [text.logs.noProfileSelected, ...lines]);
      return;
    }
    setIsAnalyzing(true);
    setPlan(null);
    setAnalyzeJob(null);
    setSyncResult(null);
    setSyncJob(null);
    setLogLines((lines) => [text.logs.analysisStarted, ...lines]);
    try {
      const response = await fetch(`${apiBase}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: selectedProfileId })
      });
      const payload = (await response.json()) as AnalyzeJob | ApiError;
      if (!isAnalyzeJob(payload)) {
        setLogLines((lines) => [payload.error, ...lines]);
        return;
      }
      setAnalyzeJob(payload);
      await pollAnalyzeJob(payload.job_id);
    } catch {
      setLogLines((lines) => [text.logs.analyzeFailedOffline, ...lines]);
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function pollAnalyzeJob(jobId: string) {
    while (true) {
      await delay(1000);
      const response = await fetch(`${apiBase}/analyze-jobs/${jobId}`);
      const payload = (await response.json()) as AnalyzeJob | ApiError;
      if (!isAnalyzeJob(payload)) {
        setLogLines((lines) => [payload.error, ...lines]);
        return;
      }
      setAnalyzeJob(payload);
      if (TERMINAL_ANALYZE_STATUSES.has(payload.status)) {
        const result = payload.result;
        if (result) {
          setPlan(result);
          const stats = getPlanStats(result);
          setLogLines((lines) => [
            fillTemplate(text.logs.analyzeCompleted, {
              changes: formatNumber(stats.syncChanges, language),
              items: formatNumber(stats.totalItems, language)
            }),
            ...lines
          ]);
        } else if (payload.status === "cancelled") {
          setLogLines((lines) => [text.logs.analyzeCancelled, ...lines]);
        } else {
          setLogLines((lines) => [
            fillTemplate(text.logs.analyzeFailed, { message: payload.error ?? translateBackendMessage(payload.message, text) }),
            ...lines
          ]);
        }
        return;
      }
    }
  }

  async function synchronizeSelectedProfile() {
    if (!selectedProfileId) {
      setLogLines((lines) => [text.logs.noProfileSelected, ...lines]);
      return;
    }
    setIsSyncing(true);
    setSyncResult(null);
    setSyncJob(null);
    setLogLines((lines) => [text.logs.synchronizationStarted, ...lines]);
    try {
      const response = await fetch(`${apiBase}/synchronize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: selectedProfileId,
          plan_id: plan?.profile.id === selectedProfileId ? plan.plan_id : null
        })
      });
      const payload = (await response.json()) as SyncJob | ApiError;
      if (!isSyncJob(payload)) {
        setLogLines((lines) => [payload.error, ...lines]);
        return;
      }
      setSyncJob(payload);
      if (payload.uses_prepared_plan) {
        setLogLines((lines) => [text.logs.usingPreparedPlan, ...lines]);
      }
      await pollSyncJob(payload.job_id);
    } catch {
      setLogLines((lines) => [text.logs.syncFailedOffline, ...lines]);
    } finally {
      setIsSyncing(false);
    }
  }

  async function pollSyncJob(jobId: string) {
    while (true) {
      await delay(1000);
      const response = await fetch(`${apiBase}/sync-jobs/${jobId}`);
      const payload = (await response.json()) as SyncJob | ApiError;
      if (!isSyncJob(payload)) {
        setLogLines((lines) => [payload.error, ...lines]);
        return;
      }
      setSyncJob(payload);
      if (TERMINAL_JOB_STATUSES.has(payload.status)) {
        const result = payload.result;
        if (result) {
          setSyncResult(result);
          setLogLines((lines) => [
            fillTemplate(text.logs.syncCompleted, {
              status: formatStatus(result.status, text),
              copied: formatNumber(result.copied_count, language),
              updated: formatNumber(result.updated_count, language),
              conflicts: formatNumber(result.conflicts_resolved_count, language)
            }),
            ...result.events.slice(0, 8),
            ...lines
          ]);
          setPlan(null);
        } else if (payload.status === "cancelled") {
          setLogLines((lines) => [text.logs.syncCancelled, ...lines]);
        } else {
          setLogLines((lines) => [
            fillTemplate(text.logs.syncFailed, { message: payload.error ?? translateBackendMessage(payload.message, text) }),
            ...lines
          ]);
        }
        return;
      }
    }
  }

  async function cancelCurrentWork() {
    const activeAnalyzeJobId = isAnalyzing ? analyzeJob?.job_id : null;
    const activeSyncJobId = isSyncing ? syncJob?.job_id : null;
    if (!activeAnalyzeJobId && !activeSyncJobId) {
      setLogLines((lines) => [text.logs.noActiveJob, ...lines]);
      return;
    }

    try {
      if (activeAnalyzeJobId) {
        const response = await fetch(`${apiBase}/analyze-jobs/${activeAnalyzeJobId}/cancel`, { method: "POST" });
        const payload = (await response.json()) as AnalyzeJob | ApiError;
        if (isAnalyzeJob(payload)) {
          setAnalyzeJob(payload);
          setLogLines((lines) => [text.logs.cancelAnalyzeRequested, ...lines]);
          return;
        }
        setLogLines((lines) => [payload.error, ...lines]);
        return;
      }

      if (activeSyncJobId) {
        const response = await fetch(`${apiBase}/sync-jobs/${activeSyncJobId}/cancel`, { method: "POST" });
        const payload = (await response.json()) as SyncJob | ApiError;
        if (isSyncJob(payload)) {
          setSyncJob(payload);
          setLogLines((lines) => [text.logs.cancelSyncRequested, ...lines]);
          return;
        }
        setLogLines((lines) => [payload.error, ...lines]);
      }
    } catch {
      setLogLines((lines) => [text.logs.cancelFailedOffline, ...lines]);
    }
  }

  const planRows = summarizePlan(plan, text);
  const progressPercent = getProgressPercent(analyzeJob, syncJob, syncResult, isAnalyzing, isSyncing);
  const progressWidth = `${progressPercent}%`;
  const isWorking = isAnalyzing || isSyncing;
  const isCancelRequested = Boolean(analyzeJob?.cancel_requested || syncJob?.cancel_requested);
  const isIndeterminate = isAnalyzing || (isSyncing && (!syncJob || syncJob.total_actions === 0));
  const rawProgressStatus = analyzeJob?.status ?? syncJob?.status ?? (syncResult ? syncResult.status : "not_running");
  const progressStatus = formatStatus(rawProgressStatus, text);
  const progressMessage = getProgressMessage(analyzeJob, syncJob, syncResult, text, language);
  const currentPath = isAnalyzing ? analyzeJob?.current_path ?? text.analyzingFolderTree : syncJob?.current_path ?? "-";
  const elapsed = analyzeJob
    ? formatDuration(analyzeJob.elapsed_seconds)
    : syncJob
      ? formatDuration(syncJob.elapsed_seconds)
      : "-";
  const progressActionLabel = getProgressActionLabel(analyzeJob, syncJob, isAnalyzing, isSyncing, text, language);

  return (
    <main className="app-shell" lang={language}>
      <aside className="sidebar">
        <div className="brand">
          <HardDrive aria-hidden="true" />
          <span>BackupFlow</span>
        </div>
        <div className="language-control">
          <label htmlFor="language-select">{text.languageLabel}</label>
          <select
            id="language-select"
            value={language}
            onChange={(event) => setLanguage(event.target.value as Language)}
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <nav className="profile-list" aria-label={text.profilesNav}>
          <button className="new-profile-button" onClick={() => setIsCreatingProfile(true)} disabled={isWorking}>
            <Plus aria-hidden="true" />
            {text.newProfileButton}
          </button>
          {profiles.length === 0 ? (
            <p className="empty-state">{text.noProfilesYet}</p>
          ) : (
            profiles.map((profile) => (
              <div className="profile-row" key={profile.id}>
                <button
                  className={`profile ${profile.id === selectedProfileId ? "active" : ""}`}
                  onClick={() => selectProfile(profile.id)}
                >
                  {profile.name}
                </button>
                <button
                  className="delete-profile-button"
                  type="button"
                  onClick={() => void deleteProfile(profile)}
                  disabled={isWorking}
                  aria-label={fillTemplate(text.deleteProfileAria, { name: profile.name })}
                  title={text.deleteProfileTitle}
                >
                  <Trash2 aria-hidden="true" />
                </button>
              </div>
            ))
          )}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{text.externalDrive}</p>
            <h1>{selectedProfile ? selectedProfile.name : text.noProfileSelected}</h1>
          </div>
          <div className="topbar-actions">
            <div className="drive-state">
              <span className={`status-dot ${backendOnline ? "" : "offline"}`} />
              {backendOnline ? text.backendConnected : text.backendOffline}
            </div>
          </div>
        </header>

        {isCreatingProfile ? (
          <section className="panel profile-form-panel">
            <div className="panel-title">
              <Plus aria-hidden="true" />
              <h2>{text.newProfileTitle}</h2>
            </div>
            <div className="profile-form-grid">
              <label>
                <span>{text.name}</span>
                <input
                  value={profileForm.name}
                  onChange={(event) => setProfileForm((form) => ({ ...form, name: event.target.value }))}
                  placeholder={text.namePlaceholder}
                />
              </label>
              <label>
                <span>{text.computerFolder}</span>
                <div className="path-picker-row">
                  <input
                    value={profileForm.local_path}
                    onChange={(event) => setProfileForm((form) => ({ ...form, local_path: event.target.value }))}
                  />
                  <button
                    className="icon-button"
                    type="button"
                    onClick={() => void chooseFolder("local_path")}
                    disabled={isSavingProfile || isAnalyzing}
                    aria-label={text.chooseComputerFolder}
                    title={text.chooseComputerFolder}
                  >
                    <FolderOpen aria-hidden="true" />
                  </button>
                </div>
              </label>
              <label>
                <span>{text.externalFolder}</span>
                <div className="path-picker-row">
                  <input
                    value={profileForm.external_path}
                    onChange={(event) => setProfileForm((form) => ({ ...form, external_path: event.target.value }))}
                  />
                  <button
                    className="icon-button"
                    type="button"
                    onClick={() => void chooseFolder("external_path")}
                    disabled={isSavingProfile || isAnalyzing}
                    aria-label={text.chooseExternalFolder}
                    title={text.chooseExternalFolder}
                  >
                    <FolderOpen aria-hidden="true" />
                  </button>
                </div>
              </label>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={profileForm.strict_verification}
                  onChange={(event) =>
                    setProfileForm((form) => ({ ...form, strict_verification: event.target.checked }))
                  }
                />
                <span className="tooltip-anchor" tabIndex={0} data-tooltip={text.strictVerificationHelp}>
                  {text.strictVerification}
                </span>
              </label>
            </div>
            <div className="actions-row">
              <button
                className="secondary-button"
                onClick={() => {
                  setIsCreatingProfile(false);
                  setProfileForm(EMPTY_PROFILE_FORM);
                }}
                disabled={isSavingProfile || isAnalyzing}
              >
                <X aria-hidden="true" />
                {text.cancel}
              </button>
              <button className="primary-button" onClick={() => void createProfile()} disabled={isSavingProfile || isAnalyzing}>
                <Save aria-hidden="true" />
                {text.save}
              </button>
            </div>
          </section>
        ) : null}

        <section className="sync-grid">
          <div className="panel folders-panel">
            <div className="panel-title">
              <Database aria-hidden="true" />
              <h2>{text.folders}</h2>
            </div>
            <div className="folder-pair">
              <span>{text.computer}</span>
              <strong>{selectedProfile?.local_path ?? "-"}</strong>
            </div>
            <div className="folder-pair">
              <span>{text.external}</span>
              <strong>{selectedProfile?.external_path ?? "-"}</strong>
            </div>
            <div className="actions-row">
              <button className="secondary-button" onClick={() => void loadProfiles()} disabled={isWorking}>
                <RefreshCw aria-hidden="true" />
                {text.refresh}
              </button>
              <button className="secondary-button" onClick={() => void analyzeSelectedProfile()} disabled={isWorking}>
                <ListChecks aria-hidden="true" />
                {text.analyze}
              </button>
              <button className="primary-button" onClick={() => void synchronizeSelectedProfile()} disabled={isWorking}>
                <Play aria-hidden="true" />
                {text.synchronize}
              </button>
            </div>
          </div>

          <div className="panel safety-panel">
            <div className="panel-title">
              <ShieldAlert aria-hidden="true" />
              <h2>{text.safety}</h2>
            </div>
            <dl>
              <div>
                <dt>{text.defaultConflictAction}</dt>
                <dd>{text.keepBoth}</dd>
              </div>
              <div>
                <dt>{text.deletionMode}</dt>
                <dd>.BackupFlowTrash</dd>
              </div>
              <div>
                <dt>{text.strictVerificationShort}</dt>
                <dd>{selectedProfile?.strict_verification ? text.on : text.off}</dd>
              </div>
            </dl>
          </div>
        </section>

        <section className="panel plan-panel">
          <div className="panel-title">
            <ListChecks aria-hidden="true" />
            <h2>{text.syncPlan}</h2>
          </div>
          <div className="plan-table" role="table">
            {planRows.length === 0 ? (
              <p className="empty-state">{text.planEmpty}</p>
            ) : planRows.map((row) => (
              <div className="plan-row" role="row" key={row.label}>
                <span>{row.label}</span>
                <strong>{row.count.toLocaleString()}</strong>
                <em>{row.size}</em>
              </div>
            ))}
          </div>
        </section>

        <section className="panel progress-panel">
          <div className="panel-title">
            <Activity aria-hidden="true" />
            <h2>{text.progress}</h2>
          </div>
          {isWorking ? (
            <div className="progress-actions">
              <button
                className="secondary-button danger-button"
                type="button"
                onClick={() => void cancelCurrentWork()}
                disabled={isCancelRequested}
              >
                <X aria-hidden="true" />
                {isCancelRequested ? text.stopping : text.stop}
              </button>
            </div>
          ) : null}
          <div
            className={`progress-track ${isIndeterminate ? "indeterminate" : ""}`}
            aria-label={text.progressAria}
          >
            <span style={{ width: progressWidth }} />
          </div>
          <div className="progress-details">
            <span>{text.stage}: {formatStage(analyzeJob?.stage ?? syncJob?.stage, text)}</span>
            <span>{text.elapsed}: {elapsed}</span>
            <span>{progressActionLabel}</span>
          </div>
          <div className="progress-message">{progressMessage}</div>
          <div className="progress-meta">
            <span>{text.current}: {currentPath}</span>
            <strong>{formatBytes(syncJob?.bytes_done ?? syncResult?.total_bytes ?? 0)}</strong>
            <span>
              {progressStatus}
              {syncResult?.conflicts_resolved_count
                ? `, ${text.keptBoth}: ${formatNumber(syncResult.conflicts_resolved_count, language)}`
                : ""}
            </span>
          </div>
        </section>

        <section className="log-panel">
          {logLines.map((line, index) => (
            <span key={`${index}-${line}`}>{line}</span>
          ))}
        </section>
      </section>
    </main>
  );
}

function summarizePlan(plan: AnalyzePlan | null, text: Translation) {
  if (!plan) {
    return [];
  }
  const byType = new Map<string, { count: number; size: number }>();
  for (const action of plan.actions) {
    const current = byType.get(action.type) ?? { count: 0, size: 0 };
    current.count += 1;
    current.size += action.size;
    byType.set(action.type, current);
  }
  return Array.from(byType.entries()).map(([type, value]) => ({
    label: formatActionType(type, text),
    count: value.count,
    size: value.size ? formatBytes(value.size) : "-"
  }));
}

function getPlanStats(plan: AnalyzePlan) {
  return {
    totalItems: plan.actions.length,
    syncChanges: plan.actions.filter((action) => !["skip", "ignore"].includes(action.type)).length
  };
}

function formatActionType(type: string, text: Translation) {
  return text.planActions[type as keyof Translation["planActions"]] ?? type.split("_").join(" ");
}

function getProgressMessage(
  analyzeJob: AnalyzeJob | null,
  syncJob: SyncJob | null,
  syncResult: SyncResult | null,
  text: Translation,
  language: Language
) {
  if (analyzeJob?.status === "completed" && analyzeJob.result) {
    const stats = getPlanStats(analyzeJob.result);
    return fillTemplate(text.progressMessages.analysisCompleted, {
      changes: formatNumber(stats.syncChanges, language),
      items: formatNumber(stats.totalItems, language)
    });
  }
  if (analyzeJob) {
    return translateBackendMessage(analyzeJob.message, text);
  }
  if (syncJob) {
    return translateBackendMessage(syncJob.message, text);
  }
  if (syncResult) {
    return text.syncFinished;
  }
  return text.noSyncRunning;
}

function translateBackendMessage(message: string, text: Translation) {
  const messages: Record<string, string> = {
    "Waiting to start analysis.": text.progressMessages.waitingAnalysis,
    "Scanning folders and building synchronization plan.": text.progressMessages.scanningFolders,
    "Analysis cancelled.": text.progressMessages.analysisCancelled,
    "Strict verification is hashing local file.": text.progressMessages.strictHashing,
    "Strict verification is hashing external file.": text.progressMessages.strictHashing,
    "Waiting to start synchronization.": text.progressMessages.waitingSync,
    "Starting synchronization.": text.progressMessages.startingSync,
    "Synchronization cancelled.": text.progressMessages.syncCancelled
  };
  return messages[message] ?? message;
}

function formatBytes(bytes: number) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function getProgressPercent(
  analyzeJob: AnalyzeJob | null,
  syncJob: SyncJob | null,
  syncResult: SyncResult | null,
  isAnalyzing: boolean,
  isSyncing: boolean
) {
  if (analyzeJob?.status === "completed") {
    return 100;
  }
  if (syncResult) {
    return 100;
  }
  if (isAnalyzing) {
    return 12;
  }
  if (!isSyncing || !syncJob) {
    return 0;
  }
  if (syncJob.total_actions <= 0) {
    return 12;
  }
  return Math.max(4, Math.min(98, Math.round((syncJob.processed_actions / syncJob.total_actions) * 100)));
}

function getProgressActionLabel(
  analyzeJob: AnalyzeJob | null,
  syncJob: SyncJob | null,
  isAnalyzing: boolean,
  isSyncing: boolean,
  text: Translation,
  language: Language
) {
  if (isSyncing && syncJob) {
    return `${text.actions}: ${formatNumber(syncJob.processed_actions, language)}/${syncJob.total_actions ? formatNumber(syncJob.total_actions, language) : "?"}`;
  }
  if (isAnalyzing) {
    return `${text.files}: ${analyzeJob?.stage === "comparing" ? text.comparingShort : text.scanningShort}`;
  }
  if (analyzeJob?.status === "completed" && analyzeJob.result) {
    const stats = getPlanStats(analyzeJob.result);
    return `${text.found}: ${formatNumber(stats.syncChanges, language)} ${text.changes}`;
  }
  if (syncJob?.status === "cancelled") {
    return `${text.actions}: ${text.cancelledActions}`;
  }
  return `${text.actions}: ${text.idle}`;
}

function formatStatus(status: string, text: Translation) {
  const labels: Record<string, string> = {
    not_running: text.notRunning,
    running: text.running,
    completed: text.completed,
    completed_with_errors: text.completedWithErrors,
    failed: text.failed,
    cancelled: text.cancelled,
    queued: text.queued
  };
  return labels[status] ?? status;
}

function formatStage(stage: string | undefined, text: Translation) {
  if (!stage) {
    return "-";
  }
  const labels: Record<string, string> = {
    queued: text.queued,
    starting: text.starting,
    analyzing: text.analyzing,
    scanning: text.scanning,
    comparing: text.comparing,
    hashing: text.hashing,
    finished: text.finished,
    failed: text.failed,
    cancelled: text.cancelled
  };
  return labels[stage] ?? stage;
}

function formatNumber(value: number, language: Language) {
  return value.toLocaleString(language === "uk" ? "uk-UA" : "en-US");
}

function formatDuration(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function discoverBackend(preferredApiBase: string) {
  const candidates = [
    preferredApiBase,
    ...API_BASE_CANDIDATES.filter((candidate) => candidate !== preferredApiBase)
  ];

  for (const candidate of candidates) {
    try {
      const response = await fetchWithTimeout(`${candidate}/health`, 900);
      if (response.ok) {
        return candidate;
      }
    } catch {
      continue;
    }
  }

  throw new Error("BackupFlow backend is offline.");
}

async function fetchWithTimeout(url: string, timeoutMs: number) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function isSyncJob(payload: SyncJob | ApiError): payload is SyncJob {
  return "job_id" in payload;
}

function isAnalyzeJob(payload: AnalyzeJob | ApiError): payload is AnalyzeJob {
  return "job_id" in payload;
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
