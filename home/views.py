"""Velvet Ember: a restaurant UI demo. No payments, email, or real orders."""
from django import forms
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_safe


CATEGORIES = (
    ("all", "All plates"),
    ("starters", "Small beginnings"),
    ("mains", "Mains"),
    ("desserts", "Sweet endings"),
)

# Illustrative dishes, prices, and images for this demonstration project.
MENU = (
    {"id": "ravioli", "name": "Brown Butter Ravioli", "category": "mains",
     "description": "Handmade-style ravioli, brown butter, crisp sage and Parmesan.",
     "price_cents": 1900, "image": "images/ravioli.webp",
     "allergens": "Sample ingredients include wheat, egg and milk."},
    {"id": "chicken", "name": "Herb-Roasted Chicken", "category": "mains",
     "description": "Golden roast potatoes, seasonal greens and a rich herb jus.",
     "price_cents": 2200, "image": "images/chicken.webp",
     "allergens": "Sample preparation may include milk and celery."},
    {"id": "fondant", "name": "Dark Chocolate Fondant", "category": "desserts",
     "description": "A molten chocolate centre, fresh berries and a little indulgence.",
     "price_cents": 900, "image": "images/fondant.webp",
     "allergens": "Sample ingredients include wheat, egg and milk."},
    {"id": "crostini", "name": "Wild Mushroom Crostini", "category": "starters",
     "description": "Toasted sourdough, whipped ricotta, woodland mushrooms and thyme.",
     "price_cents": 1100, "image": "images/crostini.webp",
     "allergens": "Sample ingredients include wheat and milk."},
)
CATALOG = {dish["id"]: dish for dish in MENU}
CART_KEY = "velvet_ember_cart_v1"
NOTICE_KEY = "velvet_ember_notice_v1"
PREVIEW_KEY = "velvet_ember_preview_v1"


def money(cents):
    return f"${cents // 100:,}.{cents % 100:02d}"


def get_cart(request):
    raw = request.session.get(CART_KEY, {})
    if not isinstance(raw, dict):
        return {}
    return {key: quantity for key, quantity in raw.items()
            if key in CATALOG and type(quantity) is int and 1 <= quantity <= 99}


def save_cart(request, cart):
    request.session[CART_KEY] = cart
    request.session.pop(PREVIEW_KEY, None)


def context(request, active, **extra):
    cart = get_cart(request)
    return {
        "active": active,
        "bag_count": sum(cart.values()),
        "categories": CATEGORIES,
        "notice": request.session.pop(NOTICE_KEY, ""),
        **extra,
    }


def dish_data(dish):
    return {**dish, "price": money(dish["price_cents"])}


class DemoContactForm(forms.Form):
    name = forms.CharField(max_length=80, label="Your name",
                           widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Alex Taylor"}))
    email = forms.EmailField(max_length=254, label="Email address",
                             widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "alex@example.com"}))
    topic = forms.ChoiceField(choices=(
        ("menu", "A question about the menu"),
        ("experience", "Feedback on the demo"),
        ("other", "Something else"),
    ))
    message = forms.CharField(min_length=10, max_length=2000,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Tell us what's on your mind…"}))


@require_safe
@ensure_csrf_cookie
def home(request):
    return render(request, "home.html", context(request, "home",
        featured=[dish_data(dish) for dish in MENU[:3]]))


@require_safe
def base(request):
    # Preserve the legacy /base/ route as a useful homepage alias.
    return redirect("home")


@require_safe
def about(request):
    return render(request, "about.html", context(request, "about"))


@require_safe
def services(request):
    return render(request, "services.html", context(request, "services"))


@require_http_methods(["GET", "POST", "HEAD"])
@csrf_protect
def menu(request):
    category = request.GET.get("category", "all")
    if category not in dict(CATEGORIES):
        category = "all"
    query = request.GET.get("q", "").strip()[:100]
    if request.method == "POST":
        dish_id = request.POST.get("dish_id", "")
        success = False
        status = 200
        if request.POST.get("action") != "add" or dish_id not in CATALOG:
            message = "That dish is unavailable. Choose another dish."
            status = 400
        else:
            cart = get_cart(request)
            if cart.get(dish_id, 0) >= 99:
                message = "Demo limit: 99 of each dish."
                status = 400
            else:
                cart[dish_id] = cart.get(dish_id, 0) + 1
                save_cart(request, cart)
                message = CATALOG[dish_id]["name"] + " added to your bag."
                success = True
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": success, "message": message,
                "bag_count": sum(get_cart(request).values())}, status=status)
        request.session[NOTICE_KEY] = message
        if request.POST.get("return_to") == "home":
            return redirect(reverse("home"))
        from urllib.parse import urlencode
        return redirect(reverse("menu") + "?" + urlencode({"category": category, "q": query}) + "#menu-grid")
    dishes = [dish_data(dish) for dish in MENU
        if (category == "all" or dish["category"] == category)
        and query.casefold() in (dish["name"] + " " + dish["description"]).casefold()]
    return render(request, "menu.html", context(request, "menu",
        dishes=dishes, selected_category=category, query=query))


@require_http_methods(["GET", "POST", "HEAD"])
@csrf_protect
def bag(request):
    cart = get_cart(request)
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action in ("update", "remove"):
            dish_id = request.POST.get("dish_id", "")
            try:
                quantity = 0 if action == "remove" else int(request.POST.get("quantity", ""))
                if dish_id not in CATALOG or not 0 <= quantity <= 99:
                    raise ValueError
                if quantity:
                    cart[dish_id] = quantity
                else:
                    cart.pop(dish_id, None)
                save_cart(request, cart)
                request.session[NOTICE_KEY] = "Your demo bag has been updated."
            except (ValueError, TypeError):
                request.session[NOTICE_KEY] = "Choose a whole quantity from 0 to 99."
        elif action == "clear":
            save_cart(request, {})
            request.session[NOTICE_KEY] = "Your demo bag is now empty."
        elif action == "preview":
            if cart:
                request.session[PREVIEW_KEY] = True
            else:
                request.session[NOTICE_KEY] = "Add a dish before previewing a demo order."
        else:
            request.session[NOTICE_KEY] = "That action is unavailable."
        return redirect("bag")
    lines = [{**dish_data(CATALOG[key]), "quantity": quantity,
              "line_total": money(CATALOG[key]["price_cents"] * quantity)}
             for key, quantity in cart.items()]
    subtotal = sum(CATALOG[key]["price_cents"] * quantity for key, quantity in cart.items())
    return render(request, "bag.html", context(request, "bag",
        lines=lines, subtotal=money(subtotal), preview=bool(lines) and request.session.get(PREVIEW_KEY, False)))


@require_http_methods(["GET", "POST", "HEAD"])
@csrf_protect
def contact(request):
    form = DemoContactForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        # Validate only. Never email, log, or store the submitted personal details.
        request.session[NOTICE_KEY] = "Demo form validated. Nothing was sent or saved."
        return redirect(reverse("contact") + "#contact-form")
    return render(request, "contact.html", context(request, "contact", form=form),
                  status=400 if request.method == "POST" else 200)
