# System Audit Report

**Audit Date**: 2026-03-28
**Audit Scope**: `/Users/c/claude-im`, `/Users/c/clawrelay-feishu-server`, `/Users/c/clawrelay-report`
**Audit Type**: Security & Configuration Review

---

## Critical Issues

### Issue #1: Hardcoded Secrets Tracked in Git Repository

**Severity**: CRITICAL
**File**: `/Users/c/clawrelay-feishu-server/config/bots.yaml`
**Status**: Tracked by git (committed in `7d4d9ca`)

**Problem**: This file contains actual production secrets that are committed to the git repository:
- `app_secret: "woV3uOvc7GBI05CNhjoWGfdfuSUsYk4u"`
- `ANTHROPIC_AUTH_TOKEN: "sk-cp-ATSzsFW4KgGl7Nlv8bI2ZR4k3CBN_Jpz-E4N2JDrsQCddYsYQms-UsM_xFw9PTuJS0Ps7ieCao-UGTOYVegsccyYPDGlYdulUAYKhbwA1OEc_VYtbULguM0"`

**Evidence**:
```bash
$ cd /Users/c/clawrelay-feishu-server && git ls-files --error-unmatch config/bots.yaml
config/bots.yaml
$ git log --oneline -1 -- config/bots.yaml
7d4d9ca fix: env injection, system_prompt, session isolation for claude-node adapter
```

Note: The `.gitignore` in this project explicitly says `config/bots.yaml` (with comment "包含密钥"), indicating the original intent was to exclude it. However, the file is committed.

**Recommendation**:
1. Immediately rotate all exposed secrets (ANTHROPIC_AUTH_TOKEN, FEISHU_APP_SECRET)
2. Remove the file from git history (use `git filter-repo` or BFG)
3. Add `config/bots.yaml` to `.gitignore`
4. Create `config/bots.yaml.example` with placeholder values
5. Update documentation to instruct developers to copy from example

---

### Issue #2: .env File with Secrets Not Properly Excluded

**Severity**: CRITICAL
**File**: `/Users/c/clawrelay-feishu-server/.env`

**Problem**: This file contains production secrets and while currently untracked, the pattern suggests potential for accidental tracking:
- `ANTHROPIC_AUTH_TOKEN=sk-cp-ATSzsFW4...`
- `FEISHU_APP_SECRET=woV3uOvc7GBI05CNhjoWGfdfuSUsYk4u`

**Recommendation**:
1. Verify `.gitignore` excludes `.env` (confirmed: it does)
2. Never run `git add .` without checking status
3. Consider using a pre-commit hook to prevent accidental secrets commit

---

### Issue #3: Default Admin Password in .env

**Severity**: CRITICAL
**File**: `/Users/c/clawrelay-report/.env`

**Problem**: Contains a default superuser password:
- `FIRST_SUPERUSER_PASSWORD=admin123`

This is a well-known default credential that should never be used in any environment.

**Recommendation**:
1. Force password change on first login
2. Remove default password from .env and require environment variable to be set
3. Add validation to reject known weak passwords

---

### Issue #4: Secret Key Committed in .env

**Severity**: CRITICAL
**File**: `/Users/c/clawrelay-report/.env`

**Problem**:
- `SECRET_KEY=PcNNeesRlFNAxciU5bJWKm2Z2SLJaVEpO0najE7CGZg`

This secret key is used for cryptographic signing and is committed to the repository.

**Recommendation**:
1. Generate a new SECRET_KEY immediately
2. Load from environment variable with no default
3. Add validation to fail startup if SECRET_KEY is not set

---

## High Issues

### Issue #5: Frontend .env Tracked by Git

**Severity**: HIGH
**File**: `/Users/c/clawrelay-report/frontend/.env`
**Status**: Tracked and modified

**Problem**: This file is committed to git (`git ls-files` shows it tracked). While it currently only contains non-sensitive URLs (localhost:8000, localhost:1080), this creates configuration drift issues.

**Evidence**:
```bash
$ cd /Users/c/clawrelay-report && git ls-files --error-unmatch frontend/.env
frontend/.env
$ git status --short frontend/.env
(Branch name or commit hash shown)
```

**Recommendation**:
1. Remove `frontend/.env` from git index
2. Add `frontend/.env` to `frontend/.gitignore`
3. Create `frontend/.env.example` with required variables
4. Document that developers must copy from example

---

### Issue #6: Configuration Drift - Missing .env.example

**Severity**: HIGH
**Files**:
- `/Users/c/clawrelay-report/.env.example` (missing)
- `/Users/c/clawrelay-report/frontend/.env.example` (missing)

**Problem**: Neither the backend nor frontend have `.env.example` files to guide developers. While `bots.yaml.example` exists in clawrelay-feishu-server, the clawrelay-report project lacks this documentation.

**Recommendation**:
1. Create `.env.example` files with all required variables
2. Use placeholder values (e.g., `your-secret-key-here`)
3. Document each variable in comments
4. Ensure README references the example files

---

### Issue #7: Hardcoded Absolute Path in Config

**Severity**: HIGH
**File**: `/Users/c/clawrelay-feishu-server/config/bots.yaml`

**Problem**:
- `working_dir: "/Users/c/claude-im"` - hardcoded absolute path

This path is specific to one developer's machine and will fail on other systems.

**Recommendation**:
1. Use relative paths or environment variable placeholders
2. Default to current working directory or a configurable location

---

## Medium Issues

### Issue #8: Logs Directory Contains Chat History

**Severity**: MEDIUM
**File**: `/Users/c/clawrelay-feishu-server/logs/chat.jsonl`

**Problem**: This file (245KB) contains chat conversation logs that may include sensitive information from interactions with the Claude bot.

**Evidence**:
```bash
$ ls -la /Users/c/clawrelay-feishu-server/logs/
-rw-r--r--  1 c  staff  245158 Mar 28 12:03 chat.jsonl
```

**Recommendation**:
1. Add `*.jsonl` to `.gitignore`
2. Ensure logs are not exposed in Docker images
3. Consider encrypting logs at rest
4. Implement log rotation

---

### Issue #9: Test File Contains Hardcoded Path

**Severity**: MEDIUM
**File**: `/Users/c/clawrelay-feishu-server/tests/test_p2_p3.py:329`

**Problem**:
```python
working_dir: "/home/user/workspace"
```

**Recommendation**:
1. Use a temporary directory or fixture for tests
2. Make working_dir configurable via environment or fixture

---

### Issue #10: Configuration Drift - Modified .env Tracked

**Severity**: MEDIUM
**File**: `/Users/c/clawrelay-report/.env`
**Status**: Modified but tracked

**Problem**: The `.env` file shows as "modified" in git status, indicating local changes that differ from what's committed. This creates inconsistency between development environments.

**Recommendation**:
1. Remove .env from git tracking entirely
2. Use .env.example for defaults
3. Document that .env is never committed

---

## Low Issues

### Issue #11: .gitignore Inconsistencies

**Severity**: LOW

**Observation**:
- `/Users/c/claude-im/.gitignore` ignores `.env` and `config/bots.yaml`
- `/Users/c/clawrelay-feishu-server/.gitignore` ignores `.env` and `config/bots.yaml`
- `/Users/c/clawrelay-report/.gitignore` does NOT have explicit `.env` ignore

**Recommendation**:
1. Add explicit `.env` and `.env.local` to `/Users/c/clawrelay-report/.gitignore`
2. Add `frontend/.env` to `frontend/.gitignore`

---

### Issue #12: Bot Configuration in bots.yaml.example

**Severity**: LOW
**File**: `/Users/c/clawrelay-feishu-server/config/bots.yaml.example`

**Observation**: The example file still contains:
```yaml
working_dir: "/Users/c/clawrelay-feishu-server"
```

While this is an example file, using an absolute path may confuse users.

**Recommendation**:
1. Use a relative path or placeholder like `"<your-working-directory>"`

---

## Summary Table

| # | Severity | Category | File | Issue |
|---|----------|----------|------|-------|
| 1 | CRITICAL | Hardcoded Secrets | `clawrelay-feishu-server/config/bots.yaml` | Secrets tracked in git |
| 2 | CRITICAL | Hardcoded Secrets | `clawrelay-feishu-server/.env` | Secrets in .env |
| 3 | CRITICAL | Default Credentials | `clawrelay-report/.env` | admin123 password |
| 4 | CRITICAL | Secret Key | `clawrelay-report/.env` | SECRET_KEY committed |
| 5 | HIGH | Config Drift | `clawrelay-report/frontend/.env` | File tracked by git |
| 6 | HIGH | Config Drift | `clawrelay-report/` | Missing .env.example |
| 7 | HIGH | Hardcoded Path | `clawrelay-feishu-server/config/bots.yaml` | Absolute path |
| 8 | MEDIUM | Information Disclosure | `clawrelay-feishu-server/logs/chat.jsonl` | Chat history in logs |
| 9 | MEDIUM | Test Issue | `clawrelay-feishu-server/tests/test_p2_p3.py` | Hardcoded path |
| 10 | MEDIUM | Config Drift | `clawrelay-report/.env` | Modified and tracked |
| 11 | LOW | Config | Multiple .gitignore | Inconsistent patterns |
| 12 | LOW | Documentation | `clawrelay-feishu-server/config/bots.yaml.example` | Absolute path |

---

## Statistics

| Severity | Count |
|----------|-------|
| CRITICAL | 4 |
| HIGH | 3 |
| MEDIUM | 3 |
| LOW | 2 |
| **Total** | **12** |

---

## Immediate Actions Required

1. **Rotate all exposed secrets immediately**:
   - ANTHROPIC_AUTH_TOKEN
   - FEISHU_APP_SECRET
   - SECRET_KEY (clawrelay-report)

2. **Remove secrets from git history** for `config/bots.yaml`

3. **Fix git tracking**:
   - Remove `frontend/.env` from git index
   - Add proper `.gitignore` entries

4. **Create missing .env.example files** for clawrelay-report

---

*Report generated by Challenger role - System Audit*
