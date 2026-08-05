# Signals — 자동 트렌드 수집기

매일 09:00 KST에 국내외 AI 연구·산업 소식을 모아 `data/radar.json`으로 만들어
포트폴리오 사이트의 "Signals from the Frontier" 섹션에 자동 반영합니다.

## 설치
저장소 루트에 이 폴더의 내용을 그대로 복사하세요.

    scripts/collect.py
    scripts/sources.yaml
    .github/workflows/signals.yml
    data/

## 먼저 테스트
    pip install requests feedparser pyyaml
    python scripts/collect.py --dry-run --no-llm

## 자동 실행
`.github/workflows/signals.yml`이 있으면 매일 자동 실행됩니다.
Actions 탭 → Signals → Run workflow 로 즉시 실행도 가능합니다.

## LLM 요약 켜기 (선택)
저장소 Settings → Secrets → Actions 에 `ANTHROPIC_API_KEY` 등록.
없으면 요약 단계만 건너뛰고 정상 작동합니다.

자세한 설명은 `사이트-편집-가이드.md`의 9장을 참고하세요.
