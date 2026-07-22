from rest_framework import serializers

from .models import (
    AuditLog,
    Comment,
    Document,
    DocumentVersion,
    Tag,
    User,
    Workspace,
    WorkspaceMember,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']


class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ['id', 'name', 'owner', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class WorkspaceDetailSerializer(WorkspaceSerializer):
    """Used for the annotated retrieve() response; member_count comes from
    an annotate(member_count=Count('members')) on the queryset."""

    member_count = serializers.IntegerField(read_only=True)

    class Meta(WorkspaceSerializer.Meta):
        fields = WorkspaceSerializer.Meta.fields + ['member_count']


class WorkspaceSummarySerializer(serializers.Serializer):
    """Response shape for GET /api/workspaces/{id}/summary/."""

    document_count = serializers.IntegerField()
    member_count = serializers.IntegerField()
    comment_count = serializers.IntegerField()


class AddWorkspaceMemberSerializer(serializers.ModelSerializer):
    """Request/response body for POST /api/workspaces/{id}/members/.
    workspace is set by the view from the URL, not accepted from the body."""

    class Meta:
        model = WorkspaceMember
        fields = ['id', 'user', 'role', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class WorkspaceMemberDetailSerializer(serializers.ModelSerializer):
    """Response shape for GET /api/workspaces/{id}/members/ — nests the
    member's user details instead of just exposing a raw FK id."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ['id', 'user', 'role', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'content', 'workspace', 'created_by', 'status', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class DocumentVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentVersion
        fields = ['id', 'document', 'content', 'version_number', 'saved_by', 'saved_at']
        read_only_fields = ['id', 'version_number', 'saved_at']


class DocumentStatsSerializer(serializers.Serializer):
    """Response shape for GET /api/documents/{id}/stats/."""

    version_count = serializers.IntegerField()
    comment_count = serializers.IntegerField()
    contributor_count = serializers.IntegerField()


class AddDocumentTagsSerializer(serializers.Serializer):
    """Request body for POST /api/documents/{id}/tags/."""

    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=100), allow_empty=False
    )


class CommentSerializer(serializers.ModelSerializer):
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'document', 'author', 'content', 'parent', 'reply_count', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_reply_count(self, obj) -> int:
        return obj.replies.count()

    def validate(self, attrs):
        parent = attrs.get('parent')
        document = attrs.get('document')
        if parent is not None and document is not None and parent.document_id != document.id:
            raise serializers.ValidationError(
                {'parent': 'Parent comment must belong to the same document as the reply.'}
            )
        return attrs


class TagSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ['id', 'name', 'documents', 'document_count']
        read_only_fields = ['id']

    def get_document_count(self, obj) -> int:
        return obj.documents.count()

    def validate_name(self, value):
        normalized = value.strip().lower()
        if not normalized:
            raise serializers.ValidationError('Tag name cannot be blank.')
        return normalized


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'action', 'model_name', 'object_id', 'timestamp']
        read_only_fields = ['id', 'actor', 'action', 'model_name', 'object_id', 'timestamp']
