import traceback
import sys
import logging

from django.db import transaction
from core.utils import get_client_ip_address
from core.settings import MAX_FILES_PER_UPLOAD

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from drf_spectacular.utils import extend_schema

from apps.ifc_validation_models.models import set_user_context
from apps.ifc_validation_models.models import ValidationRequest, ValidationTask, ValidationOutcome, Model

from .serializers import ValidationRequestSerializer
from .serializers import ValidationTaskSerializer
from .serializers import ValidationOutcomeSerializer
from .serializers import ModelSerializer
from .tasks import ifc_file_validation_task

logger = logging.getLogger(__name__)


class ValidationRequestDetailAPIView(APIView):

    queryset = ValidationRequest.objects.all()
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = ValidationRequestSerializer

    @extend_schema(operation_id='validationrequest_get')
    def get(self, request, id, *args, **kwargs):

        """
        Retrieves a single Validation Request by public_id.
        """
        
        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))

        instance = ValidationRequest.objects.filter(created_by__id=request.user.id, deleted=False, id=ValidationRequest.to_private_id(id)).first()
        if instance:
            serializer = ValidationRequestSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data = {'message': f"Validation Request with public_id={id} does not exist for user with id={request.user.id}."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(operation_id='validationrequest_delete')
    def delete(self, request, id, *args, **kwargs):

        """
        Deletes an IFC Validation Request instance by id.
        """
        
        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))

        instance = ValidationRequest.objects.filter(created_by__id=request.user.id, deleted=False, id=ValidationRequest.to_private_id(id)).first()
        if instance:
            instance.delete()
            data = {'message': f"Validation Request with public_id={id} was deleted successfully."}
            return Response(data, status=status.HTTP_204_NO_CONTENT)
        else:
            data = {'message': f"Validation Request with public_id={id} does not exist."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)


class ValidationRequestListAPIView(APIView):

    queryset = ValidationRequest.objects.all()
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = ValidationRequestSerializer

    @extend_schema(operation_id='validationrequest_list')
    def get(self, request, *args, **kwargs):

        """
        Returns a list of all Validation Requests.
        """

        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        user_requests = ValidationRequest.objects.filter(created_by__id=request.user.id, deleted=False)
        serializer = self.serializer_class(user_requests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(operation_id='validationrequest_create')
    def post(self, request, *args, **kwargs):

        """
        Creates a new Validation Request instance.
        """

        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():

            try:
                with transaction.atomic():
                    
                    # set current user context - TODO: move to middleware component?
                    if request.user.is_authenticated:
                        logger.info(f"Authenticated, user = {request.user.id}")
                        set_user_context(request.user)

                    files = request.FILES.getlist('file')
                    for i in range(0, MAX_FILES_PER_UPLOAD):
                        file_i = request.FILES.getlist(f'file[{i}]', None)
                        if file_i is not None: files += file_i
                    logger.info(f"Received {len(files)} file(s) - files: {files}")

                    # retrieve file size and save
                    uploaded_file = serializer.validated_data
                    logger.info(f'uploaded_file = {uploaded_file}')
                    f = uploaded_file['file']
                    f.seek(0, 2)
                    file_length = f.tell()
                    file_name = uploaded_file['file_name']
                    logger.info(f"file_length for uploaded file {file_name} = {file_length}")

                    # can't use this, file hasn't been saved yet
                    #file = os.path.join(MEDIA_ROOT, uploaded_file['file_name'])                   
                    #uploaded_file['size'] = os.path.getsize(file)
                    uploaded_file['size'] = file_length
                    instance = serializer.save()

                    # # submit task for background execution
                    def submit_task(instance):
                        ifc_file_validation_task.delay(instance.id, instance.file_name)
                        logger.info(f"Task 'ifc_file_validation_task' submitted for id:{instance.id} file_name: {instance.file_name})")

                    transaction.on_commit(lambda: submit_task(instance))                   

                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                
            except Exception as e:

                traceback.print_exc(file=sys.stdout)
                raise APIException(str(e))

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ValidationTaskDetailAPIView(APIView):

    queryset = ValidationTask.objects.all()
    authentication_classes = [SessionAuthentication, BasicAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ValidationTaskSerializer

    @extend_schema(operation_id='validationtask_get')
    def get(self, request, id, *args, **kwargs):

        """
        Retrieves a single Validation Task by public_id.
        """

        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        instance = ValidationTask.objects.filter(request__created_by__id=request.user.id, request__deleted=False, id=ValidationTask.to_private_id(id)).first()
        if instance:
            serializer = ValidationTaskSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data = {'message': f"Validation Task with public_id={id} does not exist for user with id={request.user.id}."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)


class ValidationTaskListAPIView(APIView):

    queryset = ValidationTask.objects.all()
    authentication_classes = [SessionAuthentication, BasicAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ValidationTaskSerializer

    @extend_schema(operation_id='validationtask_list')
    def get(self, request, *args, **kwargs):

        """
        Returns a list of all Validation Tasks, optionally filtered by request_public_id.
        """

        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        user_tasks = ValidationTask.objects.filter(request__created_by__id=request.user.id, request__deleted=False)
        
        # parse query arguments
        request_public_id = self.request.query_params.get('request_public_id', '').lower()
        request_public_ids = [id for id in (request_public_id.split(',') if request_public_id else [])]
        
        # apply filter(s)
        if request_public_ids:
            user_tasks = [t for t in user_tasks if t.request_public_id in request_public_ids]

        serializer = self.serializer_class(user_tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ValidationOutcomeDetailAPIView(APIView):

    queryset = ValidationOutcome.objects.all()
    authentication_classes = [SessionAuthentication, BasicAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ValidationOutcomeSerializer

    @extend_schema(operation_id='validationoutcome_get')
    def get(self, request, id, *args, **kwargs):

        """
        Retrieves a single Validation Outcome by public_id.
        """

        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        instance = ValidationOutcome.objects.filter(validation_task__request__created_by__id=request.user.id, validation_task__request__deleted=False, id=ValidationOutcome.to_private_id(id)).first()
        if instance:
            serializer = ValidationOutcomeSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data = {'message': f"Validation Outcome with public_id={id} does not exist for user with id={request.user.id}."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)


class ValidationOutcomeListAPIView(APIView):

    queryset = ValidationOutcome.objects.all()
    authentication_classes = [SessionAuthentication, BasicAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ValidationOutcomeSerializer

    @extend_schema(operation_id='validationoutcome_list')
    def get(self, request, *args, **kwargs):

        """
        Returns a list of all Validation Outcomes, optionally filtered by request_public_id or validation_task_public_id.
        """

        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        user_outcomes = ValidationOutcome.objects.filter(validation_task__request__created_by__id=request.user.id, validation_task__request__deleted=False)

        # parse query arguments
        request_public_id = self.request.query_params.get('request_public_id', '').lower()
        task_public_id = self.request.query_params.get('validation_task_public_id', '').lower()
        request_public_ids = [id for id in (request_public_id.split(',') if request_public_id else [])]
        task_public_ids = [id for id in (task_public_id.split(',') if task_public_id else [])]
        
        # apply filter(s)
        if request_public_ids:
            user_outcomes = [o for o in user_outcomes if o.validation_task.request_public_id in request_public_ids]
        if task_public_ids:
            user_outcomes = [o for o in user_outcomes if o.validation_task_public_id in task_public_ids]

        serializer = self.serializer_class(user_outcomes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ModelDetailAPIView(APIView):

    queryset = Model.objects.all()
    authentication_classes = [SessionAuthentication, BasicAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ModelSerializer

    @extend_schema(operation_id='model_get')
    def get(self, request, id, *args, **kwargs):

        """
        Retrieves a single Model by public_id.
        """

        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        instance = Model.objects.filter(request__created_by__id=request.user.id, request__deleted=False, id=Model.to_private_id(id)).first()
        if instance:
            serializer = self.serializer_class(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data = {'message': f"Model with public_id={id} does not exist for user with id={request.user.id}."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)


class ModelListAPIView(APIView):

    queryset = Model.objects.all()
    authentication_classes = [SessionAuthentication, BasicAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ModelSerializer

    @extend_schema(operation_id='model_list')
    def get(self, request, *args, **kwargs):

        """
        Returns a list of all Models, optionally filtered by request_public_id.
        """

        logger.info('API request - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        user_models = Model.objects.filter(request__created_by__id=request.user.id, request__deleted=False)
        
        # parse query arguments
        request_public_id = self.request.query_params.get('request_public_id', '').lower()
        request_public_ids = [id for id in (request_public_id.split(',') if request_public_id else [])]
        
        # apply filter(s)
        if request_public_ids:
            user_models = [m for m in user_models if m.request.public_id in request_public_ids]

        serializer = self.serializer_class(user_models, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
