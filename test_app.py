import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Import the flask application under test
from app import app


class TestCompanionApp(unittest.TestCase):
    """Unit test suite for the AI Companion Flask application."""

    def test_index_route(self):
        """Test that the home page index route renders HTML template successfully."""
        client = app.test_client()
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', response.data)
        self.assertIn(b'AI Companion', response.data)

    @patch('app.character_exists', True)
    @patch('app.runner')
    def test_chat_route_success_hospitality(self, mock_runner):
        """Test successful chat routing for hospitality domain."""
        client = app.test_client()
        mock_session = MagicMock()
        mock_session.user_id = 'inapp_user'
        mock_session.id = 'hospitality_sess123'

        mock_runner.session_service.get_session = AsyncMock(return_value=mock_session)
        mock_runner.app_name = "Demo App"

        async def mock_run_async(*args, **kwargs):
            part = MagicMock()
            part.text = "Hello! Welcome to our hotel."
            content = MagicMock()
            content.parts = [part]
            event = MagicMock()
            event.content = content
            yield event

        mock_runner.run_async = mock_run_async

        response = client.post('/chat', json={
            'message': 'hello',
            'session_id': 'sess123',
            'industry': 'hospitality'
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['response'], "Hello! Welcome to our hotel.")

    @patch('app.character_exists', True)
    @patch('app.runner')
    def test_chat_route_fallback_invalid_industry(self, mock_runner):
        """Test that an unrecognized industry defaults to hospitality."""
        client = app.test_client()
        mock_session = MagicMock()
        mock_session.user_id = 'inapp_user'
        mock_session.id = 'space_sess123'

        mock_runner.session_service.get_session = AsyncMock(return_value=mock_session)
        mock_runner.app_name = "Demo App"

        async def mock_run_async(*args, **kwargs):
            part = MagicMock()
            part.text = "Hello! Welcome to our hotel (fallback)."
            content = MagicMock()
            content.parts = [part]
            event = MagicMock()
            event.content = content
            yield event

        mock_runner.run_async = mock_run_async

        # Send invalid industry 'space' - should fall back to hospitality
        response = client.post('/chat', json={
            'message': 'hello',
            'session_id': 'sess123',
            'industry': 'space'
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['response'], "Hello! Welcome to our hotel (fallback).")

    @patch('app.character_exists', True)
    @patch('app.runner')
    def test_chat_route_create_session_if_none(self, mock_runner):
        """Test dynamic creation of a new session if get_session returns None."""
        client = app.test_client()
        mock_session = MagicMock()
        mock_session.user_id = 'inapp_user'
        mock_session.id = 'hospitals_sess123'

        # Force get_session to return None, and verify create_session is called
        mock_runner.session_service.get_session = AsyncMock(return_value=None)
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)
        mock_runner.app_name = "Demo App"

        async def mock_run_async(*args, **kwargs):
            part = MagicMock()
            part.text = "Patient records loaded."
            content = MagicMock()
            content.parts = [part]
            event = MagicMock()
            event.content = content
            yield event

        mock_runner.run_async = mock_run_async

        response = client.post('/chat', json={
            'message': 'find records',
            'session_id': 'sess123',
            'industry': 'hospitals'
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['response'], "Patient records loaded.")
        mock_runner.session_service.create_session.assert_called_once()

    @patch('app.character_exists', False)
    def test_chat_route_missing_character_agent(self):
        """Test edge case where character agent does not exist (returns query)."""
        client = app.test_client()
        response = client.post('/chat', json={
            'message': 'Testing message backup path',
            'session_id': 'sess123',
            'industry': 'hospitality'
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['response'], "Testing message backup path")


if __name__ == '__main__':
    unittest.main()
