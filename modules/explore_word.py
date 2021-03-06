import os, json, csv
from collections import defaultdict
from jinja2 import Markup
from pstemmer import PorterStemmer
from db import export_sql

STOPWORDS = set(
    ['i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves',
     'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their',
     'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was',
     'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the',
     'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against',
     'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in',
     'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
     'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
     'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now', \
     'the', 'of', 'to', 'and', 'a', 'in', 'is', 'it', 'you', 'that', 'he', 'was', 'for', 'on', 'are', 'with', 'as', 'I',
     'his', 'they', 'be', 'at', 'one', 'have', 'this', 'from', 'or', 'had', 'by', 'hot', 'but', 'some', 'what', 'there',
     'we', 'can', 'out', 'other', 'were', 'all', 'your', 'when', 'up', 'use', 'word', 'how', 'said', 'an', 'each',
     'she', 'which', 'do', 'their', 'time', 'if', 'will', 'way', 'about', 'many', 'then', 'them', 'would', 'write',
     'like', 'so', 'these', 'her', 'long', 'make', 'thing', 'see', 'him', 'two', 'has', 'look', 'more', 'day', 'could',
     'go', 'come', 'did', 'my', 'sound', 'no', 'most', 'number', 'who', 'over', 'know', 'water', 'than', 'call',
     'first', 'people', 'may', 'down', 'side', 'been', 'now', 'find', 'any', 'new', 'work', 'part', 'take', 'get',
     'place', 'made', 'live', 'where', 'after', 'back', 'little', 'only', 'round', 'man', 'year', 'came', 'show',
     'every', 'good', 'me', 'give', 'our', 'under', '-', '_', '\'', '\'s', 'one', 'two', 'three', 'four', 'five', 'six',
     'seven', 'eight', 'nine', 'ten'])

def render(vis, request, info):
    info["message"] = []

    reload = int(request.args.get("reload", '0'))
    table = request.args.get("table", '')
    where = request.args.get("where", '1=1')
    field = request.args.get("field", '')
    view = request.args.get("view", '')
    minlen = request.args.get("MinCharLength", '3')
    rStopWords = int(request.args.get("RemoveStopWords", '0'))
    StemWords = int(request.args.get("StemWords", '0'))
    start = request.args.get("start", '0')  # start at 0

    limit = request.args.get("limit", '200')

    if len(table) == 0 or len(field) == 0:
        info["message"].append("table or field missing.")
        info["message_class"] = "failure"
    else:
        sql = "select word, count(*) as n from (select regexp_split_to_table(regexp_replace(lower(coalesce(%s,'')),'[^a-z0-9@]+',' ','g'),' ') as word, * from %s where %s) as a  where char_length(word) > %s group by 1 order by 2 desc limit %s offset %s" % (
        field, table, where, minlen, limit, start)

        (datfile, reload, result) = export_sql(sql, vis.config, reload, None, view)
        if len(result) > 0:
            info["message"].append(result)
            info["message_class"] = "failure"
        else:
            info["message_class"] = "success"
            if reload > 0:
                info["message"].append("Loaded fresh.")
            else:
                info["message"].append("Loading from cache. Use reload=1 to reload.")

        datfileNew = datfile + 'edited.csv'

        if reload:
            with open(datfile) as f:
                terms = csv.reader(f)
                #terms = map(lambda term: term(0).replace("'s",'').replace("'", '').replace(".", " ").replace(",", " "), terms)
                if rStopWords:
                    terms = filter(lambda term: term[0] not in STOPWORDS, terms)
                if StemWords:
                    p = PorterStemmer()
                    d = defaultdict(int)
                    for term in terms:
                        d[p.stem(term[0], 0, len(term[0]) - 1)] += int(term[1])
                    terms = d.items()

                header = ["text", "size"]
                with open(datfileNew, 'w') as f2:
                    cs = csv.writer(f2)
                    cs.writerow(header)
                    for term in terms:
                        cs.writerow(term)

        info["datfile"] = datfileNew

    pfield = request.args.get("pfield", [])
    info["title"] = "FIELDS: <em>%s</em> from <br />TABLE: <em>%s</em>" \
        % (','.join(pfield), table)
    info["title"] = Markup(info["title"])

    info["message"] = Markup(''.join('<p>%s</p>' % m for m in info["message"] if len(m) > 0))
