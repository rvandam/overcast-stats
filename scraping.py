from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import timedelta
from dateutil.parser import parse
import distutils.util
import os
import pprint
import requests
import time


# TODO: use cookie jar to only use password as needed
# TODO: treat opml file as cache and only refresh if older than a day
# TODO: cache rss feeds for a day


LOGIN_URL = 'https://overcast.fm/login'
DOWNLOAD_URL = 'https://overcast.fm/account/export_opml/extended'
OPML_FILE = 'overcast.opml'

pp = pprint.PrettyPrinter(indent=4)

#pattern = "%80s%6d%7d%9d%4d:%02d:%02d"
pattern = "%80s%9d%5d:%02d:%02d%20s"


# ignore anything before this date
# TODO: need to source this from somewhere
#oldest_unplayed = parse('2021-09-08 00:00:00 -0000')
def get_oldest_unplayed():
    return parse(((os.environ.get('OLDEST') or '2021-09-08') + ' 00:00:00 -0000'))

def debug(*args):
    if bool(distutils.util.strtobool(os.environ.get('DEBUG') or '0')): print(*args)

def debug_title():
    return os.environ.get('TITLE') or ''

def no_cache():
    return bool(distutils.util.strtobool(os.environ.get('NO_CACHE') or '0'))


def print_header():
    #print('%80s%6s%7s%9s%10s' % ('title', 'total', 'played', 'unplayed', 'time'))
    print('%80s%9s%11s' % ('title', 'unplayed', 'time'))

def fetch_opml():

    if cache_ok(OPML_FILE, 12 * 60 * 60):
        return

    email = 'rvandam00@gmail.com'
    password = 'missing'
    with open('password.txt') as fp:
        password = fp.readline().strip()

    payload = {
        'email': email,
        'password': password,
    }

    with requests.Session() as s:
        p = s.post(LOGIN_URL, data=payload)

        r = s.get(DOWNLOAD_URL)
        # cache file locally
        with open(OPML_FILE, 'w') as fp:
            print(r.text, file=fp)

def parse_opml(filename):
    podcasts = {} #defaultdict(dict)
    with open(filename) as fp:
        soup = BeautifulSoup(fp, features='xml')
        urpod = podcasts['total'] = {
            'title': 'Total',
            'num_seen': 0,
            'total': 0,
            'limit': None,
            'num_unplayed': 0,
            'unplayed_duration': timedelta(),
        }
         
        print_header()
        limits = episode_limits()
        for podcast in soup.find_all('outline', type='rss'):
            title = podcast['title']
            if debug_title() not in title:
                continue
            debug(podcast.name, title)
            pod = podcasts[title] = {
                'title': title,
                'url': podcast['xmlUrl'],
                'seen': {}
            }
            for episode in podcast.find_all('outline', type="podcast-episode"):
                pod['seen'][episode['enclosureUrl']] = 1

            seen = pod['seen']
            num_seen = pod['num_seen'] = len(seen)
            urpod['num_seen'] += num_seen

            debug(title, 'seen', num_seen)
            episodes = pod['episodes'] = scrape_rss(pod['url'], podcast['overcastId'])

            limit = pod['limit'] = limits.get(title)
            pod['orig_total'] = len(episodes)
            if (limit):
                debug(f'Truncating to last {limit} episodes')
                episodes = episodes[0:limit]
            else:
                debug('No limit found')

            total = pod['total'] = len(episodes)
            urpod['total'] += total

            unplayed = pod['unplayed'] = [ d for d in episodes if not seen.get(d['id']) and d['published'] and d['published'] > get_oldest_unplayed() ]
            num_unplayed = pod['num_unplayed'] = len(unplayed)
            urpod['num_unplayed'] += num_unplayed

            unplayed_duration = pod['unplayed_duration'] = sum([ d['duration'] for d in unplayed ], timedelta())
            urpod['unplayed_duration'] += unplayed_duration


            print_pod(pod)
            for e in unplayed:
                debug(str(e['published']) + "\t" + str(e['duration']) + "\t" + e['title'])

    # asciibetical order
#    print("\nascii order\n")
#    print_header()
#    for pod in sorted(podcasts.values(), key=lambda x: remove_prefix(x.get('title'), 'The ')):
#        print_pod(pod)

    # unplayed duration order
    print("\nduration order\n")
    print_header()
    for pod in sorted(podcasts.values(), key=lambda x: (x.get('unplayed_duration'), x.get('num_unplayed'))):
        print_pod(pod)

    return podcasts

def scrape_rss(feed, id):
    episode_list = []

    debug(f'Scraping {feed}')
    try:

        filename = 'cache/' + id

        text = ''
        if cache_ok(filename, 60 * 60):
            with open(filename, 'r') as fp:
                text = fp.read()
        else:
            r = requests.get(feed, timeout=5)
            text = r.text
            with open(filename, 'w') as fp:
                print(text, file=fp)

        soup = BeautifulSoup(text, features='xml')

        episodes = soup.findAll('item')
        for e in episodes:
            itunes_title = e.find('itunes:title')
            title = e.find('title')
            title_text = (itunes_title or title).text
            enclosure = e.find('enclosure')
            enclosure_url = enclosure['url'] if enclosure else ''
            episode = {
                'id': enclosure_url or title_text,
                'title': title_text,
                'link': get_text(e.find('link')),
                'published': to_datetime(e.find('pubDate')),
                'guid': get_text(e.find('guid')),
                'duration': to_timedelta(e.find('itunes:duration'))
            }
            episode_list.append(episode)
        return episode_list
    except Exception as e:
        raise(e)
        print(f'The scraping job ({feed}) failed. See exception: ')
        print(e, e.line)

def get_text(tag):
    return tag.text if tag else ''

def to_datetime(pubDate):
    try:
        return parse(pubDate.text, tzinfos={"PST":"UTC−08:00"}) if pubDate.text else None
    except TypeError as e:
        print(pubDate)
        raise(e)

def to_timedelta(duration):
    if not duration:
        return timedelta()
    if not duration.text:
        return timedelta()

    try:
        nums = [int(x) for x in duration.text.split(':')]
        h, m, s = [0] * (3 - len(nums)) + nums
        return timedelta(hours=h, minutes=m, seconds=s)
    except Exception:
        #print('Failed to parse', duration)
        return timedelta()

def print_pod(pod):
    ts = pod['unplayed_duration'].total_seconds()
    h, r = divmod(ts, 3600)
    m, s = divmod(r, 60)
    #print(pattern % (pod['title'], pod['total'], pod['num_seen'], pod['num_unplayed'], h, m, s))
    print(pattern % (pod['title'], pod['num_unplayed'], h, m, s, f"(limit {pod['limit']})" if pod['limit'] else ''))

def remove_prefix(text, prefix):
    return text[len(prefix):] if text.startswith(prefix) else text

def cache_ok(filename, ttl):
    if no_cache():
        return False
    if os.path.isfile(filename):
        filetime = os.stat(filename).st_mtime
        seconds_ago = time.time() - filetime
        debug(f'Age of {filename} is {seconds_ago} (ttl: {ttl})')
        if seconds_ago < ttl:
            debug(f'Using cached {filename} file')
            return True
    return False

# FIXME: need to source this from somewhere
def episode_limits():
    return {
        'A Slight Change of Plans': 10,
        'A Podcast of Unnecessary Detail': 10,
        'A Slight Change of Plans': 10,
        'A Thoughtful Faith - Mormon / LDS': 10,
        'All the Hacks with Chris Hutchins': 10,
        'Another Name For Every Thing with Richard Rohr': 10,
        'Arrest DevOps': 10,
        'Articles and Investigations - ProPublica': 10,
        'Becoming Wise': 10,
        'BiggerPockets Money Podcast': 10,
        'BiggerPockets Real Estate Podcast': 10,
        'Code Switch': 10,
        'Death, Sex & Money': 10,
        'EconTalk': 10,
        'Extreme Genes - America\'s Family History and Genealogy Radio Show & Podcast': 5,
        'Generations Cafe': 5,
        'Hidden Brain': 10,
        'It\'s Been a Minute': 10,
        'Latter-day Faith': 10,
        'Mormon Discussions Podcasts – Full Lineup': 10,
        'Mormon Land': 10,
        'Mormon Stories - LDS': 10,
        'On Being with Krista Tippett': 10,
        'On The Market': 10,
        'On the Media': 10,
        'Questions from the Clost': 10,
        'Radio Free Mormon': 10,
        'RadioWest': 10,
        'Real Estate Rookie': 10,
        'Rent To Retirement: Building Financial Independence Through Turnkey Real Estate Investing': 10,
        'Rent To Retirement: Building Financial Independence': 10,
        'StarTalk Radio': 10,
        'Ten Percent Happier with Dan Harris': 10,
        'The Allusionist': 10,
        'The Genealogy Gems Podcast with Lisa Louise Cooke - Your Family History Show': 5,
        'The Genealogy Guys Podcast & Genealogy Connection': 5,
        'The Research Like a Pro Genealogy Podcast': 5,
        'This Day in Esoteric Political History': 10,
        'This Week in Virology': 10,
        'WTF with Marc Maron Podcast': 10,
        'You\'re Wrong About': 10,
    }


#print('Starting opml')
fetch_opml()
podcasts = parse_opml(OPML_FILE)
#print(len(podcasts))
#pp.pprint(podcasts)
#print('Finished opml')
#print('Starting scraping')
#scrape_rss('https://news.ycombinator.com/rss')
#scrape_rss('https://mormonstories.libsyn.com/rss')
#scrape_rss('https://rss.art19.com/id10t')
#print('Finished scraping')
