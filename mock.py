#!/usr/bin/env python
import argparse
import json

import requests
import flask

app = flask.Flask(__name__)


@app.route('/ready', methods=['POST'])
def ready():
    print("We're ready to go! :-)")
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
    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    desc = 'MARS Phase II CP2 -- Mock Test Harness'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-p', '--port',
                        type=int,
                        default=5001,
                        help='the port that should be used by this server.')
    parser.add_argument('--url-ta',
                        type=str,
                        required=True,
                        help='the URL of the TA.')
    parser.add_argument('--debug',
                        action='store_true',
                        help='enables debugging mode.')
    args = parser.parse_args()
    launch(port=args.port,
           url_ta=args.url_ta,
           debug=args.debug)
