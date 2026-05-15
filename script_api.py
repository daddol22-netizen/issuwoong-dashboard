#!/usr/bin/env python3
"""대본 생성 API 서버 — localhost:8888"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'youtube_pipeline'))

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # GitHub Pages → localhost 크로스 오리진 허용


def _build_script_prompt(topic: str, headlines: list[str], direction: str = "", target: str = "") -> str:
    headlines_text = "\n".join(f"- {h}" for h in headlines) if headlines else ""
    direction_block = f"\n【작성 방향】\n{direction}\n" if direction else ""
    target_block = f"\n【타겟 시청자】\n{target}\n" if target else ""
    return f"""다음 주제로 이슈웅 채널 유튜브 대본을 작성해주세요.

주제: {topic}
관련 뉴스 헤드라인:
{headlines_text}{direction_block}{target_block}
채널 성격: 사회 문제를 꼬집는 정보성 콘텐츠
채널 스타일: 특정 시각에서 날카롭게 분석, 시청자가 몰랐던 관점을 제시

【필수 대본 원칙】
- 두괄식 구성: 충격적 결론/반전 → 이유 분석 → 근거 → 마무리
- 씬1(훅): 배경 설명 절대 금지. 첫 문장부터 핵심 치기
- 씬2(이탈방지): 2~3분 지점에 핵심 수치/데이터 배치
- 구어체: 말하듯이 (글 형식 금지)
- 각 씬 끝에 다음 씬 궁금증 유발
- 목표 분량: 순수 내레이션(말하는 부분)만 공백 제외 최소 7,000자 이상 (18분+ 영상 기준)
- 씬을 최소 6개 이상 구성하고 각 씬마다 충분한 분량 확보
- 분량이 부족하면 수치/사례/반론/전문가 의견 등으로 내용 보강 (늘리기 위한 반복 금지)

【관점 원칙 — 반드시 준수】
- 대본 전체가 하나의 일관된 시각으로 흘러야 함
- "A도 맞고 B도 맞다", "양측 입장을 들어보면" 식의 중립적 균형 서술 금지
- 방향성/타겟이 지정된 경우: 그 시각에서 끝까지 밀어붙일 것
- 방향성/타겟이 없는 경우: 콘텐츠에서 가장 자극적인 단일 시각을 스스로 선택해서 그것으로 관통
- 반론을 다루더라도 "그 주장이 왜 틀렸는지"를 보여주기 위한 용도로만 사용

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
    direction = data.get('direction', '').strip()
    target = data.get('target', '').strip()

    if not topic:
        return jsonify({"error": "topic이 필요합니다"}), 400

    try:
        import anthropic
        from config import ANTHROPIC_API_KEY, MODEL

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=MODEL,
            max_tokens=12000,
            messages=[{"role": "user", "content": _build_script_prompt(topic, headlines, direction, target)}],
            system=[{
                "type": "text",
                "text": "당신은 유튜브 채널 이슈웅의 전문 대본 작가입니다. 성공 데이터 기반 두괄식 구성으로 완성도 높은 대본을 작성합니다.",
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
