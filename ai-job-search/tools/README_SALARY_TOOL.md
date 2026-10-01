# Salary Benchmark Tool

## What is this?

The salary lookup tool (`salary_lookup.py`) lets you benchmark company salaries against a baseline from your own data. It's used during the `/apply` workflow to show how a company's compensation compares to market rates.

**This tool is optional.** If you don't have salary data, the salary step is simply skipped during `/apply`.

## Korean data (jobseeker)

<!-- jobseeker: 원본은 덴마크 조합 통계용이다. 국내엔 그런 공개 지수가 없어 우리 데이터로 만든다. -->

Inside the jobseeker repository you do not need to supply a dataset:

```bash
python tools/build_salary_kr.py                      # writes salary_data.json (gitignored)
python salary_lookup.py "재미스튜디오" --career 신입
python salary_lookup.py "빗썸" --career "경력 5년" --json
```

Each Korean entry carries `salary_kr` (만원/년) instead of index `categories`:

| field | what it is |
|---|---|
| `size` | 중소기업 / 중견기업 / 대기업 … (from jobseeker's company stacks) |
| `bands` | researched salary bands from the employment brief, each with `basis`, `confidence` and `sources`. Often an all-staff pension-data average — **not** a starting salary |
| `posted` | salaries the company's own postings state (range midpoint, `monthly` ones ×12) |

`metadata.market` holds p25 / median / p75 of stated salaries by career stage (신입, 1~3년, 4~6년, 7년+, 무관) × company size, and `metadata.caveats` says what those numbers are not. `--career` picks the row. A company with neither a band nor a stated salary — the common case in Korea — still gets the market rows (`not_in_data: true`).

Parsing lives in `catch_capture/servers/agent_mcp/data.py` (`parse_pay`, `salary_benchmark`); the MCP tool `salary_benchmark` returns the same numbers without building a file.

## How it works

The tool reads a `salary_data.json` file in the repo root containing company salary benchmarks. It uses fuzzy matching to find companies by name, handling Danish/Nordic characters, legal suffixes (A/S, ApS), and common spelling variations.

The data format supports any index-based or absolute salary data. For example:
- Index 100 = median salary, higher is better
- Absolute salary values in your currency
- Any custom metric you want to track

## Data format

The tool expects `salary_data.json` with this structure:

```json
{
  "metadata": {
    "source": "My Union Statistics 2025",
    "index_baseline": 100,
    "index_label": "Index",
    "baseline_description": "Index 100 = median salary for private sector"
  },
  "companies": [
    {
      "company": "Novo Nordisk A/S",
      "city": "Bagsværd",
      "categories": {
        "all_employees": { "count": 500, "index": 108.5 },
        "engineering": { "count": 120, "index": 112.3 }
      }
    },
    {
      "company": "Ørsted A/S",
      "city": "Fredericia",
      "categories": {
        "all_employees": { "count": 200, "index": 105.2 }
      }
    }
  ]
}
```

### Fields

- **metadata.source**: Where the data comes from (for reference)
- **metadata.index_baseline**: The baseline value (e.g., 100 for index-based data)
- **metadata.index_label**: Label for the index column in output
- **metadata.baseline_description**: Human-readable explanation of the baseline
- **companies[].company**: Company name (required)
- **companies[].city**: City/location (optional, used for filtering)
- **companies[].categories**: Named salary categories, each with `count` and/or `index`

## Setup options

### Option A: Create salary_data.json manually

Create the file by hand with data from any source: union statistics, Glassdoor, salary surveys, networking, or personal research.

### Option B: Convert from Excel

If you have salary data in an Excel file:

```bash
pip install openpyxl
python3 tools/convert_salary_excel.py path/to/salary-data.xlsx \
  --source "My Salary Data 2025" \
  --baseline 100 \
  --baseline-desc "Index 100 = median salary"
```

On Windows, use `py` if that is how Python is exposed on your PATH. If your system uses `python` instead of `python3`, substitute that in the examples.

The converter auto-detects the Excel layout:
- Looks for a "Company"/"Firma" column and an optional "City"/"By" column
- Treats remaining columns as salary data (auto-pairs count/index columns)

### Option C: Build from research

Start with an empty template and add companies as you research them:

```json
{
  "metadata": {
    "source": "Personal research",
    "index_baseline": 0,
    "index_label": "Monthly salary (DKK)",
    "baseline_description": "Approximate monthly salary before tax"
  },
  "companies": [
    {
      "company": "Example Corp",
      "city": "Copenhagen",
      "categories": {
        "entry_level": { "index": 42000 },
        "senior": { "index": 55000 }
      }
    }
  ]
}
```

## Usage

```bash
python3 salary_lookup.py "Novo Nordisk"
python3 salary_lookup.py "Ørsted" --city "Fredericia"
python3 salary_lookup.py "COWI" --json
python3 salary_lookup.py --list-all
python3 salary_lookup.py --validate      # pre-flight check your salary_data.json
```

## Important notes

- The data file (`salary_data.json`) is **excluded from git** (see `.gitignore`). Your salary data may be proprietary or confidential.
- If the data file is missing, `salary_lookup.py` exits with a helpful error message and the `/apply` workflow skips the salary benchmark step.
- The fuzzy matcher handles Danish company name variations: legal suffixes, Nordic characters, anglicized spellings, and partial matches.
- `--validate` checks your data file for malformed category values and duplicate company names and prints a report, without performing a lookup.
