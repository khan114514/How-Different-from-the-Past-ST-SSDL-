"""Bounded resumable source bundle; original experiment evidence stays archived."""
import hashlib
import json
import os
import stat
from pathlib import Path

LIMIT = 5 * 1024 * 1024
FILE_LIMIT = 1024 * 1024
MANIFEST = 'resume_bundle_manifest.json'
CORE = {'method.py', 'method_notes.json', 'research_journal.md',
        'research_handoff.md', 'last_verified_score.json'}


def priority(name):
    path = Path(name)
    if name in CORE: return (0, name)
    if path.suffix == '.py': return (1, name)
    if path.suffix in {'.md', '.txt'}: return (2, name)
    if any(word in path.stem for word in ['summary', 'analysis', 'decision']):
        return (3, name)
    return (4, name)


def snapshot(base):
    base = Path(base)
    entries = []
    omitted = []
    for directory, dirs, names in os.walk(base, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for name in sorted(names):
            path = Path(directory) / name
            relative = str(path.relative_to(base))
            if relative == MANIFEST or path.suffix not in {'.py', '.json', '.txt', '.md'}:
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode): continue
                    if info.st_size > FILE_LIMIT:
                        omitted.append({'path': relative, 'bytes': info.st_size,
                                        'reason': 'per_file_resume_limit'})
                        continue
                    raw = os.read(fd, FILE_LIMIT + 1)
                finally:
                    os.close(fd)
                value = raw.decode('utf-8')
            except (OSError, UnicodeError):
                continue
            entries.append((relative, raw, value))
    files = {}
    total = 0
    # Reserve room for an auditable omission manifest. Keep executable sources,
    # decisions and small summaries before bulky reproducible raw traces.
    for name, raw, value in sorted(entries, key=lambda item: priority(item[0])):
        if total + len(raw) > LIMIT - 256 * 1024 or len(files) >= 255:
            omitted.append({'path': name, 'bytes': len(raw),
                            'sha256': hashlib.sha256(raw).hexdigest(),
                            'reason': 'aggregate_resume_limit'})
            continue
        files[name] = value
        total += len(raw)
    manifest = {'bundle_selection_does_not_modify_original_files': True,
                'included_bytes': total, 'resume_limit_bytes': LIMIT,
                'omitted_files': omitted,
                'guidance': 'Continue from code, journals and summaries. Reproduce raw traces only for a new discriminating experiment; do not rerun them merely to fill time.'}
    files[MANIFEST] = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
    if sum(len(v.encode()) for v in files.values()) > LIMIT:
        raise ValueError('Resume omission manifest exceeds bounded bundle')
    return files
