#!/usr/bin/env python3
"""대본 생성 API 서버 — localhost:8888"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'youtube_pipeline'))

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # GitHub Pages → localhost 크로스 오리진 허용


def _build_script_prompt(topic: str, headlines: list[str], thumbnails: list[str] = None) -> str:
    headlines_text = "\n".join(f"- {h}" for h in headlines) if headlines else ""
    thumbnails = thumbnails or []

    if thumbnails:
        thumb_lines = "\n".join(f"- {t}" for t in thumbnails)
        stance_block = f"""
【내레이터 설정 — 협상 불가】
이슈웅(내레이터)은 아래 내용을 이미 사실로 확신하고 있습니다:
{thumb_lines}

이 대본은 토론이 아닙니다. 내레이터는 이미 결론을 내린 상태이고,
같은 생각을 가진 시청자에게 "맞죠? 그 이유가 이거예요"를 설명하는 것입니다.
대본의 세계관에서 반대 입장은 존재하지 않습니다.

【이 표현들이 단 한 문장이라도 나오면 대본 전체를 다시 써야 합니다】
❌ "물론 ~측 입장도 있지만..."
❌ "~도 나름의 이유가 있습니다"
❌ "양측을 이해해보면..."
❌ "공정하게 보면..." / "균형 있게..."
❌ "~가 완전히 잘못된 건 아니에요"
❌ 반대 입장을 소개한 다음 반박하는 구조 (소개 자체를 하지 마세요)
"""
    else:
        stance_block = """
【관점 설정 — 직접 선택】
썸네일이 없습니다. 이 주제에서 가장 자극적인 단일 시각을 스스로 선택하고,
내레이터가 그것을 처음부터 이미 확신하는 세계관으로 작성하세요.
반대 입장 소개, 균형 잡기, "양측 다 맞는 점이 있다"는 금지입니다.
"""

    return f"""다음 주제로 이슈웅 채널 유튜브 대본을 작성해주세요.

주제: {topic}
관련 뉴스 헤드라인:
{headlines_text}
{stance_block}
채널 성격: 하나의 뚜렷한 시각으로 사회 문제를 꼬집는 정보성 콘텐츠. 시청자가 "이 사람 말이 맞네"라고 설득당하는 구조.
채널 스타일: 구어체, 날카롭되 무겁지 않게, 시청자가 몰랐던 관점 제시

【필수 대본 원칙】
- 두괄식 구성: 충격적 결론/반전 → 이유 분석 → 근거 → 마무리
- 씬1(훅): 배경 설명 절대 금지. 첫 문장부터 핵심 치기
- 씬2(이탈방지): 2~3분 지점에 핵심 수치/데이터 배치
- 구어체: 말하듯이 (글 형식 금지)
- 각 씬 끝에 다음 씬 궁금증 유발
- 목표 분량: 순수 내레이션(말하는 부분)만 공백 제외 최소 7,000자 이상 (18분+ 영상 기준)
- 씬을 최소 6개 이상 구성하고 각 씬마다 충분한 분량 확보
- 분량이 부족하면 수치/사례/반론/전문가 의견 등으로 내용 보강 (늘리기 위한 반복 금지)

【저작권 원칙 — 반드시 준수】
- 뉴스 기사에서 가져올 수 있는 것: 사실, 수치, 데이터, 사건의 흐름
- 절대 가져오면 안 되는 것: 기사의 문장 표현, 단어 선택, 특정 비유나 어구
- 기사 문장을 그대로 쓰거나 살짝 바꾸는 것 금지
- 같은 사실을 다루더라도 문장은 완전히 새로 써야 함
- 판단 기준: "이 문장이 뉴스 기사 없이도 나올 수 있는가?" → NO면 다시 쓸 것

【고정 인트로 — 그대로 사용】
"몰라도 사는 데 지장 없지만, 알면 세상이 달라 보이는 이야기. 이슈웅입니다."

【고정 아웃트로 — 그대로 사용】
"오늘 얘기 어떠셨나요? 당연하다고 생각했던 것들, 사실 한 번쯤은 짚어볼 필요가 있잖아요. 이슈웅은 앞으로도 그냥 지나치기 아까운 이야기들을 계속 가져올게요. 구독이랑 좋아요는 저한테 큰 힘이 됩니다. 다음 영상에서 만나요."

---

아래 형식으로 작성해주세요:

[제목 후보 3개]
1.
2.
3.

[썸네일 텍스트]
(10자 이내, 강렬하게)

[대본]
(인트로부터 아웃트로까지 완성 대본)
"""


@app.route('/api/generate-script', methods=['POST'])
def generate_script():
    data = request.get_json()
    topic = data.get('topic', '').strip()
    headlines = data.get('headlines', [])
    thumbnails = [t.strip() for t in data.get('thumbnails', []) if t.strip()]

    if not topic:
        return jsonify({"error": "topic이 필요합니다"}), 400

    try:
        import anthropic
        from config import ANTHROPIC_API_KEY, MODEL

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=MODEL,
            max_tokens=12000,
            messages=[{"role": "user", "content": _build_script_prompt(topic, headlines, thumbnails)}],
            system=[{
                "type": "text",
                "text": "당신은 유튜브 채널 이슈웅의 전문 대본 작가입니다. 이 채널의 내레이터는 항상 특정 입장을 이미 확신한 상태에서 그 이유를 시청자에게 설명합니다. 반대 입장을 소개하거나 균형을 맞추는 것은 이 채널의 포맷이 아닙니다. 썸네일에 명시된 내용이 대본의 전제이자 결론이며, 모든 사례·수치·감정선은 그 전제를 강화하는 방향으로만 선택됩니다.",
                "cache_control": {"type": "ephemeral"}
            }]
        )
        script = response.content[0].text
        usage = response.usage
        return jsonify({
            "script": script,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        })

    except ImportError:
        return jsonify({"error": "youtube_pipeline 모듈을 찾을 수 없습니다. Mac에서 실행해주세요."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "이슈웅 대본 API"})


if __name__ == '__main__':
    print("🚀 대본 생성 API 서버 시작: http://localhost:8888")
    app.run(host='0.0.0.0', port=8888, debug=False)
