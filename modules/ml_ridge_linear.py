import re
import json
from math import log, sqrt

from jinja2 import Markup
from sklearn import linear_model
from sklearn.decomposition import PCA
from scipy import stats
from sklearn import metrics
import numpy

from db import export_sql

from werkzeug.wrappers import Response

# create higher order transformations
def x2fs(X, fields, type=''):
    if type == 'Interaction':
        s2 = lambda x: x + 1
        e2 = lambda x, y: y
    elif type == 'Quadratic':
        s2 = lambda x: x
        e2 = lambda x, y: y
    elif type == 'Purely Quadratic':
        s2 = lambda x: x
        e2 = lambda x, y: x + 1
    else:
        return

    l1 = len(X[0])
    l2 = len(X[0])

    for i in range(len(X)):
        r = X[i]
        for j1 in range(l1):
            for j2 in range(s2(j1), e2(j1, l2)):
                r.append(r[j1] * r[j2])

    for j1 in range(l1):
        for j2 in range(s2(j1), e2(j1, l2)):
            fields.append(fields[j1] + '*' + fields[j2])


#
# fit_transform from sklearn doesn't return the loadings V. Here is a hacked version
def fit_transform(pca, X):
    U, S, V = pca._fit(X)

    if pca.whiten:
        # X_new = X * V / S * sqrt(n_samples) = U * sqrt(n_samples)
        U *= sqrt(X.shape[0])
    else:
        # X_new = X * V = U * S * V^T * V = U * S
        U *= S
    # transposing component matrix such that PCA_1 is in row
    V = V.transpose()
    return (U, V)


def evaluate(predicted_matches, real_matches):
    rms = 0
    p_mean = 0
    r_mean = 0
    results = {}
    for i in range(len(predicted_matches)):
        rms += float(predicted_matches[i] - real_matches[i]) ** 2
        r_mean += predicted_matches[i]
        p_mean += real_matches[i]

    rms = sqrt(rms / len(predicted_matches))
    p_mean = p_mean / len(predicted_matches)
    r_mean = r_mean / len(real_matches)

    results['rms'] = rms
    results['p_mean'] = p_mean
    results['r_mean'] = r_mean
    return results


def render(vis, request, info):
    info["message"] = []
    info["results"] = []

    # module independent user inputs
    table = request.args.get("table", '')
    where = request.args.get("where", '1=1')
    limit = request.args.get("limit", '1000')
    start = request.args.get("start", '0')  # start at 0
    reload = int(request.args.get("reload", 0))
    view = request.args.get("view", '')

    #module dependent user inputs
    field = request.args.get("field", '')
    ratio = float(request.args.get("ratio", 0.9))
    regularizer = float(request.args.get("regularizer", 1))
    pre_process = request.args.get("pre_process", '')
    pre_transform = request.args.get("pre_transform", '')

    orderBy = request.args.get("orderBy", '')
    groupBy = request.args.get("groupBy", '')
    if groupBy and len(groupBy) > 0: groupBy = ' group by %s' % groupBy
    pfield = request.args.get("pfield", [])

    # verify essential parameter details - smell test
    if len(table) == 0 or len(field) == 0:
        info["message"].append("Table or field missing")
        info["message_class"] = "failure"
    else:
        # prepare sql query
        if orderBy and len(orderBy) > 0:
            orderbyMessage = ' ordered by %s' % orderBy
            orderBy = ' order by %s' % orderBy
        else:
            orderBy = ''
            orderbyMessage = 'ordered randomly'

        sql = "select %s from %s where %s %s %s limit %s offset %s"\
                % (field, table, where, groupBy, orderBy, limit, start)

        (datfile, reload, result) = export_sql(sql, vis.config, reload, None, view)

        if len(result) > 0:
            info["message"].append(result)
            info["message_class"] = "failure"
        else:
            X = []
            Y = []
            with open(datfile, 'r') as f:
                for r in f:
                    row = r.rstrip().split(',')
                    Y.append(float(row[0]))
                    X.append([float(r) for r in row[1:]])

            if ratio == 1:
                TrainingSize = 0
            else:
                TrainingSize = int(ratio * len(X))

            xfield = pfield[1:]
            x2fs(X, xfield, pre_transform)
            pfield = [pfield[0]] + xfield

            X = numpy.array(X)

            if pre_process == "Z-Score":
                X = stats.zscore(X, axis=0)
            elif pre_process == "PCA":
                pca = PCA()
                (X, V) = fit_transform(pca, X)
                pfield = [pfield[0]] + ['PCA_%d' % (d + 1) for d in range(len(pfield[1:]))]
            elif pre_process == "Whitened PCA":
                pca = PCA(whiten=True)
                (X, V) = fit_transform(pca, X)
                pfield = [pfield[0]] + ['PCA_%d' % (d + 1) for d in range(len(pfield[1:]))]


            #clf = svm.SVC(C=regularizer, kernel='linear', probability=True, random_state=0,verbose=False)
            #clf.fit(X[1:TrainingSize], Y[1:TrainingSize])
            #yhat = clf.decision_function(X[TrainingSize:])
            #yhat = [yhat[i][0] for i in range(len(yhat))]

            clf = linear_model.Ridge(alpha=regularizer)
            clf.fit(X[1:TrainingSize], Y[1:TrainingSize])
            yhat = clf.decision_function(X[TrainingSize:])

            # summary results
            results = evaluate(yhat, Y[TrainingSize:])
            info["results"].append(
                'Predicting %s using %2.2f %% of the data %s' % (pfield[0], ratio * 100, orderbyMessage))
            info["results"].append('Number of samples: %d' % len(X))
            info["results"].append('Number of features: %d' % len(X[0]))
            info["results"].append('Mean of dependent: %.4f' % results['r_mean'])
            info["results"].append('Mean of prediction: %.4f' % results['p_mean'])
            info["results"].append('Root Mean Squared: %.4f' % results['rms'])
            info["results"].append('R^2: %.4f' % clf.score(X[TrainingSize:], Y[TrainingSize:]))

            hashquery = datfile + hex(hash(request.args.get('query', datfile)) & 0xffffffff)

            if pre_process == "PCA" or pre_process == "Whitened PCA":
                #write pca matrix file
                info["datfile_matrix"] = hashquery + '.pca.csv'
                with open(info["datfile_matrix"], 'w') as f:
                    f.write("feature,%s\n" % (','.join(xfield)))
                    for i in range(len(V)):
                        f.write('PCA_%d,%s\n' % (i + 1, ','.join([str(v) for v in V[i]])))
                info["pca_matrix_divs"] = Markup('<div id="svg-pca_matrix"></div>')
            else:
                info["pca_matrix_divs"] = ''

            # preparing weights into a js array
            f = []
            f.append('{feature:"intercept", weight:%.3f}' % clf.intercept_)
            for i in range(len(clf.coef_)):
                f.append('{feature:"%s", weight:%.3f}' % (pfield[i + 1], clf.coef_[i]))
            info["weights_data"] = Markup('weights_data=[' + ','.join(f) + '];')

            #provenance
            #0:id,1:prediction result (grouping),2:actual label(shape),3:error,4:y,or features
            info["datfile_provenance"] = hashquery + '.provenance.csv'
            with open(info["datfile_provenance"], 'w') as f:
                f.write('Error,%s\n' % (','.join(pfield)))
                for i in range(len(yhat)):
                    e = float(Y[i + TrainingSize] - yhat[i]) ** 2
                    f.write('%.4f,%f,%s\n' % (e, Y[i + TrainingSize], ','.join([str(r) for r in X[i + TrainingSize]])))

            divs = [
                '<div class="chart"><div class="title">%s<a href="javascript:reset(%d)" class="reset" style="display: none;">reset</a></div></div>' % (
                pfield[d], d + 1) for d in range(len(pfield))]
            divs = ''.join(divs)
            divs = '<div class="chart"><div class="title">Squared Error (<span id="active"></span> of <span id="total"></span> items selected.)<a href="javascript:reset(0)" class="reset" style="display: none;">reset</a></div></div>' + divs
            info['provenance_divs'] = Markup(divs)

            info["message_class"] = "success"
            if reload > 0:
                info["message"].append("Loaded fresh.")
            else:
                info["message"].append("Loading from cache. Use reload=1 to reload.")

            info[
                "title"] = "FIELD_Y: <em>%s</em>, on <br />FIELD_X(predictors): <em>%s</em> from <br />TABLE: <em>%s</em>" % (
            pfield[0], ','.join(xfield), table)
            info["title"] = Markup(info["title"])
            info["datfile"] = info["datfile_provenance"]
    # prepare some messages
    info["message"] = Markup(''.join('<p>%s</p>' % m for m in info["message"] if len(m) > 0))
    info["results"] = Markup('<ul>' + ''.join('<li>%s</li>' % m for m in info["results"] if len(m) > 0) + '</ul>')

    # format the message to encode HTML characters
    info['query'] = Markup(request.args.get('query', ''))

    t = vis.jinja_env.get_template('explore.html')
    v1 = t.render(**info)
    t = vis.jinja_env.get_template('ml_ridge_linear.html')
    v2 = t.render(**info)
    v3 = v1[:-7] + v2 + v1[-7:] + '</html>'
    return Response(v3, mimetype='text/html')
