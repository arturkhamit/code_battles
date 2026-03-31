from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "password1", "password2")

    def validate(self, attrs):
        if len(attrs["username"]) < 5:
            raise serializers.ValidationError(
                {"username": "Username has to be at least 5 characters long."}
            )
        if len(attrs["username"]) > 20:
            raise serializers.ValidationError(
                {"username": "Username has to be less then 20 characters long."}
            )
        if len(attrs["email"]) < 12:
            raise serializers.ValidationError(
                {"email": "Email has to be at least 12 characters long."}
            )
        if len(attrs["email"]) > 100:
            raise serializers.ValidationError(
                {"email": "Email has to be less then 100 characters long."}
            )
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        if len(attrs["password1"]) < 8:
            raise serializers.ValidationError(
                {"password1": "Password has to be at least 8 characters long."}
            )
        if len(attrs["password1"]) > 256:
            raise serializers.ValidationError(
                {"password1": "Password has to be less then 256 characters long."}
            )

        if User.objects.filter(username=attrs["username"]).exists():
            raise serializers.ValidationError(
                {"username": "This username is already taken."}
            )
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError({"email": "This email is already taken."})

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password1")
        validated_data.pop("password2")

        user = User.objects.create_user(password=password, **validated_data)
        return user
