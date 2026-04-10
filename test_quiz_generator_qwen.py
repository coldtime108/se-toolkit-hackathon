import json
import unittest
from unittest.mock import patch

from app import services


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class QuizGeneratorQwenTests(unittest.TestCase):
    def test_fallback_generation_creates_question_style_cards(self):
        text = (
            "Spaced repetition improves long-term retention by reviewing material at expanding intervals. "
            "A strong study plan should prioritize due cards and track user accuracy over time."
        )

        cards = services.generate_cards_from_text(text)

        self.assertGreaterEqual(len(cards), 2)
        for question, answer in cards:
            self.assertTrue(question.endswith("?"))
            self.assertNotIn("____", question)
            self.assertNotIn("fill the missing word", question.lower())
            self.assertTrue(answer)

    def test_llm_generation_uses_json_cards_when_model_responds_well(self):
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            payload = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "cards": [
                                        {
                                            "question": "Why is spaced repetition effective?",
                                            "answer": "Because it schedules reviews at increasing intervals.",
                                        },
                                        {
                                            "question": "How should a study plan treat difficult topics?",
                                            "answer": "It should review them more frequently.",
                                        },
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
            return FakeResponse(payload)

        with patch.dict(
            services.os.environ,
            {
                "LLM_API_BASE_URL": "http://ollama:11434/v1",
                "LLM_API_MODEL": "qwen2.5:3b-instruct",
                "LLM_API_KEY": "",
            },
            clear=False,
        ):
            with patch("app.services.urlrequest.urlopen", side_effect=fake_urlopen):
                cards = services.generate_cards_from_llm("Some study note text.", 5)

        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0][0], "Why is spaced repetition effective?")
        self.assertEqual(captured["body"]["model"], "qwen2.5:3b-instruct")
        prompt = captured["body"]["messages"][1]["content"]
        self.assertIn("not fill-in-the-blank", prompt)
        self.assertIn("question mark", prompt)

    def test_llm_generation_falls_back_when_model_output_is_invalid(self):
        def bad_urlopen(request, timeout=0):
            payload = {"choices": [{"message": {"content": "not json"}}]}
            return FakeResponse(payload)

        with patch("app.services.urlrequest.urlopen", side_effect=bad_urlopen):
            cards, source = services.generate_quiz_cards(
                "Spaced repetition improves long-term retention by reviewing material at expanding intervals."
                "A strong study plan should prioritize due cards and track user accuracy over time.",
                5,
            )

        self.assertEqual(source, "built-in fallback")
        self.assertGreaterEqual(len(cards), 1)
        self.assertTrue(cards[0][0].endswith("?"))
        self.assertNotIn("____", cards[0][0])


if __name__ == "__main__":
    unittest.main()