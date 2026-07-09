from rest_framework import serializers
from django.contrib.auth.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    company_name = serializers.CharField(write_only=True, required=True, max_length=255)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'company_name')
        extra_kwargs = {'email': {'required': True}}

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def create(self, validated_data):
        company_name = validated_data.pop('company_name')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.company_name = company_name
        user.save()
        return user
