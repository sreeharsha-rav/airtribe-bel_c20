from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AuditLog, Comment, Document, DocumentVersion, Tag, User, Workspace, WorkspaceMember
from .serializers import (
    AddDocumentTagsSerializer,
    AddWorkspaceMemberSerializer,
    AuditLogSerializer,
    CommentSerializer,
    DocumentSerializer,
    DocumentStatsSerializer,
    DocumentVersionSerializer,
    TagSerializer,
    UserSerializer,
    WorkspaceDetailSerializer,
    WorkspaceMemberDetailSerializer,
    WorkspaceSerializer,
    WorkspaceSummarySerializer,
)


@extend_schema_view(
    list=extend_schema(summary='List users', tags=['Users']),
    create=extend_schema(
        summary='Create a user',
        tags=['Users'],
        examples=[
            OpenApiExample(
                'Create user',
                value={
                    'first_name': 'Ada', 'last_name': 'Lovelace',
                    'email': 'ada@example.com', 'phone': '1234567890',
                },
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(summary='Get a user by id', tags=['Users']),
    update=extend_schema(summary='Replace a user', tags=['Users']),
    partial_update=extend_schema(summary='Partially update a user', tags=['Users']),
    destroy=extend_schema(summary='Delete a user', tags=['Users']),
)
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


@extend_schema_view(
    list=extend_schema(summary='List workspaces', tags=['Workspaces']),
    create=extend_schema(
        summary='Create a workspace',
        tags=['Workspaces'],
        examples=[
            OpenApiExample(
                'Create workspace',
                value={'name': 'Engineering', 'owner': '11111111-1111-1111-1111-111111111111'},
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary='Get a workspace with its member count', tags=['Workspaces']
    ),
    update=extend_schema(summary='Replace a workspace', tags=['Workspaces']),
    partial_update=extend_schema(summary='Partially update a workspace', tags=['Workspaces']),
    destroy=extend_schema(summary='Delete a workspace', tags=['Workspaces']),
)
class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer

    def perform_create(self, serializer):
        # Owner is added as an admin member atomically — either both writes
        # land or neither does.
        with transaction.atomic():
            workspace = serializer.save()
            WorkspaceMember.objects.create(
                workspace=workspace, user=workspace.owner, role=WorkspaceMember.Role.ADMIN,
            )

    @extend_schema(responses=WorkspaceDetailSerializer, tags=['Workspaces'])
    def retrieve(self, request, *args, **kwargs):
        queryset = self.get_queryset().select_related('owner').annotate(
            member_count=Count('members', distinct=True)
        )
        workspace = get_object_or_404(queryset, pk=kwargs['pk'])
        serializer = WorkspaceDetailSerializer(workspace)
        return Response(serializer.data)

    @extend_schema(
        methods=['GET'],
        summary='List workspace members',
        responses=WorkspaceMemberDetailSerializer(many=True),
        tags=['Workspaces'],
    )
    @extend_schema(
        methods=['POST'],
        summary='Add a workspace member',
        request=AddWorkspaceMemberSerializer,
        responses={201: AddWorkspaceMemberSerializer, 409: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                'Add member',
                value={'user': '22222222-2222-2222-2222-222222222222', 'role': 'editor'},
                request_only=True,
            ),
        ],
        tags=['Workspaces'],
    )
    @action(detail=True, methods=['get', 'post'], url_path='members')
    def members(self, request, pk=None):
        workspace = self.get_object()

        if request.method == 'GET':
            members = workspace.members.select_related('user').order_by('joined_at')
            serializer = WorkspaceMemberDetailSerializer(members, many=True)
            return Response(serializer.data)

        user_id = request.data.get('user')
        role = request.data.get('role')

        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, DjangoValidationError):
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if role not in WorkspaceMember.Role.values:
            return Response(
                {'role': [f'"{role}" is not a valid choice.']}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            member = WorkspaceMember.objects.create(workspace=workspace, user=user, role=role)
        except IntegrityError:
            return Response(
                {'detail': 'This user is already a member of this workspace.'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(AddWorkspaceMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary='Workspace summary counts', responses=WorkspaceSummarySerializer, tags=['Workspaces']
    )
    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        workspace = self.get_object()
        # Three Count()s over three different join paths in one aggregate()
        # fan out into a Cartesian product without distinct=True on each.
        counts = Workspace.objects.filter(pk=workspace.pk).aggregate(
            document_count=Count('documents', distinct=True),
            member_count=Count('members', distinct=True),
            comment_count=Count('documents__comments', distinct=True),
        )
        serializer = WorkspaceSummarySerializer(counts)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary='List documents',
        description='Supports filtering by workspace, status, tag name, and a title search.',
        parameters=[
            OpenApiParameter('workspace', OpenApiTypes.UUID, description='Filter by workspace id'),
            OpenApiParameter('status', OpenApiTypes.STR, description='Filter by document status'),
            OpenApiParameter('tag', OpenApiTypes.STR, description='Filter by tag name(s), comma-separated'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Case-insensitive title/content search'),
        ],
        tags=['Documents'],
    ),
    create=extend_schema(
        summary='Create a document + its first version',
        tags=['Documents'],
        examples=[
            OpenApiExample(
                'Create document',
                value={
                    'title': 'Q3 Roadmap',
                    'content': 'Initial draft of the roadmap.',
                    'workspace': '11111111-1111-1111-1111-111111111111',
                    'created_by': '22222222-2222-2222-2222-222222222222',
                    'status': 'draft',
                },
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(summary='Get a document by id', tags=['Documents']),
    update=extend_schema(
        summary='Update a document, saving a new version',
        tags=['Documents'],
        examples=[
            OpenApiExample(
                'Update document',
                value={
                    'title': 'Q3 Roadmap',
                    'content': 'Revised draft after review.',
                    'workspace': '11111111-1111-1111-1111-111111111111',
                    'created_by': '22222222-2222-2222-2222-222222222222',
                    'status': 'published',
                },
                request_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(summary='Partially update a document, saving a new version', tags=['Documents']),
    destroy=extend_schema(summary='Delete a document', tags=['Documents']),
)
class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = Document.objects.select_related('workspace', 'created_by')

        workspace_id = self.request.query_params.get('workspace')
        if workspace_id:
            queryset = queryset.filter(workspace_id=workspace_id)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        tag_names = self.request.query_params.get('tag')
        if tag_names:
            # Matching 2+ tags fans the M2M join into duplicate Document rows.
            queryset = queryset.filter(tags__name__in=tag_names.split(',')).distinct()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(content__icontains=search))

        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            document = serializer.save()
            DocumentVersion.objects.create(
                document=document, content=document.content,
                version_number=1, saved_by=document.created_by,
            )

    def perform_update(self, serializer):
        # Covers both PUT and PATCH — ModelViewSet.update() calls perform_update either way.
        with transaction.atomic():
            document = serializer.save()
            next_version_number = document.versions.count() + 1
            DocumentVersion.objects.create(
                document=document, content=document.content,
                version_number=next_version_number, saved_by=document.created_by,
            )

    @extend_schema(
        summary="List a document's versions in order",
        responses=DocumentVersionSerializer(many=True),
        tags=['Documents'],
    )
    @action(detail=True, methods=['get'], url_path='versions')
    def versions(self, request, pk=None):
        document = self.get_object()
        versions = document.versions.select_related('saved_by').order_by('version_number')
        serializer = DocumentVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Document stats: versions, comments, contributors',
        responses=DocumentStatsSerializer,
        tags=['Documents'],
    )
    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        document = self.get_object()
        counts = Document.objects.filter(pk=document.pk).aggregate(
            version_count=Count('versions', distinct=True),
            comment_count=Count('comments', distinct=True),
        )
        # exclude(saved_by__isnull=True) matters: DISTINCT over a column that
        # includes NULL (from a deleted user's SET_NULL) groups the NULLs
        # together and .count() counts that group as a "contributor", unlike
        # SQL's COUNT(DISTINCT x) which ignores NULLs.
        counts['contributor_count'] = (
            document.versions.exclude(saved_by__isnull=True)
            .values_list('saved_by', flat=True).distinct().count()
        )
        serializer = DocumentStatsSerializer(counts)
        return Response(serializer.data)

    @extend_schema(
        summary='Add one or more tags to a document',
        request=AddDocumentTagsSerializer,
        responses={201: TagSerializer(many=True)},
        examples=[
            OpenApiExample('Add tags', value={'tag_names': ['python', 'backend']}, request_only=True),
        ],
        tags=['Documents'],
    )
    @action(detail=True, methods=['post'], url_path='tags')
    def tags(self, request, pk=None):
        document = self.get_object()
        serializer = AddDocumentTagsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        names = {name.strip().lower() for name in serializer.validated_data['tag_names'] if name.strip()}

        tags = []
        with transaction.atomic():
            for name in names:
                tag, _ = Tag.objects.get_or_create(name=name)
                tag.documents.add(document)
                tags.append(tag)

        return Response(TagSerializer(tags, many=True).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        summary='List comments',
        description="Filter with ?document={id} to get a document's threaded comments.",
        parameters=[
            OpenApiParameter('document', OpenApiTypes.UUID, description='Filter by document id'),
        ],
        tags=['Comments'],
    ),
    create=extend_schema(
        summary='Add a top-level comment or a reply',
        tags=['Comments'],
        examples=[
            OpenApiExample(
                'Top-level comment',
                value={
                    'document': '33333333-3333-3333-3333-333333333333',
                    'author': '22222222-2222-2222-2222-222222222222',
                    'content': 'Looks good overall.',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Reply to a comment',
                value={
                    'document': '33333333-3333-3333-3333-333333333333',
                    'author': '11111111-1111-1111-1111-111111111111',
                    'content': 'Agreed, nice catch.',
                    'parent': '44444444-4444-4444-4444-444444444444',
                },
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(summary='Get a comment by id', tags=['Comments']),
    update=extend_schema(summary='Replace a comment', tags=['Comments']),
    partial_update=extend_schema(summary='Partially update a comment', tags=['Comments']),
    destroy=extend_schema(summary='Delete a comment', tags=['Comments']),
)
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def get_queryset(self):
        queryset = Comment.objects.select_related('author', 'parent', 'document')
        document_id = self.request.query_params.get('document')
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        return queryset


@extend_schema_view(
    list=extend_schema(summary='List tags', tags=['Tags']),
    create=extend_schema(
        summary='Create a tag',
        tags=['Tags'],
        examples=[OpenApiExample('Create tag', value={'name': 'python'}, request_only=True)],
    ),
    retrieve=extend_schema(summary='Get a tag by id', tags=['Tags']),
    update=extend_schema(summary='Replace a tag', tags=['Tags']),
    partial_update=extend_schema(summary='Partially update a tag', tags=['Tags']),
    destroy=extend_schema(summary='Delete a tag', tags=['Tags']),
)
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


@extend_schema_view(
    list=extend_schema(
        summary='List audit logs',
        description='Filter with ?actor={id}&date_from=...&date_to=...',
        parameters=[
            OpenApiParameter('actor', OpenApiTypes.UUID, description='Filter by actor (user) id'),
            OpenApiParameter('date_from', OpenApiTypes.DATETIME, description='Only entries at/after this timestamp'),
            OpenApiParameter('date_to', OpenApiTypes.DATETIME, description='Only entries at/before this timestamp'),
        ],
        tags=['Audit Logs'],
    ),
    retrieve=extend_schema(summary='Get an audit log entry by id', tags=['Audit Logs']),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        queryset = AuditLog.objects.select_related('actor').order_by('-timestamp')

        actor_id = self.request.query_params.get('actor')
        if actor_id:
            queryset = queryset.filter(actor_id=actor_id)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)

        return queryset
