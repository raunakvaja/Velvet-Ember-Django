from django.contrib import admin
from django.urls import path
from home import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("base/", views.base, name="base"),
    path("about/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("menu/", views.menu, name="menu"),
    path("contact/", views.contact, name="contact"),
    path("bag/", views.bag, name="bag"),
]
