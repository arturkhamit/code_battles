from django.urls import path

from apps.battles.views.battle_create import BattleCreateView
from apps.battles.views.battle_lobby import BattleInviteView, OpenBattlesView

urlpatterns = [
    path("create/", BattleCreateView.as_view(), name="create"),
    path("open/", OpenBattlesView.as_view(), name="open"),
    path("invite/<str:code>/", BattleInviteView.as_view(), name="invite"),
]
