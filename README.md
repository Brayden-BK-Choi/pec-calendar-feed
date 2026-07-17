# PEC 캘린더 구독 피드

Notion "📖 캘린더" DB에서 태그가 `PEC`인 항목만 뽑아 30분마다 자동 갱신되는
`.ics` 구독 링크를 만드는 저장소입니다.

## 포함된 파일

- `scripts/notion_to_ics.py` — Notion API를 호출해 `docs/pec.ics`를 생성하는 스크립트
- `.github/workflows/update-ics.yml` — 30분마다 스크립트를 실행하고 결과를 커밋하는 GitHub Actions

## 설정 순서

1. **Notion 통합(integration) 토큰 재발급**
   기존에 노출됐던 토큰은 폐기하고 [notion.so/my-integrations](https://www.notion.so/my-integrations)
   에서 재발급하세요. 그리고 "📖 캘린더" 데이터베이스에 그 통합을 다시 연결(Connect)해주세요.

2. **저장소 Secrets 등록** (Settings → Secrets and variables → Actions → New repository secret)
   - `NOTION_TOKEN` = 재발급한 통합 토큰
   - `NOTION_DATABASE_ID` = `bf573d715e4a47858569bff1c1108f2e`

3. **GitHub Actions 실행 확인**
   Actions 탭 → "Update PEC calendar feed" 워크플로우를 수동 실행(Run workflow)해서
   `docs/pec.ics` 파일이 생성/커밋되는지 확인하세요.

4. **GitHub Pages 켜기**
   Settings → Pages → Source를 "Deploy from a branch", Branch를 `main` / `docs` 폴더로 설정.
   몇 분 후 아래 형태의 URL이 생깁니다:
   `https://brayden-bk-choi.github.io/pec-calendar-feed/pec.ics`

## 구독 링크

Pages가 켜지면:

- **구글 캘린더**: 좌측 "다른 캘린더 +" → "URL로 추가" →
  `https://brayden-bk-choi.github.io/pec-calendar-feed/pec.ics` 입력
- **애플 캘린더(macOS/iOS)**: 파일 → "새로운 캘린더 구독" →
  `webcal://brayden-bk-choi.github.io/pec-calendar-feed/pec.ics` 입력

Notion에서 PEC 태그 일정이 바뀌면 GitHub Actions가 30분 내에 `pec.ics`를 갱신하고,
캘린더 앱도 주기적으로 알아서 다시 불러옵니다.

## 이벤트에 포함되는 속성

제목(이름), 날짜(시작/종료), 그리고 설명란에 `설명 / 이동방법 / 유니폼 / 촬영지원`
속성이 함께 들어갑니다. 필요 없는 항목은 `scripts/notion_to_ics.py`의
`DESCRIPTION_PROPERTIES` 목록에서 빼면 됩니다.

## 참고

이 저장소는 Public이라 위 pec.ics URL을 아는 사람은 누구나 일정 내용(아이들 이름 포함 가능)을
볼 수 있습니다. 민감하다면 GitHub Pro/Team의 비공개 Pages로 전환하는 것을 고려하세요.
