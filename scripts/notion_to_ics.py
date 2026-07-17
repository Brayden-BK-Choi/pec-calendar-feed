"""
Notion '캘린더' DB에서 태그(기본값 PEC)가 붙은 항목만 뽑아
구글/애플 캘린더가 구독할 수 있는 .ics 피드로 변환하는 스크립트.

필요한 환경변수:
  NOTION_TOKEN        - Notion 내부 통합(integration) 토큰
  NOTION_DATABASE_ID  - 대상 데이터베이스 ID (기본값: bf573d715e4a47858569bff1c1108f2e)
  NOTION_TAG_FILTER   - 필터링할 태그 이름 (기본값: PEC)
  OUTPUT_PATH         - 저장할 .ics 파일 경로 (기본값: docs/pec.ics)
"""

import os
import datetime
import hashlib
import requests

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "bf573d715e4a47858569bff1c1108f2e")
TAG_FILTER = os.environ.get("NOTION_TAG_FILTER", "PEC")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "docs/pec.ics")

NOTION_VERSION = "2022-06-28"
API_BASE = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

DESCRIPTION_PROPERTIES = ["설명", "이동방법", "유니폼", "촬영지원"]


def query_database():
    url = f"{API_BASE}/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "태그",
            "multi_select": {"contains": TAG_FILTER},
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
    return ""


def escape_ics(text):
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_line(line, limit=73):
    if len(line.encode("utf-8")) <= limit:
        return [line]
    out = []
    while len(line.encode("utf-8")) > limit:
        cut = limit
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return out


def format_datetime(value):
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%Y%m%dT%H%M%SZ")
    return dt.strftime("%Y%m%dT%H%M%S")


def build_event(page):
    props = page["properties"]
    name = get_text(props.get("이름")) or "(제목 없음)"
    date_prop = (props.get("날짜") or {}).get("date")
    if not date_prop or not date_prop.get("start"):
        return None

    start = date_prop["start"]
    end = date_prop.get("end")
    is_datetime = "T" in start

    desc_parts = []
    for label in DESCRIPTION_PROPERTIES:
        val = get_text(props.get(label))
        if val:
            desc_parts.append(f"{label}: {val}")
    description = escape_ics("\\n".join(desc_parts))

    uid = hashlib.md5(page["url"].encode()).hexdigest() + "@notion-pec"
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
    link_val = get_text(props.get("링크"))
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
        "PRODID:-//Notion PEC Calendar//KO",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:PEC 일정",
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
