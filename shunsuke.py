#!/usr/bin/python3

import os
import sys
import json
import sqlite3
import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


def timestamp():
    import time
    return int(time.time())

def connect():
    return sqlite3.connect("instance/data.db")

def parse_time(tm):
    toks = tm.split(" ")
    if len(toks) != 2:
        return None

    cnt = None
    try:
        cnt = int(toks[0])
    except:
        return None

    if toks[1].lower() in ["y", "year", "years", "yr"]:
        return timestamp() + cnt * datetime.timedelta(days=365).total_seconds()
    if toks[1].lower() in ["mon", "month", "months"]:
        return timestamp() + cnt * datetime.timedelta(days=30).total_seconds()
    if toks[1].lower() in ["h", "hr", "hour", "hours"]:
        return timestamp() + cnt * 3600
    if toks[1].lower() in ["m", "min", "mins"]:
        return timestamp() + cnt * 60
    if toks[1].lower() in ["s", "sec", "secs"]:
        return timestamp() + cnt
    return None

# /help
def help_command(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text="Hello")

# /tickle
def tickle(bot, update, job_queue):
    user = update.message.chat_id

    set_state(user, {"state": "tickle_read_message"})
    bot.sendMessage(chat_id=user, text="Now send me the message")
    #add_tickle(bot, user, "Tickle!", timestamp() + 20, job_queue)
    #bot.sendMessage(chat_id=user, text="OK")

def tickle_read_message(bot, update, job_queue, state):
    msg = update.message
    user = update.message.chat_id
    
    if hasattr(msg, "text"):
        set_state(user, {"state": "tickle_read_time", "msg": msg.text})
        bot.sendMessage(chat_id=user, text="Now send the time")

def tickle_read_time(bot, update, job_queue, state):
    msg = update.message
    user = update.message.chat_id
    
    if hasattr(msg, "text"):
        tm = parse_time(msg.text)

        if tm != None:
            set_state(user, None)
            bot.sendMessage(chat_id=user, text="OK")
            add_tickle(bot, user, state["msg"], tm, job_queue)

STATES = {"tickle_read_message": tickle_read_message,
          "tickle_read_time": tickle_read_time}

    
def text_handle(bot, update, job_queue):
    user = update.message.chat_id
    state = get_state(user)

    if state == None:
        bot.sendMessage(chat_id=user, text="Didn't understand that")
    else:
        name = state["state"]
        if name in STATES:
            STATES[name](bot, update, job_queue, state)

def set_state(user, state):
    with connect() as db:
        c = db.cursor()

        state_s = (None if state == None else json.dumps(state))
        c.execute("insert or replace into users values (?, ?)", (user, state_s))
        db.commit()

def get_state(user):
    with connect() as db:
        c = db.cursor()
        for (state,) in c.execute("select state from users where user = ?", (user,)):
            if state == None:
                return None
            else:
                return json.loads(state)

        return None
    
def add_tickle(bot, user, message, when, job_queue):
    with connect() as db:
        c = db.cursor()
        c.execute('''insert into tickle values (NULL, ?, ?, ?)''', (when, user, message))
        
        db.commit()
        job_queue.run_once(reload_database, -1)

def print_tickle(bot, job):
    with connect() as db:
        no = job.context
        
        c = db.cursor()
        
        for (user, message) in c.execute('''select user, message from tickle where id = ?''', (no,)):
            bot.sendMessage(chat_id=user, text=message)
        
            c.execute('''delete from tickle where id = ?''', (no,))
            db.commit()

def reload_database(bot, job):
    with connect() as db:
        c = db.cursor()

        tm = timestamp() + 120
        for (no,time,) in c.execute('''select id, time from tickle where time <= ?''', (tm,)):
            job.job_queue.run_once(print_tickle, time - timestamp(), no)

def init():
    global cfg
    cfg = None
    with open("instance/config.json") as fp:
        cfg = json.load(fp)

    with connect() as db:
        c = db.cursor()
        c.execute('''create table if not exists tickle
        (id integer primary key, time int not null, user int not null, message text not null)''')

        c.execute('''create table if not exists users
        (user int primary key, state text)''')
        
        
        db.commit()

    updater = Updater(token=cfg['TOKEN'])
    updater.dispatcher.add_handler(CommandHandler('start', help_command))
    updater.dispatcher.add_handler(CommandHandler('help', help_command))
    updater.dispatcher.add_handler(CommandHandler('tickle', tickle, pass_job_queue=True))
    updater.dispatcher.add_handler(MessageHandler(None, text_handle, pass_job_queue=True))
    updater.dispatcher.add_error_handler(error)
    
    bot = updater.bot
    job_queue = updater.job_queue

    job_queue.run_once(reload_database, -1)
    job_queue.run_repeating(reload_database, 60)
    
    updater.start_polling()

if __name__ == '__main__':
    init()
