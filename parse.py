import xml.etree.ElementTree as ET
from pprint import pprint
from collections import defaultdict

def parseXML(xmlfile):

    tree = ET.parse(xmlfile)
    root = tree.getroot()
    counts = {}
    for item in root.findall('./body/outline/outline[@type="rss"]'):
        print(item.attrib['text'])
        print(item.attrib)
        stats = defaultdict(int)
        if (len(item) > 0):
            for episode in item.findall('outline[@type="podcast-episode"]'):
                stats['total'] += 1
                for attr in episode.attrib:
                    try:
                        stats[attr] += int(episode.attrib[attr])
                    except Exception:
                        pass
        print(stats)
        break
#                print(item[0].tag, item[0].attrib)
#        print(item.tag, item.attrib)
#    for child in root:
#        print(child.tag, child.attrib)
#        for gchild in child:
#            print("\t", gchild.tag, gchild.attrib)
#            for ggchild in gchild:
#                print("\t\t", ggchild.tag, ggchild.attrib)


def main():
    parseXML('overcast.opml')

if __name__ == "__main__":
    main()
