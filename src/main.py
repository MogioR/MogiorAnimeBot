import re
import difflib
import telebot
import random
import time
import os
import uuid

from modules.parsers.ShikimoriParser import ShikimoriParser

bot = telebot.TeleBot(os.environ['TELEGRAM_API_KEY'])

chats_context = {}
games = {}
chat_to_games = {}
command_state = {}


# chats_context = {
#     'chat_id': {
#         'user_id': ['Name', 'list', Score],
#         'user_id': ['Name', 'list', Score]
#     }
# }
# games = {
#     uuid: True
# }
# chat_id_to_games = {
#     uuid: True
# }
# command_state = {
#     'chat_id': {
#       'user_id': 'state'
#      }
# }

def normalise_srt(a: str) -> str:
    return re.sub('[^a-zа-яё]', '', a.lower())


def check_answer(true_answer: str, answer: str) -> bool:
    if len(true_answer) > 6:
        blocks = difflib.SequenceMatcher(
            None,
            normalise_srt(true_answer),
            normalise_srt(answer)
        ).get_matching_blocks()
        if sum([block.size for block in blocks])/len(true_answer) > 0.5:
            return True
        else:
            return False
    else:
        return normalise_srt(true_answer) == normalise_srt(answer)


def get_hint(original: str, n: int) -> str:
    if len(original) > 7:
        n = int(len(original) / 7 * n)

    new_str = ['_' if ch != ' ' else ch for ch in original]
    for i in range(n):
        b = random.randrange(len(original))
        new_str[b] = original[b]
    return ''.join(new_str)


def register_list(chat, user, anime_list):
    try:
        anime_list = anime_list
        ShikimoriParser.get_titles_by_list_url(anime_list)
    except:
        return False

    if chat.id not in chats_context.keys():
        chats_context[chat.id] = {}
    if user.id not in chats_context[chat.id].keys():
        chats_context[chat.id][user.id] = [
            user.username,
            anime_list,
            0
        ]
    else:
        chats_context[chat.id][user.id][1] = anime_list
    return True


def get_tiles(chat):
    titles_set = []
    for user in chats_context[chat.id].values():
        if user[1] is not None:
            try:
                titles = ShikimoriParser.get_titles_by_list_url(user[1])
                titles_list = []
                if 'Completed' in titles.keys():
                    titles_list = titles['Completed']

            except Exception as e:
                bot.send_message(chat.id, 'Exeption: ' + str(e))
                bot.send_message(chat.id, 'At list: ' + user[1])
                continue
            titles_set += titles_list

    return list(titles_set)


def get_title_data(chat, title_id):
    try:
        return ShikimoriParser.get_title_info_by_id(title_id)
    except Exception as e:
        bot.send_message(chat.id, 'Exeption: ' + str(e))
        bot.send_message(chat.id, 'At title: ' + title_id)
        return None


def create_game(chat, title_data):
    if chat.id in chat_to_games.keys():
        return None
    else:
        game_id = uuid.uuid4()
        chat_to_games[chat.id] = game_id
        games[game_id] = [True, title_data]
        return game_id


def end_game(chat):
    if chat.id in chat_to_games.keys():
        games[chat_to_games[chat.id]][0] = False
        del chat_to_games[chat.id]


def close_game(chat, game_id):
    end_game(chat)
    del games[game_id]


def send_statistic(chat):
    if chat.id in chats_context.keys():
        score_strings = []
        for user_id in chats_context[chat.id].keys():
            score_strings.append(
                chats_context[chat.id][user_id][0] + ' отгадал ' + str(chats_context[chat.id][user_id][2]) + ' раз'
            )
        bot.send_message(chat.id, 'Статистика: \n' + '\n'.join(score_strings))


def set_state(chat, user, state):
    if chat.id not in command_state.keys():
        command_state[chat.id] = {}
    command_state[chat.id][user.id] = state


def get_state(chat, user):
    if chat.id not in command_state.keys():
        return None
    if user.id not in command_state[chat.id].keys():
        return None
    return command_state[chat.id][user.id]


def up_score(chat, user, score):
    if chat.id not in chats_context.keys():
        chats_context[chat.id] = {}
    if user.id not in chats_context[chat.id].keys():
        chats_context[chat.id][user.id] = [
            user.username,
            None,
            1
        ]
    else:
        chats_context[chat.id][user.id][2] += score


@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    message_text = message.text.replace('@MogiorAnimeBot', '')
    message_data = message_text.split()
    if message_data[0] == "/set_anime_list":
        if len(message_data) == 2:
            if register_list(message.chat, message.from_user, message_data[1]):
                bot.send_message(message.chat.id, "Лист установлен")
            else:
                bot.send_message(message.chat.id, "Лист не доступен")
        else:
            bot.send_message(message.chat.id, "Напиши shikimori list url для установки аниме листа")
            set_state(message.chat, message.from_user, 'set_anime_list')

    elif message_data[0] == "/help":
        bot.send_message(message.chat.id, "Напиши:\n"
                                          "/set_anime_list (shikimori_list_url) для установки аниме листа\n"
                                          "/start для начала игры")
    elif message_data[0] == "/start":
        if message.chat.id not in chats_context.keys():
            bot.send_message(message.chat.id, "Напиши:\n"
                                              "/set_anime_list (shikimori_list_url) для установки аниме листа")
            return

        titles = get_tiles(message.chat)
        if len(titles) == 0:
            bot.send_message(message.chat.id, "В листах не найдено аниме.")
            return

        title = random.choice(titles)
        title_data = get_title_data(message.chat, title['id'])

        game_id = create_game(message.chat, title_data)
        if game_id is None:
            bot.send_message(message.chat.id, "Игра уже идет.")
            return

        screens = 0
        for screen in title_data['screens']:
            screens += 1
            if screens > 3:
                break
            if games[game_id][0]:
                bot.send_photo(message.chat.id, screen)
            else:
                return
            time.sleep(10)

        for i in range(5):
            time.sleep(10)
            if games[game_id][0]:
                bot.send_message(
                    message.chat.id,
                    get_hint(title_data['names'][0], i)
                )
            else:
                return

        bot.send_photo(message.chat.id, title_data['poster'])
        bot.send_message(message.chat.id, str(title_data['names']))
        send_statistic(message.chat)

        close_game(message.chat, game_id)
    elif message_data[0] == "/skip":
        if message.chat.id in chat_to_games.keys():
            title_data = games[chat_to_games[message.chat.id]][1]
            bot.send_photo(message.chat.id, title_data['poster'])
            bot.send_message(message.chat.id, str(title_data['names']))
            send_statistic(message.chat)
            end_game(message.chat)
    elif message_data[0] == "/stats":
        send_statistic(message.chat)
    else:
        if get_state(message.chat, message.from_user) == 'set_anime_list':
            if register_list(message.chat, message.from_user, message_data[0]):
                bot.send_message(message.chat.id, "Лист установлен")
            else:
                bot.send_message(message.chat.id, "Лист не доступен")
            set_state(message.chat, message.from_user, 'game')
        else:
            if message.chat.id in chats_context.keys():
                if message.chat.id in chat_to_games.keys():
                    title_data = games[chat_to_games[message.chat.id]][1]
                    for name in title_data['names']:
                        if check_answer(name, message.text):
                            up_score(message.chat, message.from_user, 1)
                            bot.send_message(message.chat.id, 'Правильно!')
                            bot.send_photo(message.chat.id, title_data['poster'])
                            bot.send_message(message.chat.id, str(title_data['names']))
                            send_statistic(message.chat)

                            end_game(message.chat)


bot.polling(none_stop=True, interval=0)
