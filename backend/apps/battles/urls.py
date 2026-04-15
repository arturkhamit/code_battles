from django.urls import path

from apps.battles.views.battle_create import BattleCreateView
from apps.battles.views.battle_delete import BattleDeleteView
from apps.battles.views.battle_finish import BattleFinishView
from apps.battles.views.battle_join import BattleJoinView
from apps.battles.views.battle_leave import BattleLeaveView
from apps.battles.views.battle_start import BattleStartView
from apps.battles.views.battles import BattlesView

urlpatterns = [
    path("", BattlesView.as_view(), name="battles"),
    path("finish/<int:battle_id>/", BattleFinishView.as_view(), name="finish"),
    path("start/<int:battle_id>/", BattleStartView.as_view(), name="start"),
    path("join/<int:battle_id>/", BattleJoinView.as_view(), name="join"),
    path("leave/<int:battle_id>/", BattleLeaveView.as_view(), name="leave"),
    path("delete/<int:battle_id>/", BattleDeleteView.as_view(), name="delete"),
    path("create/", BattleCreateView.as_view(), name="create"),
]
