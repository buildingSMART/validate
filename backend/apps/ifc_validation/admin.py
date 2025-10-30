import logging
from datetime import timedelta

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_permission_codename
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ngettext
from django.utils.html import format_html
from django.db.models import F, Case, When, DurationField, Count
from django.db.models.functions import Now

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.models import ValidationTask
from apps.ifc_validation_models.models import ValidationOutcome
from apps.ifc_validation_models.models import Model
from apps.ifc_validation_models.models import ModelInstance
from apps.ifc_validation_models.models import Company
from apps.ifc_validation_models.models import AuthoringTool
from apps.ifc_validation_models.models import UserAdditionalInfo
from apps.ifc_validation_models.models import Version
from apps.ifc_validation_models.models import set_user_context

from .tasks import ifc_file_validation_task
from .filters import ProducedByAdvancedFilter, ModelProducedByAdvancedFilter, CreatedByAdvancedFilter

from core import utils
from core.filters import AdvancedDateFilter

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
        ('General Information',  {"classes": ("wide"), "fields": ["id", "public_id", "file_name", "file", "file_size_text", "model", "deleted"]}),
        ('Status Information',   {"classes": ("wide"), "fields": ["status", "status_reason", "progress", "started", "completed", "channel" ]}),
        ('Auditing Information', {"classes": ("wide"), "fields": [("created", "created_by"), ("updated", "updated_by")]})
    ]

    list_display = ["id", "public_id", "file_name", "file_size_text", "authoring_tool_link", "model_link", "status", "progress", "duration_text", "is_vendor", "is_vendor_self_declared", "is_deleted", "channel", "created", "created_by", "updated", "updated_by"]
    readonly_fields = ["id", "public_id", "deleted", "file_name", "file", "file_size_text", "duration_text", "started", "completed", "channel", "created", "created_by", "updated", "updated_by"] 
    date_hierarchy = "created"

    list_filter = [
        "status", 
        "deleted", 
        ModelProducedByAdvancedFilter, 
        "channel", 
        CreatedByAdvancedFilter, 
        "created_by__useradditionalinfo__is_vendor", 
        "created_by__useradditionalinfo__is_vendor_self_declared", 
        ('created', AdvancedDateFilter)]
    search_fields = ('file_name', 'status', 'model__produced_by__name', 'created_by__username', 'updated_by__username')

    actions = ["soft_delete_action", "soft_restore_action", "mark_as_failed_action", "restart_processing_action", "hard_delete_action"]
    actions_on_top = True

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _duration=Case(
                When(completed__isnull=True, then=Now() - F('started')),
                default=F('completed') - F('started'),
                output_field=DurationField()
            )
        )
        return queryset

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        
        # attempt to filter by public_id by converting the search term into a private_id
        # note: only works for full public_id, not partial
        try:
            decoded_id = ValidationRequest.to_private_id(search_term)
            queryset |= self.model.objects.filter(id=decoded_id)            
        except Exception:
            pass

        return queryset, may_have_duplicates

    @admin.display(description="Authoring Tool")
    def authoring_tool_link(self, obj):
        
        if not obj.model or obj.model.produced_by is None:
            return None
        
        link = reverse("admin:ifc_validation_models_authoringtool_change", args=[obj.model.produced_by.id])
        return format_html(
            '<a href="{}">{}</a>',
            link,
            obj.model.produced_by,
        )
    authoring_tool_link.admin_order_field = 'model__produced_by'

    @admin.display(description="Model")
    def model_link(self, obj):
        
        if not obj.model:
            return None
        
        link = reverse("admin:ifc_validation_models_model_change", args=[obj.model.id])
        return format_html(
            '<a href="{}">{}</a>',
            link,
            obj.model,
        )
    model_link.admin_order_field = 'model'

    @admin.display(description="Duration (sec)")
    def duration_text(self, obj):

        return '{0:.1f}'.format(obj._duration.total_seconds()) if obj._duration else None
    duration_text.admin_order_field = '_duration'

    @admin.display(description="Is Vendor ?", boolean=True)
    def is_vendor(self, obj):
        return (obj.created_by.useradditionalinfo and obj.created_by.useradditionalinfo.is_vendor)
    is_vendor.admin_order_field = 'created_by__useradditionalinfo__is_vendor'

    @admin.display(description="Is Vendor (self) ?", boolean=True)
    def is_vendor_self_declared(self, obj):
        return (obj.created_by.useradditionalinfo and obj.created_by.useradditionalinfo.is_vendor_self_declared)
    is_vendor_self_declared.admin_order_field = 'created_by__useradditionalinfo__is_vendor_self_declared'

    @admin.display(description="Deleted ?", boolean=True)
    def is_deleted(self, obj):
        return obj.deleted
    is_deleted.admin_order_field = 'deleted'

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
        ('Status Information',   {"classes": ("wide"), "fields": ["status", "status_reason", "progress", "started", "ended"]}),
        ('Auditing Information', {"classes": ("wide"), "fields": ["created", "updated"]})
    ]

    list_display = ["id", "public_id", "request", "type", "status", "progress", "started", "ended", "duration_text", "created", "updated"]
    readonly_fields = ["id", "public_id", "request", "type", "process_id", "process_cmd", "started", "ended", "created", "updated"]
    date_hierarchy = "created"

    list_filter = ["status", "type", "status", "started", "ended", ('created', AdvancedDateFilter)]
    search_fields = ('request__file_name', 'status', 'type')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _duration=Case(
                When(ended__isnull=True, then=Now() - F('started')),
                default=F('ended') - F('started'),
                output_field=DurationField()
            )
        )
        return queryset
    
    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        
        # attempt to filter by public_id by converting the search term into a private_id
        # note: only works for full public_id, not partial
        try:
            decoded_id = ValidationTask.to_private_id(search_term)
            if ValidationTask.to_public_id(decoded_id) == search_term:
                queryset |= self.model.objects.filter(id=decoded_id)
            decoded_id2 = ValidationRequest.to_private_id(search_term)
            if ValidationRequest.to_public_id(decoded_id2) == search_term:
                queryset |= self.model.objects.filter(request_id=decoded_id2)
        except Exception:
            pass

        return queryset, may_have_duplicates

    @admin.display(description="Duration (sec)")
    def duration_text(self, obj):

        return '{0:.1f}'.format(obj._duration.total_seconds()) if obj._duration else None
    duration_text.admin_order_field = '_duration'


class ValidationOutcomeAdmin(BaseAdmin, NonAdminAddable):

    list_display = ["id", "public_id", "model_text", "instance_id", "type_text", "feature", "feature_version", "outcome_code", "severity", "expected", "observed", "created", "updated"]
    readonly_fields = ["id", "public_id", "created", "updated"]
    date_hierarchy = "created"

    list_filter = ['validation_task__type', 'severity', 'validation_task__request__model', 'outcome_code', 'feature', ('created', AdvancedDateFilter)]
    search_fields = ('validation_task__request__file_name', 'feature', 'feature_version', 'outcome_code', 'severity', 'expected', 'observed')

    paginator = utils.LargeTablePaginator
    show_full_result_count = False # do not use COUNT(*) twice
    
    @admin.display(description="Model")
    def model_text(self, obj):
        return obj.validation_task.request.model
    model_text.admin_order_field = 'validation_task__request__model'

    @admin.display(description="Validation Type")
    def type_text(self, obj):
        return obj.validation_task.type
    type_text.admin_order_field = 'validation_task__type'


class ModelAdmin(BaseAdmin, NonAdminAddable):

    list_display = ["id", "public_id", "file_name", "size_text", "authoring_tool_link", "schema", "mvd", "timestamp", "header_file_name", "created", "updated"]
    readonly_fields = ["id", "public_id", "file", "file_name", "size", "size_text", "date", "schema", "mvd", "produced_by", "created", "updated"]
    date_hierarchy = "created"

    search_fields = ('file_name', 'schema', 'mvd', 'produced_by__name', 'produced_by__version')
    list_filter = [
        'schema', 
        ProducedByAdvancedFilter,
        ('date', AdvancedDateFilter), 
        ('created', AdvancedDateFilter)
    ]
    
    @admin.display(description="File Size", ordering='size')
    def size_text(self, obj):
        
        return utils.format_human_readable_file_size(obj.size)
    
    @admin.display(description="Header File Name")
    def header_file_name(self, obj):
        
        return obj.header_validation['name'] if obj.header_validation else None
    
    @admin.display(description="Header Timestamp")
    def timestamp(self, obj):
        
        return obj.date
    
    @admin.display(description="Authoring Tool")
    def authoring_tool_link(self, obj):
        
        if obj.produced_by is None:
            return None
        
        link = reverse("admin:ifc_validation_models_authoringtool_change", args=[obj.produced_by.id])
        return format_html(
            '<a href="{}">{}</a>',
            link,
            obj.produced_by,
        )
    authoring_tool_link.admin_order_field = 'produced_by'


class ModelInstanceAdmin(BaseAdmin, NonAdminAddable):

    list_display = ["id", "public_id", "model", "stepfile_id", "ifc_type", "created", "updated"]
    search_fields = ('stepfile_id', 'model__file_name', 'ifc_type')
    list_filter = ["ifc_type", "model_id", ('created', AdvancedDateFilter)]

    paginator = utils.LargeTablePaginator
    show_full_result_count = False # do not use COUNT(*) twice


class CompanyAdmin(BaseAdmin):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "name", "legal_name", "email_address_pattern", "nbr_of_tools" ]}),
        ('Auditing Information', {"classes": ("wide"), "fields": [("created", "updated")]})
    ]
    list_display = ["id", "name", "legal_name", "email_address_pattern", "nbr_of_tools", "created", "updated"]
    readonly_fields = ["id", "nbr_of_tools", "created", "updated"]
    list_filter = [
        "name", 
        ('created', AdvancedDateFilter), 
        ('updated', AdvancedDateFilter)
    ]
    search_fields = ("name", "legal_name", "email_address_pattern")

    actions = ["assign_users_action"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(nbr_of_tools=Count('company')) # TODO: fix typo in Company model ('company' -> 'tools')

    @admin.display(description="# Tools")
    def nbr_of_tools(self, obj):

        link = reverse("admin:ifc_validation_models_authoringtool_changelist")
        query_string = '?company__id__exact=' + str(obj.id)
        return format_html(
            '<a href="{}{}" title="Click to show a filtered list of Authoring Tools for this Company">{}</a>',
            link,
            query_string,
            obj.nbr_of_tools
        )
    nbr_of_tools.admin_order_field = 'nbr_of_tools'

    @admin.action(
        description="Assign Users to Company by email address pattern(s)",
        permissions=["assign_users"]
    )
    def assign_users_action(self, request, queryset):

        # TODO: move to middleware component?
        if request.user.is_authenticated:
            logger.info(f"Authenticated, user.id = {request.user.id}")
            set_user_context(request.user)

        detected_users_count = 0
        detected_users = {}
        detected_companies = []
        for company in queryset:
            matching_users = company.find_users_by_email_pattern(only_new=True)
            if matching_users:
                detected_companies.append(company)
                detected_users[company.id] = matching_users
                detected_users_count += detected_users[company.id].count()

        if detected_users_count == 0:
            self.message_user(request, "No eligible users were found.", messages.WARNING)
            return HttpResponseRedirect(request.get_full_path())

        if 'apply' in request.POST:

            updated_user_count = 0
            for company in queryset:
                if company.email_address_pattern:
                    for user in detected_users[company.id]:
                        if 'user_' + str(user.id) in request.POST:
                            uai, _ = UserAdditionalInfo.objects.get_or_create(user=user)
                            if company and (uai.company != company or not uai.is_vendor):
                                logger.info(f"User with id={user.id} and email={user.email} matches email address pattern '{company.email_address_pattern}' of Company with id={company.id} ({company.name}).")
                                uai.company = company
                                uai.is_vendor = True
                                uai.save()
                                logger.info(f"User with id={user.id} and email={user.email} was assigned to Company with id={company.id} ({company.name}) and marked as 'is_vendor'.")
                                updated_user_count += 1                                

            if updated_user_count == 0:
                self.message_user(request, "No users were assigned.", messages.WARNING)
            else:
                self.message_user(
                    request,
                    ngettext(
                        "%d User was successfully assigned.",
                        "%d Users were successfully assigned.",
                        updated_user_count
                    )
                    % updated_user_count,
                    messages.SUCCESS,
                )
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/assign_company_intermediate.html', context={'companies': detected_companies, 'detected_users': detected_users})

    def has_assign_users_permission(self, request):

        opts = self.opts
        codename = get_permission_codename("change_user", opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))


class AuthoringToolAdmin(BaseAdmin):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "company", "name", "version", "nbr_of_requests"]}),
        ('Auditing Information', {"classes": ("wide"), "fields": [("created", "updated")]})
    ]
    list_display = ["id", "company_link", "name", "version", "nbr_of_requests", "created", "updated"]
    readonly_fields = ["id", "nbr_of_requests", "created", "updated"]
    list_filter = ["company", ('created', AdvancedDateFilter), ('updated', AdvancedDateFilter)]
    search_fields = ("name", "version", "company__name")

    @admin.display(description="Company")
    def company_link(self, obj):

        if not obj.company:
            return None
        
        link = reverse("admin:ifc_validation_models_company_change", args=[obj.company.id])
        return format_html(
            '<a href="{}">{}</a>',
            link,
            obj.company,
        )
    company_link.admin_order_field = 'company'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(nbr_of_requests=Count('models')) # good proxy, no direct link to Validation Request

    @admin.display(description="# Requests")
    def nbr_of_requests(self, obj):
        return obj.nbr_of_requests
    nbr_of_requests.admin_order_field = 'nbr_of_requests'


class UserAdditionalInfoInlineAdmin(admin.StackedInline):

    model = UserAdditionalInfo
    fk_name = "user"

    fieldsets = [
        ('Vendor Information',  {"classes": ("wide"), "fields": ["id", "company", "is_vendor", "is_vendor_self_declared"]}),
        ('Auditing Information', {"classes": ("wide"), "fields":  [("created", "created_by"), ("updated", "updated_by")]})
    ]
    ordering = ("company", "is_vendor", "created", "created_by", "updated", "updated_by")
    readonly_fields = ["is_vendor_self_declared", "created", "created_by", "updated", "updated_by"]


class CustomUserAdmin(UserAdmin, BaseAdmin):

    inlines = [ UserAdditionalInfoInlineAdmin ]

    list_display = ["id", "username", "email", "first_name", "last_name", "is_active", "is_staff", "company_link", "is_vendor", "is_vendor_self_declared", "nbr_of_requests", "date_joined", "last_login"]
    list_filter = [
        'is_staff', 
        'is_superuser', 
        'is_active', 
        'useradditionalinfo__company', 
        'useradditionalinfo__is_vendor',
        'useradditionalinfo__is_vendor_self_declared', 
        ('date_joined', AdvancedDateFilter), 
        ('last_login', AdvancedDateFilter)]
    search_fields = ('username', 'email', 'first_name', 'last_name', 'useradditionalinfo__company__name', "date_joined", "last_login")
    ordering = ('-date_joined',)

    actions = ["activate_action", "deactivate_action", "remove_company_and_is_vendor_action"]
    actions_on_top = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(nbr_of_requests=Count('models')) # good proxy, no direct link to Validation Request

    @admin.action(description="Activate selected users")
    def activate_action(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected users")
    def deactivate_action(self, request, queryset):
        queryset.update(is_active=False)

    @admin.display(description="Company")
    def company_link(self, obj):
        
        if not obj.useradditionalinfo or not obj.useradditionalinfo.company:
            return None
        
        link = reverse("admin:ifc_validation_models_company_change", args=[obj.useradditionalinfo.company.id])
        return format_html(
            '<a href="{}">{}</a>',
            link,
            obj.useradditionalinfo.company,
        )
    company_link.admin_order_field = 'useradditionalinfo__company'
    
    @admin.display(description="Is Vendor?")
    def is_vendor(self, obj):
        
        return None if obj.useradditionalinfo is None else obj.useradditionalinfo.is_vendor
    is_vendor.admin_order_field = 'useradditionalinfo__is_vendor'

    @admin.display(description="Is Vendor (self-declared)?")
    def is_vendor_self_declared(self, obj):
        
        return None if obj.useradditionalinfo is None else obj.useradditionalinfo.is_vendor_self_declared
    is_vendor_self_declared.admin_order_field = 'useradditionalinfo__is_vendor_self_declared'

    @admin.display(description="# Requests")
    def nbr_of_requests(self, obj):
        return obj.nbr_of_requests
    nbr_of_requests.admin_order_field = 'nbr_of_requests'

    @admin.action(
        description="Remove Company & is_vendor status from selected users",
        permissions=["assign_users"]
    )
    def remove_company_and_is_vendor_action(self, request, queryset):

        # TODO: move to middleware component?
        if request.user.is_authenticated:
            logger.info(f"Authenticated, user.id = {request.user.id}")
            set_user_context(request.user)

        count = 0
        for user in queryset:
            uai = UserAdditionalInfo.objects.filter(user=user)
            if uai.exists():
                prev_company = uai.first().company
                uai.update(company=None, is_vendor=None)
                count = count + 1
                logger.info(f"User with id={user.id} and email={user.email} had Company '{prev_company}' and 'is_vendor' status removed.")

        self.message_user(
            request,
            ngettext(
                "%d User was successfully updated.",
                "%d Users were successfully updated.",
                count
            )
            % count,
            messages.SUCCESS,
        )

    def has_assign_users_permission(self, request):

        opts = self.opts
        codename = get_permission_codename("change_user", opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))
    

class VersionAdmin(BaseAdmin):

    fieldsets = [
        ('General Information',  {"classes": ("wide"), "fields": ["id", "name", "released", "release_notes"]}),
        ('Auditing Information', {"classes": ("wide"), "fields": [("created", "updated")]})
    ]
    list_display = ["id", "name", "released", "release_notes", "created", "updated"]
    readonly_fields = ["id", "created", "updated"]
    list_filter = [('created', AdvancedDateFilter), ('updated', AdvancedDateFilter)]
    search_fields = ("name", "released", "release_notes")


# register all admin classes
admin.site.register(ValidationRequest, ValidationRequestAdmin)
admin.site.register(ValidationTask, ValidationTaskAdmin)
admin.site.register(ValidationOutcome, ValidationOutcomeAdmin)
admin.site.register(Model, ModelAdmin)
admin.site.register(ModelInstance, ModelInstanceAdmin)
admin.site.register(Company, CompanyAdmin)
admin.site.register(AuthoringTool, AuthoringToolAdmin)
admin.site.register(Version, VersionAdmin)

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
