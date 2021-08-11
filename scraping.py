from collections import defaultdict
import requests
from bs4 import BeautifulSoup
import pprint
from dateutil.parser import parse
from datetime import timedelta
import requests


# TODO: use cookie jar to only use password as needed
# TODO: treat opml file as cache and only refresh if older than a day
# TODO: cache rss feeds for a day


# ignore anything before this date
# TODO: need to source this from somewhere
oldest_unplayed = parse('2021-05-08 00:00:00 -0000')

LOGIN_URL = 'https://overcast.fm/login'
DOWNLOAD_URL = 'https://overcast.fm/account/export_opml/extended'
OPML_FILE = 'overcast.opml'

pp = pprint.PrettyPrinter(indent=4)

pattern = "%80s%6d%7d%9d%4d:%02d:%02d"
print('%80s%6s%7s%9s%10s' % ('title', 'total', 'played', 'unplayed', 'time'))

def fetch_opml():
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
        with open(OPML_FILE, 'w') as fp:
            print(r.text, file=fp)

def parse_opml(filename):
    podcasts = {} #defaultdict(dict)
    with open(OPML_FILE) as fp:
        soup = BeautifulSoup(fp, features='xml')
        urpod = podcasts['total'] = {
            'title': 'Total',
            'num_seen': 0,
            'total': 0,
            'num_unplayed': 0,
            'unplayed_duration': timedelta(),
        }
            
        for podcast in soup.find_all('outline', type='rss'):
            title = podcast['title']
#            if '60-Second' not in title:
#                continue
#            print(podcast.name, title)
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

#            print(title, 'seen', num_seen)
            episodes = pod['episodes'] = scrape_rss(pod['url'])
            total = pod['total'] = len(episodes)
            urpod['total'] += total

            unplayed = pod['unplayed'] = [ d for d in episodes if not seen.get(d['id']) and d['published'] > oldest_unplayed ]
            num_unplayed = pod['num_unplayed'] = len(unplayed)
            urpod['num_unplayed'] += num_unplayed

            unplayed_duration = pod['unplayed_duration'] = sum([ d['duration'] for d in unplayed ], timedelta())
            urpod['unplayed_duration'] += unplayed_duration


            print_pod(pod)
#            for e in unplayed:
#                print(e['published'], e['duration'], e['title'], sep="\t")

    # asciibetical order
    print("\nascii order\n")
    for pod in sorted(podcasts.values(), key=lambda x: remove_prefix(x.get('title'), 'The ')):
        print_pod(pod)

    # unplayed duration order
    print("\nduration order\n")
    for pod in sorted(podcasts.values(), key=lambda x: (x.get('unplayed_duration'), x.get('num_unplayed'))):
        print_pod(pod)

    return podcasts

def scrape_rss(feed):
    episode_list = []

#    print(f'Scraping {feed}')
    try:
        r = requests.get(feed)
        soup = BeautifulSoup(r.content, features='xml')

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
        return parse(pubDate.text, tzinfos={"PST":"UTC−08:00"})
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
    s = pod['unplayed_duration'].total_seconds()
    h, r = divmod(s, 3600)
    m, s = divmod(h, 60)
    print(pattern % (pod['title'], pod['total'], pod['num_seen'], pod['num_unplayed'], h, m, s))

def remove_prefix(text, prefix):
    return text[len(prefix):] if text.startswith(prefix) else text



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
