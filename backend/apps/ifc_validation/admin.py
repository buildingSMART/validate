import logging
from datetime import timedelta

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_permission_codename
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ngettext
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


class NonAdminAddable(admin.ModelAdmin):

    def has_add_permission(self, request):

        # disable add via Admin ('+ Add' button)
        return False


class ValidationRequestAdmin(BaseAdmin, NonAdminAddable):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "public_id", "file_name", "file", "file_size_text", "deleted"]}),
        ('Status Information',   {"classes": ("wide"), "fields": ["status", "status_reason", "progress"]}),
        ('Auditing Information', {"classes": ("wide"), "fields": [("created", "created_by"), ("updated", "updated_by")]})
    ]

    list_display = ["id", "public_id", "file_name", "file_size_text", "status", "progress", "duration_text", "created", "created_by", "updated", "updated_by", "is_deleted"]
    readonly_fields = ["id", "public_id", "deleted", "file_name", "file", "file_size_text", "duration", "duration_text", "created", "created_by", "updated", "updated_by"] 
    date_hierarchy = "created"

    list_filter = ["status", "deleted", "created_by", "created", "updated"]
    search_fields = ('file_name', 'status', 'created_by__username', 'updated_by__username')

    actions = ["soft_delete_action", "soft_restore_action", "mark_as_failed_action", "restart_processing_action", "hard_delete_action"]
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

    @admin.display(description="Deleted ?")
    def is_deleted(self, obj):

        return ("Yes" if obj.deleted else "No")

    @admin.display(description="File Size", ordering='size')
    def file_size_text(self, obj):

        return utils.format_human_readable_file_size(obj.size)

    @admin.action(
        description="Permanently delete selected Validation Requests",
        permissions=["hard_delete"]
    )
    def hard_delete_action(self, request, queryset):
        
        if 'apply' in request.POST:

            for obj in queryset:
                obj.hard_delete()

            self.message_user(
                request,
                ngettext(
                    "%d Validation Request was successfully deleted.",
                    "%d Validation Requests were successfully deleted.",
                    len(queryset),
                )
                % len(queryset),
                messages.SUCCESS,
            )
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/hard_delete_intermediate.html', context={'val_requests': queryset, 'entity_name': 'Validation Request(s)'})
    
    @admin.action(
        description="Soft-delete selected Validation Requests",
        permissions=["soft_delete"]
    )
    def soft_delete_action(self, request, queryset):
        # TODO: move to middleware component?
        if request.user.is_authenticated:
            logger.info(f"Authenticated, user.id = {request.user.id}")
            set_user_context(request.user)

        for obj in queryset:
            obj.soft_delete()

        self.message_user(
            request,
            ngettext(
                "%d Validation Request was successfully marked as deleted.",
                "%d Validation Requests were successfully marked as deleted.",
                len(queryset),
            )
            % len(queryset),
            messages.SUCCESS,
        )

    @admin.action(
        description="Soft-restore selected Validation Requests",
        permissions=["soft_restore"]
    )
    def soft_restore_action(self, request, queryset):
        # TODO: move to middleware component?
        if request.user.is_authenticated:
            logger.info(f"Authenticated, user.id = {request.user.id}")
            set_user_context(request.user)

        for obj in queryset:
            obj.undo_delete()

        self.message_user(
            request,
            ngettext(
                "%d Validation Request was successfully marked as restored.",
                "%d Validation Requests were successfully marked as restored.",
                len(queryset),
            )
            % len(queryset),
            messages.SUCCESS,
        )

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

    def get_actions(self, request):
    
        actions = super().get_actions(request)

        # remove default 'delete' action from list
        if 'delete_selected' in actions:
            del actions['delete_selected']
    
        return actions
    
    def has_change_status_permission(self, request):

        opts = self.opts
        codename = get_permission_codename("change_status", opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))
    
    def has_hard_delete_permission(self, request):

        opts = self.opts
        codename = get_permission_codename("delete", opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def has_soft_delete_permission(self, request):

        return self.has_hard_delete_permission(request)

    def has_soft_restore_permission(self, request):

        return self.has_soft_delete_permission(request)


class ValidationTaskAdmin(BaseAdmin, NonAdminAddable):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "public_id", "request", "type", "process_id", "process_cmd"]}),
        ('Status Information',   {"classes": ("wide"), "fields": ["status", "status_reason", "progress", "started", "ended", "duration"]}),
        ('Auditing Information', {"classes": ("wide"), "fields": ["created", "updated"]})
    ]

    list_display = ["id", "public_id", "request", "type", "status", "progress", "started", "ended", "duration_text", "created", "updated"]
    readonly_fields = ["id", "public_id", "request", "type", "process_id", "process_cmd", "started", "ended", "duration", "created", "updated"]
    date_hierarchy = "created"

    list_filter = ["status", "type", "status", "started", "ended", "created", "updated"]
    search_fields = ('request__file_name', 'status', 'type')

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


class ValidationOutcomeAdmin(BaseAdmin, NonAdminAddable):

    list_display = ["id", "public_id", "file_name_text", "type_text", "instance_id", "feature", "feature_version", "outcome_code", "severity", "expected", "observed", "created", "updated"]
    readonly_fields = ["id", "public_id", "created", "updated"]

    list_filter = ['validation_task__type', 'severity', 'outcome_code']
    search_fields = ('validation_task__request__file_name', 'feature', 'feature_version', 'outcome_code', 'severity', 'expected', 'observed')

    @admin.display(description="File Name")
    def file_name_text(self, obj):
        return obj.validation_task.request.file_name

    @admin.display(description="Validation Type")
    def type_text(self, obj):
        return obj.validation_task.type


class ModelAdmin(BaseAdmin, NonAdminAddable):

    list_display = ["id", "public_id", "file_name", "size_text", "date", "schema", "mvd", "nbr_of_elements", "nbr_of_geometries", "nbr_of_properties", "produced_by", "created", "updated"]
    readonly_fields = ["id", "public_id", "file", "file_name", "size", "size_text", "date", "schema", "mvd", "number_of_elements", "number_of_geometries", "number_of_properties", "produced_by", "created", "updated"]

    search_fields = ('file_name', 'schema', 'mvd', 'produced_by__name', 'produced_by__version')
    
    @admin.display(description="# of Elements")
    def nbr_of_elements(self, obj):
        
        return None if obj.number_of_elements is None else f'{obj.number_of_elements:,}'
    
    @admin.display(description="# of Geometries")
    def nbr_of_geometries(self, obj):
        
        return None if obj.number_of_geometries is None else f'{obj.number_of_geometries:,}'
    
    @admin.display(description="# of Properties")
    def nbr_of_properties(self, obj):
        
        return None if obj.number_of_properties is None else f'{obj.number_of_properties:,}'

    @admin.display(description="File Size", ordering='size')
    def size_text(self, obj):
        
        return utils.format_human_readable_file_size(obj.size)


class ModelInstanceAdmin(BaseAdmin, NonAdminAddable):

    list_display = ["id", "public_id", "stepfile_id", "model", "ifc_type", "created", "updated"]

    search_fields = ('stepfile_id', 'model__file_name', 'ifc_type')


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


class CustomUserAdmin(UserAdmin):

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
admin.site.register(User, CustomUserAdmin)
