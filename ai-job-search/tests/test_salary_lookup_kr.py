"""Korean salary data (jobseeker addition) — Hangul matching, salary_kr rendering, market rows."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import salary_lookup
from salary_lookup import (
    career_bucket,
    collect_validation_issues,
    format_entry_kr,
    market_reference,
    match_score,
    normalize,
)

META = {
    "country": "KR",
    "unit": "만원/년",
    "market": [
        {"career": "신입", "size": "전체", "n": 156, "p25": 3000, "median": 3650, "p75": 4032},
        {"career": "신입", "size": "중소기업", "n": 38, "p25": 3362, "median": 3800, "p75": 4733},
        {"career": "4~6년", "size": "전체", "n": 90, "p25": 4500, "median": 5200, "p75": 6000},
    ],
    "sizes": {"(주)재미스튜디오": "중소기업"},
    "caveats": ["공고에 연봉 숫자를 적는 곳은 소수다."],
}

BITHUMB = {
    "company": "빗썸",
    "salary_kr": {
        "size": "중견기업",
        "bands": [{"role": "전 직군 평균", "level": "전체", "low": 5439, "high": 11600,
                   "basis": "public_data", "confidence": "inferred",
                   "sources": [{"publisher": "잡플래닛"}]}],
        "band_note": "집계 간 차이가 크다",
        "posted": [],
    },
}


class HangulMatchingTests(unittest.TestCase):
    def test_hangul_survives_normalize(self):
        self.assertEqual(normalize("재미스튜디오"), "재미스튜디오")

    def test_korean_legal_forms_are_stripped(self):
        for name in ("(주)재미스튜디오", "㈜재미스튜디오", "주식회사 재미스튜디오", "재미스튜디오(주)"):
            self.assertEqual(match_score("재미스튜디오", name), 100, name)

    def test_unrelated_korean_names_do_not_match(self):
        self.assertEqual(match_score("빗썸", "코아아이티"), 0)


class CareerBucketTests(unittest.TestCase):
    def test_buckets(self):
        self.assertEqual(career_bucket("신입"), "신입")
        self.assertEqual(career_bucket("경력 3-7년"), "1~3년")
        self.assertEqual(career_bucket("경력 5년 이상"), "4~6년")
        self.assertEqual(career_bucket("경력 10년"), "7년+")
        self.assertEqual(career_bucket("경력무관"), "무관")


class MarketReferenceTests(unittest.TestCase):
    def test_rows_follow_company_size_and_career(self):
        entry = {"company": "x", "salary_kr": {"size": "중소기업"}}
        rows = market_reference(entry, META, "신입")
        self.assertEqual({r["size"] for r in rows}, {"전체", "중소기업"})
        self.assertTrue(all(r["career"] == "신입" for r in rows))

    def test_unknown_size_gets_only_overall_row(self):
        entry = {"company": "x", "salary_kr": {"size": None}}
        rows = market_reference(entry, META, "신입")
        self.assertEqual([r["size"] for r in rows], ["전체"])


class FormatEntryKrTests(unittest.TestCase):
    def test_renders_bands_posted_and_caveats(self):
        out = format_entry_kr(BITHUMB, META, "신입")
        self.assertIn("5,439 ~ 11,600", out)
        self.assertIn("잡플래닛", out)
        self.assertIn("면접 후 결정", out)          # no stated salary → says so, not blank
        self.assertIn("3,650", out)
        self.assertIn("공고에 연봉 숫자를 적는 곳은 소수다.", out)

    def test_salary_kr_must_be_object(self):
        errors, _ = collect_validation_issues({"companies": [{"company": "x", "salary_kr": []}]})
        self.assertTrue(any("salary_kr must be an object" in e for e in errors))


class MissPathTests(unittest.TestCase):
    """Most Korean companies have neither a brief nor a stated salary — the lookup still answers."""

    def _run(self, argv):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "salary_data.json"
            path.write_text(json.dumps({"metadata": META, "companies": [BITHUMB]}, ensure_ascii=False),
                            encoding="utf-8")
            buf = io.StringIO()
            with mock.patch.object(salary_lookup, "DATA_FILE", path), \
                    mock.patch("sys.argv", ["salary_lookup.py", *argv]), redirect_stdout(buf):
                salary_lookup.main()
            return buf.getvalue()

    def test_missing_company_returns_market_reference_json(self):
        out = json.loads(self._run(["재미스튜디오", "--career", "신입", "--json"]))
        self.assertTrue(out[0]["not_in_data"])
        self.assertEqual(out[0]["salary_kr"]["size"], "중소기업")          # from metadata.sizes
        self.assertEqual({r["size"] for r in out[0]["market_reference"]}, {"전체", "중소기업"})
        self.assertTrue(out[0]["caveats"])

    def test_found_company_text_output(self):
        out = self._run(["빗썸", "--career", "신입"])
        self.assertIn("중견기업", out)
        self.assertIn("5,439 ~ 11,600", out)


if __name__ == "__main__":
    unittest.main()
