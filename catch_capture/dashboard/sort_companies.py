"""companies.json 자동 정렬/중복 제거/충돌 경고.

사용법:
    python dashboard/sort_companies.py            # in-place 정렬+dedup
    python dashboard/sort_companies.py --check    # 변경 없이 진단만 (CI용)

동작:
  - 각 (size, group) 안에서 가나다순 정렬
  - 같은 그룹 내 중복 제거 (정규화 기준)
  - 같은 size 내 다른 그룹과의 중복 경고
  - 대기업/중견기업 양쪽 버킷에 같은 회사가 있으면 ERROR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent.resolve()
COMPANIES_JSON = DASHBOARD_DIR / "companies.json"

sys.path.insert(0, str(DASHBOARD_DIR))
from classifier import _norm_company  # 동일한 정규화 사용


def _sort_key(name: str) -> tuple[int, str]:
    """가나다순 + 영문/숫자 뒤로."""
    if not name:
        return (2, "")
    first = name[0]
    if "가" <= first <= "힣":
        return (0, name.lower())
    if first.isdigit():
        return (2, name.lower())
    return (1, name.lower())


def process(data: dict, *, check: bool) -> tuple[dict, list[str]]:
    issues: list[str] = []
    out = {k: v for k, v in data.items() if k.startswith("_")}  # _comment 보존

    seen_per_size: dict[str, dict[str, str]] = {}  # size -> {norm: "group:original"}
    cross_size: dict[str, str] = {}  # norm -> "size/group:original"

    for size in ("대기업", "중견기업"):
        if size not in data:
            continue
        bucket = data[size]
        if not isinstance(bucket, dict):
            issues.append(f"[ERROR] '{size}' 는 {{group:[names]}} 구조여야 함")
            continue
        new_bucket: dict[str, list[str]] = {}
        seen_per_size[size] = {}
        # 그룹 키 자체도 가나다순 정렬
        for group in sorted(bucket.keys(), key=_sort_key):
            names = bucket[group]
            if not isinstance(names, list):
                issues.append(f"[ERROR] {size}/{group} 의 값이 리스트가 아님")
                continue
            seen_in_group: set[str] = set()
            cleaned: list[str] = []
            for name in names:
                if not isinstance(name, str) or not name.strip():
                    issues.append(f"[WARN] {size}/{group} 에 빈/비문자 항목: {name!r}")
                    continue
                name = name.strip()
                norm = _norm_company(name)
                if not norm:
                    issues.append(f"[WARN] {size}/{group}: '{name}' 정규화 결과가 비어 스킵")
                    continue
                # 같은 그룹 내 중복
                if norm in seen_in_group:
                    issues.append(f"[INFO] {size}/{group}: '{name}' 중복 제거")
                    continue
                # 같은 size, 다른 그룹과 중복
                if norm in seen_per_size[size]:
                    other = seen_per_size[size][norm]
                    issues.append(f"[WARN] {size}: '{name}' 가 [{other}] 에도 존재 — 그룹 정리 필요")
                # 다른 size 와 충돌
                if norm in cross_size:
                    issues.append(
                        f"[ERROR] '{name}' 가 [{cross_size[norm]}] 와 [{size}/{group}] 양쪽에 있음 (대기업 우선 유지 권장)"
                    )
                seen_in_group.add(norm)
                seen_per_size[size][norm] = f"{group}:{name}"
                cross_size[norm] = f"{size}/{group}:{name}"
                cleaned.append(name)
            cleaned.sort(key=_sort_key)
            new_bucket[group] = cleaned
        out[size] = new_bucket

    if not check:
        # 기존 키 순서 유지: _comment → 대기업 → 중견기업
        ordered = {}
        for k in ("_comment",):
            if k in out:
                ordered[k] = out[k]
        for k in ("대기업", "중견기업"):
            if k in out:
                ordered[k] = out[k]
        return ordered, issues
    return data, issues


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="진단만, 파일 변경 없음")
    args = ap.parse_args()

    if not COMPANIES_JSON.exists():
        print(f"[!] {COMPANIES_JSON} 없음", flush=True)
        sys.exit(1)

    data = json.loads(COMPANIES_JSON.read_text(encoding="utf-8"))
    new_data, issues = process(data, check=args.check)

    errors = [i for i in issues if i.startswith("[ERROR]")]
    warns = [i for i in issues if i.startswith("[WARN]") or i.startswith("[INFO]")]
    for line in warns:
        print(line, flush=True)
    for line in errors:
        print(line, flush=True)

    if args.check:
        if errors:
            sys.exit(2)
        print(f"[OK] check 완료. WARN/INFO {len(warns)}건, ERROR 0건", flush=True)
        return

    COMPANIES_JSON.write_text(json.dumps(new_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(v) for v in new_data.get("대기업", {}).values()) + sum(len(v) for v in new_data.get("중견기업", {}).values())
    print(f"[OK] {COMPANIES_JSON.name} 정렬 완료. 대기업 {sum(len(v) for v in new_data.get('대기업', {}).values())}건 / 중견 {sum(len(v) for v in new_data.get('중견기업', {}).values())}건 (총 {total}건)", flush=True)
    if errors:
        sys.exit(2)


if __name__ == "__main__":
    main()
