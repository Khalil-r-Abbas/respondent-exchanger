from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User


class DevelopmentAutoLoginTests(TestCase):
    @override_settings(DEBUG=True, DEV_AUTO_LOGIN=True)
    def test_builder_can_use_dummy_account_when_explicitly_enabled(self):
        response = self.client.get(reverse('forms_app:questionnaire_new'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session.get('_auth_user_id'))
        self.assertTrue(User.objects.filter(username='demo_builder', email_verified=True).exists())

    @override_settings(DEBUG=True, DEV_AUTO_LOGIN=False)
    def test_builder_still_requires_login_by_default(self):
        response = self.client.get(reverse('forms_app:questionnaire_new'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
