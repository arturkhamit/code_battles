from django.db import transaction

from apps.accounts.models import Profile


def create_profile(user_id: int):
    with transaction.atomic():
        new_profile = Profile.objects.create(
            user_id=user_id,
        )

        new_profile.save()
    return new_profile
