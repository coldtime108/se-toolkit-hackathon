#!/usr/bin/env python3
"""
Comprehensive test suite for NeuroSprint application.
Tests all features including the new spaced repetition optimizer.
"""

import requests
from datetime import datetime
from typing import Optional

BASE_URL = "http://10.93.26.30:8000"
TIMEOUT = 10

class NeuroSprintTester:
    def __init__(self):
        self.session = requests.Session()
        self.user_id: Optional[int] = None
        self.topic_ids = []
        self.card_ids = []
        self.session_id: Optional[int] = None
        self.passed = 0
        self.failed = 0
        self.results = []

    def test(self, name: str, condition: bool, message: str = ""):
        status = "✅ PASS" if condition else "❌ FAIL"
        self.results.append(f"{status}: {name}")
        if message:
            self.results.append(f"   {message}")
        if condition:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{status}: {name}")
        if message:
            print(f"   {message}")

    def register_user(self, username: str, password: str) -> bool:
        print("\n=== TESTING AUTHENTICATION ===")
        try:
            response = self.session.post(
                f"{BASE_URL}/api/auth/register",
                json={"username": username, "password": password},
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            self.test("Register user", success, f"Status: {response.status_code}")
            if success:
                data = response.json()
                self.user_id = data.get("id")
                self.test("User ID extracted", self.user_id is not None)
            return success
        except Exception as e:
            self.test("Register user", False, f"Exception: {str(e)}")
            return False

    def test_auth_me(self) -> bool:
        try:
            response = self.session.get(f"{BASE_URL}/api/auth/me", timeout=TIMEOUT)
            success = response.status_code == 200 and response.json().get("authenticated")
            self.test("Get current user", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.test("Get current user", False, f"Exception: {str(e)}")
            return False

    def create_topic(self, title: str) -> Optional[int]:
        print("\n=== TESTING TOPICS ===")
        try:
            response = self.session.post(
                f"{BASE_URL}/api/topics",
                json={"title": title},
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            self.test("Create topic", success, f"Status: {response.status_code}")
            if success:
                data = response.json()
                topic_id = data.get("id")
                self.topic_ids.append(topic_id)
                return topic_id
            return None
        except Exception as e:
            self.test("Create topic", False, f"Exception: {str(e)}")
            return None

    def list_topics(self) -> bool:
        try:
            response = self.session.get(f"{BASE_URL}/api/topics", timeout=TIMEOUT)
            success = response.status_code == 200 and isinstance(response.json(), list)
            self.test("List topics", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.test("List topics", False, f"Exception: {str(e)}")
            return False

    def create_cards(self, topic_id: int, count: int = 5) -> bool:
        print("\n=== TESTING CARDS ===")
        try:
            for i in range(count):
                response = self.session.post(
                    f"{BASE_URL}/api/topics/{topic_id}/cards",
                    json={
                        "question": f"What is question {i+1}?",
                        "answer": f"Answer {i+1}"
                    },
                    timeout=TIMEOUT
                )
                success = response.status_code == 200
                if success:
                    card_id = response.json().get("id")
                    self.card_ids.append(card_id)
                self.test(f"Create card {i+1}", success, f"Status: {response.status_code}")
            return True
        except Exception as e:
            self.test("Create cards", False, f"Exception: {str(e)}")
            return False

    def list_topic_cards(self, topic_id: int) -> bool:
        try:
            response = self.session.get(
                f"{BASE_URL}/api/topics/{topic_id}/cards",
                timeout=TIMEOUT
            )
            success = response.status_code == 200 and isinstance(response.json(), list)
            self.test("List topic cards", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.test("List topic cards", False, f"Exception: {str(e)}")
            return False

    def start_session(self, topic_id: int) -> bool:
        print("\n=== TESTING SESSIONS ===")
        try:
            response = self.session.post(
                f"{BASE_URL}/api/sessions/start?topic_id={topic_id}&limit=5",
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            self.test("Start session", success, f"Status: {response.status_code}")
            if success:
                data = response.json()
                self.session_id = data.get("session_id")
                cards_in_session = len(data.get("cards", []))
                self.test("Session has cards", cards_in_session > 0, f"Cards: {cards_in_session}")
            return success
        except Exception as e:
            self.test("Start session", False, f"Exception: {str(e)}")
            return False

    def answer_card(self, card_id: int, answer: str) -> bool:
        if not self.session_id:
            return False
        try:
            response = self.session.post(
                f"{BASE_URL}/api/sessions/{self.session_id}/answer",
                json={
                    "card_id": card_id,
                    "user_answer": answer,
                    "response_seconds": 5.0
                },
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            self.test("Answer card", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.test("Answer card", False, f"Exception: {str(e)}")
            return False

    def finish_session(self) -> bool:
        if not self.session_id:
            return False
        try:
            response = self.session.post(
                f"{BASE_URL}/api/sessions/{self.session_id}/finish",
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            self.test("Finish session", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.test("Finish session", False, f"Exception: {str(e)}")
            return False

    def get_progress_summary(self) -> bool:
        print("\n=== TESTING PROGRESS ===")
        try:
            response = self.session.get(f"{BASE_URL}/api/progress/summary", timeout=TIMEOUT)
            success = response.status_code == 200
            self.test("Get progress summary", success, f"Status: {response.status_code}")
            if success:
                data = response.json()
                self.test("Progress has required fields", 
                         all(k in data for k in ["total_cards", "due_today", "accuracy_percent"]),
                         f"Fields: {list(data.keys())}")
            return success
        except Exception as e:
            self.test("Get progress summary", False, f"Exception: {str(e)}")
            return False

    def get_forecast(self) -> bool:
        print("\n=== TESTING FORECAST ===")
        try:
            response = self.session.get(
                f"{BASE_URL}/api/forecast?days=7",
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            self.test("Get forecast", success, f"Status: {response.status_code}")
            if success:
                data = response.json()
                self.test("Forecast has required fields",
                         all(k in data for k in ["retention_percent", "projected_due"]),
                         f"Fields: {list(data.keys())}")
            return success
        except Exception as e:
            self.test("Get forecast", False, f"Exception: {str(e)}")
            return False

    def get_spaced_repetition_plan(self) -> bool:
        print("\n=== TESTING SPACED REPETITION OPTIMIZER ===")
        try:
            response = self.session.get(
                f"{BASE_URL}/api/spaced-repetition-plan",
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            self.test("Get spaced repetition plan", success, f"Status: {response.status_code}")
            if success:
                data = response.json()
                required_fields = ["generated_at", "total_cards_due", "time_windows", "recommended_today"]
                self.test("Plan has required fields",
                         all(k in data for k in required_fields),
                         f"Fields: {list(data.keys())}")
                self.test("Time windows is a list",
                         isinstance(data.get("time_windows"), list),
                         f"Time windows: {len(data.get('time_windows', []))} windows")
                
                # Check structure of time windows
                for window in data.get("time_windows", []):
                    window_required = ["window_label", "start_date", "end_date", "cards", "count"]
                    if all(k in window for k in window_required):
                        cards_in_window = len(window.get("cards", []))
                        self.test(f"Window '{window.get('window_label')}' has cards", 
                                 cards_in_window == window.get("count"),
                                 f"Expected: {window.get('count')}, Got: {cards_in_window}")
            return success
        except Exception as e:
            self.test("Get spaced repetition plan", False, f"Exception: {str(e)}")
            return False

    def test_quiz_generator(self, topic_id: int) -> bool:
        print("\n=== TESTING QUIZ GENERATOR ===")
        note_text = (
            "Spaced repetition improves long-term retention by reviewing material at expanding intervals. "
            "A strong study plan should prioritize due cards and track user accuracy over time. "
            "Active recall and short focused sessions improve exam performance. "
            "Students should review difficult concepts more frequently than easy ones."
        )

        try:
            preview_response = self.session.post(
                f"{BASE_URL}/api/quiz-generator/preview",
                json={"text": note_text, "limit": 8},
                timeout=TIMEOUT,
            )
            preview_ok = preview_response.status_code == 200
            self.test("Generate quiz draft", preview_ok, f"Status: {preview_response.status_code}")
            if not preview_ok:
                return False

            preview_data = preview_response.json()
            cards = preview_data.get("cards", [])
            self.test("Generated cards list", isinstance(cards, list) and len(cards) > 0, f"Cards: {len(cards)}")
            if not cards:
                return False

            save_response = self.session.post(
                f"{BASE_URL}/api/quiz-generator/save",
                json={"topic_id": topic_id, "cards": cards},
                timeout=TIMEOUT,
            )
            save_ok = save_response.status_code == 200
            self.test("Save generated cards", save_ok, f"Status: {save_response.status_code}")
            if not save_ok:
                return False

            save_data = save_response.json()
            saved_count = int(save_data.get("saved_count", 0))
            self.test("Saved count positive", saved_count > 0, f"Saved: {saved_count}")

            verify_response = self.session.get(f"{BASE_URL}/api/topics/{topic_id}/cards", timeout=TIMEOUT)
            verify_ok = verify_response.status_code == 200 and len(verify_response.json()) >= 5 + saved_count
            self.test("Generated cards persisted", verify_ok, f"Total cards: {len(verify_response.json())}")
            return verify_ok
        except Exception as e:
            self.test("Quiz generator flow", False, f"Exception: {str(e)}")
            return False

    def create_insight(self) -> bool:
        print("\n=== TESTING INSIGHTS ===")
        try:
            response = self.session.post(
                f"{BASE_URL}/api/insights",
                json={
                    "title": "Test Insight",
                    "body": "This is a test insight note for the notebook."
                },
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            self.test("Create insight", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.test("Create insight", False, f"Exception: {str(e)}")
            return False

    def list_insights(self) -> bool:
        try:
            response = self.session.get(f"{BASE_URL}/api/insights", timeout=TIMEOUT)
            success = response.status_code == 200 and isinstance(response.json(), list)
            self.test("List insights", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.test("List insights", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        print("NeuroSprint Comprehensive Test Suite")
        print("=" * 60)
        print(f"Testing URL: {BASE_URL}")
        print(f"Start time: {datetime.now().isoformat()}")
        print("=" * 60)

        # Test authentication
        self.register_user(f"testuser{datetime.now().timestamp()}", "testpass123")
        self.test_auth_me()

        # Test topics and cards
        topic_id = self.create_topic(f"Test Topic {datetime.now().timestamp()}")
        if topic_id:
            self.list_topics()
            self.create_cards(topic_id, 5)
            self.list_topic_cards(topic_id)
            self.test_quiz_generator(topic_id)

            # Test sessions
            self.start_session(topic_id)
            if self.card_ids:
                self.answer_card(self.card_ids[0], "Answer 1")
            self.finish_session()

        # Test progress and analytics
        self.get_progress_summary()
        self.get_forecast()
        self.get_spaced_repetition_plan()

        # Test insights
        self.create_insight()
        self.list_insights()

        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        for result in self.results:
            print(result)
        print("=" * 60)
        print(f"Total Passed: {self.passed}")
        print(f"Total Failed: {self.failed}")
        print(f"Success Rate: {self.passed / (self.passed + self.failed) * 100:.1f}%")
        print(f"End time: {datetime.now().isoformat()}")
        print("=" * 60)


if __name__ == "__main__":
    tester = NeuroSprintTester()
    tester.run_all_tests()
