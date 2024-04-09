import logging
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.contrib.auth.models import User
from core import utils

from apps.ifc_validation_models.models import ValidationRequest, ValidationTask, ValidationOutcome
from apps.ifc_validation_models.models import Model, ModelInstance, Company, AuthoringTool
from apps.ifc_validation_models.models import set_user_context

from .tasks import ifc_file_validation_task

logger = logging.getLogger(__name__)


class BaseAdmin(admin.ModelAdmin):

    def save_model(self, request, obj, form, change):

        # make sure we set user context when saving via the admin site
        if request.user.is_authenticated:
            logger.info(f"Authenticated, user.id = {request.user.id}")
            set_user_context(request.user)

        super().save_model(request, obj, form, change)


class ValidationRequestAdmin(BaseAdmin):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "public_id", "file_name", "file", "file_size_text"]}),
        ('Status Information',   {"classes": ("wide"), "fields": ["status", "status_reason", "progress"]}),
        ('Auditing Information', {"classes": ("wide"), "fields": [("created", "created_by"), ("updated", "updated_by")]})
    ]

    list_display = ["id", "public_id", "file_name", "file_size_text", "status", "progress", "duration_text", "created", "created_by", "updated", "updated_by"]
    readonly_fields = ["id", "public_id", "file_name", "file", "file_size_text", "duration", "duration_text", "created", "created_by", "updated", "updated_by"] 
    date_hierarchy = "created"

    list_filter = ["status", "created_by", "created", "updated"]
    search_fields = ('public_id', 'file_name', 'status', 'created_by__username', 'updated_by__username')

    actions = ["mark_as_failed_action", "restart_processing_action"]
    actions_on_top = True

    @admin.display(description="Duration (sec)")
    def duration_text(self, obj):

        duration = obj.duration
        if duration is not None:
            if isinstance(duration, timedelta): 
                duration = duration.total_seconds()
            return '{0:.{1}f}'.format(duration, 1)
        else:
            return None

    @admin.display(description="File Size")
    def file_size_text(self, obj):

        return utils.format_human_readable_file_size(obj.size)

    @admin.action(
        description="Mark selected Validation Requests as Failed",
        permissions=["change_status"]
    )
    def mark_as_failed_action(self, request, queryset):
        # TODO: move to middleware component?
        if request.user.is_authenticated:
            logger.info(f"Authenticated, user.id = {request.user.id}")
            set_user_context(request.user)
        queryset.update(status=ValidationRequest.Status.FAILED)

    @admin.action(
        description="Restart processing of selected Validation Requests",
        permissions=["change_status"]
    )
    def restart_processing_action(self, request, queryset):
        # TODO: move to middleware component?
        if request.user.is_authenticated:
            logger.info(f"Authenticated, user.id = {request.user.id}")
            set_user_context(request.user)

        # reset and re-submit tasks for background execution
        for obj in queryset:
            obj.mark_as_pending(reason='Resubmitted for processing via Django admin UI')
            if obj.model:
                obj.model.reset_status()
            ifc_file_validation_task.delay(obj.id, obj.file_name)
            logger.info(f"Task 'ifc_file_validation_task' re-submitted for id:{obj.id} file_name: {obj.file_name}")

    def has_change_status_permission(self, request):

        """
        Does the user have the 'change status' permission?
        """
        opts = self.opts
        codename = get_permission_codename("change_status", opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))


class ValidationTaskAdmin(BaseAdmin):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "public_id", "request", "type", "process_id", "process_cmd"]}),
        ('Status Information',   {"classes": ("wide"), "fields": ["status", "status_reason", "progress", "started", "ended", "duration"]}),
        ('Auditing Information', {"classes": ("wide"), "fields": ["created", "updated"]})
    ]

    list_display = ["id", "public_id", "request", "type", "status", "progress", "started", "ended", "duration_text", "created", "updated"]
    readonly_fields = ["id", "public_id", "request", "type", "process_id", "process_cmd", "started", "ended", "duration", "created", "updated"]
    date_hierarchy = "created"

    list_filter = ["status", "type", "status", "started", "ended", "created", "updated"]
    search_fields = ('request__file_name', 'public_id', 'status', 'type')

    @admin.display(description="Duration (sec)")
    def duration_text(self, obj):
        
        """
        Returns the duration of the Validation Task in shorter form (eg. 90.3)
        """
        duration = obj.duration        
        if duration is not None:
            if isinstance(duration, timedelta): 
                duration = duration.total_seconds()
            return '{0:.{1}f}'.format(duration, 1)
        else:
            return None


class ValidationOutcomeAdmin(BaseAdmin):

    list_display = ["id", "public_id", "file_name_text", "type_text", "instance_id", "feature", "feature_version", "outcome_code", "severity", "expected", "observed", "created", "updated"]
    readonly_fields = ["id", "public_id", "created", "updated"]

    list_filter = ['validation_task__type', 'severity', 'outcome_code']
    search_fields = ('validation_task__request__file_name', 'public_id', 'feature', 'feature_version', 'outcome_code', 'severity', 'expected', 'observed')

    @admin.display(description="File Name")
    def file_name_text(self, obj):
        return obj.validation_task.request.file_name

    @admin.display(description="Validation Type")
    def type_text(self, obj):
        return obj.validation_task.type


class ModelAdmin(BaseAdmin):

    list_display = ["id", "public_id", "file_name", "size_text", "date", "schema", "mvd", "nbr_of_elements", "nbr_of_geometries", "nbr_of_properties", "produced_by", "created", "updated"]
    readonly_fields = ["id", "public_id", "file", "file_name", "size", "size_text", "date", "schema", "mvd", "number_of_elements", "number_of_geometries", "number_of_properties", "produced_by", "created", "updated"]

    search_fields = ('file_name', 'public_id', 'schema', 'mvd', 'produced_by__name', 'produced_by__version')
    
    @admin.display(description="# of Elements")
    def nbr_of_elements(self, obj):
        
        return None if obj.number_of_elements is None else f'{obj.number_of_elements:,}'
    
    @admin.display(description="# of Geometries")
    def nbr_of_geometries(self, obj):
        
        return None if obj.number_of_geometries is None else f'{obj.number_of_geometries:,}'
    
    @admin.display(description="# of Properties")
    def nbr_of_properties(self, obj):
        
        return None if obj.number_of_properties is None else f'{obj.number_of_properties:,}'

    @admin.display(description="File Size")
    def size_text(self, obj):
        
        return utils.format_human_readable_file_size(obj.size)


class ModelInstanceAdmin(BaseAdmin):

    list_display = ["id", "public_id", "stepfile_id", "model", "ifc_type", "created", "updated"]

    search_fields = ('stepfile_id', 'public_id', 'model__file_name', 'ifc_type')


class CompanyAdmin(BaseAdmin):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "name" ]}),
        ('Auditing Information', {"classes": ("wide"), "fields": [("created", "updated")]})
    ]
    readonly_fields = ["id", "created", "updated"]
    list_filter = ["company", "created", "updated"]


class AuthoringToolAdmin(BaseAdmin):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "company", "name", "version"]}),
        ('Auditing Information', {"classes": ("wide"), "fields": [("created", "updated")]})
    ]
    list_display = ["id", "company", "name", "version", "created", "updated"]
    readonly_fields = ["id", "created", "updated"]
    list_filter = ["company", "created", "updated"]


class UserAdmin(BaseAdmin):

    list_display = ["id", "username", "email", "first_name", "last_name", "is_active", "is_staff", "is_superuser", "last_login", "date_joined"]
    list_filter = ['is_staff', 'is_superuser', 'is_active']

    search_fields = ('username', 'email', 'first_name', 'last_name', "last_login", "date_joined")

    actions = ["activate", "deactivate"]
    actions_on_top = True

    @admin.action(
        description="Activate selected user(s)"
    )
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(
        description="Deactivate selected user(s)"
    )
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


# register all admin classes
admin.site.register(ValidationRequest, ValidationRequestAdmin)
admin.site.register(ValidationTask, ValidationTaskAdmin)
admin.site.register(ValidationOutcome, ValidationOutcomeAdmin)
admin.site.register(Model, ModelAdmin)
admin.site.register(ModelInstance, ModelInstanceAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(AuthoringTool, AuthoringToolAdmin)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
