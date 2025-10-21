import traceback
import sys
import logging
import re

from django.db import transaction
from core.utils import get_client_ip_address
from core.settings import MAX_FILES_PER_UPLOAD

from rest_framework import status, serializers
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.decorators import throttle_classes
from drf_spectacular.utils import extend_schema

from apps.ifc_validation_models.models import set_user_context
from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.models import ValidationTask
from apps.ifc_validation_models.models import ValidationOutcome
from apps.ifc_validation_models.models import Model

from .serializers import ValidationRequestSerializer
from .serializers import ValidationTaskSerializer
from .serializers import ValidationOutcomeSerializer
from .serializers import ModelSerializer
from ...tasks import ifc_file_validation_task

logger = logging.getLogger(__name__)


@extend_schema(tags=['Validation Request'])
class ValidationRequestDetailAPIView(APIView):

    queryset = ValidationRequest.objects.all()
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = ValidationRequestSerializer
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id='validationrequest_get',
        responses={
            200: ValidationRequestSerializer,
            404: None,
        }
    )
    def get(self, request, id, *args, **kwargs):

        """
        Retrieves a single Validation Request by (public) id.
        """
        
        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))

        instance = ValidationRequest.objects.filter(created_by__id=request.user.id, deleted=False, id=ValidationRequest.to_private_id(id)).first()
        if instance:
            serializer = self.serializer_class(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data = {'detail': f"Validation Request with public_id={id} does not exist for user with id={request.user.id}."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        operation_id='validationrequest_delete',
        responses={
            204: None,
            404: None,
        }
    )
    def delete(self, request, id, *args, **kwargs):

        """
        Deletes an IFC Validation Request instance by id.
        """
        
        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))

        if request.user.is_authenticated:
            logger.info(f"Authenticated, user = {request.user.id}")
            set_user_context(request.user)
            
        instance = ValidationRequest.objects.filter(created_by__id=request.user.id, deleted=False, id=ValidationRequest.to_private_id(id)).first()
        if instance:
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            data = {'detail': f"Validation Request with public_id={id} does not exist."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)


@extend_schema(tags=['Validation Request'])
class ValidationRequestListAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = ValidationRequestSerializer
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = 'submit_validation_request'

    def get_throttles(self):
        """
        Applies scoped throttling only for POST requests (aka submitting a new Validation Request).
        """    
        return [ScopedRateThrottle()] if self.request.method == 'POST' else [UserRateThrottle()]

    @extend_schema(
        operation_id='validationrequest_list',
        responses={
            200: ValidationRequestSerializer(many=True),
            404: None
        }
    )
    def get(self, request, *args, **kwargs):

        """
        Returns a list of all Validation Requests.
        """

        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            ValidationRequest.objects
            .filter(created_by_id=self.request.user.id, deleted=False)
            .order_by("-created", "-id")
        )
    
        public_id = self.request.query_params.get('public_id', '').lower()
        if public_id:
            
            # apply filter(s)
            pub_ids = [p.strip() for p in public_id.split(',') if p.strip()]
            priv_ids = [ValidationRequest.to_private_id(p) for p in pub_ids]

            logger.info(f"pub_ids = {pub_ids}")
            logger.info(f"priv_ids = {priv_ids}")
        
            qs = qs.filter(id__in=priv_ids)

        return qs

    @extend_schema(
        operation_id='validationrequest_create',
        responses={
            201: ValidationRequestSerializer,
            400: None,
        }
    )
    def post(self, request, *args, **kwargs):

        """
        Creates a new Validation Request instance.
        """

        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
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

                    # only accept one file (for now) - note: can't be done easily in serializer,
                    # as we need access to request.FILES and our model only accepts one file
                    serializer.validate_files(files)

                    # retrieve file size and save
                    uploaded_file = serializer.validated_data
                    logger.info(f'uploaded_file = {uploaded_file}')
                    f = uploaded_file['file']
                    f.seek(0, 2)
                    file_length = f.tell()
                    file_name = uploaded_file['file_name']
                    logger.info(f"file_length for uploaded file {file_name} = {file_length} ({file_length / (1024*1024)} MB)")

                    # can't use this, file hasn't been saved yet
                    #file = os.path.join(MEDIA_ROOT, uploaded_file['file_name'])                   
                    #uploaded_file['size'] = os.path.getsize(file)
                    uploaded_file['size'] = file_length
                    instance = serializer.save()

                    # submit task for background execution
                    def submit_task(instance):
                        ifc_file_validation_task.delay(instance.id, instance.file_name)
                        logger.info(f"Task 'ifc_file_validation_task' submitted for id:{instance.id} file_name: {instance.file_name})")

                    transaction.on_commit(lambda: submit_task(instance))                   

                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                
            except serializers.ValidationError as e:

                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            
            except Exception as e:

                traceback.print_exc(file=sys.stdout)
                raise APIException(str(e))

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Validation Task'])
class ValidationTaskDetailAPIView(APIView):

    queryset = ValidationTask.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = ValidationTaskSerializer
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id='validationtask_get',
        responses={
            200: ValidationTaskSerializer(),
            404: None,
        }
    )
    def get(self, request, id, *args, **kwargs):

        """
        Retrieves a single Validation Task by (public) id.
        """

        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        instance = ValidationTask.objects.filter(request__created_by__id=request.user.id, request__deleted=False, id=ValidationTask.to_private_id(id)).first()
        if instance:
            serializer = ValidationTaskSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data = {'detail': f"Validation Task with public_id={id} does not exist for user with id={request.user.id}."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)


@extend_schema(tags=['Validation Task'])
class ValidationTaskListAPIView(ListAPIView):

    permission_classes = [IsAuthenticated]
    serializer_class = ValidationTaskSerializer
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id='validationtask_list',
        responses={
            200: ValidationTaskSerializer(many=True),
            404: None,
        }
    )
    def get(self, request, *args, **kwargs):

        """
        Returns a list of all Validation Tasks, optionally filtered by request_public_id.
        """

        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (ValidationTask.objects
              .filter(request__created_by_id=self.request.user.id,
                      request__deleted=False)
              .order_by("-id"))

        # parse query arguments
        req_param = self.request.query_params.get('request_public_id', '').lower()
        if req_param:
            
            # apply filter(s)
            pub_ids = [p.strip() for p in req_param.split(',') if p.strip()]
            priv_ids = [ValidationRequest.to_private_id(p) for p in pub_ids]
            qs = qs.filter(request_id__in=priv_ids)
        
        return qs


@extend_schema(tags=['Validation Outcome'])
class ValidationOutcomeDetailAPIView(APIView):

    queryset = ValidationOutcome.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = ValidationOutcomeSerializer
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id='validationoutcome_get',
        responses={
            200: ValidationOutcomeSerializer,
            404: None,
        }
    )
    def get(self, request, id, *args, **kwargs):

        """
        Retrieves a single Validation Outcome by (public) id.
        """

        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        instance = ValidationOutcome.objects.filter(validation_task__request__created_by__id=request.user.id, validation_task__request__deleted=False, id=ValidationOutcome.to_private_id(id)).first()
        if instance:
            serializer = ValidationOutcomeSerializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data = {'detail': f"Validation Outcome with public_id={id} does not exist for user with id={request.user.id}."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)


@extend_schema(tags=['Validation Outcome'])
class ValidationOutcomeListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ValidationOutcomeSerializer
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id='validationoutcome_list',
        responses=
        {
            200: ValidationOutcomeSerializer(many=True),
            404: None,
        }
    )
    def get(self, request, *args, **kwargs):

        """
        Returns a list of all Validation Outcomes, optionally filtered by request_public_id or validation_task_public_id.
        """

        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (ValidationOutcome.objects
                .filter(validation_task__request__created_by=self.request.user,
                validation_task__request__deleted=False)
            .order_by("-created", "-id"))

        def priv_ids(param, prefix, to_priv):
            raw = (self.request.query_params.get(param, "") or "").lower()
            if not raw: return []
            pat = re.compile(rf"^{prefix}\d+$")
            out = []
            for p in map(str.strip, raw.split(",")):
                if pat.match(p):
                    try: out.append(to_priv(p))
                    except ValueError: pass
            return out

        req_ids  = priv_ids("request_public_id", "r", ValidationRequest.to_private_id)
        task_ids = priv_ids("validation_task_public_id", "t", ValidationTask.to_private_id)

        if req_ids:  qs = qs.filter(validation_task__request__id__in=req_ids)
        if task_ids: qs = qs.filter(validation_task__id__in=task_ids)
        return qs


@extend_schema(tags=['Model'])
class ModelDetailAPIView(APIView):

    queryset = Model.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = ModelSerializer
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id='model_get',
        responses={
            200: ModelSerializer,
            404: None,
        }
    )
    def get(self, request, id, *args, **kwargs):

        """
        Retrieves a single Model by (public) id.
        """

        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        
        instance = Model.objects.filter(request__created_by__id=request.user.id, request__deleted=False, id=Model.to_private_id(id)).first()
        if instance:
            serializer = self.serializer_class(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data = {'detail': f"Model with public_id={id} does not exist for user with id={request.user.id}."}
            return Response(data, status=status.HTTP_404_NOT_FOUND)


@extend_schema(tags=['Model'])
class ModelListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ModelSerializer
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        operation_id='model_list',
        responses={
            200: ModelSerializer(many=True),
            404: None,
        }
    )
    def get(self, request, *args, **kwargs):

        """
        Returns a list of all Models, optionally filtered by request_public_id.
        """

        logger.info('API request v%s - User IP: %s Request Method: %s Request URL: %s Content-Length: %s' % (self.request.version, get_client_ip_address(request), request.method, request.path, request.META.get('CONTENT_LENGTH')))
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (Model.objects
              .filter(request__created_by_id=self.request.user.id,
                      request__deleted=False)
              .order_by("-id"))

        # parse query arguments
        req_param = (self.request.query_params.get('request_public_id', '') or '').lower()

        # apply filter(s)
        if req_param:
            pub_ids = [p.strip() for p in req_param.split(',') if p.strip()]
            priv_ids = [ValidationRequest.to_private_id(p) for p in pub_ids]
            qs = qs.filter(request__id__in=priv_ids)
        return qs
