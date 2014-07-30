# -*- coding: utf-8 -*-

CHANNELS = {
    'game_events': u'game_events',  # json
    'user_quests': u'user_quests',  # user_quests->id
    'broken_items': u'broken_items',  # json
    'user_changes': u'users',  # users->id
    'fights': u'pvp',
    'band_fights': u'pve',
    'energy_timer': u'energy_timer',
    'level_up': u'level_up'

}

EVENT_TYPES = dict(
    GAMEEVENT_USER_WORKED=dict(image='1b.png'),
    GAMEEVENT_USER_HUNGRY=dict(image='2b.png', href='/users/inventory'),
    GAMEEVENT_USER_HEALTH=dict(image='3d.png', href='/hospitals/index'),
    GAMEEVENT_USER_BROKENITEM=dict(image='4b.png', href='/users/inventory'),
    GAMEEVENT_USER_ONEBULLET=dict(image='5.gif', href='/users/inventory'),
    GAMEEVENT_CITY_BIGFIGHT=dict(image='6a.png', caption='timer', href='/big_fights/index'),
    GAMEEVENT_CITY_ELECTIONS=dict(image='7a.png', caption='timer', href='/city_hall/index/3'),
    GAMEEVENT_USER_BAYVGOLD=dict(image='8a.png', href='/bank/index'),
    GAMEEVENT_CITY_SPORT=dict(image='9a.png', caption='timer', href='/sport_activities/'),
    GAMEEVENT_USER_QUEST=dict(image='10a.png', href='/quests/quests/user_quests'),
    GAMEEVENT_USER_EXCHANGE=dict(image='11a.png'),
    GAMEEVENT_USER_COMPANY=dict(image='12a.png', href='/business/index'),
    GAMEEVENT_USER_RESTING=dict(image='13a.png', href='/users/inventory'),
    GAMEEVENT_GLOBAL_MEDAL=dict(image='globalA.png'),
    GAMEEVENT_GLOBAL_NEWCOMPANY=dict(image='14a.png'),
    GAMEEVENT_GLOBAL_NEWCORPORATION=dict(image='15a.png'),
    GAMEEVENT_GLOBAL_USERLICENCE=dict(image='16a.png'),
    GAMEEVENT_GLOBAL_DOCLICENCE=dict(image='16a.png'),
    GAMEEVENT_CITY_LAVVALUE=dict(image='17a.png', href='/city_hall/index'),
    GAMEEVENT_GLOBAL_NEWS=dict(image='achtungA.png'),
    GAMEEVENT_GLOBAL_SUGGESTIONS=dict(image='12a.png', href='/suggestions/index'),
    GAMEEVENT_USER_QUESTIONS=dict(image='achtungA.png', href='/marts/index')

)

START_PVP_BOT_FIGHT = 5

MESSAGE = "{\"id\":\"Hided:6\",\"data\":{\"GAMEEVENT_USER_HEALTH\":1394814654,\"GAMEEVENT_USER_QUEST\":1394815486}}"