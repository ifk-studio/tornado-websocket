# -*- coding: utf-8 -*-

import json
import os
import random
import copy
import time
import datetime
import tornado
import tornado.gen
import tornadoredis
import momoko
import psycopg2

from global_variables import EVENT_TYPES, START_PVP_BOT_FIGHT
from phpserialize import loads

c = tornadoredis.Client()
c.connect()


class BaseHandlers():
    def __init__(self, websocket, *args, **kwargs):
        self.websocket = websocket


class UserChangesHandler(BaseHandlers):
    @tornado.gen.coroutine
    def send_user_changes(self, initial=False):
        """
        Requests postgres db for user stats, parse into apropriate json format and send it to user client.
        adds User relative events
        """
        try:
            fields = ['max_health', 'health', 'prestige', 'vd_balance', 'vg_balance', 'honor', 'city_id',
                      'energy', 'max_energy', 'delta_recovery_energy', 'last_up_energy', 'user_levels.level as level']

            user_fields_sql = "SELECT %s FROM users, user_levels WHERE users.id = user_levels.user_id AND users.id=%s;" \
                              % (', '.join(fields), self.websocket.id)

            cursor = yield momoko.Op(self.websocket.db.execute, user_fields_sql)
            cursor_data = cursor.fetchone()
            # get user city
            self.websocket.city_id = cursor_data[fields.index('city_id')]
            whole_info = map(prepare,
                             ('health', 'prestige', 'vdollars', 'vgold', 'honor'),
                             [
                                 cursor_data[fields.index('health')],
                                 cursor_data[fields.index('prestige')],
                                 cursor_data[fields.index('vd_balance')],
                                 round(cursor_data[fields.index('vg_balance')], 2),
                                 cursor_data[fields.index('honor')],
                             ],
                             [cursor_data[fields.index('max_health')], 0, 0, 0, 0])

            user_info = whole_info[:2]
            energy_info = prepare('energy', cursor_data[fields.index('energy')],
                                  cursor_data[fields.index('max_energy')])
            user_info.append(energy_info)

            progress_bar = [
                dict(
                    id='#health-bar',
                    value=round(min(100, (
                        cursor_data[fields.index('health')] / cursor_data[fields.index('max_health')] * 100))),

                    title=self.websocket.localization.translate("USERS_HEALTH") +
                          ": " + round_if_float(cursor_data[fields.index('health')]) +
                          "/" + round_if_float(cursor_data[fields.index('max_health')]),

                    info=round_if_float(cursor_data[fields.index('health')]) + "/" + round_if_float(
                        cursor_data[fields.index('max_health')])
                ),
                dict(
                    id='#energy-bar',
                    value=round(min(100, (float(cursor_data[fields.index('energy')]) / cursor_data[
                        fields.index('max_energy')]) * 100)),
                    title=self.websocket.localization.translate("USERS_ENERGY") +
                          ": " + round_if_float(cursor_data[fields.index('energy')]) +
                          "/" + round_if_float(cursor_data[fields.index('max_energy')]),
                    info=str(round_if_float(cursor_data[fields.index('energy')]))
                )
            ]

            money = whole_info[2:]
            self.websocket.write_message(
                json.dumps({'user_info': user_info,
                            'progress_bar': progress_bar,
                            'money': money,
                            'type': 'personal',
                            'level': cursor_data[fields.index('user_levels.level as level')]}))
            append_event_notification = False

            if (cursor_data[fields.index('health')] / cursor_data[fields.index('max_health')]) < 0.5:
                self.websocket.events['GAMEEVENT_USER_HEALTH'] = copy.deepcopy(EVENT_TYPES['GAMEEVENT_USER_HEALTH'])
                self.websocket.events['GAMEEVENT_USER_HEALTH']['message'] = self.websocket.localization.translate(
                    'GAMEEVENT_USER_HEALTH')
                append_event_notification = True
            elif self.websocket.events.get('GAMEEVENT_USER_HEALTH'):
                del self.websocket.events['GAMEEVENT_USER_HEALTH']
                append_event_notification = True

            if (cursor_data[fields.index('energy')] / cursor_data[fields.index('max_energy')]) < 0.5:
                self.websocket.events['GAMEEVENT_USER_RESTING'] = copy.deepcopy(EVENT_TYPES['GAMEEVENT_USER_RESTING'])
                self.websocket.events['GAMEEVENT_USER_RESTING']['message'] = self.websocket.localization.translate(
                    'GAMEEVENT_USER_RESTING')
                append_event_notification = True
            elif self.websocket.events.get('GAMEEVENT_USER_RESTING'):
                del self.websocket.events['GAMEEVENT_USER_RESTING']
                append_event_notification = True

            if (cursor_data[fields.index('vg_balance')] < 1) and (
                        cursor_data[fields.index('user_levels.level as level')] >= 7):
                self.websocket.events['GAMEEVENT_USER_BAYVGOLD'] = copy.deepcopy(EVENT_TYPES['GAMEEVENT_USER_BAYVGOLD'])
                self.websocket.events['GAMEEVENT_USER_BAYVGOLD']['message'] = self.websocket.localization.translate(
                    'GAMEEVENT_USER_BAYVGOLD')
                append_event_notification = True
            elif self.websocket.events.get('GAMEEVENT_USER_BAYVGOLD'):
                del self.websocket.events['GAMEEVENT_USER_BAYVGOLD']
                append_event_notification = True

            if append_event_notification and not initial:
                self.websocket.send_game_events()

        except Exception as error:
            self.websocket.write_message(str(error))

    @tornado.gen.coroutine
    def energy_timer(self, energy_info):
        energy = float(energy_info['energy'])
        max_energy = float(energy_info['max_energy'])

        energy_recovery_speed = energy_info['energy_recovery_speed']
        last_up_energy = energy_info['last_up_energy']

        energy_time_left = energy_next_recovery_point(energy_recovery_speed,
                                                      last_up_energy) - time.time() if energy < max_energy else 0

        self.websocket.write_message(json.dumps({'energyTimeLeft': energy_time_left, 'type': 'energy_timer'}))

    @tornado.gen.coroutine
    def get_user_messages_count(self):
        cursor_messages = yield momoko.Op(self.websocket.db.execute,
                                          "SELECT count(*) "
                                          "FROM messages "
                                          "WHERE user_id = %s AND read = 1;", (self.websocket.id,))
        cursor_messages_data = cursor_messages.fetchone()
        self.websocket.write_message(json.dumps({'messages': cursor_messages_data[0], 'type': 'message_count'}))

    @tornado.gen.coroutine
    def level_up(self):
        self.websocket.write_message(json.dumps({'type': 'level_up'}))


def energy_next_recovery_point(recovery_speed, last_recovery):
    points_amount = float(time.time() - last_recovery) // recovery_speed + 1  # operation '//' return int of division
    if points_amount <= 1:
        recovery_time_point = last_recovery + (points_amount * recovery_speed)
    else:
        recovery_time_point = 0.00
    return recovery_time_point


def prepare(name, value, max_value):
    color = ''
    value = float(value)
    if max_value > 0:
        color = 'green'
        percent = round(value, 2) / max_value
        if percent < 0.25:
            color = 'red'
        elif percent < 0.6:
            color = 'orange'

        value = round_if_float(value)
        max_value = round_if_float(max_value)

    return {'id': name, 'color': color, 'value': value, 'maxValue': max_value}


def round_if_float(float):
    return '{0:g}'.format(float)


def time_until_midnight():
    tomorrow = datetime.date.today() + datetime.timedelta(1)
    midnight = datetime.datetime.combine(tomorrow, datetime.time())
    now = datetime.datetime.now()
    return midnight - now


class EventHandler(BaseHandlers):
    @tornado.gen.coroutine
    def hide_events(self, initial=False):
        hided_keys = yield tornado.gen.Task(c.keys, pattern=('GameEvent.Hided:%s*' % self.websocket.id))
        redis_data = yield tornado.gen.Task(c.mget, hided_keys)
        for hide_group in redis_data:
            decoded_data = json.loads(hide_group)
            self.websocket.hidden_events = json.loads(decoded_data['data'])

        if not initial:
            pass

    @tornado.gen.coroutine
    def get_event_data(self, initial=False):
        """
        Gets all GameEvent* notifications from redis,
        and prepare data for notifications rendering
        """
        redis_keys = dict(
            global_keys=(yield tornado.gen.Task(c.keys, pattern='GameEvent.GameEvent.Global.*')),
            city_keys=(
                yield tornado.gen.Task(c.keys, pattern=('GameEvent.GameEvent.City.%s*' % self.websocket.city_id))),
            user_keys=(yield tornado.gen.Task(c.keys, pattern=('GameEvent.GameEvent.User.%s*' % self.websocket.id))))
        redis_data = dict()
        for keys_type, keys in redis_keys.iteritems():
            if keys:
                redis_data[keys_type] = yield tornado.gen.Task(c.mget, keys)
        for redis_data_group in redis_data.values():
            for event_group in redis_data_group:
                decoded_data = json.loads(event_group)
                # Parse events related to user
                event_name = decoded_data['id'].split('.')[-1]
                if not decoded_data.get('data'):
                    decoded_data['data'] = {}
                self.websocket.events[event_name] = decoded_data['data']
                # Add image, href and other additional info for notification icon rendering
                for additional_data_type, additional_data in copy.deepcopy(EVENT_TYPES[event_name]).iteritems():
                    self.websocket.events[event_name][additional_data_type] = additional_data

                event_message = self.websocket.localization.translate(event_name)

                if '{{username}}' in event_message:
                    self.substitute_username(event_message, decoded_data['data']['user_id'], event_name)

                elif '{{cityname}}' in event_message:
                    self.substitute_cityname(event_message, event_name)
                else:
                    self.websocket.events[event_name]['message'] = event_message

                if event_name == 'GAMEEVENT_USER_EXCHANGE':
                    self.exchange_info(event_message, decoded_data.get('data'))

        if not initial:
            self.websocket.send_game_events()

    @tornado.gen.coroutine
    def exchange_info(self, event_message, exchange_data):
        item_type_sql = "SELECT %s FROM item_types WHERE id=%s ;" % ('name_%s' % self.websocket.language,
                                                                     exchange_data.get('item_type'))

        cursor_item_type = yield momoko.Op(self.websocket.db.execute, item_type_sql)
        cursor_item_type_data = cursor_item_type.fetchone()

        self.websocket.events['GAMEEVENT_USER_EXCHANGE']['message'] = str(event_message) + '|' + str(
            exchange_data.get('username')) + ': ' + cursor_item_type_data[0] + '(' + str(
            exchange_data.get('amount')) + ')'

    @tornado.gen.coroutine
    def substitute_username(self, event_message, user_id, event_name):
        cursor_username = yield momoko.Op(self.websocket.db.execute,
                                          "SELECT username "
                                          "FROM users "
                                          "WHERE id=%s;", (user_id,))

        cursor_username_data = cursor_username.fetchone()
        self.websocket.events[event_name]['message'] = event_message.replace('{{username}}', cursor_username_data[0])

    @tornado.gen.coroutine
    def substitute_cityname(self, event_message, event_name):
        # print event_message
        cursor_cityname = yield momoko.Op(self.websocket.db.execute,
                                          "SELECT content "
                                          "FROM i18n "
                                          "WHERE model=%s AND field=%s AND foreign_key=%s AND locale=%s ;",
                                          ('City', 'name', self.websocket.city_id, self.websocket.localization.code))

        cursor_cityname_data = cursor_cityname.fetchone()
        # print cursor_cityname_data
        self.websocket.events[event_name]['message'] = event_message.replace('{{cityname}}', cursor_cityname_data[0])


    @tornado.gen.coroutine
    def get_manager_messages(self, initial=False):
        cursor = yield momoko.Op(self.websocket.db.execute,
                                 "SELECT id, vd_balance "
                                 "FROM companies "
                                 "WHERE user_id=%s", (self.websocket.id,))
        cursor_data = cursor.fetchall()
        if cursor_data:
            company_notifications = []
            for company in cursor_data:
                if company[1] < 10:
                    company_notifications.append(dict(company_id=company[0], msg='money'))
                    continue
                cursor_comp_items = yield momoko.Op(self.websocket.db.execute,
                                                    "SELECT count(*) "
                                                    "FROM companies "
                                                    "WHERE id=%s AND produced_items >= 1", (int(company[0]),))
                cursor_comp_items_data = cursor_comp_items.fetchone()
                if cursor_comp_items_data:
                    company_notifications.append(dict(company_id=company[0], msg='items'))
                    continue
            if company_notifications:
                self.websocket.events['GAMEEVENT_USER_COMPANY'] = copy.deepcopy(EVENT_TYPES['GAMEEVENT_USER_COMPANY'])
                self.websocket.events['GAMEEVENT_USER_COMPANY']['message'] = self.websocket.localization.translate(
                    'GAMEEVENT_USER_COMPANY')
                self.websocket.events['GAMEEVENT_USER_COMPANY']['company_msg'] = company_notifications
        if not initial:
            self.websocket.send_game_events()

    @tornado.gen.coroutine
    def get_user_quests(self, initial=False):
        # print('user_quests')
        cursor_quests = yield momoko.Op(self.websocket.db.execute,
                                        "SELECT * "
                                        "FROM user_quests "
                                        "WHERE user_id=%s", (self.websocket.id,))
        cursor_quests_data = cursor_quests.fetchone()

        if cursor_quests_data:
            self.websocket.events['GAMEEVENT_USER_QUEST'] = copy.deepcopy(EVENT_TYPES['GAMEEVENT_USER_QUEST'])
            self.websocket.events['GAMEEVENT_USER_QUEST']['message'] = self.websocket.localization.translate(
                'GAMEEVENT_USER_QUEST')
        # print('user_quests')
        if not initial:
            self.websocket.send_game_events()


    @tornado.gen.coroutine
    def get_broken_items(self, initial=False):

        if self.websocket.events.get('GAMEEVENT_USER_BROKENITEM'):
            del self.websocket.events['GAMEEVENT_USER_BROKENITEM']

        cursor_broken = yield momoko.Op(self.websocket.db.execute,
                                        "SELECT item_type_id "
                                        "FROM user_items "
                                        "WHERE user_id=%s AND equipped=1 AND strength=1;", (self.websocket.id,))
        cursor_broken_data = cursor_broken.fetchall()
        if cursor_broken_data:
            self.websocket.events['GAMEEVENT_USER_BROKENITEM'] = copy.deepcopy(EVENT_TYPES['GAMEEVENT_USER_BROKENITEM'])
            self.websocket.events['GAMEEVENT_USER_BROKENITEM']['item'] = ', '.join(
                [str(x[0]) for x in cursor_broken_data])

            broken_items_names = []
            for item in cursor_broken_data:
                item_type_sql = "SELECT %s FROM item_types WHERE id=%s ;" % (
                    'name_%s' % self.websocket.language, item[0])
                cursor_item_type = yield momoko.Op(self.websocket.db.execute, item_type_sql)
                cursor_item_type_data = cursor_item_type.fetchone()
                broken_items_names.append(cursor_item_type_data[0])

            self.websocket.events['GAMEEVENT_USER_BROKENITEM']['value'] = ', '.join(broken_items_names)
            self.websocket.events['GAMEEVENT_USER_BROKENITEM']['message'] = str(
                self.websocket.localization.translate('GAMEEVENT_USER_BROKENITEM')) + ': ' \
                                                                            + ', '.join(broken_items_names)

        if not initial:
            self.websocket.send_game_events()

    @tornado.gen.coroutine
    def get_not_answered_questions(self, initial=False):

        if self.websocket.events.get('GAMEEVENT_USER_QUESTIONS'):
            del self.websocket.events['GAMEEVENT_USER_QUESTIONS']
        cursor_not_answered_questions = yield momoko.Op(self.websocket.db.execute,
                                                        "SELECT questions.id, users_answered "
                                                        "FROM questions "
                                                        "WHERE active = 1 AND id NOT IN ("
                                                        "SELECT question_id "
                                                        "FROM answers "
                                                        "WHERE user_id = %s"
                                                        ");", (self.websocket.id,))
        cursor_not_answered_data = cursor_not_answered_questions.fetchall()
        cursor_not_answered_data[:] = [question for question in cursor_not_answered_data if
                                       not question[1] or self.determine_answered(question[1])]
        if cursor_not_answered_data:
            self.websocket.events['GAMEEVENT_USER_QUESTIONS'] = copy.deepcopy(EVENT_TYPES['GAMEEVENT_USER_QUESTIONS'])
            self.websocket.events['GAMEEVENT_USER_QUESTIONS']['message'] = str(
                self.websocket.localization.translate('GAMEEVENT_USER_QUESTIONS'))

        if not initial:
            self.websocket.send_game_events()

    def determine_answered(self, serialized_answers):
        unserialized_answers = loads(serialized_answers)
        return self.websocket.id not in unserialized_answers.values()


class SendEvent(BaseHandlers):
    def send_game_events(self):
        """
        Renders and writes to socket notifications div
        """
        render_events = copy.deepcopy(self.websocket.events)
        # Hide events that user closed

        visible_events = self.delete_hided_events(render_events)

        html_content = self.websocket.render_string('events.html', events=visible_events,
                                                    now=datetime.datetime.now, type_func=type)
        self.websocket.write_message(json.dumps({'events_html': html_content,
                                                 'type': 'events'}))

    def delete_hided_events(self, render_events):

        for hider, timestamp in self.websocket.hidden_events.iteritems():
            if hider in self.websocket.events and timestamp > time.time():
                del render_events[hider]

        return render_events


class UserFightsHandler(BaseHandlers):
    def trigger_fight_check(self, msg):
        """
        On fight info message trigger FightInformator() js function to get and show all relevant info to user
        """
        fight_inf = json.loads(msg)
        #  Check if message is for this instance of socket
        if self.websocket.id == fight_inf.get('user_id') or \
                        self.websocket.id == fight_inf.get('opponent'):

            status = fight_inf.get('status')
            response = {'type': 'fights', 'status': status}

            if status == 'join' and self.websocket.id == fight_inf.get('opponent'):
                response['action'] = 'wait_oponent'

            elif status == 'join' and self.websocket.id == fight_inf.get('user_id'):
                response['action'] = 'check_queue'

            elif status == 'left':
                response['action'] = 'empty'
                response['type'] = 'exit_fight'

            elif status == 'approved' and self.websocket.id == fight_inf.get('user_id'):
                response['action'] = 'wait'

            elif status == 'approved' and self.websocket.id == fight_inf.get('opponent'):
                response['action'] = 'wait'

            elif status == 'rejected':
                response['action'] = 'clear_oponent'
                response['type'] = 'exit_fight'

            elif status == 'end':
                response['action'] = 'fight_log'

            self.websocket.write_message(json.dumps(response))

    def trigger_band_fight(self, msg):
        """
        Triggers events on PVE fights
        """
        response = {'type': 'fights'}
        fight_inf = json.loads(msg)
        if self.websocket.id == fight_inf.get('user_id'):
            if fight_inf['status'] == 'approved':
                response['type'] = 'pve'

            elif fight_inf['status'] == 'left':
                response['action'] = 'empty'
                response['type'] = 'exit_fight'

            elif fight_inf['status'] == 'join':

                response['action'] = 'check_queue'
                self.websocket.write_message(json.dumps(response))

                time.sleep(START_PVP_BOT_FIGHT)

                response['action'] = 'start_pvpbot_fight/' + str(fight_inf['queueId']) + '/' + str(fight_inf['user_id'])
                response['type'] = 'process'

            self.websocket.write_message(json.dumps(response))

    def check_fighting(self):
        self.check_fight_queue()


    @tornado.gen.coroutine
    def check_fight_queue(self):
        """
        Checks if user is in any queues, and if in any, triggers appropriate events
        """
        cursor = yield momoko.Op(self.websocket.db.execute,
                                 "SELECT fight_queue_id, is_bot "
                                 "FROM fight_queue_members "
                                 "WHERE user_id	=%s AND status = %s;", (self.websocket.id, 'oponent'))

        cursor_data = cursor.fetchone()
        if cursor_data:
            #  If user is an opponent in a queue fight, show him to wait for approve of his fight request
            response = {'type': 'fights', 'action': 'check_queue'}
            self.websocket.write_message(json.dumps(response))

            cursor_bot = yield momoko.Op(self.websocket.db.execute,
                                         "SELECT fight_queue_id, is_bot "
                                         "FROM fight_queue_members "
                                         "WHERE fight_queue_id = %s AND is_bot = %s;", (cursor_data[0], 1))
            cursor_bot_data = cursor_bot.fetchone()
            if cursor_bot_data:
                #  If fight is against pvp-bot, show wait window for little bit time, than start PVP-Bot fight
                time.sleep(START_PVP_BOT_FIGHT)

                response['action'] = 'start_pvpbot_fight/' + str(cursor_bot_data[0]) + '/' + str(self.websocket.id)
                response['type'] = 'process'

                self.websocket.write_message(json.dumps(response))

        cursor_master = yield momoko.Op(self.websocket.db.execute,
                                        "SELECT count(*) "
                                        "FROM fight_queue_members "
                                        "WHERE fight_queue_id IN ("
                                        "SELECT fight_queue_id "
                                        "FROM fight_queue_members "
                                        "WHERE user_id	=%s AND status = %s);"
                                        , (self.websocket.id, 'master'))

        cursor_master_data = cursor_master.fetchall()

        if cursor_master_data[0][0] > 1:
            #  If user is master and somebody requested a fight, trigger approval window
            response = {'type': 'fights', 'action': 'wait_oponent'}
            self.websocket.write_message(json.dumps(response))


    @tornado.gen.coroutine
    def check_active_fight(self):
        cursor_fight = yield momoko.Op(self.websocket.db.execute,
                                       "SELECT * "
                                       "FROM fight_members "
                                       "WHERE user_id	=%s AND fight_id IN ("
                                       "SELECT id "
                                       "FROM fights "
                                       "WHERE status = %s OR status = %s); "
                                       # "AND band_fight is NULL);"
                                       , (self.websocket.id, 'active', 'processing'))
        cursor_fight_data = cursor_fight.fetchone()
        if cursor_fight_data[0]:
            response = {'type': 'fights', 'action': 'wait', 'fight_id': cursor_fight_data}
            self.websocket.write_message(json.dumps(response))
