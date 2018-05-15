#!/usr/bin/env python
from typing import Optional, List, Any
import argparse
import json
import urllib.parse
import threading
import time
import random
import logging
import sys

import requests
import flask

logger = logging.getLogger("mockth")  # type: logging.Logger
logger.addHandler(logging.NullHandler())

app = flask.Flask(__name__)


class TestHarness(object):
    def __init__(self, url_ta: str) -> None:
        self.__finished = threading.Event()
        self.__url_ta = url_ta
        self.__thread = None # type: Optional[threading.Thread]
        self.__errored = False

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self.__url_ta, path)

    def __mutable_files(self) -> List[str]:
        url = self._url("files")
        r = requests.get(url)
        if r.status_code != 200:
            logger.error("Failed to determine mutable files: %s", r)
            raise SystemExit

        logger.debug("Parsing JSON response from GET /files")
        files = r.json()
        logger.debug("Parsed JSON response from GET /files")
        assert isinstance(files, list)
        assert all(isinstance(f, str) for f in files)
        return files

    def __perturbations(self) -> List[Any]:
        perturbations = []

        logger.info("Finding set of mutable files.")
        files = self.__mutable_files()
        logger.info("Found set of mutable files: %s", files)

        fn = random.choice(files)
        logger.info("Finding perturbations in file: %s", fn)

        response = \
            requests.get(self._url("perturbations"),
                         json={'file': fn,
                               'shape': 'delete-conditional-control-flow'})

        if response.status_code != 200:
            logger.warning("Failed to find perturbations in file: %s.\nResponse: %s",  # noqa: pycodestyle
                           fn,
                           response)
            return []

        logger.debug("Computed all perturbations in file: %s", fn)
        perturbations_in_file = response.json()
        logger.info("Found %d perturbations in file: %s",
                    len(perturbations_in_file),
                    fn)
        perturbations += perturbations_in_file

        logger.info("Finished computing set of all perturbations.")
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
        logger.info("Computing set of perturbations.")
        perturbations = self.__perturbations()
        logger.info("Computed set of %d perturbations.",
                    len(perturbations))
        logger.info("Shuffling perturbations.")
        perturbations = random.shuffle(perturbations)
        logger.info("Shuffled perturbations.")
        while perturbations:
            p = perturbations.pop()
            logger.info("Attempting to apply perturbation: %s.", p)
            r = requests.post(self._url("perturb"), json=p)
            if r.status_code == 204:
                logger.info("Successfully applied perturbation.")
                return True
            else:
                logger.debug("Failed to apply perturbation: %s\nReason: %s.",
                             p, r)

        logger.error("Failed to perturb system.")
        return False

    def __adapt(self,
              time_limit_secs: Optional[float],
              attempt_limit: Optional[int]
              ) -> None:
        assert (time_limit_secs is not None) or (attempt_limit is not None), \
            "no resource limits specified"
        logger.info("Triggering adaptation...")

        payload = {}
        if time_limit_secs is not None:
            payload['time-limit'] = time_limit_secs
        if attempt_limit is not None:
            payload['attempt-limit'] = attempt_limit

        r = requests.post(self.__url("adapt"), json=payload)
        assert r.status_code == 204
        logger.info("Triggered adaptation.")

    def __stop(self) -> None:
        logger.info("STOPPING TEST")

    def __start(self) -> None:
        time.sleep(5)
        if not self.__perturb():
            logger.error("Failed to inject ANY perturbation into the system.")
            raise SystemExit # TODO how is this handled?
        self.__adapt(600.0, None) # TODO mock values

        # wait until we're done :-)
        self.__finished.wait()
        logger.info("__start is finished.")

    def ready(self) -> None:
        logger.info("We're ready to go!")
        self.__thread = threading.Thread(target=self.__start)
        self.__thread.start()

    def error(self) -> None:
        logger.info("An error occurred -- killing the test harness")
        self.__errored = True
        self.__finished.set()

    def done(self) -> None:
        logger.info("Adaptation has finished.")
        self.__finished.set()


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
    jsn = flask.request.json
    logger.info("DONE: {}".format(json.dumps(jsn)))
    harness.done()
    return '', 204


def launch(*,
           port: int = 5001,
           url_ta: str = '0.0.0.0',
           debug: bool = True
           ) -> None:
    global harness
    harness = TestHarness(url_ta)

    log_formatter = \
        logging.Formatter('%(asctime)s:%(name)s:%(levelname)s: %(message)s',
                          '%Y-%m-%d %H:%M:%S')
    log_to_stdout = logging.StreamHandler()
    log_to_stdout.setFormatter(log_formatter)
    logging.getLogger('werkzeug').setLevel(logging.DEBUG)
    logging.getLogger('werkzeug').addHandler(log_to_stdout)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(log_to_stdout)

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
