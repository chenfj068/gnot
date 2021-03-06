from jinja2 import Markup

from db import export_sql


def render(vis, request, info):
    info["message"] = []
    table = request.args.get("table", '')
    field = request.args.get("field", '')
    where = request.args.get("where", '1=1')
    reload = int(request.args.get("reload", 0))
    view = request.args.get("view", '')
    start = request.args.get("start", '0')  # start at 0
    limit = request.args.get("limit", '5000')

    xField = request.args.get("xField", '')
    groupby = request.args.get("groupBy", '')
    if groupby and len(groupby) > 0:
        groupby = ' group by ' + groupby

    if len(table) == 0 or len(xField) == 0 or len(field) == 0:
        info["message"].append("Table or field missing.")
        info["message_class"] = "failure"
    else:

        sql = "select %s, %s from %s where %s %s order by 1 limit %s offset %s" % (
        xField, field, table, where, groupby, limit, start)
        header = "Date,%s" % field
        (datfile, reload, result) = export_sql(sql, vis.config, reload, header, view)
        if len(result) > 0:
            info["message"].append(result)
            info["message_class"] = "failure"
        else:
            info["message_class"] = "success"
            if reload > 0:
                info["message"].append("Loaded fresh.")
            else:
                info["message"].append("Loading from cache. Use reload=1 to reload.")

            info["datfile"] = datfile

    pfield = request.args.get("pfield", [])
    info["title"] = "FIELDS: <em>%s</em> from <br />TABLE: <em>%s</em>" % (','.join(pfield), table)
    info["title"] = Markup(info["title"])

    info["message"] = Markup(''.join('<p>%s</p>' % m for m in info["message"] if len(m) > 0))


	