from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import set_user_context, Company, AuthoringTool, Model, ValidationRequest

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
