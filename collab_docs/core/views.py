from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException

from .models import AuditLog, Comment, Document, Tag, User, Workspace
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


class NotImplementedYet(APIException):
    """Raised by the query-set/aggregation/transaction/integrity stubs below.

    Each raise site has a docstring or comment describing exactly what to
    write in its place — replace the `raise` with real logic and this
    exception goes away.
    """

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    default_code = 'not_implemented'

    def __init__(self, feature):
        super().__init__(detail=f"Not implemented yet: {feature}. See the TODO in views.py.")


@extend_schema_view(
    list=extend_schema(summary='List users', tags=['Users']),
    create=extend_schema(summary='Create a user', tags=['Users']),
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
    create=extend_schema(summary='Create a workspace', tags=['Workspaces']),
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
        # TODO (transactions):
        #   with transaction.atomic():
        #       workspace = serializer.save()
        #       WorkspaceMember.objects.create(
        #           workspace=workspace, user=workspace.owner, role=WorkspaceMember.Role.ADMIN,
        #       )
        # Both writes must succeed or neither should — that's what atomic() guarantees.
        raise NotImplementedYet('Workspace.create must atomically add the owner as an admin member')

    @extend_schema(responses=WorkspaceDetailSerializer, tags=['Workspaces'])
    def retrieve(self, request, *args, **kwargs):
        # TODO (aggregations):
        #   queryset = self.get_queryset().annotate(member_count=Count('members'))
        #   instance = get_object_or_404(queryset, pk=kwargs['pk'])
        #   serializer = WorkspaceDetailSerializer(instance)
        #   return Response(serializer.data)
        raise NotImplementedYet('Workspace.retrieve must annotate member_count via Count()')

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
        tags=['Workspaces'],
    )
    @action(detail=True, methods=['get', 'post'], url_path='members')
    def members(self, request, pk=None):
        workspace = self.get_object()

        if request.method == 'GET':
            # TODO (querysets):
            #   members = workspace.members.select_related('user')
            #   serializer = WorkspaceMemberDetailSerializer(members, many=True)
            #   return Response(serializer.data)
            raise NotImplementedYet('Workspace.members GET must select_related("user") and list members')

        # TODO (integrity):
        #   serializer = AddWorkspaceMemberSerializer(data=request.data)
        #   serializer.is_valid(raise_exception=True)
        #   try:
        #       member = serializer.save(workspace=workspace)
        #   except IntegrityError:
        #       return Response(
        #           {'detail': 'This user is already a member of this workspace.'},
        #           status=status.HTTP_409_CONFLICT,
        #       )
        #   return Response(AddWorkspaceMemberSerializer(member).data, status=status.HTTP_201_CREATED)
        raise NotImplementedYet('Workspace.members POST must add a member and return 409 on duplicates')

    @extend_schema(
        summary='Workspace summary counts', responses=WorkspaceSummarySerializer, tags=['Workspaces']
    )
    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        workspace = self.get_object()  # noqa: F841 — used once the TODO below is implemented
        # TODO (aggregations): a single query beats three round trips —
        #   counts = Workspace.objects.filter(pk=workspace.pk).aggregate(
        #       document_count=Count('documents', distinct=True),
        #       member_count=Count('members', distinct=True),
        #       comment_count=Count('documents__comments', distinct=True),
        #   )
        #   serializer = WorkspaceSummarySerializer(counts)
        #   return Response(serializer.data)
        raise NotImplementedYet('Workspace.summary must aggregate document/member/comment counts')


@extend_schema_view(
    list=extend_schema(
        summary='List documents',
        description='Supports filtering by workspace, status, tag name, and a title search.',
        parameters=[
            OpenApiParameter('workspace', OpenApiTypes.UUID, description='Filter by workspace id'),
            OpenApiParameter('status', OpenApiTypes.STR, description='Filter by document status'),
            OpenApiParameter('tag', OpenApiTypes.STR, description='Filter by tag name'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Case-insensitive title search'),
        ],
        tags=['Documents'],
    ),
    create=extend_schema(summary='Create a document + its first version', tags=['Documents']),
    retrieve=extend_schema(summary='Get a document by id', tags=['Documents']),
    update=extend_schema(summary='Update a document, saving a new version', tags=['Documents']),
    partial_update=extend_schema(summary='Partially update a document, saving a new version', tags=['Documents']),
    destroy=extend_schema(summary='Delete a document', tags=['Documents']),
)
class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = Document.objects.all()
        # TODO (querysets & filtering): honor query params before returning, e.g.
        #   workspace_id = self.request.query_params.get('workspace')
        #   if workspace_id:
        #       queryset = queryset.filter(workspace_id=workspace_id)
        #   status_param = self.request.query_params.get('status')
        #   if status_param:
        #       queryset = queryset.filter(status=status_param)
        #   tag_name = self.request.query_params.get('tag')
        #   if tag_name:
        #       queryset = queryset.filter(tags__name=tag_name)
        #   search = self.request.query_params.get('search')
        #   if search:
        #       queryset = queryset.filter(Q(title__icontains=search))
        # Currently returns everything, ignoring all four query params above.
        return queryset

    def perform_create(self, serializer):
        # TODO (transactions):
        #   with transaction.atomic():
        #       document = serializer.save()
        #       DocumentVersion.objects.create(
        #           document=document, content=document.content,
        #           version_number=1, saved_by=document.created_by,
        #       )
        raise NotImplementedYet('Document.create must atomically create the first DocumentVersion')

    def perform_update(self, serializer):
        # TODO (transactions): applies to both PUT and PATCH —
        #   with transaction.atomic():
        #       document = serializer.save()
        #       next_version_number = document.versions.count() + 1
        #       DocumentVersion.objects.create(
        #           document=document, content=document.content,
        #           version_number=next_version_number, saved_by=document.created_by,
        #       )
        raise NotImplementedYet('Document.update must atomically create a new DocumentVersion')

    @extend_schema(
        summary='List a document\'s versions in order',
        responses=DocumentVersionSerializer(many=True),
        tags=['Documents'],
    )
    @action(detail=True, methods=['get'], url_path='versions')
    def versions(self, request, pk=None):
        document = self.get_object()  # noqa: F841 — used once the TODO below is implemented
        # TODO (querysets):
        #   versions = document.versions.order_by('version_number')
        #   serializer = DocumentVersionSerializer(versions, many=True)
        #   return Response(serializer.data)
        raise NotImplementedYet('Document.versions must list versions ordered by version_number')

    @extend_schema(
        summary='Document stats: versions, comments, contributors',
        responses=DocumentStatsSerializer,
        tags=['Documents'],
    )
    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        document = self.get_object()  # noqa: F841 — used once the TODO below is implemented
        # TODO (aggregations):
        #   counts = Document.objects.filter(pk=document.pk).aggregate(
        #       version_count=Count('versions', distinct=True),
        #       comment_count=Count('comments', distinct=True),
        #       contributor_count=Count('versions__saved_by', distinct=True),
        #   )
        #   serializer = DocumentStatsSerializer(counts)
        #   return Response(serializer.data)
        raise NotImplementedYet('Document.stats must aggregate version/comment/contributor counts')

    @extend_schema(
        summary='Add one or more tags to a document',
        request=AddDocumentTagsSerializer,
        responses={201: TagSerializer(many=True)},
        tags=['Documents'],
    )
    @action(detail=True, methods=['post'], url_path='tags')
    def tags(self, request, pk=None):
        document = self.get_object()  # noqa: F841 — used once the TODO below is implemented
        # TODO (integrity):
        #   serializer = AddDocumentTagsSerializer(data=request.data)
        #   serializer.is_valid(raise_exception=True)
        #   tags = []
        #   for name in serializer.validated_data['tag_names']:
        #       tag, _ = Tag.objects.get_or_create(name=name.strip().lower())
        #       tag.documents.add(document)
        #       tags.append(tag)
        #   return Response(TagSerializer(tags, many=True).data, status=status.HTTP_201_CREATED)
        raise NotImplementedYet('Document.tags must get_or_create tags and attach them to the document')


@extend_schema_view(
    list=extend_schema(
        summary='List comments',
        description='Filter with ?document={id} to get a document\'s threaded comments.',
        parameters=[
            OpenApiParameter('document', OpenApiTypes.UUID, description='Filter by document id'),
        ],
        tags=['Comments'],
    ),
    create=extend_schema(summary='Add a top-level comment or a reply', tags=['Comments']),
    retrieve=extend_schema(summary='Get a comment by id', tags=['Comments']),
    update=extend_schema(summary='Replace a comment', tags=['Comments']),
    partial_update=extend_schema(summary='Partially update a comment', tags=['Comments']),
    destroy=extend_schema(summary='Delete a comment', tags=['Comments']),
)
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def get_queryset(self):
        queryset = Comment.objects.select_related('author', 'parent')
        # TODO (querysets & filtering):
        #   document_id = self.request.query_params.get('document')
        #   if document_id:
        #       queryset = queryset.filter(document_id=document_id)
        # Currently returns every comment, ignoring ?document=.
        return queryset


@extend_schema_view(
    list=extend_schema(summary='List tags', tags=['Tags']),
    create=extend_schema(summary='Create a tag', tags=['Tags']),
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
        queryset = AuditLog.objects.order_by('-timestamp')
        # TODO (querysets & filtering):
        #   actor_id = self.request.query_params.get('actor')
        #   if actor_id:
        #       queryset = queryset.filter(actor_id=actor_id)
        #   date_from = self.request.query_params.get('date_from')
        #   if date_from:
        #       queryset = queryset.filter(timestamp__gte=date_from)
        #   date_to = self.request.query_params.get('date_to')
        #   if date_to:
        #       queryset = queryset.filter(timestamp__lte=date_to)
        # Currently returns every entry, ignoring actor/date_from/date_to.
        return queryset
