# AI 트렌드 스크랩 운영

대상은 `hbp001/hyobin.github.io`의 `#radar` / Signals입니다. 현재 공개 URL은 https://hbp001.github.io/hyobin.github.io/ 입니다. 다른 후보 `hbp001/hbp001.github.io`는 AIS-LLM 논문 소개 사이트입니다. 기존 연구·프로젝트·사진·인라인 CSS는 보존합니다.

## 구현한 경로

공개 arXiv API와 OpenAI 공식 RSS → 최근 14일 최대 60개 후보 → 공식 메타데이터 독립 재조회 → 제목·URL·발행일 대조 및 중복 검사 → 정적 사이트 조립 → GitHub Pages 배포입니다. 유료 LLM과 새 API 키는 사용하지 않습니다. 자동 배포는 저장소 커밋을 만들지 않으며, 실질 내용 digest가 같으면 배포도 생략합니다. 실패하면 배포 단계에 도달하지 않아 현재 공개 사이트가 유지됩니다.

두 가지 카드의 의미는 다릅니다.

- **서지 메타데이터 대조됨 / 해설 미검토**: 공식 출처에서 제목·URL·발행일을 대조한 자동 카드입니다. 제목 기반 카테고리는 분류 제안입니다. 초록·본문·이미지·만들어낸 요약·면접 해설은 싣지 않습니다. 내용·성능·안전성이 검증됐다는 뜻이 아닙니다.
- **서지 메타데이터 대조됨 / 해설 원문 검토됨**: `data/reviews.json`의 짧은 자체 요약·한계·면접 질문·미실행 적용 아이디어까지 원문과 검토한 읽기 노트입니다. AI 도움을 받은 초안은 검토해야 하며 자신의 연구 실적으로 표현하지 않습니다.

첫 노트는 2610.35193 v1 서베이입니다. 부모 작업에서 평가 설계·결론을 확인했고 공개 API의 제목·발행일도 대조했습니다. 학회·저널 게재나 성능 향상 실험으로 소개하지 않습니다. 원문 정보가 바뀌면 전체 갱신을 차단하여 해설 재검토를 요구합니다.

## 로컬 검사

```
python3 -m unittest discover -s tests -v
node tests/trends-ui.test.js
python3 scripts/trends.py refresh --dry-run --output /tmp/radar.json
python3 scripts/trends.py refresh --output /tmp/radar.json
python3 scripts/trends.py refresh --previous /tmp/radar.json --output /tmp/next-radar.json
```

`--dry-run`은 공개 출처를 읽어 검증하지만 파일·커밋·배포를 만들지 않습니다. `refresh`는 성공 후에만 JSON을 원자적으로 씁니다. 동일 자료의 timestamp 변화는 digest에 반영하지 않으며 첫 수집일을 보존합니다. 사이트 조립은 원본 사진이 없는 불완전 체크아웃이나 symlink가 있으면 차단합니다. 공개 패키지에는 명시한 HTML·사진·CSS·UI JavaScript·피드만 넣고 `.git`·수집기·검토 설정·후보·credentials는 제외합니다.

## 활성화 상태와 최소 권한

공개 배포와 매일 09:00 KST 자동 게시를 승인한 범위의 코드입니다. 기존 Pages 배포와 일일 게시 workflow의 활성화는 별도로 확인합니다. 인증·권한이나 Pages 게시 방식을 자동 변경하지 않습니다.

실행 기본값은 계속 비활성입니다. `trends.yml`은 PR·main push·수동 실행 시 검증과 artifact 생성만 하며 `contents: read`입니다. 실제 매일 게시 경로는 `.github/workflows/trends-publish.yml.disabled`에 완성했으나 `.disabled` 확장자로 실행되지 않습니다. 이 템플릿은 파일명과 명시적 활성화 변수 두 조건이 충족되어야 게시합니다.

연결 권한 문제가 해결된 뒤 다음 단계를 진행합니다.

1. GitHub 연결의 설치 대상에 해당 저장소가 포함되어 있고, 코드 업로드에 필요한 **Contents: Read and write**, workflow 파일 업로드에 필요한 **Workflows: Read and write**가 있는지 확인해야 합니다. 403 응답은 부족한 세부 권한명을 제공하지 않으므로 현재 원인을 이 둘 중 하나로 단정하지 않습니다. 권한 확대나 credentials 생성은 직접 실행하지 않습니다.
2. 검토한 패치를 브랜치에 반영하고 PR을 통해 main에 통합합니다. 원격 쓰기가 거부되면 연결 수정 증거를 확인하기 전 재시도하지 않습니다.
3. 소유자가 Pages의 publishing source가 **GitHub Actions**인지 확인합니다. 현재 설정을 읽을 수 있는 도구가 없어 branch 방식인지 확정하지 못했습니다. 변경이 필요하면 소유자가 처리해야 합니다.
4. 게시 템플릿의 확장자를 `.yml`로 바꾸고 repository variable `AI_TRENDS_AUTOPUBLISH=approved`를 설정합니다. 이는 별도의 자격증명이 아닙니다. `github-pages` 환경의 기존 브랜치·보호 규칙을 유지합니다.
5. 배포 job은 GitHub 공식 요구에 따라 **pages: write**, **id-token: write**가 필요합니다. **contents: write는 필요하지 않습니다.** 현재 자동 발급 GITHUB_TOKEN에 이 권한을 사용할 수 있는지는 확인되지 않았습니다. 로컬 비활성 템플릿만 작성했으며 실제 권한을 확대하지 않았습니다.
6. main에서 `dry_run=true` 수동 실행을 확인한 다음 `dry_run=false`로 첫 배포합니다. 이후 cron `0 0 * * *`가 매일 한국 시간 오전 9시 갱신합니다. 첫 배포 전 기존 `/data/radar.json`의 404만 빈 피드로 허용하며 기타 네트워크·JSON 오류는 배포를 차단합니다.

공식 Pages workflow 요구사항: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

기존 `signals-pipeline/signals/`는 보존된 참고 코드이며 새 경로에서는 실행하지 않습니다. Notion·회사 자료·메일을 읽거나 공개하지 않습니다. Actions 사용량과 실행 가능 여부는 계정 정책에 따릅니다.
