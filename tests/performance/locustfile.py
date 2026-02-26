"""
Locust Performance Tests for Story Life API

This module contains load tests for the API endpoints using Locust.

Installation:
    pip install locust

Usage:
    # Run with web UI
    locust -f tests/performance/locustfile.py
    
    # Run headless (for CI)
    locust -f tests/performance/locustfile.py --headless -u 10 -r 2 -t 60s
    
    # Run specific test
    locust -f tests/performance/locustfile.py GamePlayUser --headless -u 5 -r 1 -t 30s

Environment Variables:
    API_HOST: Target host (default: http://localhost:8000)
    TEST_USER_TOKEN: Bearer token for authenticated requests
"""
import os
import random
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner


# Configuration
API_HOST = os.getenv("API_HOST", "http://localhost:8000")
TEST_USER_TOKEN = os.getenv("TEST_USER_TOKEN", "")


class BaseAPIUser(HttpUser):
    """Base user class with common functionality."""
    
    abstract = True
    host = API_HOST
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when a user starts."""
        self.auth_headers = {}
        if TEST_USER_TOKEN:
            self.auth_headers = {"Authorization": f"Bearer {TEST_USER_TOKEN}"}
    
    def make_request(self, method, path, **kwargs):
        """Make an HTTP request with error handling."""
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"].update(self.auth_headers)
        
        with self.client.request(method, path, catch_response=True, **kwargs) as response:
            if response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            elif response.status_code >= 400:
                response.failure(f"Client error: {response.status_code}")
            else:
                response.success()
            return response


class AnonymousUser(BaseAPIUser):
    """
    Simulates an anonymous user browsing the application.
    
    Tests:
    - Landing page load
    - Registration flow
    - Basic API discovery
    """
    
    weight = 3  # 30% of users
    
    @task(5)
    def get_api_docs(self):
        """Access API documentation."""
        self.client.get("/docs", name="/docs")
    
    @task(3)
    def health_check(self):
        """Health check endpoint."""
        self.client.get("/health", name="/health")
    
    @task(2)
    def register_user(self):
        """Simulate user registration."""
        display_name = f"TestUser_{random.randint(1000, 9999)}"
        self.client.post(
            "/api/auth/register",
            json={"display_name": display_name},
            name="/api/auth/register"
        )


class GamePlayUser(BaseAPIUser):
    """
    Simulates an authenticated user playing the game.
    
    Tests:
    - Game creation
    - Event generation
    - Decision making
    - Save/load operations
    """
    
    weight = 5  # 50% of users
    
    def on_start(self):
        """Register and get auth token."""
        super().on_start()
        
        if not TEST_USER_TOKEN:
            # Register a new user for this test session
            display_name = f"PerfTest_{random.randint(10000, 99999)}"
            response = self.client.post(
                "/api/auth/register",
                json={"display_name": display_name},
                name="/api/auth/register"
            )
            if response.status_code == 200:
                data = response.json()
                self.auth_headers = {"Authorization": f"Bearer {data.get('token', '')}"}
    
    @task(5)
    def get_saved_games(self):
        """Retrieve saved games list."""
        self.make_request("GET", "/api/games", name="/api/games")
    
    @task(3)
    def get_presets(self):
        """Get character presets."""
        self.make_request("GET", "/api/presets", name="/api/presets")
    
    @task(2)
    def create_game(self):
        """Create a new game."""
        game_data = {
            "character_settings": {
                "era": {"era_name": "现代"},
                "age": {"start_age": 25},
                "gender": {"gender": "male"},
            },
            "player_name": f"PerfPlayer_{random.randint(1000, 9999)}",
            "life_vision": "Live a happy life",
            "language": "zh"
        }
        self.make_request("POST", "/api/games", json=game_data, name="/api/games [POST]")
    
    @task(1)
    def get_game_state(self):
        """Get game state (requires active game)."""
        # This would need a valid game_id
        game_id = random.randint(1, 100)
        self.make_request("GET", f"/api/games/{game_id}/state", name="/api/games/{id}/state")


class APIStressUser(BaseAPIUser):
    """
    High-intensity user for stress testing.
    
    Tests rapid-fire requests to stress the system.
    """
    
    weight = 2  # 20% of users
    wait_time = between(0.1, 0.5)  # Very short wait times
    
    @task
    def rapid_health_checks(self):
        """Rapid health check requests."""
        for _ in range(5):
            self.client.get("/health", name="/health [stress]")
    
    @task
    def rapid_game_list(self):
        """Rapid game list requests."""
        for _ in range(3):
            self.make_request("GET", "/api/games", name="/api/games [stress]")


# Event handlers for test reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts."""
    print(f"\n{'='*60}")
    print("Locust Performance Test Starting")
    print(f"Target Host: {API_HOST}")
    print(f"{'='*60}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops."""
    print(f"\n{'='*60}")
    print("Locust Performance Test Completed")
    print(f"{'='*60}\n")


# Custom test scenarios
class QuickSmokeTest(BaseAPIUser):
    """
    Quick smoke test for CI/CD pipelines.
    
    Run with: locust -f tests/performance/locustfile.py QuickSmokeTest --headless -u 1 -t 10s
    """
    
    wait_time = between(0.5, 1)
    
    @task
    def smoke_test(self):
        """Run basic smoke test requests."""
        # Health check
        self.client.get("/health", name="smoke/health")
        
        # API docs
        self.client.get("/docs", name="smoke/docs")
        
        # Register
        self.client.post(
            "/api/auth/register",
            json={"display_name": f"SmokeTest_{random.randint(1000, 9999)}"},
            name="smoke/register"
        )
