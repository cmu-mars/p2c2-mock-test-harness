#!/usr/bin/env python
import argparse
import json

import requests
import flask

app = flask.Flask(__name__)


@app.route('/ready', methods=['POST'])
def ready():
    ip_list = ['host.docker.internal:6060']
    return flask.jsonify(ip_list), 200


@app.route('/error', methods=['POST'])
def error():
    # TODO this should somehow kill everything?
    jsn = flask.request.json
    print("ERROR: {}".format(json.dumps(jsn)))


@app.route('/status', methods=['POST'])
def status():
    jsn = flask.request.json
    print("STATUS: {}".format(json.dumps(jsn)))


@app.route('/done', methods=['POST'])
def done():
    jsn = flask.request.json
    print("DONE: {}".format(json.dumps(jsn)))


def launch(*,
           port: int = 5001,
           url_ta: str = '0.0.0.0',
           debug: bool = True
           ) -> None:
    app.run(host='0.0.0.0', port=port, debug=True)


if __name__ == '__main__':
    # FIXME pass in TA URL
    port = 5001
    url_ta = 'http://cp2_ta:5000'
    debug = True
    launch(port=port, url_ta=url_ta, debug=True)
