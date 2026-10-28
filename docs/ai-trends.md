# AI 트렌드 스크랩 운영

대상은 `hbp001/hyobin.github.io`의 `#radar` / Signals입니다. 현재 공개 URL은 https://hbp001.github.io/hyobin.github.io/ 입니다. 다른 후보 `hbp001/hbp001.github.io`는 AIS-LLM 논문 소개 사이트입니다. 기존 연구·프로젝트·사진·인라인 CSS는 보존합니다.

## 구현한 경로

공개 arXiv API와 OpenAI 공식 RSS → 최근 14일 최대 60개 후보 → 공식 메타데이터 독립 재조회 → 제목·URL·발행일 대조 및 중복 검사 → 실질 변경이 있을 때만 기존 GitHub 연결로 `data/radar.json` 갱신 → 기존 GitHub Pages 배포 확인 순서입니다. 유료 LLM과 새 API 키는 사용하지 않습니다. 실질 내용 digest가 같으면 데이터 커밋을 만들지 않습니다. 수집·검증 실패 시 기존 데이터와 공개 사이트를 유지합니다.

두 가지 카드의 의미는 다릅니다.

- **서지 메타데이터 대조됨 / 해설 미검토**: 공식 출처에서 제목·URL·발행일을 대조한 자동 카드입니다. 제목 기반 카테고리는 분류 제안입니다. 초록·본문·이미지·만들어낸 요약·면접 해설은 싣지 않습니다. 내용·성능·안전성이 검증됐다는 뜻이 아닙니다.
- **서지 메타데이터 대조됨 / 해설 원문 검토됨**: `data/reviews.json`의 짧은 자체 요약·한계·면접 질문·미실행 적용 아이디어까지 원문과 검토한 읽기 노트입니다. AI 도움을 받은 초안은 검토해야 하며 자신의 연구 실적으로 표현하지 않습니다.

첫 노트는 2610.35193 v1 서베이입니다. 원문 검토에서 평가 설계·결론을 확인했고 공개 API의 제목·발행일도 대조했습니다. 학회·저널 게재나 성능 향상 실험으로 소개하지 않습니다. 원문 정보가 바뀌면 전체 갱신을 차단하여 해설 재검토를 요구합니다.

## 로컬 검사

```
python3 -m unittest discover -s tests -v
node tests/trends-ui.test.js
python3 scripts/trends.py refresh --dry-run --output /tmp/radar.json
python3 scripts/trends.py refresh --output /tmp/radar.json
python3 scripts/trends.py refresh --previous /tmp/radar.json --output /tmp/next-radar.json
```

`--dry-run`은 공개 출처를 읽어 검증하지만 파일·커밋·배포를 만들지 않습니다. `refresh`는 성공 후에만 JSON을 원자적으로 씁니다. 동일 자료의 timestamp 변화는 digest에 반영하지 않으며 첫 수집일을 보존합니다. 사이트 조립은 원본 사진이 없는 불완전 체크아웃이나 symlink가 있으면 차단합니다. 공개 패키지에는 명시한 HTML·사진·CSS·UI JavaScript·피드만 넣고 `.git`·수집기·검토 설정·후보·credentials는 제외합니다.

## 현재 운영 상태

공개 사이트와 첫 41건의 배포를 완료했습니다. 원문 검토 해설 1건과 서지 메타데이터 카드 40건을 구분해 표시합니다.

일일 갱신 예약은 활성화되어 있으며 **2026년 10월 29일부터 매일 오전 9시(Asia/Seoul)** 실행합니다. 외부 예약 작업이 공개 자료를 확인하고 스키마·중복·출처 검사를 통과한 실질 변경만 기존 GitHub 연결로 `data/radar.json`에 반영한 뒤, 기존 Pages 배포 결과를 확인합니다. 동일한 자료만 있으면 불필요한 커밋을 만들지 않습니다. 새로운 자격증명이나 Pages 토큰 권한, Actions 게시 설정 변경 없이 운영하는 경로입니다.

첫 예약 실행은 아직 미래이므로 예약 활성화와 최초 공개 배포는 확인됐지만, **첫 정기 실행의 성공은 아직 검증되지 않았습니다.** 실행 후 데이터 갱신과 Pages 배포 결과를 확인해야 합니다.

`trends.yml`은 PR·main push·수동 실행 시 검사와 검증용 artifact를 생성하는 CI입니다. `contents: read`이며 데이터 파일을 쓰거나 정기 공개를 중복 실행하지 않습니다.

## 비활성 대안: GitHub Actions 직접 게시

`.github/workflows/trends-publish.yml.disabled`는 정적 사이트를 조립해 Pages에 직접 게시하는 대안 템플릿입니다. 현재는 `.disabled` 확장자로 비활성 상태를 유지하며 외부 예약과 함께 켜지 않습니다.

이 대안으로 전환할 때만 다음 항목을 별도로 검토합니다.

1. 외부 일일 예약을 중지하여 두 게시 경로가 중복 실행되지 않게 합니다.
2. Pages의 publishing source가 GitHub Actions인지 확인합니다. 변경이 필요하면 소유자가 처리합니다.
3. 템플릿의 확장자를 `.yml`로 바꾸고 repository variable `AI_TRENDS_AUTOPUBLISH=approved`를 설정합니다. 기존 `github-pages` 환경의 브랜치·보호 규칙을 유지합니다.
4. 직접 배포 job에는 `pages: write`, `id-token: write`가 필요합니다. 직접 배포는 데이터 커밋을 만들지 않으므로 `contents: write`는 필요하지 않습니다. 이는 현재 외부 예약 경로에 추가할 권한이 아닙니다.
5. main에서 `dry_run=true`로 확인한 뒤 `dry_run=false`로 첫 배포합니다. 템플릿의 일정은 매일 09:00 KST입니다. 네트워크·JSON·원문 대조 오류는 배포를 차단합니다.

공식 Pages workflow 요구사항: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

기존 `signals-pipeline/signals/`는 보존된 참고 코드이며 새 경로에서는 실행하지 않습니다. Notion·회사 자료·메일을 읽거나 공개하지 않습니다. Actions 사용량과 실행 가능 여부는 계정 정책에 따릅니다.
