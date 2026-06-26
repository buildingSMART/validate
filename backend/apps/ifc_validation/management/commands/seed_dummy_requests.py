from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import set_user_context, Company, AuthoringTool, Model, ValidationRequest, UserAdditionalInfo

class Command(BaseCommand):
    help = "Seed 51 dummy ValidationRequest rows for pagination tests"

    def handle(self, *args, **opts):
        user, _ = User.objects.get_or_create(
            username="root",
            defaults={"is_staff": True, "is_superuser": True}
        )
        user.set_password("root")
        user.save()
        set_user_context(user)

        # Pre-provision the local DEV user that get_current_user() lazy-creates,
        # with is_vendor_self_declared set so the SelfDeclarationDialog stays closed
        # in e2e runs (an open MUI dialog hides the rest of the app from
        # aria-role queries).
        dev_user, _ = User.objects.get_or_create(
            username="development",
            defaults={
                "email": "noreply@localhost",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Dev",
                "last_name": "User",
            },
        )
        UserAdditionalInfo.objects.update_or_create(
            user=dev_user,
            defaults={"is_vendor_self_declared": False},
        )

        company, _ = Company.objects.get_or_create(name="DummyCorp")
        tool, _ = AuthoringTool.objects.get_or_create(company=company, name="DummyTool", version="1.0")

        payload = b"ISO-10303-21;\nEND-ISO-10303-21;"  

        for i in range(51):
            file_name = f"dummy_{i:03d}.ifc"

            m = Model(
                produced_by=tool,
                file_name=file_name,
                file=f"uploads/{file_name}",  
                size=len(payload),
                uploaded_by=user,
                schema="IFC4X3_ADD2",
                license=Model.License.UNKNOWN,
            )
            m.save()

            vr = ValidationRequest(
                file_name=file_name,
                size=len(payload),
                status=ValidationRequest.Status.PENDING,
                model=m,
                channel=ValidationRequest.Channel.API,
            )
            vr.file.save(file_name, ContentFile(payload), save=False)
            vr.save()
