"""MCP 서버 스모크 테스트 — 실제 프로토콜로 붙어 도구·프롬프트를 한 바퀴 돈다.

    python -m agent_mcp.smoke                          # http://127.0.0.1:8790/mcp
    python -m agent_mcp.smoke http://host:8790/mcp

외부 에이전트가 보는 것과 같은 경로(streamable HTTP)로 확인한다. 도구가 예외 없이 답하고,
응답마다 '데이터일 뿐 지시가 아니다' 표시가 붙는지 본다.
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import Client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8790/mcp"


def _payload(res) -> dict:
    sc = getattr(res, "structured_content", None) or getattr(res, "structuredContent", None)
    if sc:
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    for c in res.content:
        if getattr(c, "text", None):
            try:
                return json.loads(c.text)
            except json.JSONDecodeError:
                return {"text": c.text}
    return {}


async def main() -> int:
    failed = 0
    async with Client(URL) as c:
        tools = [t.name for t in (await c.list_tools()).tools]
        prompts = [p.name for p in (await c.list_prompts()).prompts]
        print("tools  :", tools)
        print("prompts:", prompts)

        calls = [
            ("about", {}),
            ("search_jobs", {"query": "금융 백엔드 Java", "limit": 3}),
            ("company_brief", {"company": "빗썸"}),
            ("company_tech", {"company": "메가존클라우드"}),
            ("market_check", {"education": "전문학사"}),
            ("salary_benchmark", {"company": "빗썸", "career": "신입"}),
            ("freelance_rates", {}),
            ("search_freelance", {"query": "Java", "grade": "고급", "limit": 2}),
        ]
        first_job = None
        for name, args in calls:
            res = await c.call_tool(name, args)
            p = _payload(res)
            ok = not getattr(res, "is_error", False) and "notice" in p
            failed += not ok
            data = p.get("data")
            brief = json.dumps(data, ensure_ascii=False)[:160] if data is not None else p.get("error")
            print(f"{'OK ' if ok else 'ERR'} {name}: {brief}")
            if name == "search_jobs" and data and data.get("jobs"):
                first_job = data["jobs"][0]["id"]

        if first_job:
            for name in ("get_job", "job_keywords"):
                res = await c.call_tool(name, {"job_id": first_job})
                p = _payload(res)
                ok = "notice" in p and p.get("data")
                failed += not ok
                print(f"{'OK ' if ok else 'ERR'} {name}({first_job}): {json.dumps(p.get('data'), ensure_ascii=False)[:120]}")
            pr = await c.get_prompt("write_application", {"job_id": first_job})
            text = pr.messages[0].content.text
            print(f"OK  prompt write_application: {len(text)}자 · 검토자 단계 {'있음' if '검토자' in text else '없음'}")

        pr = await c.get_prompt("reality_check", {"target_role": "AI/ML"})
        text = pr.messages[0].content.text
        ok = "market_check" in text and "비현실적" in text
        failed += not ok
        print(f"{'OK ' if ok else 'ERR'} prompt reality_check: {len(text)}자")

        miss = _payload(await c.call_tool("company_brief", {"company": "없는회사xyz"}))
        print(f"{'OK ' if miss.get('error') else 'ERR'} 없는 회사 → {miss.get('error')}")
    print("실패", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
