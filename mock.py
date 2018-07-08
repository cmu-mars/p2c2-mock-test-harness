#!/usr/bin/env python
from typing import Optional, List, Any
from pprint import pprint as pp
import argparse
import json
import urllib.parse
import threading
import time
import random
import logging
import logging.handlers
import sys

import requests
import flask
import http.client

logger = logging.getLogger("mockth")  # type: logging.Logger
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())

app = flask.Flask(__name__)

OPERATORS = [
    'flip-arithmetic-operator',
    'flip-relational-operator',
    'flip-boolean-operator',
    'flip-signedness',
    'delete-conditional-control-flow',
    'undo-transformation',
    'delete-void-function-call'
]


class TestHarness(object):
    def __init__(self,
                 url_ta: str,
                 time_limit_mins: Optional[float],
                 attempts: Optional[int] = None,
                 operator: Optional[str] = None,
                 filename: Optional[str] = None,
                 line: Optional[int] = None
                 ) -> None:
        # assert time_limit_mins > 0
        self.__filename = filename
        self.__line = line
        self.__time_limit_mins = time_limit_mins
        self.__attempts = attempts
        self.__finished = threading.Event()
        self.__url_ta = url_ta
        self.__thread = None # type: Optional[threading.Thread]
        self.__errored = False

        if attempts:
            logger.info("using attempt limit: %d attempts", attempts)
        else:
            logger.info("not using attempt limit")

        if time_limit_mins:
            logger.info("using time limit: %d minutes", time_limit_mins)
        else:
            logger.info("not using time limit")

        if not operator:
            logger.info("no perturbation operator specified: choosing one at random.")  # noqa: pycodestyle
            operator = random.choice(OPERATORS)
        else:
            assert operator in OPERATORS
        logger.info("using perturbation operator: %s", operator)
        self.__operator = operator

    def _url(self, path: str) -> str:
        return '{}/{}'.format(self.__url_ta, path)

    def __mutable_files(self) -> List[str]:
        url = self._url("files")
        r = requests.get(url)
        if r.status_code != 200:
            logger.error("failed to determine mutable files: %s", r)
            raise SystemExit

        logger.debug("parsing JSON response from GET /files")
        files = r.json()
        logger.debug("parsed JSON response from GET /files")
        assert isinstance(files, list)
        assert all(isinstance(f, str) for f in files)
        return files

    def __perturbations(self) -> List[Any]:
        perturbations = []

        logger.info("finding set of mutable files.")
        files = self.__mutable_files()
        logger.info("found set of mutable files:\n%s",
                    '\n'.join(['  * {}'.format(f) for f in files]))

        if not self.__filename:
            logger.info("no file specified: choosing one at random.")
            fn = random.choice(files)
        else:
            fn = self.__filename
        logger.info("finding perturbations in file: %s", fn)

        response = \
            requests.get(self._url("perturbations"),
                         json={'file': fn,
                               'shape': self.__operator})
        if response.status_code != 200:
            logger.warning("failed to find perturbations in file: %s.\nResponse: %s",  # noqa: pycodestyle
                           fn,
                           response)
            return []

        logger.debug("computed all perturbations in file: %s", fn)
        try:
            jsn = response.json()
            assert isinstance(jsn, dict)
            assert 'perturbations' in jsn
            assert isinstance(jsn['perturbations'], list)
            perturbations_in_file = jsn['perturbations']
        except Exception as e:
            logger.exception("Failed to decode perturbations: %s", e)
            raise
        logger.info("found %d perturbations in file: %s",
                    len(perturbations_in_file), fn)
        perturbations += perturbations_in_file
        return perturbations

    def __perturb(self) -> bool:
        """
        Attempts to perturb the system.

        Returns:
            true if successfully perturbed, or false if no perturbation could
            be successfully applied.
        """
        logger.info("Perturbing system...")

        # keep attempting to apply perturbations until one is successful
        logger.info("computing set of perturbations.")
        perturbations = self.__perturbations()
        logger.info("computed set of %d perturbations.",
                    len(perturbations))
        random.shuffle(perturbations)
        logger.debug("%d perturbations: %s.",
                     len(perturbations), perturbations)
        while perturbations:
            p = perturbations.pop()
            logger.info("attempting to apply perturbation: %s.", p)
            logger.debug("%d perturbations left.", len(perturbations))
            r = requests.post(self._url("perturb"), json=p)
            if r.status_code == 204:
                logger.info("successfully applied perturbation.")
                return True
            else:
                logger.warning("failed to apply perturbation: %s [reason: %s].",
                               p, r)

        logger.error("failed to perturb system.")
        return False

    def __adapt(self) -> None:
        logger.info("triggering adaptation...")

        payload = {}
        if self.__time_limit_mins:
            logger.info("using time limit: %d minutes",
                        self.__time_limit_mins)
            payload['time-limit'] = self.__time_limit_mins
        else:
            logger.info("not using time limit")

        if self.__attempts:
            logger.info("using attempt limit: %d attempts",
                        self.__attempts)
            payload['attempt-limit'] = self.__attempts
        else:
            logger.info("not using attempt limit")
        logger.info("using payload: %s", payload)

        logger.debug("computing /adapt URL")
        logger.debug("payload for /adapt: %s", payload)
        url = self._url("adapt")
        r = requests.post(url, json=payload)
        logger.debug("/adapt response: %s", r)
        logger.debug("/adapt response: %s", r.json())
        logger.debug("/adapt code: %d", r.status_code)
        if not r.status_code == 202:
            logger.error("Failed to trigger adaptation.")
        logger.info("Triggered adaptation.")

    def __stop(self) -> None:
        logger.info("STOPPING TEST")

    def __start(self) -> None:
        time.sleep(5)
        if not self.__perturb():
            logger.error("failed to inject ANY perturbation into the system.")
            raise SystemExit # TODO how is this handled?
        self.__adapt()

        # wait until we're done :-)
        self.__finished.wait()
        logger.info("__start is finished.")

    def ready(self) -> None:
        logger.info("we're ready to go!")
        self.__thread = threading.Thread(target=self.__start)
        self.__thread.start()

    def error(self) -> None:
        logger.info("an error occurred -- killing the test harness")
        self.__errored = True
        self.__finished.set()

    def done(self, report) -> None:
        logger.info("adaptation has finished.")
        self.__finished.set()
        pp(report)
        num_attempts = report['num-attempts']
        running_time = report['running-time']
        outcome = report['outcome']
        logger.info("num. attempted patches: %d", num_attempts)
        logger.info("running time: %.2f minutes", running_time)
        logger.info("outcome: %s", outcome)


harness = None # type: Optional[TestHarness]


# WARNING possible race condition
@app.route('/ready', methods=['POST'])
def ready():
    harness.ready()
    ip_list = ['host.docker.internal:6060']
    jsn = {'bugzoo-server-urls': ip_list}
    return flask.jsonify(jsn), 200


@app.route('/error', methods=['POST'])
def error():
    # TODO this should somehow kill everything?
    jsn = flask.request.json
    logger.info("ERROR: {}".format(json.dumps(jsn)))
    harness.error()
    return '', 204


@app.route('/status', methods=['POST'])
def status():
    jsn = flask.request.json
    logger.info("STATUS: {}".format(json.dumps(jsn)))
    return '', 204


@app.route('/done', methods=['POST'])
def done():
    report = flask.request.json
    harness.done(report)
    return '', 204


def launch(*,
           port: int = 5001,
           url_ta: str = '0.0.0.0',
           debug: bool = True,
           log_file: str = 'cp2th.log',
           time_limit_mins: Optional[float] = None,
           attempts: Optional[int] = None,
           operator: Optional[str] = None,
           filename: Optional[str] = None
           ) -> None:
    global harness
    harness = TestHarness(url_ta,
                          time_limit_mins=time_limit_mins,
                          attempts=attempts,
                          operator=operator,
                          filename=filename)

    log_formatter = \
        logging.Formatter('%(asctime)s:%(name)s:%(levelname)s: %(message)s',
                          '%Y-%m-%d %H:%M:%S')
    log_to_stdout = logging.StreamHandler()
    log_to_stdout.setFormatter(log_formatter)
    log_to_stdout.setLevel(logging.DEBUG)

    log_to_file = \
        logging.handlers.WatchedFileHandler(log_file, mode='w')
    log_to_file.setFormatter(log_formatter)
    log_to_file.setLevel(logging.DEBUG)

    http.client.HTTPConnection.debuglevel = 1

    logging.getLogger('werkzeug').setLevel(logging.DEBUG)
    logging.getLogger('werkzeug').addHandler(log_to_stdout)
    logging.getLogger('werkzeug').addHandler(log_to_file)

    log_requests = logging.getLogger('requests')  # type: logging.Logger  # noqa: pycodestyle
    log_requests.propagate = True
    log_requests.setLevel(logging.DEBUG)
    log_requests.addHandler(log_to_stdout)
    log_requests.addHandler(log_to_file)

    log_requests = logging.getLogger('requests.packages.urllib3')  # type: logging.Logger  # noqa: pycodestyle
    log_requests.propagate = True
    log_requests.setLevel(logging.DEBUG)
    log_requests.addHandler(log_to_stdout)
    log_requests.addHandler(log_to_file)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(log_to_stdout)
    logger.addHandler(log_to_file)

    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    desc = 'MARS Phase II CP2 -- Mock Test Harness'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-p', '--port',
                        type=int,
                        default=5001,
                        help='the port that should be used by this server.')
    parser.add_argument('--url-ta',
                        type=str,
                        help='the URL of the TA.')
    parser.add_argument('--log-file',
                        type=str,
                        required=True,
                        help='the path to the file where logs should be written.')  # noqa: pycodestyle
    parser.add_argument('--time-limit-mins',
                        type=float,
                        default=None,
                        help='the number of minutes given to the adaptation process.')
    parser.add_argument('--attempts',
                        type=int,
                        help='the number of attempts minutes given to the adaptation process.')
    parser.add_argument('--operator',
                        type=str,
                        default=None,
                        help='the perturbation operator that should be chosen.')
    parser.add_argument('--filename',
                        type=str,
                        default=None,
                        help='the name of the file that should be perturbed.')
    parser.add_argument('--debug',
                        action='store_true',
                        help='enables debugging mode.')
    args = parser.parse_args()
    launch(port=args.port,
           url_ta=args.url_ta,
           log_file=args.log_file,
           debug=args.debug,
           time_limit_mins=args.time_limit_mins,
           attempts=args.attempts,
           operator=args.operator,
           filename=args.filename)
