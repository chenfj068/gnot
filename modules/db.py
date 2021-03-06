#!/usr/bin/python
import os

def export_sql(sql, config, reload=0, header=None, view=None, addHeader=False):
    hsql = hex(hash(sql + str(view)) & 0xffffffff)  # 32bit
    datfile = 'cache/%s_%s.csv' % (config.get("uid", ''), hsql)

    result = ''
    if reload > 0 or (not os.path.exists(os.path.realpath(datfile))):
        reload = 1
        if view and len(view) > 0:
            view_name = config.get("schema", '') + 'custom_view'
            view = "DROP VIEW IF EXISTS %s; CREATE VIEW %s as %s;" % (view_name, view_name, view)
            if config.get('db_system', '') == 'mysql':
                view = 'mysql %s %s %s --database %s -e "%s" ' % (
                    config.get("user", ''), config.get("passwd", ''), config.get("host", ''),
                    config.get("database", ''), view)
            elif config.get('db_system', '') == 'psql':
                view = 'psql %s %s %s -d %s -c "%s"' % (
                    config.get("port", ''), config.get("host", ''), config.get("user", ''),
                    config.get("database", ''), view)

            if not config.get("isProduction", ''): 
                print(view)
            sysresult = os.popen(view).close()
            if sysresult: 
                result += ' <p><strong>Error creating view! </strong></p><p>%s</p>' % sysresult

        if header:
            os.popen("echo '%s' > %s" % (header, datfile))
        else:
            os.popen("rm %s" % (datfile))  # make sure we are not appending to an existing file

        if addHeader:
            if config.get('db_system', '') == 'mysql':
                sql = 'mysql %s %s %s --database %s -e "%s" | sed "s/\\t/,/g" | grep -v "NULL" 2>&1 1>> %s' % (
                    config.get("user", ''), config.get("passwd", ''), config.get("host", ''), 
                    config.get("database", ''), sql, datfile)
            elif config.get('db_system', '') == 'psql':
                sql = 'psql %s %s %s -d %s -c "copy (%s) to stdout with CSV HEADER" 2>&1 1>> %s' % (
                    config.get("port", ''), config.get("host", ''), config.get("user", ''), 
                    config.get("database", ''), sql, datfile)

            elif config.get('db_system', '') == 'redshift':
                sql = 'psql %s %s %s -d %s -c "%s" | sed "s/ //g" | sed "s/|/,/g" | sed -n -e "/\,/{p;}" | grep -v "NULL" 2>&1 1>> %s' % (
                    config.get("port", ''), config.get("host", ''), config.get("user", ''), 
                    config.get("database", ''), sql, datfile)

        else:
            if config.get('db_system', '') == 'mysql':
                sql = 'mysql %s %s %s --database %s -e "%s" | sed "s/\\t/,/g" | grep -v "NULL" | tail -n +2 2>&1 1>> %s' % (
                    config.get("user", ''), config.get("passwd", ''), config.get("host", ''), 
                    config.get("database", ''), sql, datfile)
            elif config.get('db_system', '') == 'psql':
                sql = 'psql %s %s %s -d %s -c "copy (%s) to stdout with CSV" 2>&1 1>> %s' % (
                    config.get("port", ''), config.get("host", ''), config.get("user", ''),
                    config.get("database", ''), sql, datfile)
            elif config.get('db_system', '') == 'redshift':
                sql = 'psql %s %s %s -d %s -c "%s" | sed "s/ //g" | sed "s/|/,/g" | sed -n -e "/\,/{p;}" | tail -n +2 | grep -v "NULL" 2>&1 1>> %s' % (
                    config.get("port", ''), config.get("host", ''), config.get("user", ''), 
                    config.get("database", ''), sql, datfile)

        if not config.get("isProduction", ''): 
            print(sql)

        sysout = os.popen(sql)
        sysresult = sysout.read()
        if sysout.close():
            result += ' <p><strong>Error querying relation! </strong></p><p>%s</p>' % sysresult
            os.popen("rm %s" % (datfile)) # delete older files

    return (datfile, reload, result)
