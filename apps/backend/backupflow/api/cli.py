from __future__ import annotations

import argparse
import json
from pathlib import Path

from backupflow.config.defaults import DEFAULT_EXCLUSIONS
from backupflow.api.server import run_server
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backupflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")
    subparsers.add_parser("list-profiles")

    serve = subparsers.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    create_profile = subparsers.add_parser("create-profile")
    create_profile.add_argument("name")
    create_profile.add_argument("local_path")
    create_profile.add_argument("external_path")

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("profile_id", type=int)

    sync = subparsers.add_parser("sync")
    sync.add_argument("profile_id", type=int)

    args = parser.parse_args(argv)

    if args.command == "serve":
        run_server(args.host, args.port)
        return 0

    with connect() as connection:
        initialize_schema(connection)

        if args.command == "init-db":
            print(json.dumps({"database": str(get_db_path()), "status": "ok"}, indent=2))
            return 0

        profile_repo = ProfileRepository(connection)

        if args.command == "create-profile":
            profile = profile_repo.create(
                args.name,
                Path(args.local_path).expanduser().resolve(),
                Path(args.external_path).expanduser().resolve(),
                DEFAULT_EXCLUSIONS,
            )
            print(_profile_to_json(profile))
            return 0

        if args.command == "list-profiles":
            print(json.dumps([json.loads(_profile_to_json(profile)) for profile in profile_repo.list()], indent=2))
            return 0

        if args.command == "analyze":
            profile = profile_repo.get(args.profile_id)
            if profile is None:
                parser.error(f"Profile not found: {args.profile_id}")
            metadata_repo = FileMetadataRepository(connection)
            plan = SyncAnalyzer().analyze(profile, metadata_repo.list_for_profile(args.profile_id))
            print(_plan_to_json(plan))
            return 0

        if args.command == "sync":
            profile = profile_repo.get(args.profile_id)
            if profile is None:
                parser.error(f"Profile not found: {args.profile_id}")
            metadata_repo = FileMetadataRepository(connection)
            session_repo = SyncSessionRepository(connection)
            conflict_repo = ConflictRepository(connection)
            result = SyncExecutor(session_repo, metadata_repo, conflict_repo).synchronize(profile)
            print(_sync_result_to_json(result))
            return 0

    return 1


def _profile_to_json(profile) -> str:
    return json.dumps(
        {
            "id": profile.id,
            "name": profile.name,
            "local_path": str(profile.local_path),
            "external_path": str(profile.external_path),
            "exclude_rules": list(profile.exclude_rules),
            "strict_verification": profile.strict_verification,
        },
        indent=2,
    )


def _plan_to_json(plan) -> str:
    return json.dumps(
        {
            "profile": json.loads(_profile_to_json(plan.profile)),
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
        },
        indent=2,
    )


def _sync_result_to_json(result) -> str:
    return json.dumps(
        {
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
        },
        indent=2,
    )
