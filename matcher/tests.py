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


class SendMsgTest(TestCase):
    
    @patch('matcher.tasks.client')
    def test_send_msg_with_text_kwargs_no_payload(self, mock_client):
        """Test send_msg with text in kwargs and no payload"""
        from matcher.tasks import send_msg
        mock_client.chat_postMessage.return_value = {"ok": True}
        
        channel_id = "C123456789"
        result = send_msg(channel_id, text="Hello world!")
        
        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel_id, 
            as_user=True, 
            text="Hello world!"
        )
        mock_client.call_api.assert_not_called()
        self.assertEqual(result, f"{channel_id}: \"Hello world!\"")
    
    @patch('matcher.tasks.client')
    def test_send_msg_with_blocks_kwargs_no_payload(self, mock_client):
        """Test send_msg with blocks in kwargs and no payload"""
        from matcher.tasks import send_msg
        
        mock_client.chat_postMessage.return_value = {"ok": True}
        test_blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test block"}}]
        
        channel_id = "C123456789"
        result = send_msg(channel_id, blocks=test_blocks)
        
        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel_id, 
            as_user=True, 
            blocks=test_blocks
        )
        mock_client.call_api.assert_not_called()
        self.assertEqual(result, f"{channel_id}: \"{test_blocks}\"")
    
    @patch('matcher.tasks.client')
    @patch('matcher.tasks.messages.format_selected_block')
    def test_send_msg_with_payload_and_text(self, mock_format_selected_block, mock_client):
        """Test send_msg with payload and text kwargs"""
        from matcher.tasks import send_msg
        
        mock_client.chat_postMessage.return_value = {"ok": True}
        mock_client.api_call.return_value = {"ok": True}
        mock_format_selected_block.return_value = [{"type": "section", "text": "updated"}]
        
        payload = {
            "actions": [{"value": "selected_option"}],
            "message": {
                "ts": "1234567890.123456",
                "blocks": [{"type": "section", "text": "original"}]
            },
            "channel": {"id": "C987654321"}
        }
        
        channel_id = "C123456789"
        result = send_msg(channel_id, payload=payload, text="Updated message")
        
        # Verify the original message was updated
        mock_client.api_call.assert_called_once_with("chat.update", json={
            "channel": "C987654321",
            "ts": "1234567890.123456",
            "blocks": [{"type": "section", "text": "updated"}]
        })
        
        # Verify new message was posted
        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel_id, 
            as_user=True, 
            text="Updated message"
        )
        
        self.assertEqual(result, f"{channel_id}: \"Updated message\"")
    
    @patch('matcher.tasks.client')
    def test_send_msg_with_payload_missing_message(self, mock_client):
        """Test send_msg with payload that has missing message"""
        from matcher.tasks import send_msg
        
        mock_client.chat_postMessage.return_value = {"ok": True}
        
        payload = {
            "channel": {"id": "C987654321"}
        }
        
        channel_id = "C123456789"
        send_msg(channel_id, payload=payload, text="Test message")
        
        # Should not call api_call when actions are missing
        mock_client.api_call.assert_not_called()
        
        # Should still post the new message
        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel_id, 
            as_user=True, 
            text="Test message"
        )
    
    @patch('matcher.tasks.client')
    @patch('matcher.tasks.logger')
    def test_send_msg_payload_update_failure(self, mock_logger, mock_client):
        """Test send_msg when payload update fails but message posting succeeds"""
        from matcher.tasks import send_msg
        
        mock_client.api_call.side_effect = Exception("Update failed")
        mock_client.chat_postMessage.return_value = {"ok": True}
        
        payload = {
            "actions": [{"value": "selected_option"}],
            "message": {
                "ts": "1234567890.123456",
                "blocks": [{"type": "section", "text": "original"}]
            },
            "channel": {"id": "C987654321"}
        }
        
        channel_id = "C123456789"
        result = send_msg(channel_id, payload=payload, text="Test message")
        
        # Should still post the new message
        mock_client.chat_postMessage.assert_called_once_with(
            channel=channel_id, 
            as_user=True, 
            text="Test message"
        )
        
        self.assertEqual(result, f"{channel_id}: \"Test message\"")


class AdminTest(TestCase):
    
    @patch('matcher.admin.Match.objects.filter')
    @patch('matcher.admin.Person.objects')
    @patch('matcher.admin.random.choice')
    def test_odd_number_excludes_participant_successfully(self, mock_random_choice, mock_person_objects, mock_match_filter):
        """Test that function successfully excludes someone when there's an odd number of participants"""
        from matcher.admin import get_round_participants
        
        # Create mock round object
        mock_round = type('MockRound', (), {})()
        mock_round.pool = type('MockPool', (), {'name': 'test-pool'})()
        
        # Create person objects
        mock_person1 = type('MockPerson', (), {'id': 1, 'user_name': 'user1', 'can_be_excluded': True})()
        mock_person2 = type('MockPerson', (), {'id': 2, 'user_name': 'user2', 'can_be_excluded': False})()
        mock_person3 = type('MockPerson', (), {'id': 3, 'user_name': 'user3', 'can_be_excluded': True})()
        
        # Mock the queryset for excludable people (people who can be excluded)
        person_to_exclude = mock_person1
        excludable_people = [person_to_exclude, mock_person3]
        
        # Mock the final queryset after exclusion (even number)
        people_to_match__minus_excluded = type('MockQuerySet', (), {
            '__len__': lambda self: 2  # even number after exclusion
        })()
        
        # Mock the queryset for initial people
        mock_query_set = type('MockQuerySet', (), {
            '__len__': lambda self: 3,  # odd number
            'filter': lambda self, **kwargs: excludable_people if kwargs.get('can_be_excluded') else self,
            'exclude': lambda self, **kwargs: people_to_match__minus_excluded,
            'order_by': lambda self, field: self
        })()
        
        # Set up the mock chain
        mock_match_filter.return_value.count.return_value = 0
        mock_person_objects.filter.return_value = mock_query_set
        mock_random_choice.return_value = person_to_exclude  # person to exclude
        
        # Call the function
        result = get_round_participants(mock_round)
        
        # Verify the result is the final queryset with even number
        self.assertEqual(result, people_to_match__minus_excluded)
        self.assertEqual(len(result), 2)

    @patch('matcher.admin.Match.objects.filter')
    @patch('matcher.admin.Person.objects')
    @patch('matcher.admin.logger')
    def test_odd_number_no_excludable_raises_exception(self, mock_logger, mock_person_objects, mock_match_filter):
        """Test that function raises exception when there's an odd number but no one can be excluded"""
        from matcher.admin import get_round_participants
        
        # Create mock round object
        mock_round = type('MockRound', (), {})()
        mock_round.pool = type('MockPool', (), {'name': 'test-pool'})()
        
        # Mock the queryset for initial people
        mock_query_set = type('MockQuerySet', (), {
            '__len__': lambda self: 3,  # odd number
            'filter': lambda self, **kwargs: [] if kwargs.get('can_be_excluded') else self,
            'order_by': lambda self, field: self
        })()
        
        # Set up the mock chain
        mock_match_filter.return_value.count.return_value = 0
        mock_person_objects.filter.return_value = mock_query_set
        
        # Call the function and expect an exception
        with self.assertRaises(Exception) as context:
            get_round_participants(mock_round)
        
        # Verify the exception message
        self.assertIn("There are an odd number of people to match this round", str(context.exception))
        self.assertIn("no one in this pool is marked as available and as a person who can be excluded", str(context.exception))

    def test_person_can_be_excluded_default_true(self):
        """Test that Person model has can_be_excluded=True as default value"""
        from matcher.models import Person
        
        # Create a person without specifying can_be_excluded
        person = Person(
            user_id="U123456789",
            user_name="testuser",
            full_name="Test User"
        )
        person.save()
        
        # Verify that can_be_excluded defaults to True
        self.assertTrue(person.can_be_excluded)
        
        # Clean up
        person.delete()


class CreateRoundTest(TestCase):
    
    @patch('matcher.models.ask_availability')
    def test_ask_availability_called_on_round_save(self, mock_ask_availability):
        """Test that ask_availability is called when a new round is saved"""
        from matcher.models import Pool, Round
        
        # Create a pool for the round
        pool = Pool.objects.create(
            name="Test Pool",
            channel_id="C1234567890",
            channel_name="#test-channel"
        )
        
        # Create a new round, which should trigger ask_availability
        round_instance = Round(pool=pool)
        round_instance.save()
        
        # Verify ask_availability was called with the round instance
        mock_ask_availability.assert_called_once_with(round_instance)

    @patch('matcher.views.ask_if_met')
    @patch('matcher.views.send_msg')
    def test_ask_if_met_called_on_availability_update(self, mock_send_msg, mock_ask_if_met):
        """Test that ask_if_met is called when updating availability"""

        from matcher.models import Pool, Person, PoolMembership
        from unittest.mock import MagicMock
        from matcher.views import update_availability

        # Create a pool and person
        pool = Pool.objects.create(
            name="Test Pool",
            channel_id="C1234567890",
            channel_name="#test-channel"
        )
        person = Person.objects.create(
            user_id="U1234567890",
            user_name="testuser",
            full_name="Test User",
            casual_name="Test"
        )
        PoolMembership.objects.create(person=person, pool=pool)
        
        # Mock the Celery chain
        mock_chain = MagicMock()
        mock_send_msg.s.return_value = mock_chain
        mock_chain.__or__ = MagicMock(return_value=mock_chain)
        mock_chain.delay = MagicMock()
        
        # Create payload and action for the update_availability function
        payload = {"user": {"id": "U1234567890"}}
        action = {"value": "yes"}
        
        # Call update_availability
        update_availability(payload, action, pool.id)
        
        # Verify ask_if_met was included in the chain
        mock_ask_if_met.s.assert_called_once_with("U1234567890", pool.pk)
