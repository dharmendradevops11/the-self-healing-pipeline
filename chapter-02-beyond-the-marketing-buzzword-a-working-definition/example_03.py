SAFE_PATH_PREFIXES = ["src/", "lib/", "app/", "packages/"]

FORBIDDEN_PATH_PATTERNS = [
    r"^infrastructure/",
    r"^\.github/",
    r"(^|/)migrations/",
    r"(^|/)Dockerfile$",
    r"\.ya?ml$",
    r"\.sh$",
]

def is_path_remediable(file_path: str) -> bool:
    if any(re.search(pattern, file_path) for pattern in FORBIDDEN_PATH_PATTERNS):
        return False
    return any(file_path.startswith(prefix) for prefix in SAFE_PATH_PREFIXES)

def apply_remediation(diff: str, changed_files: list[str]) -> dict:
    unsafe = [f for f in changed_files if not is_path_remediable(f)]
    if unsafe:
        return {"applied": False, "reason": f"forbidden paths: {unsafe}"}

    branch = f"healer/{date.today()}-{slugify(diff_summary(diff))}"
    checkout_branch(branch, base="main")
    result = apply_patch(diff)
    if not result.success:
        rollback_branch(branch)  # leave main untouched on partial apply
        return {"applied": False, "reason": result.error}

    push_branch(branch)
    return {"applied": True, "branch": branch, "rollback": lambda: delete_branch(branch)}
