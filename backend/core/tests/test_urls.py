from django.test import SimpleTestCase


class AdminURLTests(SimpleTestCase):
    def test_admin_without_slash_redirects_and_preserves_query(self):
        response = self.client.get('/admin?next=/admin/auth/user/')
        self.assertRedirects(response, '/admin/?next=/admin/auth/user/',
                             status_code=301, fetch_redirect_response=False)

    def test_admin_with_slash_reaches_admin_login(self):
        response = self.client.get('/admin/')
        self.assertRedirects(response, '/admin/login/?next=/admin/',
                             fetch_redirect_response=False)


class DocumentationURLTests(SimpleTestCase):
    def test_documentation_without_slash_redirects_and_preserves_query(self):
        for resource in ('schema', 'swagger-ui', 'redoc'):
            with self.subTest(resource=resource):
                response = self.client.get(f'/api/v1/{resource}?lang=en')
                self.assertRedirects(response, f'/api/v1/{resource}/?lang=en',
                                     status_code=301, fetch_redirect_response=False)
