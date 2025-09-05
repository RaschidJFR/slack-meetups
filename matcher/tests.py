import json
from django.test import TestCase, Client
from django.http import HttpResponse
from unittest.mock import patch


class HandleSlackMessageTest(TestCase):
    
    def setUp(self):
        self.client = Client()
        self.url = '/slack/message/'
    
    @patch('matcher.middleware.VerifySlackRequest.process_request')
    def test_url_verification_success(self, mock_verify):
        """Test successful URL verification challenge response"""
        # Mock the middleware to skip signature verification in tests
        mock_verify.return_value = None
        
        challenge_value = "test_challenge_string_12345"
        payload = {
            "type": "url_verification",
            "challenge": challenge_value,
            "token": "test_token"
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data["challenge"], challenge_value)
    
    @patch('matcher.middleware.VerifySlackRequest.process_request')
    @patch('matcher.views.send_message_as_bot')
    @patch('matcher.views.respond_to_user')
    def test_bot_message_ignored(self, mock_respond_to_user, mock_send_message_as_bot, mock_verify):
        """Test that messages from bots are ignored and return 204"""
        mock_verify.return_value = None
        
        payload = {
            "event": {
                "type": "message",
                "bot_id": "B123456789",
                "user": "U123456789",
                "text": "This is from a bot"
            }
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Ensure neither function is called when bot message is processed
        mock_send_message_as_bot.assert_not_called()
        mock_respond_to_user.assert_not_called()
        self.assertEqual(response.status_code, 204)
    
    @patch('matcher.middleware.VerifySlackRequest.process_request')
    @patch('matcher.views.send_message_as_bot')
    @patch('matcher.views.get_mention')
    def test_admin_mention_message_sent_as_bot(self, mock_get_mention, mock_send_message_as_bot, mock_verify):
        """Test that admin messages with @-mentions are sent as bot"""
        mock_verify.return_value = None
        mock_get_mention.return_value = "U987654321"  # mentioned user ID
        mock_send_message_as_bot.return_value = HttpResponse(status=204)
        
        with patch('matcher.views.ADMIN_SLACK_USER_ID', 'U123456789'):
            payload = {
                "event": {
                    "type": "message",
                    "user": "U123456789",  # admin user
                    "text": "<@U987654321> Hello from admin!"
                }
            }
            
            self.client.post(
                self.url,
                data=json.dumps(payload),
                content_type='application/json'
            )

            mock_get_mention.assert_called_once_with("<@U987654321> Hello from admin!")
            mock_send_message_as_bot.assert_called_once_with("<@U987654321> Hello from admin!")
    
    @patch('matcher.middleware.VerifySlackRequest.process_request')
    @patch('matcher.views.respond_to_user')
    @patch('matcher.views.get_mention')
    def test_non_admin_message_goes_to_respond_to_user(self, mock_get_mention, mock_respond_to_user, mock_verify):
        """Test that non-admin messages go to respond_to_user function"""
        mock_verify.return_value = None
        mock_get_mention.return_value = None  # no mention
        mock_respond_to_user.return_value = HttpResponse(status=204)
        
        with patch('meetups.settings.ADMIN_SLACK_USER_ID', 'U123456789'):
            payload = {
                "event": {
                    "type": "message",
                    "user": "U987654321",  # non-admin user
                    "text": "Hello bot!"
                }
            }
            
            response = self.client.post(
                self.url,
                data=json.dumps(payload),
                content_type='application/json'
            )

            mock_respond_to_user.assert_called_once_with(payload["event"])
    
    @patch('matcher.middleware.VerifySlackRequest.process_request')
    @patch('matcher.views.respond_to_user')
    @patch('matcher.views.get_mention')
    def test_admin_message_without_mention_goes_to_respond_to_user(self, mock_get_mention, mock_respond_to_user, mock_verify):
        """Test that admin messages without @-mentions go to respond_to_user"""
        mock_verify.return_value = None
        mock_get_mention.return_value = None  # no mention
        mock_respond_to_user.return_value = HttpResponse(status=204)
        
        with patch('meetups.settings.ADMIN_SLACK_USER_ID', 'U123456789'):
            payload = {
                "event": {
                    "type": "message",
                    "user": "U123456789",  # admin user
                    "text": "Just a regular message from admin"
                }
            }
            
            response = self.client.post(
                self.url,
                data=json.dumps(payload),
                content_type='application/json'
            )

            mock_respond_to_user.assert_called_once_with(payload["event"])


class RespondToUserTest(TestCase):
    
    @patch('matcher.views.prompt_intro_update')
    @patch('matcher.models.Person.objects.get')
    def test_update_intro_message_calls_prompt_intro_update(self, mock_person_get, mock_prompt_intro_update):
        """Test that 'update intro' message calls prompt_intro_update function"""
        from matcher.views import respond_to_user
        
        mock_prompt_intro_update.return_value = HttpResponse(status=204)
        
        # Mock a Person object
        mock_person = type('MockPerson', (), {})()
        mock_person.last_query = None
        mock_person_get.return_value = mock_person
        
        event = {
            "type": "message",
            "user": "U987654321",
            "text": "update intro"
        }
        
        response = respond_to_user(event)

        mock_prompt_intro_update.assert_called_once_with(event, mock_person)
        self.assertEqual(response.status_code, 204)

