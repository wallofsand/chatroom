#!/usr/bin/env python3
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import asyncio
import tornado
import os.path
import uuid
import string
import json

from tornado.options import define, options, parse_command_line

define("port", default=8888, help="run on the given port", type=int)
define("debug", default=True, help="run in debug mode")

# location of the users and message database
script_dir = os.path.dirname(__file__)
user_db = os.path.join(script_dir, "db", "users")
msg_db = os.path.join(script_dir, "db", "msg")

def read_users(src):
    """Get the dict of users from the file at src."""
    users = {}
    with open(os.path.abspath(src), 'r', encoding="utf-8") as f:
        line = f.readline()
        while line != '':
            # trim trailing whitespace from passwords
            if line[-1] in string.whitespace:
                line = line[:-1]
            uname, pwd = line.split(',')
            if uname and pwd:
                users[uname] = pwd
            line = f.readline()
    return users

def write_user(dest, uname, pwd):
    """Write the dict users to the file at dest."""
    with open(os.path.abspath(dest), 'a', encoding="utf-8") as f:
        f.write(uname + ',' + pwd + '\n')

def log_msg(logfile, message):
    """Write messages to the text file at logfile"""
    filepath = os.path.abspath(logfile)
    with open(filepath, 'a', encoding="utf-8") as logf:
        json.dump(message, logf)
        logf.write("\n")

def read_messages(logfile):
    """Adds messages at src to cache.
    Run once at startup."""
    filepath = os.path.abspath(logfile)
    with open(filepath, 'r', encoding="utf-8") as logf:
        line = logf.readline()
        while line != '':
            yield json.loads(line)
            line = logf.readline()


class MessageBuffer(object):
    def __init__(self):
        # cond is notified whenever the message cache is updated
        self.cond = tornado.locks.Condition()
        self.cache = []
        self.cache_size = 200
        msg_count = 0
        print("Reading messages from database...")
        for msg in read_messages(msg_db):
            self.cache.append(msg)
            if len(self.cache) > self.cache_size:
                self.cache= self.cache[-self.cache_size :]
            msg_count += 1
        print("{} messages loaded.".format(msg_count))

    def get_messages_since(self, cursor):
        """Returns a list of messages newer than the given cursor.

        ``cursor`` should be the ``id`` of the last message received.
        """
        results = []
        for msg in reversed(self.cache):
            if msg["id"] == cursor:
                break
            results.append(msg)
        results.reverse()
        return results

    def add_message(self, message):
        self.cache.append(message)
        log_msg(msg_db, message)
        if len(self.cache) > self.cache_size:
            self.cache = self.cache[-self.cache_size :]
        print(message["sender"] + ": " + message["body"])
        self.cond.notify_all()

# Making this a non-singleton is left as an exercise for the reader.
global_message_buffer = MessageBuffer()


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_cookie("user")


class MainHandler(BaseHandler):
    def get(self):
        # if there is no user logged in
        if not self.current_user:
            self.redirect("/login")
            return
        self.render("index.html",
            messages=global_message_buffer.cache,
            username=self.current_user,
        )


class AutomataHandler(BaseHandler):
    def get(self):
        self.render("autocell.html")


class LoginHandler(BaseHandler):
    def get(self):
        self.render("login.html")

    def post(self):
        if self.get_argument("logout", None) != None:
            self.clear_cookie("user")
            self.redirect("/login")
            return
        uname = self.get_argument("uname")
        pwd = self.get_argument("pwd")
        users = read_users(user_db)
        if uname in users:
            if pwd == users[uname]:
                self.set_cookie("user", uname)
                self.redirect("/")
            else:
                self.redirect("/login")
        else:
            print("username not found")
            self.redirect("/login")

class CreateHandler(BaseHandler):
    def get(self):
        self.render("create.html")

    def post(self):
        uname = self.get_argument("uname")
        pwd = self.get_argument("pwd")
        conf = self.get_argument("conf")
        users = read_users(user_db)
        if uname in users:
            print("choose a new username")
            self.redirect("/login")
        else:
            if pwd == conf:
                write_user(user_db, uname, pwd)
                self.redirect("/login")
            else:
                print("passwords must be the same")


class MessageNewHandler(BaseHandler):
    """Post a new message to the chat room."""

    def post(self):
        message = {
            "id": str(uuid.uuid4()),
            "sender": self.get_current_user(),
            "body": self.get_argument("body")
        }
        # render_string() returns a byte string, which is not supported
        # in json, so we must convert it to a character string.
        message["html"] = tornado.escape.to_unicode(
            self.render_string("message.html", message=message)
        )
        if self.get_argument("next", None):
            self.redirect(self.get_argument("next"))
        else:
            self.write(message)
        global_message_buffer.add_message(message)


class MessageUpdatesHandler(BaseHandler):
    """Long-polling request for new messages.

    Waits until new messages are available before returning anything.
    """

    async def post(self):
        cursor = self.get_argument("cursor", None)
        messages = global_message_buffer.get_messages_since(cursor)
        while not messages:
            # Save the Future returned here so we can cancel it in
            # on_connection_close.
            self.wait_future = global_message_buffer.cond.wait()
            try:
                await self.wait_future
            except asyncio.CancelledError:
                return
            messages = global_message_buffer.get_messages_since(cursor)
        if self.request.connection.stream.closed():
            return
        self.write(dict(messages=messages))

    def on_connection_close(self):
        self.wait_future.cancel()


async def main():
    parse_command_line()
    app = tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/login", LoginHandler),
            (r"/create", CreateHandler),
            (r"/a/message/new", MessageNewHandler),
            (r"/a/message/updates", MessageUpdatesHandler),
            (r"/autocell", AutomataHandler)
        ],
        cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        xsrf_cookies=True,
        debug=options.debug,
    )
    app.listen(options.port)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
