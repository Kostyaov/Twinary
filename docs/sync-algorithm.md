# Synchronization Algorithm

BackupFlow synchronizes two folder trees by relative path.

1. Load profile settings.
2. Scan local and external roots in the background.
3. Apply default and profile-specific exclusions.
4. Build maps of normalized `relative_path -> file metadata`.
5. Compare both maps.
6. Generate actions:
   - local-only file: copy local to external
   - external-only file: copy external to local
   - same size and modification time within filesystem tolerance: skip
   - different size: copy the newest version unless both sides changed
   - same size but different modification time: copy the newest version
7. Detect conflicts using previous metadata from the last sync.
8. Return an analyze plan for user confirmation.
9. Execute only non-conflicting copy and update actions.
10. Resolve conflicts with the default `Keep both` strategy:
    - copy the older version to a `.backupflow-conflict-...` filename on both sides
    - align the original path to the newer version
    - record the conflict resolution in SQLite
11. Store sync session summary, events, and refreshed file metadata.

Relative paths are normalized to NFC before comparison so APFS/exFAT Unicode filename differences do not create repeated copy actions for visually identical names.

BackupFlow allows a small modification-time tolerance to handle filesystem timestamp rounding. File size must still match before a file can be skipped.

Strict verification may hash small files with the same size and different modification time. Large files and common media/archive formats use fast metadata comparison even in strict mode to avoid very slow repeated reads of video, audio, archives, and disk images.
