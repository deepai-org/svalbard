import sys, json, collections, xml.etree.ElementTree as ET
c = collections.Counter()
for ev, el in ET.iterparse(sys.argv[1]):
    if el.tag == 'item':
        cat = el.findtext('category') or ''
        c[cat.strip("'").split(':')[0].strip("' ")] += 1
        el.clear()
print(json.dumps(dict(total=sum(c.values()), rules=dict(sorted(c.items()))), indent=0))
