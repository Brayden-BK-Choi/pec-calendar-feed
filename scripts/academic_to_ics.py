"""
Notion '⛸️ 학사달력' DB에서 부서 태그가 출결/학급/학급상담/할일 인 항목만 뽑아
구글/애플 캘린더가 구독할 수 있는 .ics 피드로 변환하는 스크립트.

필요한 환경변수:
  NOTION_TOKEN                - Notion 내부 통합(integration) 토큰 (notion_to_ics.py와 동일한 토큰 사용)
  NOTION_ACADEMIC_DATABASE_ID - 대상 데이터베이스 ID (기본값: 372a9cfbe97881ffbe6ecc20c263264a)
  NOTION_DEPT_TAGS            - 필터링할 부서 태그(콤마 구분, 기본값: 출결,학급,학급상담,할일)
  OUTPUT_PATH                 - 저장할 .ics 파일 경로 (기본값: docs/academic.ics)
"""

import os
import datetime
import hashlib
import requests

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ.get("NOTION_ACADEMIC_DATABASE_ID", "372a9cfbe97881ffbe6ecc20c263264a")
DEPT_TAGS = [t.strip() for t in os.environ.get("NOTION_DEPT_TAGS", "출결,학급,학급상담,할일").split(",") if t.strip()]
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "docs/academic.ics")

NOTION_VERSION = "2022-06-28"
API_BASE = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

DESCRIPTION_PROPERTIES = ["비고", "시간, 장소", "담당자"]
TITLE_PROPERTY = "일정명"
DATE_PROPERTY = "날짜"
DEPT_PROPERTY = "부서"
LINK_PROPERTY = "링크"


def query_database():
    url = f"{API_BASE}/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "or": [
                {"property": DEPT_PROPERTY, "multi_select": {"contains": tag}}
                for tag in DEPT_TAGS
            ]
        },
        "page_size": 100,
    }
    results = []
    while True:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        if data.get("has_more"):
            payload["start_cursor"] = data["next_cursor"]
        else:
            break
    return results


def get_text(prop):
    if not prop:
        return ""
    t = prop.get("type")
    if t == "title":
        return "".join(x["plain_text"] for x in prop["title"])
    if t == "rich_text":
        return "".join(x["plain_text"] for x in prop["rich_text"])
    if t == "url":
        return prop.get("url") or ""
    if t == "multi_select":
        return ", ".join(o["name"] for o in prop["multi_select"])
    if t == "checkbox":
        return "예" if prop.get("checkbox") else ""
    return ""


def escape_ics(text):
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_line(line, limit=75):
    """iCalendar 사양(RFC 5545)상 한 줄은 75옥텟을 넘으면 접어야(fold) 함.
    바이트(옥텟) 길이 기준으로 안전하게 자르되, 멀티바이트 문자(한글 등)의
    중간을 자르지 않도록 문자 단위로 누적 바이트 길이를 계산한다."""
    if len(line.encode("utf-8")) <= limit:
        return [line]

    out = []
    remaining = line
    first = True
    while remaining:
        budget = limit if first else limit - 1
        chunk = ""
        chunk_bytes = 0
        idx = 0
        for ch in remaining:
            ch_bytes = len(ch.encode("utf-8"))
            if chunk_bytes + ch_bytes > budget:
                break
            chunk += ch
            chunk_bytes += ch_bytes
            idx += 1
        if not chunk:
            chunk = remaining[0]
            idx = 1
        out.append(chunk if first else " " + chunk)
        remaining = remaining[idx:]
        first = False
    return out


def format_datetime(value):
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%Y%m%dT%H%M%SZ")
    return dt.strftime("%Y%m%dT%H%M%S")


def build_event(page):
    props = page["properties"]
    name = get_text(props.get(TITLE_PROPERTY)) or "(제목 없음)"
    date_prop = (props.get(DATE_PROPERTY) or {}).get("date")
    if not date_prop or not date_prop.get("start"):
        return None

    start = date_prop["start"]
    end = date_prop.get("end")
    is_datetime = "T" in start

    dept = get_text(props.get(DEPT_PROPERTY))
    desc_parts = []
    if dept:
        desc_parts.append(f"부서: {dept}")
    for label in DESCRIPTION_PROPERTIES:
        val = get_text(props.get(label))
        if val:
            desc_parts.append(f"{label}: {val}")
    description = escape_ics("\\n".join(desc_parts))

    uid = hashlib.md5(page["url"].encode()).hexdigest() + "@notion-academic"
    dtstamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{dtstamp}"]

    if is_datetime:
        lines.append(f"DTSTART:{format_datetime(start)}")
        if end:
            lines.append(f"DTEND:{format_datetime(end)}")
    else:
        lines.append(f"DTSTART;VALUE=DATE:{start.replace('-', '')}")
        if end:
            end_date = datetime.date.fromisoformat(end) + datetime.timedelta(days=1)
        else:
            end_date = datetime.date.fromisoformat(start) + datetime.timedelta(days=1)
        lines.append(f"DTEND;VALUE=DATE:{end_date.strftime('%Y%m%d')}")

    lines.append(f"SUMMARY:{escape_ics(name)}")
    if description:
        lines.append(f"DESCRIPTION:{description}")
    link_val = get_text(props.get(LINK_PROPERTY))
    if link_val:
        lines.append(f"URL:{link_val}")
    lines.append(f"SOURCE:{page['url']}")
    lines.append("END:VEVENT")

    folded = []
    for line in lines:
        folded.extend(fold_line(line))
    return folded


def main():
    pages = query_database()
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Notion Academic Calendar//KO",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:학사달력 (출결/학급/학급상담/할일)",
        "X-WR-TIMEZONE:Asia/Seoul",
        "REFRESH-INTERVAL;VALUE=DURATION:PT30M",
    ]
    count = 0
    for page in pages:
        event = build_event(page)
        if event:
            ics_lines.extend(event)
            count += 1
    ics_lines.append("END:VCALENDAR")

    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(ics_lines) + "\r\n")

    print(f"Wrote {count} events to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
