from django.contrib import admin
from django.apps import apps

all_models = apps.get_models()

# register all models of all apps
print("Loading all models into Django Admin...")
for model in all_models:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass