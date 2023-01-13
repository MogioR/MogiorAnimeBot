import requests
import re

from .SourceParser import SourceParser
from bs4 import BeautifulSoup

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 YaBrowser/22.11.5.715 Yowser/2.5 Safari/537.36'
}


class ShikimoriParser(SourceParser):
    @staticmethod
    def get_title_info_by_id(title_id: str):
        return ShikimoriParser.get_title_info_by_url('https://shikimori.one/animes/' + title_id)

    @staticmethod
    def get_title_info_by_url(title_url: str):
        title_page = requests.get(title_url, headers=headers)
        bs = BeautifulSoup(title_page.text, 'html.parser')

        facts = {}

        left_info = bs.find('div', {'class': 'c-info-left'})
        info_right = bs.find('div', {'class': 'c-info-right'})
        info_block = left_info.find('div', {'class': 'b-entry-info'})
        info = info_block.find_all('div', {'class': 'line-container'}, recursive=False)

        # Main info
        for info_line in info:
            fact = ShikimoriParser.line_container_get_fact(info_line)
            facts = {**facts, **fact}

        # Rating_score
        facts['rating_score'] = info_right.find('meta', {'itemprop': 'ratingValue'}).attrs['content']

        # Studio_name
        facts['studio_name'] = info_right.contents[1].contents[1].a.attrs['title']

        # Poster
        facts['poster'] = bs.find('div', {'class': 'c-poster'}).img.attrs['src']

        # Description
        facts['description'] = bs.find('div', {'itemprop': 'description'}).text

        # Description
        facts['status'] = bs.find('span', {'class': 'b-anime_status_tag'}).attrs['data-text']

        # Name
        facts['names'] = [name.strip() for name in bs.find('header', {'class': 'head'}).h1.text.split('/')]
        main_name = facts['names'][0]

        names_page = requests.get(title_url + '/other_names', headers=headers)
        names_bs = BeautifulSoup(names_page.text, 'html.parser')
        info = names_bs.find('section', {'class': 'l-page'}).div.contents

        names = {}
        for info_line in info:
            names_line = ShikimoriParser.line_container_get_fact(info_line)
            names = {**names, **names_line}
        for name in names.values():
            if type(name) is str:
                facts['names'].append(name)
            else:
                facts['names'] += name
        buf = set(facts['names'])
        buf.discard(main_name)
        facts['names'] = [main_name] + list(buf)

        # Screens
        screens_page = requests.get(title_url + '/resources', headers=headers)
        screens_bs = BeautifulSoup(screens_page.text, 'html.parser')
        screens = []
        screen_tags = screens_bs.find('div', {'class': 'c-screenshots'}).find('div', {'class': 'cc'}).contents
        for tag in screen_tags:
            screens.append(tag.attrs['href'])
        facts['screens'] = screens

        return ShikimoriParser.format_title_info(facts)

    @staticmethod
    def get_titles_by_list_url(list_url: str):
        list_page = requests.get(list_url, headers=headers)
        bs = BeautifulSoup(list_page.text, 'html.parser')
        list_categories_block_content = \
            bs.find('div', {'class': 'l-content'}).find('div', {'class': 'list-groups'}).contents
        list_categories = \
            [list_categories_block_content[i:i + 4] for i in range(0, len(list_categories_block_content), 4)]

        anime_list = {}
        for category in list_categories:
            category_data = ShikimoriParser.get_category_data(category)

            anime_list = {**anime_list, **category_data}

        return anime_list

    @staticmethod
    def line_container_get_fact(line_container):
        key = line_container.div.contents[1].text
        if len(line_container.div.contents[3]) == 1:
            value = line_container.div.contents[3].text
        else:
            value = []
            for tag in line_container.div.contents[3]:
                value.append(tag.text)

        return {key: value}

    @staticmethod
    def format_title_info(title_info: dict) -> dict:
        subtypes = {
            'TV Сериал': 'series',
            'Фильм': 'film',
            'OVA': 'OVA',
            'ONA': 'ONA',
            'Спешл': 'special',
            'Клип': 'AMV',

        }

        formatted_title_info = {}
        if 'Тип:' in title_info.keys():
            if title_info['Тип:'] in subtypes.keys():
                formatted_title_info['subtype'] = subtypes[title_info['Тип:']]
                del title_info['Тип:']
            else:
                formatted_title_info['subtype'] = 'unknown'
                print('Error:', 'incorrect subtype', title_info['Тип:'])

        if 'Эпизоды:' in title_info.keys():
            raw_episodes = [e.strip() for e in title_info['Эпизоды:'].split('/')]
            if len(raw_episodes) == 1:
                formatted_title_info['episode_count'] = int(raw_episodes[0])
            else:
                formatted_title_info['current_episode'] = int(raw_episodes[0])
                if raw_episodes[1] != '?':
                    formatted_title_info['episode_count'] = int(raw_episodes[0])
                else:
                    formatted_title_info['episode_count'] = int(raw_episodes[0])
            del title_info['Эпизоды:']

        if 'Альтернативные названия:' in title_info.keys():
            del title_info['Альтернативные названия:']

        if 'Жанры:' in title_info.keys():
            formatted_title_info['tags'] = [re.sub('[А-ЯЁа-яё]', '', tag) for tag in title_info['Жанры:']]
            del title_info['Жанры:']

        if 'Рейтинг:' in title_info.keys():
            formatted_title_info['age_rating'] = []
            del title_info['Рейтинг:']

        return title_info

    @staticmethod
    def get_category_data(category: list) -> dict:
        if len(category) != 4:
            return {}
        category_name = ShikimoriParser.format_category_name(category[0].contents[2].text)
        category_titles = []

        table_anime = category[1].tbody.contents
        for anime_row in table_anime:
            category_titles.append({
                'id': anime_row.contents[1].a.attrs['href'].split('/')[-1],
                'score': float(anime_row.contents[2].text) if anime_row.contents[2].text != '–' else None
            })

        return {
            category_name: category_titles
        }

    @staticmethod
    def format_category_name(category_name: str)->str:
        if category_name == 'Запланировано':
            return 'Planning'
        elif category_name == 'Смотрю':
            return 'Watching'
        elif category_name == 'Просмотрено':
            return 'Completed'
        elif category_name == 'Отложено':
            return 'Paused'
        elif category_name == 'Брошено':
            return 'Dropped'
        else:
            return category_name
