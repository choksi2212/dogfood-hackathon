from django.apps import AppConfig


class AbuseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.abuse"
    label = "abuse"
    verbose_name = "Abuse"
