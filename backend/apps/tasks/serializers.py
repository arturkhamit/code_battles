from rest_framework import serializers


class TestCasesSerializer(serializers.Serializer):
    input = serializers.ListField(
        child=serializers.CharField(allow_blank=True), allow_empty=True
    )
    output = serializers.ListField(
        child=serializers.CharField(allow_blank=True), allow_empty=True
    )


class SolutionsSerializer(serializers.Serializer):
    language = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
    solution = serializers.ListField(
        child=serializers.CharField(allow_blank=True), allow_empty=True
    )


class TaskImportSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()

    public_tests = TestCasesSerializer()
    private_tests = TestCasesSerializer()
    generated_tests = TestCasesSerializer()

    source = serializers.IntegerField(required=False, allow_null=True)
    difficulty = serializers.IntegerField(required=False, allow_null=True)

    solutions = SolutionsSerializer()
    incorrect_solutions = SolutionsSerializer()

    cf_contest_id = serializers.IntegerField(required=False, allow_null=True)
    cf_index = serializers.CharField(required=False, allow_blank=True)
    cf_points = serializers.FloatField(required=False, allow_null=True)
    cf_rating = serializers.IntegerField(required=False, allow_null=True)
    cf_tags = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )

    is_description_translated = serializers.BooleanField(default=False)
    untranslated_description = serializers.CharField(required=False, allow_blank=True)

    time_limit = serializers.JSONField(required=False, allow_null=True)
    memory_limit_bytes = serializers.JSONField(required=False, allow_null=True)
    input_file = serializers.CharField(required=False, allow_blank=True)
    output_file = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        for test_type in ["public_tests", "private_tests", "generated_tests"]:
            tests = attrs.get(test_type)
            if tests and len(tests["input"]) != len(tests["output"]):
                raise serializers.ValidationError(
                    f"В {test_type} количество input ({len(tests['input'])}) "
                    f"не совпадает с количеством output ({len(tests['output'])})."
                )
        return attrs
