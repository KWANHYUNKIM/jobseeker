#!/usr/bin/env python3
"""
Salary Benchmark Lookup Tool

Looks up company salary data from a user-provided dataset.
Supports any salary data source — union statistics, Glassdoor exports,
manually collected benchmarks, etc.

This tool requires a data file (salary_data.json) that you create
from your own salary data. See tools/README_SALARY_TOOL.md for
instructions on the expected format and how to convert from Excel.

Usage:
    python salary_lookup.py "Company Name"
    python salary_lookup.py "Company Name" --city "København"
    python salary_lookup.py "Company Name" --json
    python salary_lookup.py --list-all

Korean data (jobseeker): build salary_data.json with
    python tools/build_salary_kr.py
then look up a company in Korean, optionally with the candidate's career stage:
    python salary_lookup.py "재미스튜디오" --career 신입
Korean entries carry a `salary_kr` object (만원/년) instead of index categories: the
company's researched salary bands with sources, the salaries its own postings state,
and a market reference (p25/median/p75 of stated salaries by career stage and
company size) from `metadata.market`.
"""

import json
import sys
import re
import argparse
import unicodedata
from pathlib import Path

DATA_FILE = Path(__file__).parent / "salary_data.json"

# Common Danish <-> anglicized spelling variants
SPELLING_VARIANTS = {
    "ø": "o", "æ": "ae", "å": "aa",
    "ö": "o", "ä": "ae", "ü": "u",
}

# Legal suffixes and noise to strip when matching company names
STRIP_PATTERNS = [
    r"\ba/s\b", r"\baps\b", r"\bi/s\b", r"\bp/s\b", r"\bk/s\b",
    r"\bivs\b", r"\bamba\b", r"\ba\.m\.b\.a\.?\b",
    r"\(vg\)", r"\(.*?\)",  # (VG) and other parentheticals
    r"\bdanmark\b", r"\bdenmark\b", r"\bscandinavia\b", r"\bnordic\b",
    r"\bgroup\b", r"\bholding\b",
    r",\s*.*$",  # everything after comma (sub-entities)
    # Korean legal forms (jobseeker). "(주)" is already covered by the parenthetical rule.
    r"주식회사", r"㈜", r"유한회사",
]


def fail_data_error(message):
    """Exit with a user-facing salary data setup error."""
    print(f"Error: invalid salary_data.json: {message}", file=sys.stderr)
    print("", file=sys.stderr)
    print("See tools/README_SALARY_TOOL.md for the expected format.", file=sys.stderr)
    sys.exit(1)


def collect_validation_issues(data):
    """Return (errors, warnings) for the salary data shape.

    errors   -> hard problems that make lookups crash or emit wrong output
                (these cause validate_data() to exit(1)).
    warnings -> usability concerns that still work (e.g. duplicate company
                names); --validate reports them but exits 0.
    """
    errors = []
    warnings = []

    if not isinstance(data, dict):
        errors.append("top-level JSON value must be an object")
        return errors, warnings

    metadata = data.get("metadata", {})
    if metadata is not None and not isinstance(metadata, dict):
        errors.append("'metadata' must be an object when provided")

    companies = data.get("companies")
    if not isinstance(companies, list):
        errors.append("'companies' must be a list")
        return errors, warnings

    seen_companies = {}
    for index, entry in enumerate(companies, start=1):
        if not isinstance(entry, dict):
            errors.append(f"companies[{index}] must be an object")
            continue

        company = entry.get("company")
        if not isinstance(company, str) or not company.strip():
            errors.append(f"companies[{index}].company must be a non-empty string")
        else:
            key = company.lower()
            if key in seen_companies:
                warnings.append(
                    f"Duplicate company name '{company}' "
                    f"(companies[{seen_companies[key]}] and companies[{index}])"
                )
            else:
                seen_companies[key] = index

        city = entry.get("city")
        if city is not None and not isinstance(city, str):
            errors.append(f"companies[{index}].city must be a string when provided")

        salary_kr = entry.get("salary_kr")
        if salary_kr is not None and not isinstance(salary_kr, dict):
            errors.append(f"companies[{index}].salary_kr must be an object when provided")

        categories = entry.get("categories", {})
        if categories is not None and not isinstance(categories, dict):
            errors.append(f"companies[{index}].categories must be an object when provided")
        elif categories:
            for cat_label, cat_data in categories.items():
                if not isinstance(cat_data, dict):
                    errors.append(
                        f"companies[{index}].categories.{cat_label} must be an object "
                        f"with 'count' and/or 'index' (got {type(cat_data).__name__})"
                    )
                    continue
                count = cat_data.get("count")
                if count is not None and not isinstance(count, (int, float)):
                    errors.append(
                        f"companies[{index}].categories.{cat_label}.count must be a "
                        f"number (got {type(count).__name__})"
                    )
                index_val = cat_data.get("index")
                if index_val is not None and not isinstance(index_val, (int, float, str)):
                    errors.append(
                        f"companies[{index}].categories.{cat_label}.index must be a "
                        f"number or string (got {type(index_val).__name__})"
                    )

    return errors, warnings


def validate_data(data):
    """Validate the salary data shape before lookups use it.

    Preserves historical behavior: exits(1) on the first hard error with the
    same user-facing message, and returns data unchanged when valid.
    """
    errors, _ = collect_validation_issues(data)
    if errors:
        fail_data_error(errors[0])
    return data


def read_raw_data():
    """Load and JSON-parse salary_data.json; exit with a helpful message if missing/invalid."""
    if not DATA_FILE.exists():
        print("Error: salary_data.json not found.", file=sys.stderr)
        print("", file=sys.stderr)
        print("This tool requires a salary data file.", file=sys.stderr)
        print("See tools/README_SALARY_TOOL.md for setup instructions.", file=sys.stderr)
        print("", file=sys.stderr)
        print("If you don't have salary data, the salary lookup", file=sys.stderr)
        print("step will be skipped during /apply.", file=sys.stderr)
        sys.exit(1)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        fail_data_error(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
    return data


def load_data():
    """Load, parse, and validate salary_data.json for lookups."""
    return validate_data(read_raw_data())


def normalize(s):
    """Normalize string for robust fuzzy matching."""
    s = s.lower().strip()
    for pat in STRIP_PATTERNS:
        s = re.sub(pat, "", s)
    s = re.sub(r"[^a-zæøåöäü0-9가-힣]", "", s)
    return s.strip()


def anglicize(s):
    """Convert Danish/Nordic characters to anglicized equivalents."""
    s = s.lower()
    for danish, english in SPELLING_VARIANTS.items():
        s = s.replace(danish, english)
    return s


def extract_core_words(s):
    """Extract meaningful words from a company name, ignoring noise."""
    s = s.lower()
    for pat in STRIP_PATTERNS:
        s = re.sub(pat, "", s)
    words = re.findall(r"[a-zæøåöäü0-9가-힣]+", s)
    return [w for w in words if len(w) > 1]


def match_score_optimized(q_norm, q_ang, q_words_set, q_words_ang_set, query, entry_name):
    """Compute a match score between 0 and 100 using precalculated query values."""
    n_norm = normalize(entry_name)

    if not q_norm or not n_norm:
        return 0

    if q_norm == n_norm:
        return 100

    if q_norm in n_norm:
        ratio = len(q_norm) / len(n_norm)
        if len(q_norm) <= 4 and ratio < 0.5:
            n_words = set(extract_core_words(entry_name))
            if not q_words_set & n_words:
                pass
            else:
                return 80 + int(ratio * 10)
        else:
            return 80 + int(ratio * 10)
    if n_norm in q_norm:
        ratio = len(n_norm) / len(q_norm)
        if len(n_norm) <= 4 and ratio < 0.5:
            pass
        else:
            return 80 + int(ratio * 10)

    n_ang = anglicize(n_norm)
    if q_ang == n_ang:
        return 85
    if q_ang in n_ang or n_ang in q_ang:
        shorter = min(len(q_ang), len(n_ang))
        longer = max(len(q_ang), len(n_ang))
        if shorter <= 4 and shorter / longer < 0.5:
            n_words_ang = {anglicize(w) for w in extract_core_words(entry_name)}
            if q_words_ang_set & n_words_ang:
                return 75
        else:
            return 75

    n_words = set(extract_core_words(entry_name))
    if not q_words_set or not n_words:
        return 0

    overlap = q_words_set & n_words
    if not overlap:
        n_words_ang = {anglicize(w) for w in n_words}
        overlap = q_words_ang_set & n_words_ang

    if overlap:
        if len(q_words_set) == 1:
            q_word = list(q_words_set)[0]
            if q_word in n_words or anglicize(q_word) in {anglicize(w) for w in n_words}:
                return 70
            else:
                return 0

        coverage = len(overlap) / len(q_words_set)
        return int(30 + coverage * 40)

    return 0


def match_score(query, entry_name):
    """Compute a match score between 0 and 100 for ranking results."""
    q_norm = normalize(query)
    q_ang = anglicize(q_norm)
    q_words = extract_core_words(query)
    q_words_set = set(q_words)
    q_words_ang_set = {anglicize(w) for w in q_words}
    return match_score_optimized(q_norm, q_ang, q_words_set, q_words_ang_set, query, entry_name)


def search_company(data, query, city=None):
    """Search for a company by name. Returns matching entries sorted by relevance."""
    companies = data.get("companies", [])
    scored = []

    # Pre-calculate query representations once to avoid redundant computations inside the loop
    q_norm = normalize(query)
    q_ang = anglicize(q_norm)
    q_words = extract_core_words(query)
    q_words_set = set(q_words)
    q_words_ang_set = {anglicize(w) for w in q_words}

    for entry in companies:
        if city:
            city_lower = city.lower()
            entry_city = (entry.get("city") or "").lower()
            if city_lower not in entry_city and anglicize(city_lower) not in anglicize(entry_city):
                continue

        score = match_score_optimized(q_norm, q_ang, q_words_set, q_words_ang_set, query, entry["company"])
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: (-x[0], x[1]["company"]))

    min_score = 30
    return [entry for score, entry in scored if score >= min_score]


def career_bucket(career):
    """Career stage bucket used by the Korean market table (mirrors jobseeker's agent_mcp)."""
    c = career or ""
    if "신입" in c:
        return "신입"
    m = re.search(r"(\d+)", c)
    if m:
        n = int(m.group(1))
        return "1~3년" if n <= 3 else "4~6년" if n <= 6 else "7년+"
    return "무관" if "무관" in c else ""


def market_reference(entry, metadata, career=None):
    """Market rows (stated salaries of similar postings) for this company's size and career stage."""
    rows = (metadata or {}).get("market") or []
    size = (entry.get("salary_kr") or {}).get("size")
    bucket = career_bucket(career) if career else ""
    out = []
    for row in rows:
        if bucket and row.get("career") != bucket:
            continue
        if row.get("size") not in ("전체", size):
            continue
        out.append(row)
    return out


def _won(v):
    return f"{v:,}" if isinstance(v, (int, float)) else "-"


def format_entry_kr(entry, metadata, career=None):
    """Korean entry: researched bands, salaries stated in the company's postings, market reference."""
    kr = entry.get("salary_kr") or {}
    lines = [f"\n{'='*60}", f"  {entry['company']}"]
    where = " · ".join(x for x in (entry.get("city"), kr.get("size")) if x)
    if where:
        lines.append(f"  {where}")
    lines.append(f"{'='*60}")
    lines.append("  단위: 만원/년")

    bands = kr.get("bands") or []
    lines.append("")
    lines.append("  [회사 연봉 밴드 — 취업 브리핑]")
    if bands:
        for b in bands:
            rng = _won(b.get("low")) if b.get("low") == b.get("high") else f"{_won(b.get('low'))} ~ {_won(b.get('high'))}"
            src = ((b.get("sources") or [{}])[0]).get("publisher") or ""
            lines.append(f"  {b.get('role', ''):<14} {b.get('level', ''):<6} {rng:>15}  "
                         f"({b.get('basis', '')}, {b.get('confidence', '')}{', ' + src if src else ''})")
        if kr.get("band_note"):
            lines.append(f"  주의: {kr['band_note'][:160]}")
    else:
        lines.append("  없음 (이 회사는 브리핑이 없다)")

    posted = kr.get("posted") or []
    lines.append("")
    lines.append("  [이 회사 공고에 적힌 연봉]")
    if posted:
        for p in posted:
            rng = _won(p.get("low")) + (f" ~ {_won(p.get('high'))}" if p.get("high") else " 이상/고정")
            month = " (월급×12)" if p.get("monthly") else ""
            lines.append(f"  {rng:>17}{month}  {p.get('career') or '':<12} {(p.get('title') or '')[:34]}")
    else:
        lines.append("  없음 (대부분의 국내 공고는 '회사 내규' · '면접 후 결정')")

    ref = market_reference(entry, metadata, career)
    lines.append("")
    lines.append("  [비슷한 자리 시세 — 공고에 적힌 값]")
    if ref:
        lines.append(f"  {'경력':<8} {'규모':<10} {'n':>4} {'p25':>7} {'중앙값':>7} {'p75':>7}")
        for r in ref:
            lines.append(f"  {r.get('career', ''):<8} {r.get('size', ''):<10} {r.get('n', ''):>4} "
                         f"{_won(r.get('p25')):>7} {_won(r.get('median')):>7} {_won(r.get('p75')):>7}")
    else:
        lines.append("  표본 부족")
    for c in (metadata or {}).get("caveats") or []:
        lines.append(f"  * {c}")
    return "\n".join(lines)


def format_entry(entry, metadata):
    """Format a single company entry for display."""
    # `metadata` and `entry["categories"]` may be an explicit null: --validate
    # treats a null the same as an omitted key ("...must be an object when
    # provided"), but dict.get(key, default) only substitutes the default for an
    # absent key, so a null reached `.get()`/`[]` here and crashed the lookup.
    metadata = metadata or {}
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  {entry['company']}")
    if entry.get("city"):
        lines.append(f"  Location: {entry['city']}")
    lines.append(f"{'='*60}")

    # Get category data (everything except company/city fields).
    categories = entry.get("categories") or {}
    if not categories:
        # Fallback: treat any numeric fields as categories
        skip_keys = {"company", "city", "categories"}
        for key, value in entry.items():
            if key not in skip_keys and isinstance(value, dict):
                categories[key] = value

    if categories:
        index_label = metadata.get("index_label", "Index")
        baseline = metadata.get("index_baseline", 100)

        lines.append(f"  {'Category':<22} {'Count':>6} {index_label:>8}  {'vs Baseline':>10}")
        lines.append(f"  {'-'*50}")

        suppressed = False  # did any row render its index as N/A*?
        for label, data in categories.items():
            display_label = label.replace("_", " ").title()
            count = data.get("count")
            index = data.get("index")
            if count is not None or index is not None:
                count_str = str(count) if count is not None else "-"
                if isinstance(index, (int, float)):
                    index_str = f"{index:.1f}"
                    if baseline == 0:
                        diff_str = ""
                    else:
                        diff_pct = ((index - baseline) / baseline) * 100
                        sign = "+" if diff_pct >= 0 else ""
                        diff_str = f"{sign}{diff_pct:.1f}%"
                elif index is not None:
                    index_str = str(index)
                    diff_str = ""
                else:
                    index_str = "N/A*"
                    diff_str = ""
                    suppressed = True
                lines.append(f"  {display_label:<22} {count_str:>6} {index_str:>8}  {diff_str:>10}")

        # The footnote explains the N/A* marker; printing it under a table with
        # no such row asserts a privacy suppression that did not happen.
        lines.append("")
        if suppressed:
            lines.append("  * N/A = Too few employees to publish (privacy)")
        if metadata.get("baseline_description"):
            lines.append(f"  {metadata['baseline_description']}")
        else:
            lines.append(f"  {index_label} {baseline} = baseline")
    else:
        # Simple format: just show all non-standard fields
        skip_keys = {"company", "city", "categories"}
        for key, value in entry.items():
            if key not in skip_keys:
                display_key = key.replace("_", " ").title()
                lines.append(f"  {display_key}: {value}")

    return "\n".join(lines)


def print_validation_report(errors, warnings):
    """Print an actionable validation report. Returns the process exit code."""
    if not errors and not warnings:
        print("OK - no issues found.")
        return 0
    print(f"Found {len(errors) + len(warnings)} issue(s):")
    if errors:
        print("  Errors:")
        for i, msg in enumerate(errors, start=1):
            print(f"    [{i}] {msg}")
    if warnings:
        print("  Warnings:")
        for i, msg in enumerate(warnings, start=1):
            print(f"    [{i}] {msg}")
    if errors:
        print("")
        print("Fix the errors above, then re-run. See tools/README_SALARY_TOOL.md "
              "for the expected format.")
        return 1
    return 0


def _force_utf8_output() -> None:
    """Write UTF-8 whatever the host's default encoding is.

    A piped stdout on Windows defaults to the ANSI code page (cp1252 on most
    Western installs), so printing a company, title or file name outside it
    raised UnicodeEncodeError before the workflow saw any output.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)  # absent on a StringIO under test
        if reconfigure:
            reconfigure(encoding="utf-8")


def main():
    _force_utf8_output()
    parser = argparse.ArgumentParser(description="Salary Benchmark Lookup")
    parser.add_argument("company", nargs="?", help="Company name to search for")
    parser.add_argument("--city", help="Filter by city name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--list-all", action="store_true", help="List all companies")
    parser.add_argument("--career", help="Korean data: candidate's career stage (신입, 경력 3년 …) "
                                         "to pick the market reference row")
    parser.add_argument("--validate", action="store_true",
                        help="Validate salary_data.json and print a report, then exit")
    args = parser.parse_args()

    if args.validate:
        data = read_raw_data()
        errors, warnings = collect_validation_issues(data)
        print(f"Validating {DATA_FILE.name} ...")
        print("")
        sys.exit(print_validation_report(errors, warnings))

    data = load_data()
    metadata = data.get("metadata", {})
    companies = data.get("companies", [])

    if args.list_all:
        for entry in companies:
            city = entry.get("city", "")
            city_str = f" ({city})" if city else ""
            print(f"{entry['company']}{city_str}")
        return

    if not args.company:
        parser.print_help()
        sys.exit(1)

    results = search_company(data, args.company, args.city)

    if not results and (metadata or {}).get("country") == "KR":
        # Most Korean postings state no salary and most companies have no brief, so a
        # miss is the common case — the market reference is still the useful answer.
        sizes = (metadata or {}).get("sizes") or {}
        size = next((v for k, v in sizes.items() if match_score(args.company, k) >= 90), None)
        results = [{"company": args.company, "not_in_data": True,
                    "salary_kr": {"size": size, "bands": [], "posted": []}}]

    if not results:
        print(f"No results found for '{args.company}'")
        if args.city:
            print(f"  (filtered by city: {args.city})")
        print("\nTry a shorter or different name. Company names in the dataset")
        print("may include legal suffixes like 'A/S' or 'ApS'.")
        sys.exit(1)

    if args.json:
        out = []
        for entry in results:
            if entry.get("salary_kr") is not None:
                entry = {**entry, "market_reference": market_reference(entry, metadata, args.career),
                         "caveats": (metadata or {}).get("caveats") or []}
            out.append(entry)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if results[0].get("not_in_data"):
            print(f"\n'{args.company}' — 회사 밴드도, 공고에 적힌 연봉도 없다. 비슷한 자리 시세만 보인다:")
        else:
            print(f"\nFound {len(results)} match(es) for '{args.company}':")
        for entry in results:
            if entry.get("salary_kr") is not None:
                print(format_entry_kr(entry, metadata, args.career))
            else:
                print(format_entry(entry, metadata))
        print()


if __name__ == "__main__":
    main()
