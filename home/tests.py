from django.test import Client, TestCase
from django.urls import resolve, reverse
from . import views


class VelvetEmberTests(TestCase):
    def add(self, dish="ravioli", **extra):
        return self.client.post(reverse("menu"), {
            "action": "add", "dish_id": dish, **extra,
        }, follow=True)

    def test_existing_routes(self):
        for name, path in {"home": "/", "base": "/base/", "about": "/about/",
                "services": "/services/", "menu": "/menu/", "contact": "/contact/"}.items():
            self.assertEqual(reverse(name), path)
            self.assertEqual(resolve(path).url_name, name)

    def test_admin_route(self):
        self.assertEqual(resolve("/admin/").url_name, "index")

    def test_pages_render(self):
        for name in ("home", "about", "services", "menu", "contact", "bag"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, "Velvet Ember")

    def test_legacy_base_alias(self):
        self.assertRedirects(self.client.get("/base/"), "/")

    def test_local_photography(self):
        response = self.client.get("/")
        self.assertContains(response, "/static/images/ravioli.webp")
        self.assertNotContains(response, "unsplash.com")

    def test_explicit_demo_labels(self):
        for path in ("/", "/menu/", "/bag/", "/contact/"):
            self.assertContains(self.client.get(path), "No orders, deliveries, payments, or emails are processed.")

    def test_fresh_home_composition(self):
        response = self.client.get('/')
        self.assertContains(response, '/static/images/hero-approved.webp')
        self.assertContains(response, 'class="home-page"')
        self.assertNotContains(response, 'Sample menu &amp; prices · No real payments')
        self.assertNotContains(response, 'class="header-caption"')
        self.assertNotContains(response, 'class="demo-label"')

    def test_category_filter(self):
        response = self.client.get("/menu/", {"category": "desserts"})
        self.assertContains(response, 'id="dish-fondant"')
        self.assertNotContains(response, 'id="dish-ravioli"')

    def test_unknown_category_falls_back(self):
        response = self.client.get("/menu/", {"category": "javascript:alert(1)"})
        self.assertContains(response, 'id="dish-ravioli"')

    def test_search(self):
        response = self.client.get("/menu/", {"q": "MUSHROOM"})
        self.assertContains(response, 'id="dish-crostini"')
        self.assertNotContains(response, 'id="dish-chicken"')

    def test_empty_search_results(self):
        self.assertContains(self.client.get("/menu/", {"q": "missing-dish"}), "No plates found.")

    def test_search_escaping(self):
        attack = '"><script>alert(1)</script>'
        response = self.client.get("/menu/", {"q": attack})
        self.assertNotContains(response, attack)
        self.assertContains(response, "&lt;script&gt;")

    def test_get_does_not_add(self):
        self.client.get("/menu/", {"action": "add", "dish_id": "ravioli"})
        self.assertEqual(views.get_cart(self.client.get("/bag/").wsgi_request), {})

    def test_add_and_quantity_count(self):
        self.add(); self.add()
        self.assertEqual(self.client.session[views.CART_KEY], {"ravioli": 2})
        self.assertContains(self.client.get("/bag/"), "$38.00")

    def test_unknown_dish_rejected(self):
        self.add("not-a-dish")
        self.assertEqual(self.client.session.get(views.CART_KEY, {}), {})

    def test_price_comes_from_server(self):
        self.add(price="0.01", quantity="9999")
        self.assertContains(self.client.get("/bag/"), "$19.00")
        self.assertEqual(self.client.session[views.CART_KEY]["ravioli"], 1)

    def test_redirect_is_internal(self):
        response = self.client.post("/menu/", {"action": "add", "dish_id": "ravioli", "return_to": "https://evil.example"})
        self.assertTrue(response["Location"].startswith("/menu/"))

    def test_home_add_returns_home(self):
        response = self.client.post("/menu/", {"action": "add", "dish_id": "ravioli", "return_to": "home"})
        self.assertEqual(response["Location"], "/")

    def test_background_add_returns_json_and_persists_bag(self):
        response = self.client.post('/menu/', {'action': 'add', 'dish_id': 'ravioli'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['bag_count'], 1)
        self.assertTrue(response.json()['success'])
        self.assertNotIn('Location', response)
        self.assertEqual(self.client.session[views.CART_KEY], {'ravioli': 1})
        self.assertNotIn(views.NOTICE_KEY, self.client.session)
        self.assertContains(self.client.get('/bag/'), '$19.00')

    def test_background_add_rejects_unknown_dish(self):
        response = self.client.post('/menu/', {'action': 'add', 'dish_id': 'unknown'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertEqual(response.json()['bag_count'], 0)

    def test_background_add_enforces_limit(self):
        session = self.client.session
        session[views.CART_KEY] = {'ravioli': 99}
        session.save()
        response = self.client.post('/menu/', {'action': 'add', 'dish_id': 'ravioli'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['bag_count'], 99)

    def test_background_add_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        denied = client.post('/menu/', {'action': 'add', 'dish_id': 'ravioli'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(denied.status_code, 403)
        client.get('/')
        accepted = client.post('/menu/', {'action': 'add', 'dish_id': 'ravioli', 'csrfmiddlewaretoken': client.cookies['csrftoken'].value}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()['bag_count'], 1)

    def test_menu_is_html_not_python(self):
        response = self.client.get('/menu/')
        self.assertContains(response, 'id="menu-grid"')
        self.assertNotContains(response, 'def menu(request)')
        self.assertContains(response, 'id="bag-count"')
        self.assertNotContains(response, 'Demo bag (<span')

    def test_quantity_update_and_subtotal(self):
        self.add(); self.add("fondant")
        self.client.post("/bag/", {"action": "update", "dish_id": "ravioli", "quantity": "3"})
        self.assertContains(self.client.get("/bag/"), "$66.00")

    def test_invalid_quantities(self):
        self.add()
        for quantity in ("-1", "100", "NaN", "1.5", "", "999999999999"):
            self.client.post("/bag/", {"action": "update", "dish_id": "ravioli", "quantity": quantity})
            self.assertEqual(self.client.session[views.CART_KEY]["ravioli"], 1)

    def test_quantity_limit(self):
        self.add()
        self.client.post("/bag/", {"action": "update", "dish_id": "ravioli", "quantity": "99"})
        self.add()
        self.assertEqual(self.client.session[views.CART_KEY]["ravioli"], 99)

    def test_zero_removes(self):
        self.add()
        self.client.post("/bag/", {"action": "update", "dish_id": "ravioli", "quantity": "0"})
        self.assertEqual(self.client.session[views.CART_KEY], {})

    def test_remove_and_clear(self):
        self.add(); self.add("chicken")
        self.client.post("/bag/", {"action": "remove", "dish_id": "ravioli"})
        self.assertEqual(self.client.session[views.CART_KEY], {"chicken": 1})
        self.client.post("/bag/", {"action": "clear"})
        self.assertEqual(self.client.session[views.CART_KEY], {})

    def test_empty_preview(self):
        response = self.client.post("/bag/", {"action": "preview"}, follow=True)
        self.assertNotContains(response, "DEMO PREVIEW READY")

    def test_preview_is_demo_only(self):
        self.add()
        response = self.client.post("/bag/", {"action": "preview"}, follow=True)
        self.assertContains(response, "DEMO PREVIEW READY")
        self.assertContains(response, "no order was placed")
        self.assertEqual(self.client.session[views.CART_KEY], {"ravioli": 1})

    def test_cart_change_invalidates_preview(self):
        self.add(); self.client.post("/bag/", {"action": "preview"})
        self.add("fondant")
        self.assertNotContains(self.client.get("/bag/"), "DEMO PREVIEW READY")

    def test_corrupt_session_cart_is_sanitized(self):
        session = self.client.session
        session[views.CART_KEY] = {"ravioli": True, "chicken": -1, "fondant": "99", "unknown": 1}
        session.save()
        self.assertContains(self.client.get("/bag/"), "$0.00")

    def test_contact_validation(self):
        response = self.client.post("/contact/", {"name": "", "email": "bad", "message": "short"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Please check the highlighted fields.", status_code=400)

    def test_contact_success_does_not_store_personal_data(self):
        data = {"name": "Sample Guest", "email": "guest@example.com", "topic": "menu", "message": "A sample message about the menu."}
        response = self.client.post("/contact/", data, follow=True)
        self.assertContains(response, "Nothing was sent or saved.")
        stored = str(dict(self.client.session))
        self.assertNotIn(data["email"], stored)
        self.assertNotIn(data["message"], stored)

    def test_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        for path in ("/menu/", "/bag/", "/contact/"):
            self.assertEqual(client.post(path, {"action": "add", "dish_id": "ravioli"}).status_code, 403)

    def test_csrf_valid_post(self):
        import re
        client = Client(enforce_csrf_checks=True)
        response = client.get("/")
        token = re.search('name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode()).group(1)
        response = client.post("/menu/", {"action": "add", "dish_id": "ravioli", "csrfmiddlewaretoken": token})
        self.assertEqual(response.status_code, 302)

    def test_read_only_routes_reject_post(self):
        for path in ("/", "/about/", "/services/", "/base/"):
            self.assertEqual(self.client.post(path).status_code, 405)

    def test_head_requests(self):
        for path in ("/", "/menu/", "/about/", "/services/", "/contact/", "/bag/"):
            response = self.client.head(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b"")
