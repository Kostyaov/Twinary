from __future__ import annotations

import json
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backupflow.config.defaults import DEFAULT_EXCLUSIONS
from backupflow.db.connection import connect, get_db_path
from backupflow.db.repositories import (
    ConflictRepository,
    FileMetadataRepository,
    ProfileRepository,
    SyncSessionRepository,
)
from backupflow.db.schema import initialize_schema
from backupflow.sync.analyzer import SyncAnalyzer
from backupflow.sync.executor import SyncExecutor


TERMINAL_JOB_STATUSES = {"completed", "completed_with_errors", "failed", "cancelled"}


class AnalyzePlanManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plans: dict[str, dict] = {}

    def store(self, profile_id: int, plan) -> str:
        plan_id = uuid.uuid4().hex
        with self._lock:
            self._plans[plan_id] = {
                "profile_id": profile_id,
                "plan": plan,
                "created_at": time.time(),
            }
        return plan_id

    def get(self, plan_id: str | None, profile_id: int):
        if not plan_id:
            return None
        with self._lock:
            stored = self._plans.get(plan_id)
        if stored is None or stored["profile_id"] != profile_id:
            return None
        return stored["plan"]


class AnalyzeJobManager:
    def __init__(self, plan_manager: AnalyzePlanManager) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._plan_manager = plan_manager

    def start(self, profile_id: int) -> dict:
        job_id = uuid.uuid4().hex
        now = time.time()
        job = {
            "job_id": job_id,
            "profile_id": profile_id,
            "status": "queued",
            "stage": "queued",
            "message": "Waiting to start analysis.",
            "elapsed_seconds": 0,
            "started_at": now,
            "finished_at": None,
            "result": None,
            "error": None,
            "cancel_requested": False,
        }
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(target=self._run, args=(job_id, profile_id), daemon=True)
        thread.start()
        return self.get(job_id) or job

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            snapshot = dict(job)
        end_time = snapshot["finished_at"] or time.time()
        snapshot["elapsed_seconds"] = max(0, int(end_time - snapshot["started_at"]))
        return snapshot

    def cancel(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job["status"] not in TERMINAL_JOB_STATUSES:
                job.update(
                    cancel_requested=True,
                    message="Cancel requested. Stopping analysis after the current file.",
                )
        return self.get(job_id)

    def _update(self, job_id: str, **updates) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(updates)

    def _is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.get("cancel_requested"))

    def _run(self, job_id: str, profile_id: int) -> None:
        self._update(
            job_id,
            status="running",
            stage="analyzing",
            message="Scanning folders and building synchronization plan.",
        )

        def progress_callback(event: dict) -> None:
            self._update(job_id, **event)

        def should_cancel() -> bool:
            return self._is_cancel_requested(job_id)

        try:
            with connect() as connection:
                initialize_schema(connection)
                profile_repo = ProfileRepository(connection)
                profile = profile_repo.get(profile_id)
                if profile is None:
                    raise ValueError(f"Profile not found: {profile_id}")
                metadata_repo = FileMetadataRepository(connection)
                plan = SyncAnalyzer(progress_callback=progress_callback, should_cancel=should_cancel).analyze(
                    profile,
                    metadata_repo.list_for_profile(profile_id),
                )
            plan_id = self._plan_manager.store(profile_id, plan)
            self._update(
                job_id,
                status="completed",
                stage="finished",
                message="Analysis completed.",
                result=_plan_to_dict(plan, plan_id),
                finished_at=time.time(),
            )
        except InterruptedError as error:
            self._update(
                job_id,
                status="cancelled",
                stage="cancelled",
                message="Analysis cancelled.",
                error=str(error),
                finished_at=time.time(),
            )
        except Exception as error:
            self._update(
                job_id,
                status="failed",
                stage="failed",
                message="Analysis failed.",
                error=str(error),
                finished_at=time.time(),
            )


class SyncJobManager:
    def __init__(self, plan_manager: AnalyzePlanManager) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._plan_manager = plan_manager

    def start(self, profile_id: int, plan_id: str | None = None) -> dict:
        job_id = uuid.uuid4().hex
        now = time.time()
        uses_prepared_plan = self._plan_manager.get(plan_id, profile_id) is not None
        job = {
            "job_id": job_id,
            "profile_id": profile_id,
            "plan_id": plan_id,
            "uses_prepared_plan": uses_prepared_plan,
            "status": "queued",
            "stage": "queued",
            "message": "Waiting to start synchronization.",
            "current_path": None,
            "processed_actions": 0,
            "total_actions": 0,
            "bytes_done": 0,
            "elapsed_seconds": 0,
            "started_at": now,
            "finished_at": None,
            "result": None,
            "error": None,
            "cancel_requested": False,
        }
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(target=self._run, args=(job_id, profile_id, plan_id), daemon=True)
        thread.start()
        return self.get(job_id) or job

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            snapshot = dict(job)
        end_time = snapshot["finished_at"] or time.time()
        snapshot["elapsed_seconds"] = max(0, int(end_time - snapshot["started_at"]))
        return snapshot

    def cancel(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job["status"] not in TERMINAL_JOB_STATUSES:
                job.update(
                    cancel_requested=True,
                    message="Cancel requested. Stopping synchronization after the current file.",
                )
        return self.get(job_id)

    def _update(self, job_id: str, **updates) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(updates)

    def _is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.get("cancel_requested"))

    def _run(self, job_id: str, profile_id: int, plan_id: str | None) -> None:
        self._update(job_id, status="running", stage="starting", message="Starting synchronization.")

        def progress_callback(event: dict) -> None:
            self._update(job_id, **event)

        def should_cancel() -> bool:
            return self._is_cancel_requested(job_id)

        try:
            with connect() as connection:
                initialize_schema(connection)
                profile_repo = ProfileRepository(connection)
                profile = profile_repo.get(profile_id)
                if profile is None:
                    raise ValueError(f"Profile not found: {profile_id}")
                metadata_repo = FileMetadataRepository(connection)
                session_repo = SyncSessionRepository(connection)
                conflict_repo = ConflictRepository(connection)
                prepared_plan = self._plan_manager.get(plan_id, profile_id)
                self._update(job_id, uses_prepared_plan=prepared_plan is not None)
                result = SyncExecutor(
                    session_repo,
                    metadata_repo,
                    conflict_repo,
                    progress_callback=progress_callback,
                    should_cancel=should_cancel,
                ).synchronize(profile, prepared_plan)

            self._update(
                job_id,
                status=result.status,
                stage="finished",
                message=f"Synchronization {result.status}.",
                current_path=None,
                result=_sync_result_to_dict(result),
                finished_at=time.time(),
            )
        except InterruptedError as error:
            self._update(
                job_id,
                status="cancelled",
                stage="cancelled",
                message="Synchronization cancelled.",
                current_path=None,
                error=str(error),
                finished_at=time.time(),
            )
        except Exception as error:
            self._update(
                job_id,
                status="failed",
                stage="failed",
                message="Synchronization failed.",
                error=str(error),
                finished_at=time.time(),
            )


ANALYZE_PLANS = AnalyzePlanManager()
ANALYZE_JOBS = AnalyzeJobManager(ANALYZE_PLANS)
SYNC_JOBS = SyncJobManager(ANALYZE_PLANS)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), BackupFlowRequestHandler)
    print(json.dumps({"status": "listening", "host": host, "port": port, "database": str(get_db_path())}))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(json.dumps({"status": "stopped"}))
    finally:
        server.server_close()


class BackupFlowRequestHandler(BaseHTTPRequestHandler):
    server_version = "BackupFlow/1.0"

    def do_GET(self) -> None:
        route = urlparse(self.path)
        try:
            if route.path == "/health":
                self._send_json({"status": "ok", "database": str(get_db_path())})
                return
            if route.path == "/profiles":
                with connect() as connection:
                    initialize_schema(connection)
                    profiles = ProfileRepository(connection).list()
                self._send_json({"profiles": [_profile_to_dict(profile) for profile in profiles]})
                return
            if route.path == "/analyze":
                query = parse_qs(route.query)
                profile_id = int(query.get("profile_id", ["0"])[0])
                self._send_json(_analyze_profile(profile_id))
                return
            if route.path.startswith("/sync-jobs/"):
                job_id = route.path.removeprefix("/sync-jobs/")
                job = SYNC_JOBS.get(job_id)
                if job is None:
                    self._send_json({"error": f"Sync job not found: {job_id}"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json(job)
                return
            if route.path.startswith("/analyze-jobs/"):
                job_id = route.path.removeprefix("/analyze-jobs/")
                job = ANALYZE_JOBS.get(job_id)
                if job is None:
                    self._send_json({"error": f"Analyze job not found: {job_id}"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json(job)
                return
        except FileNotFoundError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        except (ValueError, TypeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        route = urlparse(self.path)
        try:
            if route.path == "/analyze":
                payload = self._read_json()
                profile_id = int(payload["profile_id"])
                self._send_json(ANALYZE_JOBS.start(profile_id), HTTPStatus.ACCEPTED)
                return
            if route.path.startswith("/analyze-jobs/") and route.path.endswith("/cancel"):
                job_id = route.path.split("/")[2]
                job = ANALYZE_JOBS.cancel(job_id)
                if job is None:
                    self._send_json({"error": f"Analyze job not found: {job_id}"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json(job, HTTPStatus.ACCEPTED)
                return
            if route.path == "/synchronize":
                payload = self._read_json()
                profile_id = int(payload["profile_id"])
                plan_id = payload.get("plan_id")
                self._send_json(SYNC_JOBS.start(profile_id, plan_id), HTTPStatus.ACCEPTED)
                return
            if route.path.startswith("/sync-jobs/") and route.path.endswith("/cancel"):
                job_id = route.path.split("/")[2]
                job = SYNC_JOBS.cancel(job_id)
                if job is None:
                    self._send_json({"error": f"Sync job not found: {job_id}"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json(job, HTTPStatus.ACCEPTED)
                return
            if route.path == "/profiles":
                payload = self._read_json()
                with connect() as connection:
                    initialize_schema(connection)
                    profile = ProfileRepository(connection).create(
                        payload["name"],
                        Path(payload["local_path"]).expanduser().resolve(),
                        Path(payload["external_path"]).expanduser().resolve(),
                        tuple(payload.get("exclude_rules") or DEFAULT_EXCLUSIONS),
                        bool(payload.get("strict_verification", False)),
                    )
                self._send_json({"profile": _profile_to_dict(profile)}, HTTPStatus.CREATED)
                return
        except (KeyError, ValueError, TypeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        route = urlparse(self.path)
        try:
            if route.path.startswith("/profiles/"):
                profile_id = int(route.path.removeprefix("/profiles/"))
                with connect() as connection:
                    initialize_schema(connection)
                    deleted = ProfileRepository(connection).delete(profile_id)
                if not deleted:
                    self._send_json({"error": f"Profile not found: {profile_id}"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json({"deleted": True, "profile_id": profile_id})
                return
        except (ValueError, TypeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "http://localhost:1420")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def _analyze_profile(profile_id: int) -> dict:
    with connect() as connection:
        initialize_schema(connection)
        profile_repo = ProfileRepository(connection)
        profile = profile_repo.get(profile_id)
        if profile is None:
            raise ValueError(f"Profile not found: {profile_id}")
        metadata_repo = FileMetadataRepository(connection)
        plan = SyncAnalyzer().analyze(profile, metadata_repo.list_for_profile(profile_id))
    plan_id = ANALYZE_PLANS.store(profile_id, plan)
    return _plan_to_dict(plan, plan_id)


def _sync_profile(profile_id: int) -> dict:
    with connect() as connection:
        initialize_schema(connection)
        profile_repo = ProfileRepository(connection)
        profile = profile_repo.get(profile_id)
        if profile is None:
            raise ValueError(f"Profile not found: {profile_id}")
        metadata_repo = FileMetadataRepository(connection)
        session_repo = SyncSessionRepository(connection)
        conflict_repo = ConflictRepository(connection)
        result = SyncExecutor(session_repo, metadata_repo, conflict_repo).synchronize(profile)
    return _sync_result_to_dict(result)


def _profile_to_dict(profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "local_path": str(profile.local_path),
        "external_path": str(profile.external_path),
        "exclude_rules": list(profile.exclude_rules),
        "strict_verification": profile.strict_verification,
    }


def _plan_to_dict(plan, plan_id: str | None = None) -> dict:
    return {
        "plan_id": plan_id,
        "profile": _profile_to_dict(plan.profile),
        "summary": {
            "total_actions": len(plan.actions),
            "total_bytes": plan.total_bytes,
            "ignored_count": plan.ignored_count,
        },
        "actions": [
            {
                "type": action.action_type,
                "relative_path": action.relative_path,
                "source": action.source,
                "destination": action.destination,
                "size": action.size,
                "reason": action.reason,
            }
            for action in plan.actions
        ],
    }


def _sync_result_to_dict(result) -> dict:
    return {
        "session_id": result.session_id,
        "status": result.status,
        "copied_count": result.copied_count,
        "updated_count": result.updated_count,
        "skipped_count": result.skipped_count,
        "conflict_count": result.conflict_count,
        "conflicts_resolved_count": result.conflicts_resolved_count,
        "error_count": result.error_count,
        "total_bytes": result.total_bytes,
        "events": list(result.events),
    }
