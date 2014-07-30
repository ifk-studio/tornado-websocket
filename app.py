# -*- coding: utf-8 -*-

import json
import os
import random
import tornado.httpserver
import tornado.web
import tornado.websocket
import tornado.ioloop
import tornado.gen
import tornado.locale
from tornado.options import define, options
import tornadoredis
import momoko
import psycopg2
from global_variables import CHANNELS, EVENT_TYPES, MESSAGE
from handlers import UserChangesHandler, EventHandler, SendEvent, UserFightsHandler
from system import compile_translations, compile_translations_err

define("port", default=8888, help="run on the given port", type=int)

c = tornadoredis.Client()
c.connect()

locale_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app/Locale'))
compile_translations(locale_dir)

tornado.locale.load_gettext_translations(locale_dir, 'default')

try:
    from database import SERVER_ADDRESS, set_database_settings
except ImportError:
    from database_default import SERVER_ADDRESS, set_database_settings


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("template.html",
                    title="PubSub + WebSocket Demo",
                    rand=random.randrange,
                    server_address=SERVER_ADDRESS)


def json_func(result):
    result = unicode(result)
    print(result)
    print(type(result))

    json_data = json.loads(result)
    print(json_data)


class NewMessageHandler(tornado.web.RequestHandler):
    def post(self):

        message_body = self.get_argument('message')
        private_message = self.get_argument('private')
        print(message_body)
        print(private_message)
        who_sent = self.get_argument('id')
        message = {'message': message_body, 'private_message': private_message, 'who_sent': who_sent}
        if private_message:
            c.publish(CHANNELS['user_changes'], private_message)
            compile_translations_err(self)
        if message_body:
            c.publish(CHANNELS['fights'], message_body)

        self.set_header('Content-Type', 'text/plain')
        self.write('sent: %s' % (message,))


class BaseHandler(tornado.websocket.WebSocketHandler):
    """
    Base class with postgres db connection for asynchronous requests.
    """

    @property
    def db(self):
        return self.application.db

    @property
    def blocking_db(self):
        return self.application.blocking_db


class MessageHandler(BaseHandler):
    """
    WebSockets routine.
    """

    online_users = {}

    def __init__(self, *args, **kwargs):
        super(MessageHandler, self).__init__(*args, **kwargs)
        self.client = tornadoredis.Client()
        self.ping_counter = 0

        self.id = None
        self.localization = ''
        self.language = ''

        self.events = {}
        self.hidden_events = {}

        user_data_handler_class = UserChangesHandler(self)
        self.send_user_changes = user_data_handler_class.send_user_changes
        self.get_user_messages_count = user_data_handler_class.get_user_messages_count
        self.energy_timer = user_data_handler_class.energy_timer
        self.level_up = user_data_handler_class.level_up

        event_handler_class = EventHandler(self)
        self.hide_events = event_handler_class.hide_events
        self.get_event_data = event_handler_class.get_event_data
        self.get_user_quests = event_handler_class.get_user_quests
        self.get_broken_items = event_handler_class.get_broken_items
        self.get_manager_messages = event_handler_class.get_manager_messages
        self.get_not_answered_questions = event_handler_class.get_not_answered_questions

        self.send_game_events = SendEvent(self).send_game_events

        fights_handler_class = UserFightsHandler(self)
        self.trigger_fight_check = fights_handler_class.trigger_fight_check
        self.check_fighting = fights_handler_class.check_fighting
        self.trigger_band_fight = fights_handler_class.trigger_band_fight

        self.listen()

    def open(self):
        """
        On socket open send initial values, and set user_id and user_localization
        """

        self.stream.set_nodelay(True)
        self.id = int(self.get_argument('id'))

        # Set localization
        self.language = self.get_argument('language')
        if self.language == 'ru':
            language = 'rus'
        else:
            language = 'eng'
        try:
            self.localization = tornado.locale.Locale.get(language)
        except:
            self.localization = tornado.locale.get(language)

        # Write logged user in list of online users
        if self.online_users.get(self.id):
            self.online_users[self.id].append(self)
        else:
            self.online_users[self.id] = [self]

        # Get user initial data and events, send it to page

        self.async_initial_wrapper(on_start=True)
        self.ping('PING')

    @tornado.gen.coroutine
    def async_initial_wrapper(self, on_start=False):
        # Send user stats and get events related to user stats
        yield tornado.gen.Task(self.send_user_changes, initial=True)
        yield tornado.gen.Task(self.get_user_messages_count)
        yield tornado.gen.Task(self.hide_events, initial=True)
        yield tornado.gen.Task(self.get_event_data, initial=True)
        yield tornado.gen.Task(self.get_user_quests, initial=True)
        yield tornado.gen.Task(self.get_broken_items, initial=True)
        yield tornado.gen.Task(self.get_manager_messages, initial=True)
        yield tornado.gen.Task(self.get_not_answered_questions, initial=True)
        if on_start:
            self.check_fighting()

        # Send all user events
        self.send_game_events()

    @tornado.gen.coroutine
    def listen(self):
        self.client.connect()
        yield tornado.gen.Task(self.client.subscribe, CHANNELS.values())

        self.client.listen(self.on_message)

    @tornado.gen.coroutine
    def on_message(self, msg):
        if msg == 'PING':
            self.ping('ping')
        try:
            if msg.kind == 'message':
                if msg.channel == CHANNELS['fights']:
                    self.trigger_fight_check(msg.body)

                elif msg.channel == CHANNELS['band_fights']:
                    self.trigger_band_fight(msg.body)

                elif msg.channel == CHANNELS['energy_timer']:
                    msg_inf = json.loads(msg.body)
                    if msg_inf.get('user_id') == self.id:
                        self.energy_timer(msg_inf)
                elif msg.channel == CHANNELS['level_up']:
                    msg_inf = json.loads(msg.body)
                    if msg_inf.get('user_id') == self.id:
                        self.level_up()
                else:
                    msg_inf = json.loads(msg.body)
                    if msg_inf.get('user_id') == self.id:
                        self.events = {}
                        yield tornado.gen.Task(self.hide_events, initial=True)
                        self.async_initial_wrapper()

            if msg.kind == 'disconnect':
                # Do not try to reconnect, just send a message back
                # to the client and close the client connection
                self.write_message('The connection terminated '
                                   'due to a Redis server error.')
                self.close()

        except AttributeError:
            message_data = json.loads(msg)
            print message_data
            print type(message_data)

    def on_close(self):
        if self.online_users.get(self.id):
            if self in self.online_users[self.id]:
                self.online_users[self.id].remove(self)
            if not self.online_users[self.id]:
                del self.online_users[self.id]
        if self.client.subscribed:
            for channel in CHANNELS:
                self.client.unsubscribe(CHANNELS[channel])
            self.client.disconnect()

    def on_pong(self, data):
        self.write_message(json.dumps({'type': 'PONG'}))


class OnlineUsers(object):
    pass


class Application(tornado.web.Application):
    def __init__(self):
        self.user_management = OnlineUsers()

        handlers = [
            (r'/', MainHandler),
            (r'/msg', NewMessageHandler),
            (r'/track', MessageHandler),
        ]

        settings = {
            'template_path': os.path.join(os.path.dirname(__file__), "templates"),
            'static_path': os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', 'app/View/Themed/OneFrame/webroot/img/')),
            'debug': True,
        }

        tornado.web.Application.__init__(self, handlers, **settings)


if __name__ == '__main__':
    tornado.options.parse_command_line()
    app = Application()
    app.db = momoko.Pool(
        dsn=set_database_settings(),
        size=1,
        max_size=10,
        setsession=("SET TIME ZONE UTC",),
        raise_connect_errors=False,
    )
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
