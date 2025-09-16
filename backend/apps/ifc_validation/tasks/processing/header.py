import json
import datetime
import os

from apps.ifc_validation_models.models import Model, AuthoringTool, Company
from .. import TaskContext, logger, with_model

def process_header(context:TaskContext):
    header_validation = context.result

    with with_model(context.request.id) as model:
        agg_status = context.task.determine_aggregate_status()
        setattr(model, context.config.status_field.name, agg_status)
        model.size = os.path.getsize(context.file_path)
        logger.debug(f'Detected size = {model.size} bytes')
        
        model.schema = header_validation.get('schema_identifier')
        logger.debug(f'The schema identifier = {header_validation.get("schema")}')
        # time_stamp 
        if ifc_file_time_stamp := header_validation.get('time_stamp', False):
            try:
                logger.debug(f'Timestamp within file = {ifc_file_time_stamp}')
                date = datetime.datetime.strptime(ifc_file_time_stamp, "%Y-%m-%dT%H:%M:%S")
                date_with_tz = datetime.datetime(
                    date.year, 
                    date.month, 
                    date.day, 
                    date.hour, 
                    date.minute, 
                    date.second, 
                    tzinfo=datetime.timezone.utc)
                model.date = date_with_tz
            except ValueError:
                try:
                    model.date = datetime.datetime.fromisoformat(ifc_file_time_stamp)
                except ValueError:
                    pass
                
        # mvd
        model.mvd = header_validation.get('mvd')
        
        app = header_validation.get('application_name')
        
        version = header_validation.get('version')
        name = None if any(value in (None, "Not defined") for value in (app, version)) else app + ' ' + version
        company_name = header_validation.get('company_name')
        logger.debug(f'Detected Authoring Tool in file = {name}')
        
        validation_errors = header_validation.get('validation_errors', [])
        invalid_marker_fields = ['originating_system', 'version', 'company_name', 'application_name']
        if any(field in validation_errors for field in invalid_marker_fields):
            model.status_header = Model.Status.INVALID
        else:
            # parsing was successful and model can be considered for scorecards
            model.status_header = Model.Status.VALID
            authoring_tool = AuthoringTool.find_by_full_name(full_name=name)
            if (isinstance(authoring_tool, AuthoringTool)):
                
                if authoring_tool.company is None:
                    company, _ = Company.objects.get_or_create(name=company_name)
                    authoring_tool.company = company
                    authoring_tool.save()
                    logger.debug(f'Updated existing Authoring Tool with company: {company.name}')

                model.produced_by = authoring_tool
                logger.debug(f'Retrieved existing Authoring Tool from DB = {model.produced_by.full_name}')

            elif authoring_tool is None:
                company, _ = Company.objects.get_or_create(name=company_name)
                authoring_tool, _ = AuthoringTool.objects.get_or_create(
                    company=company,
                    name=app,
                    version=version
                )
                model.produced_by = authoring_tool
                logger.debug(f'Authoring app not found, ApplicationFullName = {app}, Version = {version} - created new instance')
            else:
                model.produced_by = None
                logger.warning(f'Retrieved multiple Authoring Tool from DB: {authoring_tool} - could not assign any')  
                        
        # update header validation
        model.header_validation = header_validation
        model.save(update_fields=['status_header', 'header_validation']) 
        model.save()
        
        return f'agg_status = {Model.Status(agg_status).label}\nraw_output = {header_validation}'
